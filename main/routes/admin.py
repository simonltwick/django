
from routes.models import Place, Track, PlaceType, Tag

from django.contrib.gis import admin

# if not hasattr(admin, 'GISModelAdmin'):
#     assert hasattr(admin, 'GeoModelAdmin')
#     # for earlier django release support (GISModelAdmin in 5.2)
#     admin.GISModelAdmin = admin.GeoModelAdmin


@admin.register(Place)
class PlaceAdmin(admin.GISModelAdmin):
    readonly_fields=('user',)
    list_display = ("name", "location")


@admin.register(Track)
class TrackAdmin(admin.GISModelAdmin):
    readonly_fields=('user',)
    list_display = ("name", "pk")  #, "track"
    #3d multilinestrings not supported, so just displays textarea


@admin.register(PlaceType)
class PlaceTypeAdmin(admin.ModelAdmin):
    readonly_fields=('user',)
    fields=('name', 'icon')


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    readonly_fields=('user',)
    fields=('name',)
