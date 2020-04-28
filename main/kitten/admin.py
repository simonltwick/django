from django.contrib import admin
from django.contrib.auth.models import User
from .models import Network, Team, LineTemplate, GameTemplate, PlaceTemplate, \
    Game, Line, LineLocation, Station, Train


admin.site.register(GameTemplate)
admin.site.register(Team)
admin.site.register(LineLocation)
admin.site.register(Station)
admin.site.register(Train)


"""class UserInline(admin.TabularInline):
    model = User  # causes problems, no FK for Teams on User


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    inlines = [UserInline]"""


class LineTemplateInline(admin.TabularInline):
    model = LineTemplate


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    inlines = [LineTemplateInline]


class PlaceTemplateInline(admin.TabularInline):
    model = PlaceTemplate
    ordering = ['position']


@admin.register(LineTemplate)
class LineTemplateAdmin(admin.ModelAdmin):
    inlines = [PlaceTemplateInline]


class LineInline(admin.TabularInline):
    model = Line


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    inlines = [LineInline]


class LineLocationInline(admin.TabularInline):
    model = LineLocation
    ordering = ['position']


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    inlines = [LineLocationInline]
    