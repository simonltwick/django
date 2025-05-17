#!/usr/bin/env python3
import json
import logging
from typing import TYPE_CHECKING

from django.core.serializers import serialize
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import TemplateView


from .models import Marker
from .forms import GpxFileForm

# all these imports for copied answer
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect
from django.core.context_processors import csrf
from django.contrib.gis.geos import Point, LineString, MultiLineString

from myapp.forms import UploadGpxForm
from myapp.models import GPXPoint, GPXTrack, gpxFile

from django.conf import settings

import gpxpy
import gpxpy.gpx


if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class MapView(TemplateView):
    """ (test version) send the default map of the globe, showing markers """
    template_name = "map.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["markers"] = json.loads(
            serialize(
                "geojson",
                Marker.objects.all(),
            )
        )
        return ctx


def upload_file(request):
    """ upload a gpx file (test version) 
    
    This literally stores the file as a blob, no spatialite/geo parsing.
    Ref: https://docs.djangoproject.com/en/5.1/topics/http/file-uploads/ """
    """ important post here:
    https://web.archive.org/web/20160425053015/http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
    """
    if request.method == "POST":
        form = UploadGpxForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            gpx_id = form.cleaned_data["id"]
            log.info("gpx file saved, id %d", gpx_id)
            return HttpResponseRedirect("/success/url/")
    else:
        form = UploadGpxForm()
    return render(request, "gpx_upload.html", {"form": form})


def SaveGPXtoPostGIS(f, file_instance):

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
                for point in segment.points:

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
    args.update(csrf(request))

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

    return render_to_response('myapp/form.html', args)


def upload_success(request):
    return render_to_response('myapp/success.html')
