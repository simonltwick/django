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
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.gzip import gzip_page
from django.views.generic import TemplateView
# all these imports for copied answer

from .models import Place, Track
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
def place(request, pk=None):
    if request.method == 'GET':
        assert pk is None, "get with pk not yet supported"
        # expect lat/lon to be specified as query parameters ?lat=555&lon=666
        lat = request.GET.get('lat')
        lon = request.GET.get('lon')
        if lat is None or lon is None:
            return HttpResponse('lat / lon not specified', status=400)
        form = PlaceForm()
    else:
        # handle POST request
        # ref: https://forum.djangoproject.com/t/django-ajax-form-submission-is-always-invalid/23521/3
        if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return HttpResponse("must request using XML", status=400)
        data = json.load(request)
        del data["csrfmiddlewaretoken"]
        data["location"] = Point(float(data["lon"]), float(data["lat"]))
        if not data["id"]:  # returned as empty string
            del data["id"]
        log.info("place request data=%s", data)
        if pk is None:
            place_inst = Place()
        else:
            assert pk == data["id"], "invalid ID in post response"
            place_inst = Place.objects.get(pk=pk)
            form = PlaceForm(initial=data, instance=place)

        if data["name"]:   # sole validation for now
            place_inst.name = data["name"]
            place_inst.location = data["location"]
            log.info("Place is valid")
            place_inst.save()
            # note: location coords are lon,lat  (x,y)
            log.info("Saved Place id %d: %s @ %s", place_inst.id,
                     place_inst.name, place_inst.location.coords)
            # TODO: add json place ID in json in the response
            # return JsonResponse({"instance": "saved successfully",
            #                      "form_isbound" : form.is_bound,
            #                      "django_backend": test}, status=200)
            return JsonResponse({"instance": "saved successfully", "type": "",
                                 "name": place_inst.name, "id": place_inst.pk},
                                 status=200)

        log.error("PlaceForm is not valid: %s", form.errors)
        return render(request, 'place.html', context={'form': form})

    return render(request, 'place.html',
                  context={"form": form, "lat": lat, "lon": lon})


