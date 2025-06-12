""" models for routes app """
import logging
import os.path
from typing import List, TYPE_CHECKING

from django.contrib.gis.db import models
from django.contrib.gis.geos import Point, LineString, MultiLineString


if TYPE_CHECKING:
    from gpxpy.gpx import GPX


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class Place(models.Model):
    """ a named point on the map """
    name = models.CharField(max_length=40)
    location = models.PointField()

    def __str__(self):
        return str(self.name)

class RawGpx(models.Model):
    """ to store the raw gpx file for a track """
    # FIXME: should declare a save_to path for saving files
    content = models.FileField(editable=True)


class Track(models.Model):
    """ a (gpx) track """
    raw_gpx_id = models.ForeignKey(RawGpx, on_delete=models.SET_NULL,
                                   blank=True, null=True)
    name = models.CharField(unique=True, max_length=40)
    track = models.MultiLineStringField(dim=3)
    # , srid=4326 is the default)

    @classmethod
    def new_from_gpx(cls, gpx: "GPX", fname: str) -> List["Track"]:
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
            new_track = cls()

            # check filename is unique
            fname = os.path.basename(fname)  # remove dirname if present
            if track.name:
                new_track.name = track.name
            elif track_num == 0:
                new_track.name = fname
            else:
                fname_base, ext = os.path.splitext(fname)
                new_track.name = f"{fname_base}#{track_num}{ext}"
            if cls.objects.filter(name=new_track.name).exists():
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
