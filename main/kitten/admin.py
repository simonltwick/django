from django.contrib import admin
# from django.contrib.auth.models import User
from .models import (
    Network, Team, LineTemplate, GameTemplate, PlaceTemplate,
    Game, Line, LineLocation, Station, Train, Incident, Impact, IncidentType,
    Response, TeamInvitation, TeamGameStatus,
    )


admin.site.register(Team)


admin.site.register(TeamInvitation)


"""class UserInline(admin.TabularInline):
    model = User  # causes problems, no FK for Teams on User


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    inlines = [UserInline]"""


@admin.register(Impact)
class ImpactAdmin(admin.ModelAdmin):
    model = Impact
    list_display = ('name', 'network', 'type')
    list_filter = ('network', 'type')
    ordering = ('network', 'type')


@admin.register(IncidentType)
class IncidentTypeAdmin(admin.ModelAdmin):
    model = IncidentType
    list_display = ('name', 'network', 'type')
    list_filter = ('network', 'type')
    ordering = ('network', 'type')


@admin.register(GameTemplate)
class GameTemplateAdmin(admin.ModelAdmin):
    model = GameTemplate
    list_display = ('level', 'network')
    ordering = ('network',)
    list_filter = ('network',)
    fields = ('network', 'level', 'incident_rate')
    readonly_fields = ('network',)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'line', 'location', 'start_time')


@admin.register(Response)
class ResponseAdmin(admin.ModelAdmin):
    list_display = ('name', 'network')
    fields = ('network', 'name', 'developer_description',
              'effectiveness_percent', 'impacts', 'time_to_fix')
    readonly_fields = ('network',)
    list_filter = ('network',)
    ordering = ('network', 'name')


class LineTemplateInline(admin.TabularInline):
    model = LineTemplate


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    inlines = [LineTemplateInline]
    fieldsets = [
        (None, {'fields': ['name', 'description', 'owner']}),
        ('Traffic', {'fields': ['night_traffic', 'peak_morning_traffic',
                                'peak_evening_traffic']}),
        ('Timings', {'fields': ['day_start_time', 'day_end_time',
                                'peak_morning_end', 'peak_evening_start']})
        ]


@admin.register(PlaceTemplate)
class PlaceTemplateAdmin(admin.ModelAdmin):
    model = PlaceTemplate
    fieldsets = [
        (None, {'fields': ['name', 'line', 'position', 'type']}),
        ('Operational', {'fields': ['transit_delay',
                                    'turnaround_percent_direction1',
                                    'turnaround_percent_direction2']}),
        ('Stations only', {'fields': ['passenger_traffic_dir1',
                                      'passenger_traffic_dir2']})
        ]
    readonly_fields = ('line',)
    list_display = ('name', 'line', 'position')
    list_filter = ('line',)
    ordering = ('line', 'position', 'name', )


class PlaceTemplateInline(admin.TabularInline):
    model = PlaceTemplate
    ordering = ['position']


@admin.register(LineTemplate)
class LineTemplateAdmin(admin.ModelAdmin):
    inlines = [PlaceTemplateInline]
    fieldsets = [
        (None, {'fields': ['network', 'name', 'direction1', 'direction2']}),
        ('Trains', {'fields': ['trains_dir1', 'trains_dir2',
                               'train_interval', 'train_type']})
        ]


class LineInline(admin.TabularInline):
    model = Line


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['name', 'play_status',
                           'current_time',  # 'delay'
                           ]}),
        ('Setup', {'fields': ['level', 'network_name',
                              'incident_rate', 'incident_types']}),
        ('Timings', {'fields': ['tick_interval',
                                'game_round_duration',
                                'day_start_time', 'day_end_time']}),
        # started, last_played are non-editable
        # teams M2M has a relationship table, can't be specified
        ]
    inlines = [LineInline]


@admin.register(TeamGameStatus)
class TeamGameStatusAdmin(admin.ModelAdmin):
    model = TeamGameStatus
    list_display = ('game', 'team', 'play_status_title')
    list_display_links = ('play_status_title',)
    ordering = ('game', 'team')
    list_filter = ('game', 'team')


class TrainInLine(admin.TabularInline):
    model = Train
    show_change_link = True


@admin.register(LineLocation)
class LineLocationAdmin(admin.ModelAdmin):
    model = LineLocation
    fieldsets = [
        (None, {'fields': ['line', 'name', 'type']}),
        ('Position', {'fields': [
            'position', 'direction', 'direction_is_forward',
            'is_start_of_line', 'is_end_of_line']}),
        ('Operational', {'fields': ['transit_delay', 'turnaround_percent',
                                    'last_train_time']})
        ]
    readonly_fields = ('line', 'position', 'direction', 'direction_is_forward',
                       'is_start_of_line', 'is_end_of_line')
    inlines = (TrainInLine,)
    list_display = ('name', 'line', 'direction', 'position')
    list_filter = ('line',)
    list_select_related = ('line',)
    ordering = ('line', 'direction', 'position')


class LineLocationInline(admin.TabularInline):
    model = LineLocation
    ordering = ['position']


class StationInline(admin.TabularInline):
    model = Station
    ordering = ['name']


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    model = Line
    fieldsets = [
        (None, {'fields': ['game', 'name', 'operator']}),
        ('Trains', {'fields': ['trains_dir1', 'trains_dir2',
                               'train_interval', 'train_type']}),
        ('Operational', {'fields': ['total_arrivals', 'on_time_arrivals',
                                    'total_delay']})
        ]
    inlines = [LineLocationInline, StationInline]


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    model = Station
    fields = ('line', 'name')
    readonly_fields = ('line',)
    list_display = ('name', 'line')
    ordering = ('line', 'name')
    list_filter = ('line',)
