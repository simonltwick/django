
from routes.models import Marker

from django.contrib.gis import admin

@admin.register(Marker)
class RoutesAdmin(admin.GeoModelAdmin):
    list_display = ("name", "location")