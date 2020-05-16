from django.db import models
from django.urls import reverse
from datetime import date
from django.contrib.auth.models import User

from enum import IntEnum


class Bike(models.Model):
    name = models.CharField(max_length=100, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='bikes')
    description = models.CharField(max_length=200)

    def get_absolute_url(self):
        return reverse('bike:bike', kwargs={'pk': self.id})

    def __str__(self):
        return self.name


class DistanceUnits(IntEnum):
    MILES = 10
    KILOMETRES = 20

    @classmethod
    def choices(cls):
        return [(key.value, key.name) for key in cls]


class DistanceMixin(models.Model):
    distance = models.DecimalField(max_digits=7, decimal_places=2,
                                   null=True, blank=True)
    distance_units = models.PositiveSmallIntegerField(
        choices=DistanceUnits.choices(), default=DistanceUnits.MILES)

    class Meta:
        abstract = True


class AscentUnits:
    METRES = 1
    FEET = 2
    CHOICES = ((METRES, 'm'), (FEET, 'Ft'))


class Preferences(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                primary_key=True, related_name='preferences')
    distance_units = models.PositiveSmallIntegerField(
        choices=DistanceUnits.choices(), default=DistanceUnits.MILES)
    ascent_units = models.PositiveSmallIntegerField(
        choices=AscentUnits.CHOICES, default=AscentUnits.METRES)

    class Meta:
        verbose_name_plural = 'preferences'

    def get_absolute_url(self):
        return reverse('preferences', kwargs={'pk': self.pk})

    def __str__(self):
        return f"Preferences for {self.user.username}"


class Ride(DistanceMixin):
    rider = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='rides')
    date = models.DateField(default=date.today)
    description = models.CharField(max_length=400, null=True, blank=True)
    ascent = models.DecimalField(max_digits=7, decimal_places=2,
                                 null=True, blank=True)
    ascent_units = models.PositiveSmallIntegerField(
        choices=AscentUnits.CHOICES, default=AscentUnits.METRES)
    bike = models.ForeignKey(Bike, on_delete=models.SET_NULL, null=True,
                             blank=True, related_name='rides')

    def __str__(self):
        return f"{self.date}: {self.description}"

    def get_absolute_url(self):
        return reverse('bike:ride', kwargs={'pk': self.id})


class Odometer(DistanceMixin):
    date = models.DateField(default=date.today)
    bike = models.ForeignKey(Bike, on_delete=models.CASCADE,
                             related_name='odometer_readings')
    comment = models.CharField(max_length=100)


class IntervalUnits:
    MILES = 101
    KILOMETRES = 102
    DAYS = 103
    YEARS = 104
    CHOICES = ((MILES, 'Miles'), (KILOMETRES, 'Kilometres'),
               (DAYS, 'Days'), (YEARS, 'Years'))


class ComponentType(models.Model):
    type = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='component_types')
    description = models.CharField(max_length=200)
    subtype_of = models.ForeignKey('ComponentType', related_name='subtypes',
                                   on_delete=models.PROTECT,
                                   blank=True, null=True)
    # fk maintenance schedule
    maintenance_interval = models.PositiveIntegerField(null=True, blank=True)
    maint_interval_units = models.PositiveSmallIntegerField(
        choices=IntervalUnits.CHOICES)

    def __str__(self):
        return f"{self.type}"


class Component(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='components')
    bike = models.ForeignKey(Bike, related_name='components', null=True,
                             blank=True, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    type = models.ForeignKey(ComponentType, on_delete=models.PROTECT)
    specification = models.CharField(max_length=200, null=True, blank=True)
    subcomponent_of = models.ForeignKey(
        'Component', related_name='components', on_delete=models.PROTECT,
        null=True, blank=True,
        help_text="leave blank if this is a direct subcomponent of a bike")
    # fk maintenance history
    # fk component history
    # fk subcomponent history
    date_acquired = models.DateField(default=date.today, null=True, blank=True)
    supplier = models.CharField(max_length=200, null=True, blank=True)
    notes = models.CharField(max_length=400, null=True, blank=True)

    def get_absolute_url(self):
        return reverse('bike:component', kwargs={'pk': self.id})

    def __str__(self):
        return f"{self.type}: {self.name} on {self.bike}"


class MaintenanceSchedule(models.Model):
    component_type = models.ForeignKey(ComponentType, on_delete=models.CASCADE)
    activity = models.CharField(max_length=100)
    reference_info = models.CharField(max_length=300)

# TODO: only require units if distance/ascent field is filled in
# TODO: remove maint. interval and descriptoin from component type
# TODO: "new component type" option on New Component form

class MaintenanceAction(DistanceMixin):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='maintenance_actions')
    component = models.ForeignKey(Component, on_delete=models.CASCADE)
    completed_date = models.DateField(default=date.today, null=True,
                                      blank=True)


class ComponentChange(DistanceMixin):
    date = models.DateField(default=date.today, null=True, blank=True)
    changed_component = models.ForeignKey(Component, on_delete=models.CASCADE,
                                          related_name='component_history')
    parent_component = models.ForeignKey(Component, on_delete=models.CASCADE,
                                         related_name='subcomponent_history')
    description = models.CharField(max_length=200)
