""" models for routes app """
import csv
import logging
import os.path
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING

from gpxpy.gpx import GPX, GPXTrack, GPXTrackSegment, GPXTrackPoint
from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.contrib.gis.geos import (
    Point, LineString, MultiLineString, Polygon)
from django.contrib.gis.measure import D  # synonym for Distance

from bike.models import DistanceUnits, Preferences

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class QueryStringError(ValueError):
    """ signifies invalid query string in a web request """
    pass

class PlaceType(models.Model):
    """ a type of place, eg. Pub, Cafe """
    # choices for place type icons.  icon name refers to an image in the
    # static folder.  Does not have to be svg but recommended.
    # Icons should be 16x16; in Inkscape document info choose Icon 16x16 size
    # mapping between placetype.name and placetype.icon is stored in the DB,
    # the ICON_CHOICES key is just a starting point and never used by the app
    # In future, it may be possible to choose colour dynamically through css
    ICON_CHOICES= {
        "Beer": "cup-straw-pink.svg",
        "Coffee": "cup-orange.svg",
        "Tea": "teapot-brown-web.svg",
        "Place": "geo-green.svg",
        "Camera": "camera-yellow.svg",
        "Bullseye": "bullseye-blue.svg"
        }
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=40, unique=True)
    icon = models.CharField(max_length=30, choices=ICON_CHOICES,
                            default="geo-green.svg")

    def __str__(self) -> str:
        return self.name


def get_default_place_type() -> PlaceType:
    """ used when removing blank=True/null=True from Place.type """
    return PlaceType.objects.get_or_create(name='Place')[0]


def get_default_place_type_pk() -> int:
    return get_default_place_type().pk


def get_default_user() -> int:
    """ WARNING this actually returns the user.pk, not the user.
    Don't rename - required for historic migrations """
    return User.objects.get(username='simon').pk


class Tag(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=20, unique=True, db_collation="NOCASE")

    def __str__(self):
        return self.name


class Place(models.Model):
    """ a named point on the map """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=40)
    location = models.PointField()
    type = models.ForeignKey(PlaceType, on_delete=models.PROTECT,
                             default=get_default_place_type_pk)
    tag = models.ManyToManyField(Tag, related_name="place")

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
        csv_reader = csv.DictReader(
            csv_contents.splitlines(),
            fieldnames=["name", "latitude", "longitude", "type"])
        header = next(csv_reader)  # ignore header row
        log.debug("ignoring header row values: %s", header)
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


class Track(models.Model):
    """ a (gpx) track """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(unique=True, max_length=40)
    track = models.MultiLineStringField(dim=3)
    # , srid=4326 is the default)
    creator = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    moving_time = models.FloatField(blank=True, null=True,
                                      help_text="Moving time in seconds")
    moving_distance = models.FloatField(blank=True, null=True,
                                          help_text="Moving distance in metres")
    ascent = models.FloatField(blank=True, null=True,
                                 help_text="Ascent in metres")
    tag = models.ManyToManyField(Tag, related_name="track")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=['user', 'name'], name='unique_name'),
        ]

    @property
    def ascent_user_units(self) -> Optional[float]:
        """ return the ascent in units of the user's preference """
        if self.ascent is None:
            return None
        conv_factor = Preferences.conversion_factor_ascent(self.user)
        return self.ascent * conv_factor

    @property
    def moving_distance_user_units(self) -> Optional[float]:
        """return moving distance in units of the user's preference """
        if self.moving_distance is None:
            return None
        conv_factor = Preferences.conversion_factor_distance(self.user)
        return self.moving_distance * conv_factor

    @classmethod
    def new_from_gpx(cls, gpx: "GPX", fname: str, user: User, save: bool
                     ) -> List["Track"]:
        """ convert a GPX object to a track (or possibly, several tracks)
        but DOES NOT SAVE the tracks 
        If Save is false, don't check for duplicate filenames."""
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
            if hasattr(gpx, "creator"):
                new_track.creator = gpx.creator

            # check filename is unique
            fname = os.path.basename(fname)  # remove dirname if present
            if track.name:
                new_track.name = track.name
            elif track_num == 0:
                new_track.name = fname
            else:
                fname_base, ext = os.path.splitext(fname)
                new_track.name = f"{fname_base}#{track_num}{ext}"
            if save and cls.objects.filter(name=new_track.name, user=user
                                           ).exists():
                raise FileExistsError(new_track.name)

            # add track segments
            segments = []
            for segment in track.segments:
                points = []
                for point in segment.points:

                    # if elevation is None, replace with 0.0
                    point_in_segment = Point(
                        point.longitude, point.latitude, point.elevation or 0.0)
                    points.append(point_in_segment.coords)

                if len(points) > 1:
                    segments.append(LineString(points))

            if segments:
                new_track.track = MultiLineString(segments)
                # log.debug("track %s has %d segments",
                #           new_track.name, len(segments))
                # new_track.gpx_file = file_instance
                new_track.add_gpx_stats(track)
                tracks.append(new_track)

        return tracks

    def as_gpx(self, name: Optional[str]=None) -> "GPX":
        """ return the track's "track" field as a gpxpy.GPX object.
        The gpx file will have no timestamps, as these are not stored, but
        it will have elevations if these are present. """
        gpx = GPX()
        gpx.name = name or self.name
        if self.creator:
            gpx.creator = self.creator
        if self.description:
            gpx.description = self.description
        gpx_track = GPXTrack()
        gpx.tracks.append(gpx_track)

        for linestring in self.track:
            gpx_segment = GPXTrackSegment()
            gpx_track.segments.append(gpx_segment)

            for point in linestring:
                gpx_point = GPXTrackPoint(
                    latitude=point[1], longitude=point[0],
                    elevation=point[2] or None)
                gpx_segment.points.append(gpx_point)

        return gpx

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

    def add_gpx_stats(self, gpx_track: "GPXTrack"):
        """ add stats calculated from the gpx file """
        time_bounds = gpx_track.get_time_bounds()
        self.start_time = time_bounds.start_time
        self.end_time = time_bounds.end_time
        moving_data = gpx_track.get_moving_data()
        self.moving_time = moving_data.moving_time
        self.moving_distance =  moving_data.moving_distance
        self.ascent = gpx_track.get_uphill_downhill().uphill


class Boundary(models.Model):
    """ a perimeter for searching or clipping tracks, e.g. a county """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=40, db_collation="NOCASE")
    name = models.CharField(max_length=40, db_collation="NOCASE")
    polygon = models.PolygonField(dim=2)

    class Meta:
        verbose_name_plural="Boundaries"
        constraints = [models.UniqueConstraint(
            fields=['user', 'category', 'name'], name='unique_boundary'),
        ]

    def __str__(self):
        return f"{self.category}:{self.name}"

    @classmethod
    def polygon_from_gpx(cls, gpx: "GPX") -> Polygon:
        """ convert a GPX object to a polygon.
        Points from all track segments are simply concatenated. """

        if len(gpx.tracks) != 1:
            raise ValueError("Boundary GPX must contain 1 track, not "
                             f"{len(gpx.tracks)}")

        track = gpx.tracks[0]
        points = []
        for segment in track.segments:
            for point in segment.points:
                point = Point(point.longitude, point.latitude)
                points.append(point.coords)

        if len(points) <= 3:
            raise ValueError("Boundary GPX must contain > 2 points.")

        if points[0] != points[-1]:
            points.append(points[0])  # close the LinearRing
        polygon = Polygon(points)
        return polygon

    @classmethod
    def get_category_choices(cls) -> List[Tuple[int, str]]:
        """ return the distinct values of boundary categories, as 2-tuple.
        The category name is also the key ([0] as well as the value [1],
        so that the name is returned in form POST data """
        categories = cls.objects.order_by().values_list('category').distinct()
        category_list = [(cat[0], cat[0]) for cat in categories]
        # log.debug("Boundary.get_category_choices -> %s", category_list)
        return category_list
