from django.contrib import admin
from django.contrib.auth.models import User
from .models import Network, Team, Game, Line, GameLineParameters, \
    LineLocation, LineTemplate, GameTemplate, PlaceTemplate


admin.site.register(GameTemplate)
# admin.site.register(GameLineParameters)
# admin.site.register(LineLocation)

"""
class UserInline(admin.TabularInline):
    model = User


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    inlines = [UserInline]
"""


class LineTemplateInline(admin.TabularInline):
    model = LineTemplate


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    inlines = [LineTemplateInline]


class PlaceTemplateInline(admin.TabularInline):
    model = PlaceTemplate


@admin.register(LineTemplate)
class LineTemplateAdmin(admin.ModelAdmin):
    inlines = [PlaceTemplateInline]
