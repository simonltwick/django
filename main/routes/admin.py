
from routes.models import Marker, Track

from django.contrib.gis import admin

@admin.register(Marker)
class MarkerAdmin(admin.GeoModelAdmin):
    list_display = ("name", "location")

@admin.register(Track)
class TrackAdmin(admin.GeoModelAdmin):
    list_display = ("name", "pk")  #, "track"
    #3d multilinestrings not supported, so just displays textarea
