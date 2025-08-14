
from routes.models import Place, Track, PlaceType, Tag

from django.contrib.gis import admin

# if not hasattr(admin, 'GISModelAdmin'):
#     assert hasattr(admin, 'GeoModelAdmin')
#     # for earlier django release support (GISModelAdmin in 5.2)
#     admin.GISModelAdmin = admin.GeoModelAdmin


@admin.register(Place)
class PlaceAdmin(admin.GISModelAdmin):
    readonly_fields=('user',)
    list_display = ('user', "name", "type")


@admin.register(Track)
class TrackAdmin(admin.GISModelAdmin):
    date_hierarchy='start_time'
    readonly_fields=('user', "moving_distance", "ascent")
    list_display=("name", "pk")  #, "track"
    fields=('user', 'name', "start_time", "moving_distance", "ascent", "tag")
    #3d multilinestrings not supported, so track display just displays textarea
    # with loads of points


@admin.register(PlaceType)
class PlaceTypeAdmin(admin.ModelAdmin):
    readonly_fields=('user',)
    list_display=('name', 'icon')
    fields=('user', 'name', 'icon')


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    readonly_fields=('user',)
    fields=('user', 'name',)
