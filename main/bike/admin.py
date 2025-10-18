from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (
    Component, ComponentType, Ride, Odometer, Preferences,
    Bike, MaintenanceType, MaintenanceAction, MaintenanceActionHistory
    )

admin.site.register(Component)
admin.site.register(ComponentType)
# admin.site.register(Ride)
admin.site.register(Bike)
admin.site.register(Odometer)
# admin.site.register(Preferences)
# admin.site.register(MaintenanceAction)
# admin.site.register(MaintenanceActionHistory)


@admin.register(MaintenanceType)
class MaintActionTypeAdmin(admin.ModelAdmin):
    readonly_fields=('component_type',)
    fields=('component_type', 'description', 'reference_info', 
            'recurring', 
            (
             'maintenance_interval_distance',
             # 'user_preferences_distance_units',
             ),
            'maint_interval_days', )


@admin.register(MaintenanceAction)
class MaintActionAdmin(admin.ModelAdmin):
    readonly_fields=('bike', 'component', 'maint_type')
    fields=('bike', 'component', 'maint_type', 'description', 'completed', 
            'due_date', 'due_distance',
            'recurring', 
            # (
                'maintenance_interval_distance',
             # 'user_preferences_distance_units',),
            'maint_interval_days', )


@admin.register(MaintenanceActionHistory)
class MaintActionHistoryAdmin(admin.ModelAdmin):
    readonly_fields=('bike', 'component', 'action',)
    fields=('bike', 'component', 'action',
            'completed_date', 'distance', 'distance_units')


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    readonly_fields=('rider',)
    date_hierarchy='date'


# define preferences as an inline form within User Admin
class PreferencesInline(admin.StackedInline):
    model = Preferences
    can_delete = False
    verbose_name_plural = "preferences"


# Define a new User admin
class UserAdmin(BaseUserAdmin):
    inlines = [PreferencesInline]


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
