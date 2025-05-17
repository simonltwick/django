from django.contrib.gis.db import models


class Marker(models.Model):
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
    track = models.MultiLineStringField(dim=3)
    # , srid=4326 is the default)
