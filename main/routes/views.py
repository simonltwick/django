#!/usr/bin/env python3
""" views for routes app """
import datetime as dt
from io import BytesIO
import json
import logging
from pathlib import Path
from typing import (
    TYPE_CHECKING, Optional, List, Dict, Tuple, Set, Any, Sequence)

from gpxpy.parser import GPXParser
from gpxpy.gpx import GPX

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers import serialize
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.gis.geos.geometry import GEOSGeometry
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import NumPoints
from django.contrib.gis.measure import D  # synonym for Distance
from django.db.models import Exists, OuterRef, QuerySet, Q
from django.db.utils import IntegrityError
from django.http import (
    HttpResponseRedirect, HttpResponse, JsonResponse, HttpResponseForbidden,
    Http404, FileResponse)
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.gzip import gzip_page
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DeleteView)

from .models import (
    Place, Track, Boundary, PlaceType, get_default_place_type, Tag)
from bike.models import Preferences
from .forms import (
    UploadGpxForm2, PlaceForm, TrackDetailForm, TrackSearchForm,
    PlaceSearchForm, CommonSearchForm, PlaceUploadForm, UploadBoundaryForm,
    # BoundaryForm, TestCSRFForm
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
    """ handle a search for tracks or places, returning results and search query
     as Json,
    or returning the HTML form if form errors """
    url_params = {key: request.GET.get(key) for key in
                 ("track_search_history", "place_search_history")}
    if request.method == "GET":
        track_form = TrackSearchForm()
        place_form = PlaceSearchForm()
        common_form = CommonSearchForm()
        return render(request, "search.html", context={
            "track_form": track_form, "place_form": place_form,
            "search_type": "track", "common_form": common_form,
            "url_params": url_params})

    # POST
    search_type = request.GET.get("search_type")
    track_form = TrackSearchForm(request.POST)
    place_form = PlaceSearchForm(request.POST)
    common_form = CommonSearchForm(request.POST)
    if search_type == "track":
        if track_form.is_valid() and common_form.is_valid():
            try:
                return _do_track_search(
                    request, track_form.cleaned_data | common_form.cleaned_data)
            except ValidationError as e:
                track_form.add_error(None, e.args[0])

        log.error("search ? track: form errors=%s", track_form.errors)

    # search_type == 'place'
    elif search_type == "place":
        if place_form.is_valid() and common_form.is_valid():
            try:
                cleaned_data = place_form.cleaned_data | common_form.cleaned_data
                return _do_place_search(request, cleaned_data)
            except ValidationError as e:
                place_form.add_error(None, e.args[0])

        log.error("search ? place: form errors=%s", place_form.errors)

    else:
        log.error("search_type not recognised: POST=%s", request.POST)
        return HttpResponse("Search_type not defined", status=400)

    return render(request, "search.html", context={
        "track_form": track_form, "place_form": place_form,
        "search_type": search_type, "common_form": common_form,
        "url_params": url_params})


def _encode_place_search(request, cleaned_data
                         ) -> Tuple[Optional["SearchQ"], Dict]:
    q: List["SearchQ"] = []
    if (name := cleaned_data.get("name")):
        # __icontains: case insensitive search for *value*
        q.append(SearchQ(name__icontains=name))
    if (place_types := cleaned_data.get("type")):
        place_type_names = [place_type.name for place_type in place_types]
        q.append(SearchQ(type__name__in=place_type_names))
    if (tags_str := cleaned_data.get("tags")):
        if (tag_names := [tag.strip() for tag in tags_str.split(',') if tag]):
            q.append(SearchQ(tag__name__in=tag_names))
    if (boundary_name := cleaned_data.get("boundary_name")):
        boundary_category = cleaned_data.get("boundary_category")
        boundary_search_q = BoundarySearchQ(request.user, boundary_category,
                                            location__within=boundary_name)
        boundary_polygon = json.loads(
            serialize("geojson", [boundary_search_q.boundary]))
        q.append(boundary_search_q)
    else:
        boundary_polygon = None
    return AndSearchQ(*q) if len(q)>1 else q[0] if q else None, boundary_polygon


def _do_place_search(request, cleaned_data) -> JsonResponse:
    """ carry out a place search, returning a Json response.
    Expects a valid place_form """
    # log.info("place_search: form.cleaned_data=%s", cleaned_data)
    query_json, boundary_polygon = _encode_place_search(request, cleaned_data)
    if query_json is None:
        required_keys = ("name", "type", "tags", "boundary_name")
        # TODO: provide correct info in ValidationError code, params, field
        raise ValidationError(
            f"At least one of {', '.join(required_keys)} must be specified")

    try:
        query_json = get_search_history(request, query_json)
    except ValueError as e:
        return HttpResponse(e.args[0], status=400)
    log.debug("_do_place_search: query_json=%s, Q=%s, q.json=%s", query_json,
              query_json.Q(), query_json.json())
    places = Place.objects.filter(query_json.Q(), user=request.user)

    result_count = places.count()
    result_limit = request.user.routes_preferences.place_search_result_limit
    places = places[:result_limit]
    places_json = json.loads(serialize("geojson", places))
    search_history = query_json.json()
    log.info("search ? place: %d %s places returned", result_count,
             (f"of {result_limit}" if result_count > result_limit else ""))
    result = {"status": "success", "places": places_json,
              "result_count": result_count, "result_limit": result_limit,
              "boundary": boundary_polygon, "search_history": search_history}
    return JsonResponse(result, status=200)


def _encode_track_search(request, cleaned_data
                         ) -> Tuple[Optional["SearchQ"], Dict]:
    q: List["SearchQ"] = []
    if (start_date := cleaned_data.get("start_date")):
        start_datetime = dt.datetime.combine(start_date, dt.time(0),
                                             tzinfo=dt.timezone.utc)
        q.append(SearchQ(start_time__gte=start_datetime))
    if (end_date := cleaned_data.get("end_date")):
        end_datetime = dt.datetime.combine(end_date, dt.time(23,59,59),
                                             tzinfo=dt.timezone.utc)
        q.append(SearchQ(start_time__lte=end_datetime))
    if (tags_str := cleaned_data.get("tags")):
        if (tag_names := [tag.strip() for tag in tags_str.split(',') if tag]):
            q.append(SearchQ(tag__name__in=tag_names))
    if (boundary_name := cleaned_data.get("boundary_name")):
        boundary_category = cleaned_data.get("boundary_category")
        boundary_search_q = BoundarySearchQ(request.user, boundary_category,
                                            track__intersects=boundary_name)
        # overlaps, touches, intersects, crosses all possible
        # not crosses (has to cross boundary so excludes fully enclosed)
        # not overlaps, touches (none found)
        boundary_polygon = json.loads(
            serialize("geojson", [boundary_search_q.boundary]))
        q.append(boundary_search_q)
    else:
        boundary_polygon = None
    return AndSearchQ(*q) if len(q)>1 else q[0] if q else None, boundary_polygon


def _do_track_search(request, cleaned_data) -> JsonResponse:
    """ carry out a track search, returning a JSON response.
    Expects a valid track_form 
    Can raise a ValidationError if form errors found (boundary DoesNotExist)"""
    query_json, boundary_polygon = _encode_track_search(request, cleaned_data)
    if query_json is None:
        required_keys = ("start_date", "end_date", "tags", "boundary_name")
        # TODO: provide correct info in ValidationError code, params, field
        raise ValidationError(
            f"At least one of {', '.join(required_keys)} must be specified")

    try:
        query_json = get_search_history(request, query_json)
    except ValueError as e:
        return HttpResponse(e.args[0], status=400)
    log.debug("_do_track_search: query_json=%s, Q=%s, q.json=%s", query_json,
              query_json.Q(), query_json.json())
    tracks = Track.objects.filter(query_json.Q(), user=request.user)

    result_count = tracks.count()
    result_limit = request.user.preferences.track_search_result_limit
    tracks=tracks[:result_limit]
    tracks_json = json.loads(serialize("geojson", tracks))
    query_as_json = query_json.json()
    log.info("search ? track: %d%s tracks returned", result_count,
             f" of {result_limit}" if result_count > result_limit else "")
    result = {"status": "success", "tracks": tracks_json,
              "result_limit": result_limit, "result_count": result_count,
              "boundary": boundary_polygon, "search_history": query_as_json}
    return JsonResponse(result, status=200)


def filter_by_tags(request, queryset: QuerySet, tags: str) -> QuerySet:
    """ if tags are defined, return the filtered queryset, otherwise,
    return it unchanged """
    if tags is not None:
        tag_names = [tag.strip() for tag in tags.split(',') if tag]
        if tag_names:
            log.debug("filter_by_tags: tag names in %s", tag_names)
            return queryset.filter(tag__name__in=tag_names)
            # tags = Tag.objects.filter(user=request.user, name__in=tag_names
            #                           ).distinct()
            # return queryset.filter(tag__in=tags).distinct()
    return queryset


def _get_boundary(request, cleaned_data) -> Optional[Boundary]:
    boundary_name = cleaned_data.get("boundary_name")
    if not boundary_name:
        return None

    boundary_category = cleaned_data.get("boundary_category")
    try:
        boundary = Boundary.objects.get(user=request.user,
                                        category=boundary_category,
                                        pk=boundary_name)
    except Boundary.DoesNotExist as e:
        log.error("Boundary pk=%s, category=%s not found",
                  boundary_name, boundary_category)
        raise ValidationError(
            "No boundary found with this name and category") from e
    log.debug("%s search: _get_boundary -> %s:%s",
              request.GET.get("search_type"), boundary.category, boundary.name)
    return boundary

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
    # log.info("track_json(%s): GET=%s", request.method, request.GET)
    if request.method == "GET":
        lat, lon, prefs = nearby_search_params(request)
        query_json = NearbySearchQ(
            lat=lat, lon=lon,
            track__distance_lte=prefs.track_nearby_search_distance_metres)
        try:
            query_json = get_search_history(request, query_json)
        except ValueError as e:
            return HttpResponse(e.args[0], status=400)
        nearby_tracks = Track.objects.filter(query_json.Q(), user=request.user)
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
         "result_limit": result_limit, "tracks": tracks_json,
         "search_history": query_json.json()}, status=200)

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
    gpx = parse_uploaded_gpx(request, file)
    tracks = Track.new_from_gpx(gpx, file.name, user=request.user, save=save)
    return tracks


def parse_uploaded_gpx(request, file: "UploadedFile") -> GPX:
    log.info("uploading file %s, size %d", file.name, file.size)
    # upload a gpx file and convert to a GPX object
    # decode the file as a text file (not binary)
    encoding = file.charset or 'utf-8'
    xml_string = file.read().decode(encoding=encoding)
    gpx = GPXParser(xml_string).parse()
    if not gpx:
        raise TypeError(f"Failed to parse {file.name}" )
    log.info("gpx file %s parsed ok, creator=%s", file.name, gpx.creator)
    return gpx


class TrackDeleteView(BikeLoginRequiredMixin, DeleteView):
    model=Track
    template_name = "track_confirm_delete.html"

    def form_valid(self, _form):
        self.object.delete()
        return HttpResponse(status=204)  # ok, no content


# ------ boundary handling ------
@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "POST"])
def boundary_upload(request):
    """ upload one or more gpx files and convert to a Boundary (or Boundaries).    
    """
    if request.method == "GET":
        form = UploadBoundaryForm()

    else:  # POST
        form = UploadBoundaryForm(request.POST, request.FILES)
        if form.is_valid():
            files = form.cleaned_data['gpx_file']
            errors: List[str] = []
            boundaries: List[Boundary] = []
            for file in files:
                try:
                    gpx = parse_uploaded_gpx(request, file)
                    polygon = Boundary.polygon_from_gpx(gpx)
                    filename = Path(file.name).stem
                except (TypeError, ValueError) as e:
                    log.error("uploading boundary %s: %r", file.name, e)
                    form.add_error("gpx_file", f"{file.name}: {e}")
                    continue

                boundary = Boundary(
                    user=request.user,
                    category = form.cleaned_data["category"],
                    name = filename,
                    polygon = polygon
                    )
                boundaries.append(boundary)

                if Boundary.objects.filter(user=request.user,
                                           category=boundary.category,
                                           name=boundary.name).exists():
                    log.error("boundary already exists in DB: %s:%s",
                              boundary.category, boundary.name)
                    form.add_error("gpx_file", "Duplicate boundary: "
                                   f"{boundary.category}:{boundary.name}")

            if form.is_valid():
                for boundary in boundaries:
                    boundary.save()
                success_url = request.GET.get("next") or reverse(
                    "routes:boundaries")
                return HttpResponseRedirect(success_url)

        log.info("errors were found")
    return render(request, "boundary_upload.html", {"form": form})


class BoundaryListView(BikeLoginRequiredMixin, ListView):
    model = Boundary
    paginate_by = 20  # if pagination is desired
    template_name = "boundary_list.html"

    def get_queryset(self):
        return Boundary.objects.filter(user=self.request.user
                                       ).order_by("category", "name")


class BoundaryUpdateView(BikeLoginRequiredMixin, UpdateView):
    model = Boundary
    fields = ('category', 'name')
    # form_class = BoundaryForm
    template_name = "boundary.html"
    success_url=reverse_lazy("routes:boundaries")

    def get_object(self, queryset=None):
        return get_object_or_404(
            Boundary, user=self.request.user, pk=self.kwargs["pk"])

    def get_context_data(self):
        ctx = super().get_context_data()
        feature_collection = json.loads(
            serialize("geojson", [self.object]))
        feature_collection["bbox"] = leaflet_bounds(self.object.polygon)
        ctx["feature_collection"] = feature_collection
        return ctx


class BoundaryDeleteView(BikeLoginRequiredMixin, DeleteView):
    model = Boundary
    template_name = "boundary_confirm_delete.html"
    success_url=reverse_lazy("routes:boundaries")

    def get_object(self, queryset=None):
        return get_object_or_404(
            Boundary, user=self.request.user, pk=self.kwargs["pk"])

    def get_context_data(self, object=None):
        assert isinstance(object, Boundary), (
            "expecting a Boundary instance, not {object!r}")
        ctx = super(DeleteView, self).get_context_data()
        feature_collection = json.loads(
            serialize("geojson", [object]))
        feature_collection["bbox"] = leaflet_bounds(object.polygon)
        ctx["feature_collection"] = feature_collection
        return ctx


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET"])
def boundary_category_names(request, category:str):
    """ return boundary names in a given category, formatted as <option>s for
    a select statement """
    results = (Boundary.objects.filter(user=request.user, category=category)
                 .values_list("id", "name"))
    options = ['<option value="" selected>-select name(s)-</option>']
    options.extend(
        [f'<option value="{pk}">{name}</option>' for pk, name in results])
    return HttpResponse('\n'.join(options), status=200)


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


def nearby_search_params(request) -> Tuple[float, float, Preferences]:
    """ extract parms for a nearby search latlon=|andlatlon=|orlatlon= """
    latlon: str = request.GET["latlon"]
    try:
        lat, lon = (float(coord) for coord in latlon.split(','))
    except ValueError as e:
        log.error("Unable to parse latlon value %s: %r", latlon, e)
        return HttpResponse("Invalid latlon parameter specified", status=400)
    prefs = Preferences.objects.get_or_create(user=request.user)[0]
    return lat, lon, prefs


def get_search_history(request, query: "SearchQ") -> "SearchQ":
    """ extract search history from query string and recreate the SearchQ """
    if not (join := request.GET.get("join")):
        return query

    if not (search_history := request.GET.get("search_history")):
        raise ValueError("Unable to retrieve search_history from url parameter")
    try:
        searchq_json = json.loads(search_history)
        searchq = SearchQ.from_json(request.user, searchq_json)
    except json.decoder.JSONDecodeError as e:
        raise ValueError(f"Unable to decode search history from url param: {e}"
                         ) from e
    except ValueError as e:
        raise ValueError(f"Unable to parse search history from json: {e}"
                         ) from e
    log.debug("url search_history param=%s", search_history)
    if join == "or":
        query = searchq | query
    elif join == "and":
        query = searchq & query
    else:
        raise ValueError(f"Invalid url join parameter: {join}")
    return query


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET"])
def place_json(request):
    """ return a selection of places based on search parameters including
    &latlon=  &andlatlon=,  &orlatlon=, """
    # log.info("place_json(%s): GET=%s", request.method, request.GET)
    assert request.method == "GET"
    lat, lon, prefs = nearby_search_params(request)
    query_json = NearbySearchQ(
        lat=lat, lon=lon,
        location__distance_lte=prefs.place_nearby_search_distance_metres)
    try:
        query_json = get_search_history(request, query_json)
    except ValueError as e:
        return HttpResponse(e.args[0], status=400)
    nearby_places = Place.objects.filter(query_json.Q(), user=request.user)
    result_count = nearby_places.count()
    result_limit = prefs.place_search_result_limit
    nearby_places = nearby_places[:result_limit]
    if result_count > result_limit:
        log.info("place_json returned %d of %d places", result_count,
                 result_limit)
    else:
        log.info("place_json returned %d places", result_count)
    places = json.loads(serialize("geojson", nearby_places,
                               fields=["name", "type", "id", "pk"],
                               geometry_field="location"))
    result = {"status": "success", "places": places,
              "result_count": result_count, "result_limit": result_limit,
              "boundary": None, "search_history": query_json.json()}
    return JsonResponse(result, status=200)


def _show_places(request, places: List[Place]):
    """ INTERNAL METHOD: no url.  show the given places on a map.
    Used by upload_csv. """
    ctx = get_map_context(request)
    # geojson serialiser has to be defined in settings.py
    # don't serialise tag field because it requires track to have an id
    # - if using view gpx the track is not saved
    ctx["places"] = json.loads(
        serialize("geojson", places, fields=["name", "type", "id", "pk"],
                  geometry_field="location")
        )
    return render(request, "map.html", context=ctx)


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
                messages.success(request, f"{len(places)} places uploaded.")
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


def csrf_failure(request, reason=""):
    log.error("CSRF failure for request %s, \nheaders=%s, \nreason=%s",
              request, request.headers, reason)
    return HttpResponseForbidden('CSRF failure')


def do_logout(request):
    logout(request)
    return HttpResponse("Logged out", status=200)


def leaflet_bounds(obj: GEOSGeometry) -> List[List[float]]:
    """ transform a geosGeometry extent (x1, y1, x2, y2) into a Leaflet
    compatible list [[y1, x1], [y2, x2]]  i.e. lat, lon pairs """
    assert isinstance(obj, GEOSGeometry), "expecting GEOSGeometry, not {obj!r}"
    x1, y1, x2, y2 = obj.extent
    return [[y1, x1], [y2, x2]]


class SearchQDecodeError(ValueError):
    pass


class SearchQ:
    """ represent a django Q query that can be executed by Django and also
    serialised to json, for reuse in future queries.
    Ref:
    https://docs.djangoproject.com/en/5.2/topics/db/queries/#complex-lookups-with-q-objects
    """
    def __init__(self, **kwargs):
        assert len(kwargs) == 1, f"expecting a single kw arg, not {kwargs}"
        self._key, self._value = next(iter(kwargs.items()))

    def __repr__(self):
        return f"SearchQ({self._key}={self._value})"

    def __eq__(self, other):  # for unit testing
        return (self.__class__ == other.__class__ and self._key == other._key
                and self._value == other._value)

    def __and__(self, other: "SearchQ"):
        if not isinstance(other, SearchQ):
            raise TypeError(f"expecting SearchQ, not {other!r}")
        return AndSearchQ(self, other)

    def __or__(self, other: "SearchQ"):
        if not isinstance(other, SearchQ):
            raise TypeError(f"expecting SearchQ, not {other!r}")
        return OrSearchQ(self, other)

    def Q(self) -> Q:
        """ return a Q function """
        return Q(**{self._key: self._value})

    def json(self) -> Dict[str, Any]:
        """ return json representation """
        if isinstance(self._value, dt.datetime):
            return {"SearchQ":
                    {"key": self._key, "datetime": self._value.isoformat()}}
        return {"SearchQ": {"key": self._key, "value": self._value}}


    @classmethod
    def from_json(cls, user, source: Dict[str, Any]):
        match source:
            case {"SearchQ": {"key": key, "value": value}}:
                return SearchQ(**{key: value})
            case {"SearchQ": {"key": key, "datetime": datetime_str}}:
                return SearchQ(**{key: dt.datetime.fromisoformat(datetime_str)})
            case {"AndSearchQ": [*searchq_list_source]}:
                searchq_list = SearchQ.list_from_json(user, searchq_list_source)
                return AndSearchQ(*searchq_list)
            case {"OrSearchQ": [*searchq_list_source]}:
                searchq_list = SearchQ.list_from_json(user, searchq_list_source)
                return OrSearchQ(*searchq_list)
            case {"BoundarySearchQ": {"category": category, "key": key,
                                      "name": name}}:
                return BoundarySearchQ(user, category, **{key: name})
            case {"NearbySearchQ": {"lat": lat, "lon": lon, "key": key,
                                    "distance": distance}}:
                return NearbySearchQ(lat=lat, lon=lon, **{key: distance})
            case _:
                raise SearchQDecodeError(
                    f"Unable to parse SearchQ from '{source}'")

    @classmethod
    def list_from_json(cls, user, source_list: List[Dict[str, Any]]
                       ) -> List["SearchQ"]:
        searchq_list: List["SearchQ"] = []
        for i, item in enumerate(source_list):
            try:
                searchq = SearchQ.from_json(user, item)
            except SearchQDecodeError as e:
                raise SearchQDecodeError(f"{e.args[0]} (in list item {i})"
                                         ) from e
            searchq_list.append(searchq)
        return searchq_list


class AndSearchQ(SearchQ):
    """ contains a list of SearchQ queries that are logically ANDed together """
    def __init__(self, *args: Sequence[SearchQ]):
        not_searchQ = [str(type(arg))
                       for arg in args
                       if not isinstance(arg, SearchQ)]
        if not_searchQ:
            raise TypeError(
                f"all args must be type SearchQ, not {','.join(not_searchQ)}")
        assert len(args) >1 , "expecting at least two arguments"
        self._args = args

    def __repr__(self):
        return f"AndSearchQ({' & '.join(str(arg) for arg in self._args)})"

    def __eq__(self, other):
        return self.__class__ == other.__class__ and self._args == other._args

    def Q(self) -> Q:
        q = self._args[0].Q()
        for arg in self._args[1:]:
            q &= arg.Q()
        return q

    def json(self) -> Dict[str, List[Dict]]:
        return {"AndSearchQ": [arg.json() for arg in self._args]}


class OrSearchQ(AndSearchQ):
    """ contains a list of SearchQ queries that are logically ORed together""" 
    # __ init__ and __eq__ as for AndSearchQ

    def __repr__(self):
        """ parenthesize and or or sub-arguments """
        str_args = (f"({arg})" if isinstance(arg, (AndSearchQ, OrSearchQ))
                    else f"{arg}" for arg in self._args)
        return f"OrSearchQ({' | '.join(str_args)})"

    def Q(self) -> Q:
        q = self._args[0].Q()
        for arg in self._args[1:]:
            q |= arg.Q()
        return q

    def json(self) -> Dict[str, Any]:
        return {"OrSearchQ": [arg.json() for arg in self._args]}


class BoundarySearchQ(SearchQ):
    """ contains a search query within a boundary specified by name and category
    This is validated every time it's used in case boundaries have been renamed.
    kwargs are e.g. location__within=name or track__intersects=name 
    """
    def __init__(self, user, boundary_category, **kwargs):
        self.boundary_category = boundary_category
        assert len(kwargs) == 1, f"expecting one keyword arg, not {kwargs}"
        self._key, self.boundary_name = next(iter(kwargs.items()))
        try:
            self.boundary = Boundary.objects.get(
                user=user, category=boundary_category, pk=self.boundary_name)
        except Boundary.DoesNotExist as e:
            log.error("Boundary pk=%s, category=%s not found",
                      self.boundary_name, boundary_category)
            raise ValidationError(
                "No boundary found with this name and category") from e

    def __repr__(self):
        return (f"BoundarySearchQ("
                f"{self.boundary_category}, {self._key}={self.boundary_name})")

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and self.user == other.user
                and self.boundary == other.boundary)

    def Q(self) -> Q:
        return Q(**{self._key: self.boundary.polygon})

    def json(self) -> Dict[str, Any]:
        return {"BoundarySearchQ": {
            "category": self.boundary_category, "key": self._key,
            "name": self.boundary_name}}

class NearbySearchQ(SearchQ):
    """ Contains a search query for tracks/places within a set distance of a
    point.  Distance in metres """
    def __init__(self, *, lat: float, lon: float, **kwargs):
        self._lat = lat
        self._lon = lon
        assert len(kwargs) == 1, (
            f"expecting one keyword arg after lat, lon, not {kwargs}")
        self._key, self._distance = next(iter(kwargs.items()))

    def __repr__(self):
        return (f"NearbySearchQ(lat={self._lat}, lon={self._lon}, "
                f"{self._key}={self._distance})")

    def __eq__(self, other):
        return (self.__class__ == other.__class__ and self._lat == other._lat
                and self._lon == other._lon and self._key == other._key
                and self._distance == other._distance)

    def Q(self)-> Q:
        return Q(**{
            self._key: (Point(self._lon, self._lat), D(m=self._distance))})

    def json(self) -> Dict[str, Any]:
        return {"NearbySearchQ": {"lat": self._lat, "lon": self._lon,
                                  "key": self._key, "distance": self._distance}}
