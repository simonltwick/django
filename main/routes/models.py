""" models for routes app """
from dataclasses import dataclass, field
from enum import IntEnum
import logging
import os.path
from typing import List, Dict, TYPE_CHECKING

from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point, LineString, MultiLineString

from bike.models import DistanceUnits

if TYPE_CHECKING:
    from gpxpy.gpx import GPX


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

""" choices for place type icons.  icon name refers to an image in the
static folder.  Does not have to be svg but recommended.
In future, it may be possible to choose colour dynamically through css """
ICON_CHOICES= {
    "Beer": "cup-straw-pink.svg",
    "Coffee": "cup-orange.svg",
    "Tea": "teapot.svg",
    "Place": "geo-green.svg",
    "Camera": "camera-yellow.svg",
    "Bullseye": "bullseye-blue.svg"
    }


class PlaceType(models.Model):
    """ a type of place, eg. Pub, Cafe """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=40)
    icon = models.CharField(max_length=30, choices=ICON_CHOICES,
                            default="geo-green.svg")

    def __str__(self):
        return self.name


def get_default_place_type():
    return PlaceType.objects.get_or_create(name='Place')[0].id

class Place(models.Model):
    """ a named point on the map """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=40)
    location = models.PointField()
    type = models.ForeignKey(PlaceType, on_delete=models.PROTECT,
                             default=get_default_place_type)

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return f"Place(name={self.name},location={self.location})"

class RawGpx(models.Model):
    """ to store the raw gpx file for a track """
    # FIXME: should declare a save_to path for saving files
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.FileField(editable=True)


class Track(models.Model):
    """ a (gpx) track """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    raw_gpx_id = models.ForeignKey(RawGpx, on_delete=models.SET_NULL,
                                   blank=True, null=True)
    name = models.CharField(unique=True, max_length=40)
    track = models.MultiLineStringField(dim=3)
    # , srid=4326 is the default)

    @classmethod
    def new_from_gpx(cls, gpx: "GPX", fname: str, user: User) -> List["Track"]:
        """ convert a GPX object to a track (or possibly, several tracks)
        but DO NOT SAVE the tracks """

        # """
        # if gpx.waypoints:
        #     for waypoint in gpx.waypoints:
        #         new_waypoint = GPXPoint()
        #         if waypoint.name:
        #             new_waypoint.name = waypoint.name
        #         else:
        #             new_waypoint.name = 'unknown'
        #         new_waypoint.point = Point(waypoint.longitude, waypoint.latitude)
        #         new_waypoint.gpx_file = file_instance
        #             new_waypoint.save()
        # """

        if not gpx.tracks:
            log.error("Gpx contains no tracks")

        tracks = []
        for track_num, track in enumerate(gpx.tracks):
            log.info("converting track #%d name: %s in file %s",
                     track_num, track.name, fname)
            new_track = cls(user=user)

            # check filename is unique
            fname = os.path.basename(fname)  # remove dirname if present
            if track.name:
                new_track.name = track.name
            elif track_num == 0:
                new_track.name = fname
            else:
                fname_base, ext = os.path.splitext(fname)
                new_track.name = f"{fname_base}#{track_num}{ext}"
            if cls.objects.filter(name=new_track.name, user=user).exists():
                raise FileExistsError(f"duplicate filename: {new_track.name}")

            # add track segments
            segments = []
            for segment in track.segments:
                points = []
                for point in segment.points:

                    point_in_segment = Point(point.longitude, point.latitude,
                                             point.elevation)
                    points.append(point_in_segment.coords)

                segments.append(LineString(points))

            new_track.track = MultiLineString(segments)
            # new_track.gpx_file = file_instance
            tracks.append(new_track)

        return tracks


# ------ Settings handling ------
class Preferences(models.Model):
    """ store user preferences for distance units, and for search """
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                primary_key=True, related_name='routes_preferences')
    distance_units = models.IntegerField(default=DistanceUnits.KILOMETRES,
                                         choices=DistanceUnits)
    # units for the settings below are yards or metres (dep. on distance_units)
    track_nearby_search_distance = models.FloatField(default=5)
    track_search_result_limit = models.IntegerField(default=100)
    place_nearby_search_distance = models.FloatField(default=20)
    place_search_result_limit = models.IntegerField(default=1000)
