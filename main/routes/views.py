#!/usr/bin/env python3
""" views for routes app """
import datetime as dt
from io import BytesIO
import json
import logging
from typing import TYPE_CHECKING, Optional, List, Dict, Tuple,Set

from gpxpy.parser import GPXParser
from gpxpy.gpx import GPX

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers import serialize
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import NumPoints
from django.contrib import messages
from django.db.models import Exists, OuterRef, QuerySet
from django.db.utils import IntegrityError
from django.http import (
    HttpResponseRedirect, HttpResponse, JsonResponse, HttpResponseForbidden,
    Http404, FileResponse)
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods
from django.views.decorators.gzip import gzip_page
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DeleteView)

from .models import (
    Place, Track, PlaceType, get_default_place_type, Tag, Preference)
from .forms import (
    UploadGpxForm2, PlaceForm, PreferenceForm, TrackDetailForm, TrackSearchForm,
    PlaceSearchForm, PlaceUploadForm, # TestCSRFForm
    )


if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


LOGIN_URL = '/bike/login?next=/bike'

class BikeLoginRequiredMixin(LoginRequiredMixin):
    login_url = LOGIN_URL


def get_map_context(request) -> Dict:
    ctx = {
        "places_count":  Place.objects.filter(user=request.user).count(),
        "tracks_count": Track.objects.filter(user=request.user).count(),
        "ocm_api_key": settings.OCM_API_KEY
    }
    return ctx


def get_db_bounds(user) -> Optional[Tuple[Tuple[float, float],
                                          Tuple[float, float]
                                          ]]:
    """ get the extent (bounds) of tracks & places, as a pair of lat-lon 
    2-tuples - lower left, upper right bound.
    Extent returns x,y coordinates, i.e. lon-lat """
    track_bounds: Optional[Tuple] = Track.objects.filter(user=user).aggregate(
        Extent('track'))['track__extent']
    place_bounds: Optional[Tuple] = Place.objects.filter(user=user).aggregate(
        Extent('location'))["location__extent"]
    if not track_bounds:
        return ((place_bounds[1], place_bounds[0]),
                (place_bounds[3], place_bounds[2]))

    if not place_bounds:
        return ((track_bounds[1], track_bounds[0]),
                (track_bounds[3], track_bounds[2]))

    return ((min(track_bounds[1], place_bounds[1]),
             min(track_bounds[0], place_bounds[0])),
            (max(track_bounds[3], place_bounds[3]),
             max(track_bounds[2], place_bounds[2])))


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET"])
def map(request, search: bool=False):
    """ return an empty map with an info/help popup dialog.
    If search is true, popup a map search dialog instead """
    context = get_map_context(request)
    context["bounds"] = get_db_bounds(request.user)
    context["search"] = search
    return render(request, 'map.html', context=context)


@login_required(login_url=LOGIN_URL)
@require_http_methods(["POST", "GET"])
@gzip_page
def search(request) -> JsonResponse|HttpResponse:
    """ handle a search for tracks or places, returning results as Json,
    or returning the HTML form if form errors """
    if request.method == "GET":
        track_form = TrackSearchForm()
        place_form = PlaceSearchForm()
        return render(request, "search.html", context={
            "track_form": track_form, "place_form": place_form})

    search_type = request.GET.get("search_type")
    track_form = TrackSearchForm(request.POST)
    place_form = PlaceSearchForm(request.POST)
    if search_type == "track":
        if not track_form.is_valid():
            log.error("search ? track: form errors=%s", track_form.errors)
            return render(request, "search.html", context={
                "track_form": track_form, "place_form": place_form})

        return _do_track_search(request, track_form)

    if search_type != 'place':
        log.error("search_type not recognised: POST=%s", request.POST)
        return HttpResponse("Search_type not defined", status=400)

    # search_type == 'place'
    if not place_form.is_valid():
        log.error("search ? place: form errors=%s", place_form.errors)
        return render(request, "search.html", context={
            "track_form": track_form, "place_form": place_form})

    return _do_place_search(request, place_form)


def _do_place_search(request, place_form) -> JsonResponse:
    """ carry out a place search, returning a Json response.
    Expects a valid place_form """
    cleaned_data = place_form.cleaned_data
    # log.info("place_search: form.cleaned_data=%s", cleaned_data)
    places = Place.objects.filter(user=request.user)
    if "name" in cleaned_data and cleaned_data["name"]:
        # __icontains: case insensitive search for *value*
        # log.info("search?place: filtering for name like*%s*", cleaned_data["name"])
        places = places.filter(name__icontains=cleaned_data["name"])
    if "type" in cleaned_data:
        types = cleaned_data["type"]
        # value is a queryset of selected types
        if types.count() > 0:
            # log.info("search?place: filtering for type in %s", cleaned_data["type"])
            places = places.filter(type__in=cleaned_data["type"])
    tags = cleaned_data.get("place_tags")
    places = filter_by_tags(request, places, tags)
    result_count = places.count()
    result_limit = request.user.routes_preference.place_search_result_limit
    places = places[:result_limit]
    places_json = json.loads(serialize("geojson", places))
    log.info("search ? place: %d of %d places returned",
             len(places_json["features"]), result_limit)
    return JsonResponse({"status": "success", "result_count": result_count,
                         "result_limit": result_limit, "places": places_json},
                        status=200)


def _do_track_search(request, track_form) -> JsonResponse:
    """ carry out a track search, returning a JSON response.
    Expects a valid track_form """
    tracks = Track.objects.filter(user=request.user)
    start_date = track_form.cleaned_data.get("start_date")
    if start_date is not None:
        start_datetime = dt.datetime.combine(start_date, dt.time(),
                                             tzinfo=dt.timezone.utc)
        tracks = tracks.filter(start_time__gte=start_datetime)
        log.debug("track search: start_time>=%r", start_datetime)
    end_date = track_form.cleaned_data["end_date"]
    if end_date is not None:
        end_datetime = dt.datetime.combine(end_date, dt.time(23, 59, 59),
                                           tzinfo=dt.timezone.utc)
        tracks = tracks.filter(start_time__lte=end_datetime)
        log.debug("track search: start_time<=%r", end_datetime)
    tags = track_form.cleaned_data.get("track_tags")
    tracks = filter_by_tags(request, tracks, tags)
    result_count = tracks.count()
    result_limit = request.user.routes_preference.track_search_result_limit
    tracks=tracks[:result_limit]
    tracks_json = json.loads(serialize("geojson", tracks))
    log.info("search ? track: %d of %d tracks returned",
             len(tracks_json["features"]), result_count)
    return JsonResponse(
        {"status": "success", "count": result_count, 
         "result_limit": result_limit, "tracks": tracks_json},
        status=200)


def filter_by_tags(request, queryset: QuerySet, tags: str) -> QuerySet:
    """ if tags are defined, return the filtered queryset, otherwise,
    return it unchanged """
    if tags is not None:
        tag_names = [tag.strip() for tag in tags.split(',') if tag]
        if tag_names:
            tags = Tag.objects.filter(user=request.user, name__in=tag_names
                                      ).distinct()
            log.debug("filter_by_tags: tag names in %s", tag_names)
            return queryset.filter(tag__in=tags).distinct()
    return queryset

# def test_csrf(request):
#     if request.method == 'GET':
#         form = TestCSRFForm()
#         return render(request, 'test_csrf.html', context={'form': form})
#
#     log.info("test_csrf: POST=%s", request.POST)
#     form = TestCSRFForm(request.POST)
#     log.info("form received successfully.  is_valid=%s", form.is_valid())
#     return HttpResponse(status=204)  # ok, no content

# ------ Track handling ------
@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "POST"])
def track(request, pk: int):
    """ return track summary or detailed info depending on parm """
    track = get_object_or_404(Track, pk=pk, user=request.user)
    if request.method == "GET":
        template, moving_time = "track.html", "n/a"
        form = None
        if request.GET.get("detail"):
            template = "track_detail.html"
            form = TrackDetailForm(instance=track)
            moving_time = as_hhmm(track.moving_time)

    else:  # POST (detail implied)
        form = TrackDetailForm(request.POST, instance=track)
        if form.is_valid():
            form.save()
            return HttpResponse(status=204)  # ok, no content
        template = "track_detail.html"
        moving_time = as_hhmm(track.moving_time)
    return render(request, template, context={
        "track": track, "moving_time": moving_time, "form": form})


def as_hhmm(time_secs: float) -> str:
    days, secs = divmod(time_secs, 24*3600)
    mins = round(secs/60)
    hrs, mins = divmod(mins, 60)
    s = f"{hrs}h{mins:02d}"
    if days:
        s = f"{days} days, {s}"
    return s

class TracksView(BikeLoginRequiredMixin, TemplateView):
    """ show a track or tracks, requested by track id or a comma-separated list
    of track ids """
    # FIXME: url broken - needs sorting out
    template_name = "map.html"

    def get(self, _request, *_args, **kwargs):
        try:
            context = self.get_context_data(**kwargs)
        except ValidationError as e:
            return HttpResponse(e, status=400)
        return self.render_to_response(context, status=403)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        log.info("TracksView got kwargs=%s", kwargs)
        try:
            trackids = [int(trackid) for trackid in kwargs['trackids'].split(',')]
        except ValueError as e:
            raise ValidationError(f"Invalid track id: {e.args[0]}") from e
        tracks = Track.objects.filter(id__in=trackids, user=request.user)
        ctx["tracks"] = json.loads(serialize("geojson", tracks))
        return ctx


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "HEAD"])
@gzip_page
def track_json(request):
    """ return a selection of tracks based on search parameters including
    &latlon=  &andlatlon=,  &orlatlon=, (name, date - not yet defined) 
    also ?name= to determine whether a track exists or not (returns status 404
    or 200 with the number of points in the track)"""
    # query = Track.objects
    log.info("track_json(%s): GET=%s", request.method, request.GET)
    if request.method == "GET":
        limits, prefs = nearby_search_params(request)
        nearby_tracks: QuerySet = Track.nearby(limits, prefs)
        result_count = nearby_tracks.count()
        result_limit = prefs.track_search_result_limit
        nearby_tracks = nearby_tracks[:result_limit]
        if result_count > result_limit:
            log.info("track_json returned %d of %d tracks", result_count,
                     result_limit)
        else:
            log.info("track_json returned %d tracks", result_count)
        tracks_json = json.loads(serialize(
            "geojson", nearby_tracks, fields=["name", "track", "pk"]))
        return JsonResponse({"status": "success", "result_count": result_count,
         "result_limit": result_limit, "tracks": tracks_json}, status=200)

    # "HEAD": just return num_points if the track is there.  Search by ?name=
    name = request.GET.get("name")
    if name is None:
        log.error("HEAD request requires a search param ?name=")
        return HttpResponse("HEAD request without search params ?name=",
                            status=400)
    try:
        track = Track.objects.annotate(num_points=NumPoints("track")
                                       ).get(user=request.user, name=name)
    except Track.DoesNotExist as e:
        raise Http404 from e
    log.info("Track %s found: %s, num_points=%s", name, track, track.num_points)
    # HEAD request does not return body: set content-length header to num_points
    response = HttpResponse(status=204)  # ok, no content
    response.headers["Content-Length"] = track.num_points
    return response

def parse_latlon(value: str) -> Tuple[float, float]:
    """ parse a string containing two floats """
    values = value.split(',')
    float_values = tuple(float(v) for v in values)
    assert len(float_values) == 2, f"expecting 2 values for latlon, not {value!r}"
    return float_values


def _show_tracks(request, tracks: List[Track]):
    """ INTERNAL METHOD: no url.  show the given tracks on a map.
    Used by upload_file. """
    ctx = get_map_context(request)
    # geojson serialiser has to be defined in settings.py
    # don't serialise tag field because it requires track to have an id
    # - if using view gpx the track is not saved
    ctx["tracks"] = json.loads(
        serialize("geojson", tracks, fields=["name", "track", "id", "pk"])
        )
    return render(request, "map.html", context=ctx)


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET"])
@gzip_page
def track_download(request, pk: int):
    """ create a gpx file for a track and download it, using a name specified
    in the url query parameters """
    track = get_object_or_404(Track, pk=pk, user=request.user)
    gpx = track.as_gpx(name=request.GET.get("name"))
    gpx_xml = gpx.to_xml()  # prettyprint=True for debug
    # build response
    filename = gpx.name
    if not filename.lower().endswith('.gpx'):
        filename += ".gpx"
    bytes_io = BytesIO(gpx_xml.encode('utf-8'))
    response = FileResponse(bytes_io, as_attachment=True, filename=filename)
    log.debug("gpx response content-type before updating was %s",
              response.headers["content-type"])
    response.headers["content-type"] = 'application/gpx+xml; charset=utf-8'
    # response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required(login_url=LOGIN_URL)
def upload_gpx(request, save: bool=True):
    """ upload a gpx file and convert to a Track (or Tracks).
    If save=True, save the Track(s) in the DB, otherwise just view without
    saving
    
    Ref: https://docs.djangoproject.com/en/5.1/topics/http/file-uploads/ 
    important post here:
    https://web.archive.org/web/20160425053015/http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
    """
    if request.method == "POST":
        form = UploadGpxForm2(request.POST, request.FILES)
        if form.is_valid():
            files = form.cleaned_data['gpx_file']
            tracks: List[Track] = []
            duplicate_filenames: List[str] = []
            for file in files:
                try:
                    tracks.extend(handle_uploaded_gpx(request, file, save=save))
                except TypeError as e:
                    return HttpResponse(e, status=400)
                except FileExistsError as e:
                    duplicate_filenames.append(e.args[0])

            if duplicate_filenames:
                log.warning("uploaded gpx filename(s) already in DB: %s",
                            ', '.join(duplicate_filenames))
                form.add_error("gpx_file",
                               "The following track names are already "
                               f"uploaded: {', '.join(duplicate_filenames)}")
            else:
                if save:
                    errors = save_uploaded_tracks(request, tracks)
                    for error in errors:
                        form.add_error("gpx_file", error)
                if form.is_valid():  # re-check for errors
                    # log.debug("request.GET=%s", request.GET)
                    if request.GET.get("map") == "False":
                        return HttpResponse(status=204)  # ok, no content
                    return _show_tracks(request, tracks)

        log.info("errors were found")
    else:
        form = UploadGpxForm2()
    tags = get_all_tags(request)
    return render(request, "gpx_upload.html", {"form": form, "save": save, "tags": tags})


def save_uploaded_tracks(request, tracks) -> List[str]:
    """ save any uploaded tracks, with tags, and return a list of errors """
    # create new tags & get tag ids of new & checked tags
    tag_ids = get_checked_tag_ids(request)
    new_tag_names = get_new_tag_names(request)
    if new_tag_names:
        # check if new tag names already exist
        new_tags_already_defined = Tag.objects.filter(
            user=request.user, name__in=new_tag_names).all()
        for tag in new_tags_already_defined:
            tag_ids.add(tag.name)
            new_tag_names.remove(tag.name)
    for tag_name in new_tag_names:
        tag = Tag(user=request.user, name=tag_name)
        tag.save()
        log.debug("added new tag %s, id=%d",tag.name, tag.pk)
        tag_ids.add(tag.pk)
    # save the tracks & link to tags
    errors: List[str] = []
    for track in tracks:
        try:
            track.save()
        except IntegrityError as e:
            log.error("Error saving track %s of %s: %r, track.track=%s",
                      track.name, len(tracks), e, str(track.track)[:1000])
            errors.append(f"Error saving track {track.name}: "
                           f"{e!r}")
            continue
        log.debug("saved track %s, id=%d", track.name, track.pk)
        track.tag.add(*tag_ids)
    return errors


def handle_uploaded_gpx(request, file: "UploadedFile", save: bool) -> List[Track]:
    """ parse a gpx file and turn it into a list of Tracks.
    Each GPX file can contain multiple tracks. 
    If Save is False, don't check for duplicate filename """
    log.info("uploading file %s, size %d", file.name, file.size)
    # upload a gpx file and convert to a GPX object
    # decode the file as a text file (not binary)
    encoding = file.charset or 'utf-8'
    xml_string = file.read().decode(encoding=encoding)
    gpx = GPXParser(xml_string).parse()
    if not gpx:
        raise TypeError(f"Failed to parse {file.name}" )
    log.info("gpx file %s parsed ok, creator=%s", file.name, gpx.creator)
    tracks = Track.new_from_gpx(gpx, file.name, user=request.user, save=save)
    return tracks


def test_save_gpx(_request):
    """ test saving a specific file from disk to the database """
    raise NotImplementedError("Track now requires a User field")
    # fname = ("/home/simon/Documents/Travel/CoastalAdventure/2025-South/Actual/"
    #         "2025-05-25-08-32-09.gpx")
    # with open(fname, 'rt', encoding='utf-8') as infile:
    #     xml_string = infile.read()
    # gpx = GPXParser(xml_string).parse()
    # if not gpx:
    #     return HttpResponse("Failed to parse file", status=400)
    # log.info("gpx file %s parsed ok", gpx)
    # try:
    #     tracks = Track.new_from_gpx(gpx, fname)# , user=1 for simon
    # except IntegrityError as e:
    #     return HttpResponse(status=400, content=e.args)
    # trackids = ','.join(str(track.id) for track in tracks)
    # return HttpResponseRedirect(
    #     reverse("routes:tracks_view", kwargs={"trackids": trackids}))


class TrackDeleteView(DeleteView):
    model=Track
    template_name = "track_confirm_delete.html"

    def form_valid(self, _form):
        self.object.delete()
        return HttpResponse(status=204)  # ok, no content


# ------------- place handling ---------------
@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "POST"])
def place(request, pk=None):
    """ insert or update place details """
    # log.info("place.%s(pk=%r, request.GET=%s, request.POST=%s)",
    #          request.method, pk, request.GET, request.POST)
    # css for icons references use ID field of INPUT fields, which are 0-indexed
    # not linked to the pk
    icons = [f"icons/{item.get_icon_display()}"
             for item in PlaceType.objects.all()]
    if request.method == 'GET':
        if pk is not None:
            place_inst = get_object_or_404(Place, pk=pk, user=request.user)
            form = PlaceForm(instance=place_inst)
        else:
            form = PlaceForm()
            place_inst = None

        return render(request, 'place.html', context={
            "form": form, "pk": pk, "icons": icons, "instance": place_inst})

    # handle POST request
    if "multipart/form-data" not in request.headers.get('Content-Type'):
        raise ValueError("expecting html form data (did you send json??)")
    # """ investigate form POST using HTML.  Ref:
    # https://www.geeksforgeeks.org/jquery/how-to-send-formdata-objects-with-ajax-requests-in-jquery/"""
    if pk is None:
        form = PlaceForm(request.POST)
        lat, lon = request.POST.get('lat'), request.POST.get("lon")
        location = Point(float(lon), float(lat))
        form.instance.location=location
        form.instance.user=request.user
    else:
        assert str(pk) == request.POST.get("pk"), "invalid ID in post response"
        place_inst = get_object_or_404(Place, pk=pk, user=request.user)
        form = PlaceForm(request.POST, instance=place_inst)
    if form.is_valid():
        form.save()
        return JsonResponse(
            {"instance": "saved successfully", "type": form.instance.type.pk,
             "name": form.instance.name, "pk": form.instance.pk},
            status=200)

    # handle form errors
    return render(request, 'place.html', context={
        "form": form, "pk": pk, "icons": icons, "instance": place_inst})


def nearby_search_params(request) -> Tuple[Dict, Preference]:
    """ extract and format parameters for a "nearby" search request """
    if not set(request.GET) & set(("latlon", "andlatlon"),):
        return HttpResponse("No search criteria specified", status=400)
    params = request.GET
    defaults = {'latlon': None,  # float, float,
                'andlatlon': None,  # float, float
                }
    limits = {key: params.get(key, default_value)
              for key, default_value in defaults.items()}
    prefs = Preference.objects.get_or_create(user=request.user)[0]
    return limits, prefs


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET"])
def place_json(request):
    """ return a selection of places based on search parameters including
    &latlon=  &andlatlon=,  &orlatlon=, """
    # query = Place.objects
    log.info("place_json(%s): GET=%s", request.method, request.GET)
    assert request.method == "GET"
    limits, prefs = nearby_search_params(request)
    nearby_places: dict = Place.nearby(limits, prefs)
    log.info("track_json returned %d places", len(nearby_places))
    msg = json.loads(serialize("geojson", nearby_places))
    return JsonResponse(msg, status=200)


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "POST"])
def upload_csv(request):
    """ upload a csv file of places with name, lat, lon, type """
    default_place_type = get_default_place_type()
    place_types = {place_type.pk: place_type.name
    for place_type in PlaceType.objects.filter(user=request.user).all()}

    if request.method == "GET":
        form = PlaceUploadForm()

    else:  # POST
        log.debug("request.FILES=%s", request.FILES)
        file = request.FILES['csv_file']
        log.info("uploading file %s, size %d", file.name, file.size)
        form = PlaceUploadForm(request.POST, request.FILES)
        try:
            if form.is_valid():
                places = Place.build_places_from_csv(
                    form.cleaned_data['csv_file'],
                    request.user,
                    place_types, default_place_type)
                if not places:
                    raise ValueError("No data rows in CSV file")

                log.info("places csv file parsed ok")
                for place in places:
                    place.save()
                log.debug("request.GET=%s", request.GET)
                if request.GET.get("map") == "False":
                    return HttpResponse(status=204)  # ok, no content
                return _show_places(request, places)
        except ValueError as e:
            log.error("Error processing CSV file: %s", e)
            form.add_error('csv_file', e)

        log.info("form was not valid")
    return render(request, 'place_csv_upload.html', context={
            "form": form, "place_types": place_types,
            "default_place_type": default_place_type})


@login_required(login_url=LOGIN_URL)
def place_delete(request, pk: int):
    """ handle a delete request """
    if request.method == "GET":
        # send the delete confirmation form, (with CSRF token)
        place_inst = get_object_or_404(Place, pk=pk, user=request.user)
        return render(request, 'place_delete.html', context={"place": place_inst})

    # else (POST): actually do the delete after confirmation
    form_pk = request.POST.get("pk")
    assert form_pk == str(pk), "pk in url doesn't match pk in form"
    get_object_or_404(Place, pk=pk, user=request.user).delete()
    return JsonResponse({"instance": "deleted successfully", "pk": pk},
                         status=200)


@login_required(login_url=LOGIN_URL)
def place_move(request, pk: int):
    """ handle a move request """
    place_inst = get_object_or_404(Place, pk=pk, user=request.user)
    #log.info("place_move: request.GET=%s, request.POSt=%s", request.GET,
    #         request.POST)
    if request.method == "GET":
        return render(request, 'place_move.html', context={'place': place_inst})

    # else (POST)
    lat, lon = request.POST.get('lat'), request.POST.get("lon")
    assert request.POST.get("pk") == str(pk), "url mismatch to form data for pk"
    place_inst.location = Point(float(lon), float(lat))
    place_inst.save()
    return HttpResponse(status=204)  # ok, no content


# ---- place types ----
class PlaceTypeListView(BikeLoginRequiredMixin, ListView):
    model = PlaceType
    context_object_name = "place_types"
    template_name = "placetype_list.html"

    def get_queryset(self):
        return PlaceType.objects.filter(user=self.request.user).all()


@login_required(login_url=LOGIN_URL)
def place_type_list_json(request):
    """ return a json list of icons & names for all defined place types """
    data = {place_type.pk:
            {"icon": f"{settings.STATIC_URL}icons/{place_type.get_icon_display()}",
             "name": place_type.name}
            for place_type in PlaceType.objects.filter(user=request.user).all()
            }
    # default entry gives the default pk
    data["default"] = get_default_place_type().pk
    # log.info("PlaceTypeListJson returning %s", data)
    # must set safe=False in order to send lists, otherwise only dict allowed
    return JsonResponse(data, status=200)


class PlaceTypeCreateView(BikeLoginRequiredMixin, CreateView):
    model = PlaceType
    fields = ["name", "icon"]
    success_url = reverse_lazy("routes:api_place_types")
    template_name = "placetype_form.html"

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        return super(PlaceTypeCreateView, self).form_valid(form)


class PlaceTypeUpdateView(BikeLoginRequiredMixin, UpdateView):
    model = PlaceType
    fields = ["name", "icon"]
    success_url = reverse_lazy("routes:api_place_types")
    template_name = "placetype_form.html"

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        return super(PlaceTypeUpdateView, self).form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        if not PlaceType.objects.filter(pk=self.kwargs['pk'],
                                        user=request.user).exists():
            return HttpResponse("Unauthorised place type", status=401)
        return super(PlaceTypeUpdateView, self).dispatch(
            request, *args, **kwargs)


class PlaceTypeDeleteView(BikeLoginRequiredMixin, DeleteView):
    model = PlaceType
    success_url = reverse_lazy("routes:api_place_types")
    template_name = "placetype_confirm_delete.html"

    def dispatch(self, request, *args, **kwargs):
        if self.kwargs['pk'] == get_default_place_type().pk:
            return HttpResponse(
                "Cannot delete the default place type", status=403)
        if not PlaceType.objects.filter(pk=self.kwargs['pk'],
                                        user=request.user).exists():
            return HttpResponse("Unauthorised place type", status=401)
        return super(PlaceTypeDeleteView, self).dispatch(
            request, *args, **kwargs)


# ------ tags handling ------
@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "POST"])
def place_tags(request, pk: int):
    """ show & process form for updating tags for a place """
    # annotate tags with whether checked for this place
    instance = get_object_or_404(Place, pk=pk, user=request.user)
    if request.method == 'GET':
        tags = Tag.objects.filter(
            user=request.user
            ).annotate(is_checked=Exists(Tag.place.through.objects.filter(
                tag_id=OuterRef('pk'), place_id=pk)
                )
            ).order_by("-is_checked")
        # tags_str = ', '.join(f"{tag}: checked={tag.is_checked}" for tag in tags)
        # log.info("tags=%s", tags_str)
        return render(request, 'tag_list.html', context={
            "tags": tags, "object_type": "place", "pk": pk,
            "instance": instance})

    # else: POST
    handle_tags_update(request, instance)
    return HttpResponseRedirect(reverse_lazy("routes:place", kwargs={"pk": pk}))


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "POST"])
def track_tags(request, pk: int):
    """ show & process form for updating tags for a track """
    # annotate tags with whether checked for this place
    instance = get_object_or_404(Track, pk=pk, user=request.user)
    if request.method == 'GET':
        tags = Tag.objects.filter(
            user=request.user
            ).annotate(is_checked=Exists(Tag.track.through.objects.filter(
                tag_id=OuterRef('pk'), track_id=pk)
                )
            ).order_by("-is_checked")
        # tags_str = ', '.join(f"{tag}: checked={tag.is_checked}" for tag in tags)
        # log.info("tags=%s", tags_str)
        return render(request, 'tag_list.html', context={
            "tags": tags, "object_type": "track", "pk": pk,
            "instance": instance})

    # else: POST
    handle_tags_update(request, instance)
    return HttpResponseRedirect(reverse_lazy("routes:track", kwargs={"pk": pk}))


def get_all_tags(request) -> List[Tag]:
    """ return a list of all tags for a user, marking those checked or named
    in the previous POST request """
    tags = Tag.objects.filter(user=request.user).all()
    if request.method == 'POST':
        # check POST data for checked tags and set .is_checked
        checked_tag_ids: Set[str] = get_checked_tag_ids(request)
        new_tag_names: Set[str] = set(get_new_tag_names(request))
        for tag in tags:
            tag.is_checked = (tag.pk in checked_tag_ids
                              or tag.name in new_tag_names)
    return tags


def get_checked_tag_ids(request) -> Set[str]:
    """ return the set of checked tag keys from a post request """
    # only checked checkboxes are returned in the POST data
    return {int(key[4:]) for key in request.POST.keys()
        if key.startswith("tag_")}


def get_new_tag_names(request) -> List[str]:
    """ return a list of non-blank new tag names """
    return [tag_name.strip()
            for tag_name in request.POST.get('new-tags', '').split(',')
            if tag_name.strip()]


def handle_tags_update(request, instance):
    """ handle a tags update post for either a place or a track """
    log.debug("%s_tags: request.POST=%s", type(instance), request.POST)
    # ensure checked tags match checked tags in instance (including any unchecked)
    checked_tag_ids = get_checked_tag_ids(request)
    current_tag_ids = {tag.id for tag in instance.tag.all()}
    log.debug("current_tag_ids=%s, checked_tag_ids=%s", current_tag_ids,
              checked_tag_ids)
    removed_tag_ids = tuple(current_tag_ids - checked_tag_ids)
    if removed_tag_ids:
        log.info("removing tag ids %s",removed_tag_ids)
        instance.tag.remove(*removed_tag_ids)
    added_tag_ids = tuple(checked_tag_ids - current_tag_ids)
    if added_tag_ids:
        log.info("adding tag ids %s", added_tag_ids)
        instance.tag.add(*added_tag_ids)
    # add any new tags
    new_tag_names = get_new_tag_names(request)
    if new_tag_names:
        log.info("adding new tag names %s", new_tag_names)
        for name in new_tag_names:
            # create, save and link the new tag
            instance.tag.create(name=name, user=request.user)
    instance.save()


# --- test ---
@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET"])
def test(request):
    messages.info(request, "Hello world.")
    messages.success(request, "Succeeded.")
    messages.error(request, "Failed.")
    messages.warning(request, "Watch out!")
    return render(request, 'test.html')

# ------ preferences handling ------
@login_required(login_url=LOGIN_URL)
def preference(request):
    """ Preferences is a 1:1 object for each user.  Create it or get it """
    preference = Preference.objects.get_or_create(user=request.user)[0]
    if request.method == "GET":
        form = PreferenceForm(instance=preference)
    else:
        form = PreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse_lazy("routes:api_preference"))

    return render(request, 'preference_form.html', context={"form": form})


@login_required(login_url=LOGIN_URL)
def preference_as_json(request):
    """ this returns a list of a single preferences object,
    with search distances converted to metres """
    preference = Preference.objects.get_or_create(user=request.user)[0]
    # it has to be a list or queryset in order to serialise it
    # add search distances in metres
    data = serialize("json", [preference])
    json_data = json.loads(data)
    fields = json_data[0]["fields"]
    fields["track_nearby_search_distance_metres"] = (
        preference.track_nearby_search_distance_metres)
    fields["place_nearby_search_distance_metres"] = (
        preference.place_nearby_search_distance_metres)
    # log.info("preference_as_json: data=%s", data)
    return JsonResponse(json_data, safe=False, status=200)


def csrf_failure(request, reason=""):
    log.error("CSRF failure for request %s, \nheaders=%s, \nreason=%s",
              request, request.headers, reason)
    return HttpResponseForbidden('CSRF failure')


def do_logout(request):
    logout(request)
    return HttpResponse("Logged out", status=200)
