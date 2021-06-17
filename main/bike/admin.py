from django.contrib import admin

from .models import (
    Component, ComponentType, Ride, Odometer, Preferences,
    Bike, MaintenanceType, MaintenanceAction, MaintenanceActionHistory
    )

admin.site.register(Component)
admin.site.register(ComponentType)
admin.site.register(Ride)
admin.site.register(Bike)
admin.site.register(Odometer)
admin.site.register(Preferences)
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
