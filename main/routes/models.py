from django.contrib.gis.db import models


class Marker(models.Model):
    """ a named point on the map """
    name = models.CharField(max_length=40)
    location = models.PointField()

    def __str__(self):
        return str(self.name)
