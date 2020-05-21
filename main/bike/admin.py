from django.contrib import admin

from .models import (
    Component, ComponentType, Ride, Odometer, Preferences,
    Bike, MaintenanceAction
    )

admin.site.register(Component)
admin.site.register(ComponentType)
admin.site.register(Ride)
admin.site.register(Bike)
admin.site.register(Odometer)
admin.site.register(Preferences)
admin.site.register(MaintenanceAction)
