#!/usr/bin/env python3
""" views for routes app """
import json
import logging
from typing import TYPE_CHECKING, Optional, List, Dict, Tuple

from gpxpy.parser import GPXParser
from gpxpy.gpx import GPX

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers import serialize
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.gis.geos import Point
from django.http import (
    HttpResponseRedirect, HttpResponse, JsonResponse, HttpResponseForbidden)
from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods
from django.views.decorators.gzip import gzip_page
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DeleteView)

from .models import (
    Place, Track, PlaceType, get_default_place_type, Preference)
from .forms import (
    UploadGpxForm2, PlaceForm, PreferenceForm, TrackSearchForm, PlaceSearchForm,
    TestCSRFForm)


if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


LOGIN_URL = '/bike/login?next=/bike'

class BikeLoginRequiredMixin(LoginRequiredMixin):
    login_url = LOGIN_URL


def get_map_context(request) -> Dict:
    # geojson serialiser has to be defined in settings.py
    ctx = {}
    ctx["markers"] = json.loads(
        serialize("geojson", Place.objects.filter(user=request.user).all())
        )
    ctx["tracks"] = json.loads(
        serialize("geojson", Track.objects.filter(user=request.user).all())
        )
    ctx["ocm_api_key"] = settings.OCM_API_KEY
    return ctx


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET"])
@gzip_page
def map(request):
    """ return a map showing ALL tracks and markers """
    context = get_map_context(request)
    return render(request, 'map.html', context=context)


@login_required(login_url=LOGIN_URL)
@require_http_methods(["POST", "GET"])
@gzip_page
def search(request, search_type: Optional[str]):
    log.info("search(search_type=%s), method=%s", search_type, request.method)

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
            return render(request, "search.html", context={
                "track_form": track_form, "place_form": place_form})

        tracks = Track.objects.filter(user=request.user)
        start_date = track_form.cleaned_data.get("start_date")
        if start_date is not None:
            tracks = tracks.filter(start_time__gte=start_date)
        end_date = track_form.cleaned_data["end_date"]
        if end_date is not None:
            tracks = tracks.filter(start_time__lte=end_date)
        tracks=tracks[:request.user.routes_preference.track_search_result_limit]
        tracks_json = json.loads(serialize("geojson",tracks))
        return JsonResponse({"status": "success", "tracks": tracks_json},
                            status=200)
    if search_type != 'place':
        log.error("search_type not recognised: POST=%s", request.POST)
        return HttpResponse("Search_type not defined", status=400)

    # search_type == 'place'
    if not place_form.is_valid():
        return render(request, "search.html", context={
            "track_form": track_form, "place_form": place_form})

    log.info("place_search: form.cleaned_data=%s", place_form.cleaned_data)
    return HttpResponse("Not implemented", status=501)


def test_csrf(request):
    if request.method == 'GET':
        form = TestCSRFForm()
        return render(request, 'test_csrf.html', context={'form': form})

    log.info("test_csrf: POST=%s", request.POST)
    form = TestCSRFForm(request.POST)
    log.info("form received successfully.  is_valid=%s", form.is_valid())
    return HttpResponse("OK", status=200)


class TracksView(BikeLoginRequiredMixin, TemplateView):
    """ show a track or tracks, requested by track id or a comma-separated list
    of track ids """
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
@require_http_methods(["GET"])
@gzip_page
def track_json(request):
    """ return a selection of tracks based on search parameters including
    &latlon=  &andlatlon=,  &orlatlon=, (name, date - not yet defined) """
    # query = Track.objects
    log.info("track_json: GET=%s", request.GET)
    params = request.GET
    defaults = {'latlon': None,  # float, float,
                'andlatlon': None,  # float, float
                }
    limits = {key: params.get(key, default_value)
              for key, default_value in defaults.items()}
    prefs = Preference.objects.get_or_create(user=request.user)[0]
    nearby_tracks: dict = Track.nearby(limits, prefs)
    log.info("track_json returned %d tracks", len(nearby_tracks))
    msg = json.loads(serialize("geojson", nearby_tracks))
    return JsonResponse(msg, status=200)


def parse_latlon(value: str) -> Tuple[float, float]:
    """ parse a string containing two floats """
    values = value.split(',')
    if len(values) > 2:
        raise ValueError(f"Too many values for latlon: {value!r}")
    float_values = tuple(float(v) for v in values)
    return float_values


def _show_tracks(request, tracks: List[Track]):
    """ INTERNAL METHOD: no url.  show the given tracks on a map.
    Used by upload_file. """
    ctx = {}
    ctx["tracks"] = json.loads(serialize("geojson", tracks))
    return render(request, "map.html", context=ctx)


@login_required(login_url=LOGIN_URL)
def upload_file(request, save=True):
    """ upload a gpx file and convert to a Track (or Tracks).
    If save=True, save the Track(s) in the DB, otherwise just view without
    saving
    
    Ref: https://docs.djangoproject.com/en/5.1/topics/http/file-uploads/ 
    important post here:
    https://web.archive.org/web/20160425053015/http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
    """
    if request.method == "POST":
        file = request.FILES.get('gpx_file')
        log.info("uploading file %s, size %d", file.name, file.size)
        form = UploadGpxForm2(request.POST, request.FILES)
        if form.is_valid():
            gpx = convert_file_to_gpx(form.cleaned_data['gpx_file'])
            if not gpx:
                return HttpResponse("Failed to parse file", status=400)
            log.info("gpx file %s parsed ok", gpx)

            try:
                tracks = Track.new_from_gpx(
                    gpx, form.cleaned_data['gpx_file'].name, user=request.user)
            except FileExistsError as e:
                return HttpResponse(status=400, content=e.args[0])
            # gpx_id = form.cleaned_data["id"]
            for track in tracks:
                track.save()
                log.debug("saved track %s, id=%d", track.name, track.pk)
            return _show_tracks(request, tracks)

        log.info("form was not valid")
    else:
        form = UploadGpxForm2()
    return render(request, "gpx_upload.html", {"form": form, "save": save})


def convert_file_to_gpx(file: "UploadedFile") -> Optional[GPX]:
    """ upload a gpx file and convert to a GPX object """
    log.info("gpx file %s is valid", file.name)
    # decode the file as a text file (not binary)
    encoding = file.charset or 'utf-8'
    xml_string = file.read().decode(encoding=encoding)
    return GPXParser(xml_string).parse()


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


# ------------- place handling ---------------
@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "POST"])
def place(request, pk=None):
    """ insert or update place details """
    # log.info("place.%s(pk=%r, request.GET=%s, request.POST=%s)",
    #          request.method, pk, request.GET, request.POST)
    if request.method == 'GET':
        if pk is not None:
            place_inst = get_object_or_404(Place, pk=pk, user=request.user)
            form = PlaceForm(instance=place_inst)
        else:
            form = PlaceForm()

        return render(request, 'place.html', context={"form": form, "pk": pk})

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
    return render(request, 'place.html', context={"form": form, 'pk': pk})


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
    return HttpResponse(status=200)


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
    data["default"] = get_default_place_type()
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
    template_name = "placetype_delete_form.html"

    def dispatch(self, request, *args, **kwargs):
        if self.kwargs['pk'] == get_default_place_type():
            return HttpResponse(
                "Cannot delete the default place type", status=403)
        if not PlaceType.objects.filter(pk=self.kwargs['pk'],
                                        user=request.user).exists():
            return HttpResponse("Unauthorised place type", status=401)
        return super(PlaceTypeDeleteView, self).dispatch(
            request, *args, **kwargs)


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
    data = json.dumps(json_data)
    # log.info("preference_as_json: data=%s", data)
    return JsonResponse(data, safe=False, status=200)


def csrf_failure(request, reason=""):
    log.error("CSRF failure for request %s, \nheaders=%s, \nreason=%s",
              request, request.headers, reason)
    return HttpResponseForbidden('CSRF failure')
