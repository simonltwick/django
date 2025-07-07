""" models for routes app """
import csv
from io import StringIO
import logging
import os.path
from typing import List, Dict, TYPE_CHECKING

from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point, LineString, MultiLineString
from django.contrib.gis.measure import D  # synonym for Distance

from bike.models import DistanceUnits

if TYPE_CHECKING:
    from gpxpy.gpx import GPX, GPXTrack
    from django.core.files.uploadedfile import UploadedFile


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class QueryStringError(ValueError):
    """ signifies invalid query string in a web request """
    pass


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


def get_default_place_type() -> PlaceType:
    return PlaceType.objects.get_or_create(name='Place')[0]

def get_default_place_type_pk() -> int:
    return get_default_place_type().pk

class Place(models.Model):
    """ a named point on the map """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=40)
    location = models.PointField()
    type = models.ForeignKey(PlaceType, on_delete=models.PROTECT,
                             default=get_default_place_type_pk)

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return f"Place(name={self.name},location={self.location})"


    @classmethod
    def build_places_from_csv(cls, file: "UploadedFile", user: User,
                              place_types: Dict[int, str],
                              default_place_type: PlaceType
                              ) -> List["Place"]:
        placetype_name_to_pk = {name.lower(): pk
                                for pk, name in place_types.items()}
        default_type_pk = default_place_type.pk
        encoding = file.charset or 'utf-8'
        csv_contents = file.read().decode(encoding=encoding)
        log.debug("csv_contents=%r", csv_contents)
        csv_reader = csv.DictReader(
            csv_contents.splitlines(),
            fieldnames=["name", "latitude", "longitude", "type"])
        header = next(csv_reader)  # ignore header row
        log.debug("header row has values:", header)
        places: List["Place"] = []
        for row_num, row in enumerate(csv_reader):
            log.debug("processing row %s ", row)
            try:
                col = "latitude"
                lat = float(row[col])
                col = "longitude"
                lon = float(row[col])
            except ValueError as e:
                raise ValueError(
                    f"Invalid value {row[col]!r} in row {row_num+1} for {col}"
                    ) from e
            type_pk = placetype_name_to_pk.get(
                row["type"].lower(), default_type_pk)
            place = cls(user=user, name=row["name"],
                        location=Point(lon, lat), type_id=type_pk)
            places.append(place)
        return places

    @classmethod
    def nearby(cls, limits: Dict, prefs: "Preference"):
        """ return a queryset of places according to limits such as
        latlon: latlon (less than preferences.place_search_distance from latlon)
        """
        query = Place.objects.filter(user=prefs.user)
        for key, value in limits.items():
            # log.debug("Place.nearby: key=%s, value=%s", key, value)
            if value is None:
                continue # value can be stored as a list, terminated by None
            if key in {"latlon", "andlatlon"}:
                lat, lon = parse_floats(value, 2, f'{key} must be y,x')
                query = query.filter(location__distance_lte=(Point(lon, lat), D(
                    m=prefs.place_nearby_search_distance_metres)))
            else:
                raise QueryStringError(f"unrecognised query keyword {key!r}")
        # limit the number of results returned
        query = query[:prefs.place_search_result_limit]
        return query


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
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    moving_time = models.FloatField(blank=True, null=True,
                                      help_text="Moving time in seconds")
    moving_distance = models.FloatField(blank=True, null=True,
                                          help_text="Moving distance in metres")
    ascent = models.FloatField(blank=True, null=True,
                                 help_text="Ascent in metres")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['user', 'name'], name='unique_name'),
        ]

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
            new_track.add_gpx_stats(track)
            tracks.append(new_track)

        return tracks

    def __str__(self):
        s = self.name or self.start_time or "unnamed Track"
        if self.moving_distance:
            preferred_distance_units = self.user.routes_preference.distance_units
            distance = DistanceUnits.convert(
                self.moving_distance/1000.0,
                DistanceUnits.KILOMETRES, preferred_distance_units)
            units_display_name = DistanceUnits.display_name(
                preferred_distance_units)
            s += f" ({distance:.0f} {units_display_name})"
        return s

    @classmethod
    def nearby(cls, limits: Dict, prefs: "Preference"):
        """ return a queryset of tracks according to limits such as
        latlon: latlon (less than preferences.track_search_distance from latlon)
        """
        query = Track.objects.filter(user=prefs.user)
        for key, value in limits.items():
            # log.debug("Track.nearby: key=%s, value=%s", key, value)
            if value is None:
                continue # value can be stored as a list, terminated by None
            if key in {"latlon", "andlatlon"}:
                lat, lon = parse_floats(value, 2, f'{key} must be y,x')
                query = query.filter(track__distance_lte=(Point(lon, lat), D(
                    m=prefs.track_nearby_search_distance_metres)))
            else:
                raise QueryStringError(f"unrecognised query keyword {key!r}")
        # limit the number of results returned
        query = query[:prefs.track_search_result_limit]
        return query

    def add_gpx_stats(self, gpx_track: "GPXTrack"):
        """ add stats calculated from the gpx file """
        time_bounds = gpx_track.get_time_bounds()
        self.start_time = time_bounds.start_time
        self.end_time = time_bounds.end_time
        moving_data = gpx_track.get_moving_data()
        self.moving_time = moving_data.moving_time
        self.moving_distance =  moving_data.moving_distance
        self.ascent = gpx_track.get_uphill_downhill().uphill


# ------ Settings handling ------
class Preference(models.Model):
    """ store user preference for distance units, and for search """
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                primary_key=True, related_name='routes_preference')
    distance_units = models.IntegerField(default=DistanceUnits.KILOMETRES,
                                         choices=DistanceUnits)
    # units for the settings below are yards or metres (dep. on distance_units)
    track_nearby_search_distance = models.FloatField(default=5)
    track_search_result_limit = models.IntegerField(default=100)
    place_nearby_search_distance = models.FloatField(default=20)
    place_search_result_limit = models.IntegerField(default=1000)

    @property
    def track_nearby_search_distance_metres(self):
        """ for use in Leaflet - distances are in metres """
        return DistanceUnits.convert(
            self.track_nearby_search_distance,
            self.distance_units, DistanceUnits.KILOMETRES) * 1000.0

    @property
    def place_nearby_search_distance_metres(self):
        return DistanceUnits.convert(
            self.place_nearby_search_distance,
            self.distance_units, DistanceUnits.KILOMETRES) * 1000.0


def parse_floats(arg_string, n_floats, error_msg):
    # log.debug("parse_floats(%s, ...)", arg_string)
    args = arg_string.split(',')
    if len(args) != n_floats:
        raise QueryStringError(error_msg)
    try:
        return [float(a) for a in args]
    except ValueError as e:
        raise QueryStringError(f'{error_msg}: {e.args[0]}')

