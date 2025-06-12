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
from django.db.utils import IntegrityError
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.views.decorators.gzip import gzip_page
from django.views.generic import TemplateView
# all these imports for copied answer

from .models import Marker, Track
from .forms import UploadGpxForm2


if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)



def get_map_context() -> Dict:
    # geojson serialiser has to be defined in settings.py
    ctx = {}
    ctx["markers"] = json.loads(
        serialize("geojson", Marker.objects.all())
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


def SaveGPXtoPostGIS(f, file_instance):
    """ reference implementation from web.  source: 
    http://web.archive.org/web/20160425053015/http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
    """

    gpx_file = open(settings.MEDIA_ROOT+ '/uploaded_gpx_files'+'/' + f.name)
    gpx = gpxpy.parse(gpx_file)

    if gpx.waypoints:
        for waypoint in gpx.waypoints:
            new_waypoint = GPXPoint()
            if waypoint.name:
                new_waypoint.name = waypoint.name
            else:
                new_waypoint.name = 'unknown'
            new_waypoint.point = Point(waypoint.longitude, waypoint.latitude)
            new_waypoint.gpx_file = file_instance
            new_waypoint.save()

    if gpx.tracks:
        for track in gpx.tracks:
            log.info("track name: %s", track.name)
            new_track = GPXTrack()
            for segment in track.segments:
                track_list_of_points = []
                for point in segment.track_points:

                    point_in_segment = Point(point.longitude, point.latitude)
                    track_list_of_points.append(point_in_segment.coords)

                new_track_segment = LineString(track_list_of_points)

            new_track.track = MultiLineString(new_track_segment)
            new_track.gpx_file = file_instance
            new_track.save()


def upload_gpx(request):
    """ upload and parse a GPX file.  source: 
    http://web.archive.org/web/20160425053015/http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
    """
    args = {}

    if request.method == 'POST':
        file_instance = gpxFile()
        form = UploadGpxForm(request.POST, request.FILES, instance=file_instance)
        args['form'] = form
        if form.is_valid():
            form.save()
            SaveGPXtoPostGIS(request.FILES['gpx_file'], file_instance)

            return HttpResponseRedirect('success/')

    else:
        args['form'] = UploadGpxForm()

    return render(request, 'myapp/form.html', args)
