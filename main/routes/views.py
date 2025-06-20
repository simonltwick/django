#!/usr/bin/env python3
""" views for routes app """
import json
import logging
from typing import TYPE_CHECKING, Optional, List, Dict

from gpxpy.parser import GPXParser
from gpxpy.gpx import GPX

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers import serialize
from django.core.serializers.base import SerializerDoesNotExist
from django.contrib.gis.geos import Point
from django.db.utils import IntegrityError
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods
from django.views.decorators.gzip import gzip_page
from django.views.generic import (
    TemplateView, ListView, CreateView, UpdateView, DeleteView)
# all these imports for copied answer
from .models import Place, Track, PlaceType, ICON_CHOICES
from .forms import UploadGpxForm2, PlaceForm


if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)



def get_map_context() -> Dict:
    # geojson serialiser has to be defined in settings.py
    ctx = {}
    ctx["markers"] = json.loads(
        serialize("geojson", Place.objects.all())
        )
    ctx["tracks"] = json.loads(
        serialize("geojson", Track.objects.all())
        )
    ctx["ocm_api_key"] = settings.OCM_API_KEY
    return ctx


@require_http_methods(["GET"])
@gzip_page
def map(request):
    """ return a map showing ALL tracks and markers """
    context = get_map_context()
    return render(request, 'map.html', context=context)


class TracksView(TemplateView):
    """ show a track or tracks, requested by track id or a comma-separated list
    of track ids """
    template_name = "map.html"

    def get(self, request, *args, **kwargs):
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
            raise ValidationError(f"Invalid track id: {e.args[0]}")
        tracks = Track.objects.filter(id__in=trackids)
        ctx["tracks"] = json.loads(serialize("geojson", tracks))
        return ctx


def show_tracks(request, tracks: List[Track]):
    """ show the given tracks on a map """
    ctx = {}
    ctx["tracks"] = json.loads(serialize("geojson", tracks))
    return render(request, "map.html", context=ctx)


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
                    gpx, form.cleaned_data['gpx_file'].name)
            except FileExistsError as e:
                return HttpResponse(status=400, content=e.args[0])
            # gpx_id = form.cleaned_data["id"]
            for track in tracks:
                track.save()
                log.debug("saved track %s, id=%d", track.name, track.pk)
            return show_tracks(request, tracks)
            # trackids = ','.join(str(track.id) for track in tracks)
            # return HttpResponseRedirect(
            #     reverse("routes:tracks_view", kwargs={"trackids": trackids}))

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
    fname = ("/home/simon/Documents/Travel/CoastalAdventure/2025-South/Actual/"
            "2025-05-25-08-32-09.gpx")
    with open(fname, 'rt', encoding='utf-8') as infile:
        xml_string = infile.read()
    gpx = GPXParser(xml_string).parse()
    if not gpx:
        return HttpResponse("Failed to parse file", status=400)
    log.info("gpx file %s parsed ok", gpx)
    try:
        tracks = Track.new_from_gpx(gpx, fname)
    except IntegrityError as e:
        return HttpResponse(status=400, content=e.args)
    trackids = ','.join(str(track.id) for track in tracks)
    return HttpResponseRedirect(
        reverse("routes:tracks_view", kwargs={"trackids": trackids}))


# ------------- place handling ---------------
@require_http_methods(["GET", "POST"])
def place(request, pk=None):
    """ insert or update place details """
    # log.info("place.%s(pk=%r, request.GET=%s, request.POST=%s)",
    #          request.method, pk, request.GET, request.POST)
    if request.method == 'GET':
        if pk is not None:
            place_inst = get_object_or_404(Place, pk=pk)
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
    else:
        assert str(pk) == request.POST.get("pk"), "invalid ID in post response"
        place_inst = get_object_or_404(Place, pk=pk)
        form = PlaceForm(request.POST, instance=place_inst)
    if form.is_valid():
        form.save()
        type_name = form.instance.type.name if form.instance.type else ''
        return JsonResponse(
            {"instance": "saved successfully", "type": type_name,
             "name": form.instance.name, "pk": form.instance.pk},
            status=200)

    # handle form errors
    return render(request, 'place.html', context={"form": form, 'pk': pk})


def place_delete(request, pk: int):
    """ handle a delete request """
    if request.method == "GET":
        # send the delete confirmation form, (with CSRF token)
        place = get_object_or_404(Place, pk=pk)
        return render(request, 'place_delete.html', context={"place": place})

    # else (POST): actually do the delete after confirmation
    form_pk = request.POST.get("pk")
    assert form_pk == str(pk), "pk in url doesn't match pk in form"
    get_object_or_404(Place, pk=pk).delete()
    return JsonResponse({"instance": "deleted successfully", "pk": pk},
                         status=200)


def place_move(request, pk: int):
    """ handle a move request """
    place = get_object_or_404(Place, pk=pk)
    #log.info("place_move: request.GET=%s, request.POSt=%s", request.GET,
    #         request.POST)
    if request.method == "GET":
        return render(request, 'place_move.html', context={'place': place})

    # else (POST)
    lat, lon = request.POST.get('lat'), request.POST.get("lon")
    assert request.POST.get("pk") == str(pk), "url mismatch to form data for pk"
    place.location = Point(float(lon), float(lat))
    place.save()
    return HttpResponse(status=200)


# ---- place types ----
class PlaceTypeListView(ListView):
    model = PlaceType
    context_object_name = "place_types"
    template_name = "placetype_list.html"


# class PlaceTypeFormView(FormView):
#     model = PlaceType
#     form_class = PlaceTypeForm
#     success_url = reverse_lazy("routes:map")
#     template_name = "placetype_form.html"
#
#     def form_valid(self, form):
#         log.info("PlaceType form is valid: %s", form)
#         form.save()
#         return super().form_valid(form)

def place_type_list_json(request):
    """ return a json list of icons & names for all defined place types """
    data = {place_type.pk:
            {"icon": f"{settings.STATIC_URL}icons/{place_type.get_icon_display()}",
             "name": place_type.name}
            for place_type in PlaceType.objects.all()}
    # log.info("PlaceTypeListJson returning %s", data)
    # must set safe=False in order to send lists, otherwise only dict allowed
    return JsonResponse(data, status=200)


class PlaceTypeCreateView(CreateView):
    model = PlaceType
    fields = ["name", "icon"]
    success_url = reverse_lazy("routes:place_types")
    template_name = "placetype_form.html"

class PlaceTypeUpdateView(UpdateView):
    model = PlaceType
    fields = ["name", "icon"]
    success_url = reverse_lazy("routes:place_types")
    template_name = "placetype_form.html"

class PlaceTypeDeleteView(DeleteView):
    model = PlaceType
    success_url = reverse_lazy("routes:place_types")
    template_name = "placetype_delete_form.html"
