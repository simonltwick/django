from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from collections import defaultdict
import datetime as dt
from enum import IntEnum
import logging
from typing import Optional

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class Bike(models.Model):
    name = models.CharField(max_length=100, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='bikes')
    description = models.CharField(max_length=200)
    current_odo = models.FloatField(
        default=0, help_text="calculated current odometer, in distance units"
        " from preferences.")

    def get_absolute_url(self):
        return reverse('bike:bike', kwargs={'pk': self.id})

    def __str__(self):
        return self.name

    def update_current_odo(self):
        last_odo = Odometer.previous_odo(self.id, timezone.now())
        date_after = last_odo.date if last_odo else None
        log.info("update_current_odo: date_after=%s", date_after)
        distance_since = Ride.distance_after(date_after, self)
        log.info("update_current_odo: distance_since=%s", distance_since)
        distances = [(entry['distance'], entry['distance_units'])
                     for entry in distance_since]
        log.info("update_current_odo: distance_since(2)=%s", distance_since)
        if last_odo:
            distances.append({'distance': last_odo.distance,
                              'distance_units': last_odo.distance_units})
        log.info("update_current_odo: distance_since(3)=%s", distance_since)
        target_units = self.owner.preferences.distance_units
        self.current_odo = DistanceUnits.sum(distances, target_units)
        log.info("update_current_odo: current_odo=%s", self.current_odo)


class DistanceUnits(IntEnum):
    MILES = 10
    KILOMETRES = 20

    @classmethod
    def choices(cls):
        return [(key.value, key.name.lower()) for key in cls]

    @classmethod
    def sum(cls, distances_list, target_units):
        """ sum a list of distances (with units), and convert to target_units
        distance_list is a list of dicts [{'distance': d, 'distance_units': x}]
        where x is a DistanceUnits instance
        """
        log.info("DistanceUnits.sum(%s, target_units=%s", distances_list,
                 target_units)
        distances = defaultdict(lambda: 0)
        for item in distances_list:
            distances[item['distance_units']] += item['distance']
        # log.info("distances=%s", list(distances.items()))
        total_distance = sum(cls.convert(distance, from_units=units,
                                         to_units=target_units)
                             for units, distance in distances.items())
        return total_distance

    @classmethod
    def convert(cls, distance, from_units, to_units):
        if from_units == to_units:
            return distance
        factors = {DistanceUnits.MILES: {DistanceUnits.MILES: 1,
                                         DistanceUnits.KILOMETRES: 1.60934},
                   DistanceUnits.KILOMETRES: {DistanceUnits.MILES: 0.621371,
                                              DistanceUnits.KILOMETRES: 1}}
        # log.info("convert %s from %s to %s", distance, from_units, to_units)
        factor = factors[from_units][to_units]
        return distance * factor


class DistanceMixin(models.Model):
    distance = models.FloatField(null=True, blank=True)
    distance_units = models.PositiveSmallIntegerField(
        choices=DistanceUnits.choices(), default=DistanceUnits.MILES)

    class Meta:
        abstract = True

    @property
    def distance_units_display(self):
        return self.get_distance_units_display().lower()


class DistanceRequiredMixin(DistanceMixin):
    distance = models.FloatField()

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
        return reverse('bike:preferences', kwargs={'pk': self.pk})

    def __str__(self):
        return f"Preferences for {self.user.username}"


class Ride(DistanceMixin):
    rider = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='rides')
    date = models.DateTimeField(default=timezone.now)
    is_adjustment = models.BooleanField(
        default=False, help_text="If true, signifies this is not a real ride"
        " but a ride distance adjustment between odometer readings.")
    description = models.CharField(max_length=400, null=True, blank=True)
    ascent = models.FloatField(null=True, blank=True)
    ascent_units = models.PositiveSmallIntegerField(
        choices=AscentUnits.CHOICES, default=AscentUnits.METRES)
    bike = models.ForeignKey(Bike, on_delete=models.SET_NULL, null=True,
                             blank=True, related_name='rides')

    class Meta:
        unique_together = ('rider', 'date', 'bike', 'description')

    def __str__(self):
        return f"{self.date.date()}: {self.description}"

    def get_absolute_url(self):
        return reverse('bike:ride', kwargs={'pk': self.id})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # allow updating of odometer adjustment ride, if any
        Odometer.ride_updated(self)

    @property
    def ascent_units_display(self):
        return self.get_ascent_units_display()

    def clean(self):
        validation_errors = {}
        if self.distance and not self.distance_units:
            validation_errors['distance_units'] = "You must specify units."
        if self.ascent and not self.ascent_units:
            validation_errors['ascent_units'] = "You must specify units."
        if validation_errors:
            raise ValidationError(validation_errors)

    @classmethod
    def distance_after(cls, when: Optional[dt.datetime], bike=None):
        """ return ride distance after a datetime, in mixed distance_units, on
        bike=bike if given, else for all bikes
        Result is a list of dicts with bike_id, distance_units, distance """
        log.info("Ride.distance_after(when=%s, bike=%s", when, bike)
        query = Ride.objects
        log.info("distance_after(1). query=%s", query)
        if bike is not None:
            query = query.filter(bike=bike)
            log.info("distance_after(2). query=%s", query)
        if when is not None:
            query = query.filter(date__gt=when)
            log.info("distance_after(3). query=%s", query)
        return (query
                .order_by('bike_id', 'distance_units')
                .values('bike_id', 'distance_units')
                .annotate(distance=Sum('distance'))
                )

    @classmethod
    def mileage_by_month(cls, user, year, bike=None):
        """ return total mileage by month, for a given year [and bike]
        Also return the detailed data, grouped by month, if detail=True """
        rides = cls.objects.filter(date__year=year, rider=user)
        if bike is not None:
            rides = rides.filter(bike=bike)

        rides = rides.order_by('date', 'distance_units').all()
        monthly_mileage = defaultdict(lambda: defaultdict(int))

        for ride in rides:
            if ride.distance is not None:
                monthly_mileage[ride.date.month][
                    ride.distance_units_display] += ride.distance

        # return a dict, not defaultdict: templates won't iterate over
        #     defaultdict
        monthly_mileage = {month: {k: v for k, v in value.items()}
                           for month, value in monthly_mileage.items()}
        return monthly_mileage


class Odometer(DistanceRequiredMixin):
    rider = models.ForeignKey(User, on_delete=models.CASCADE)
    initial = models.BooleanField(
        default=False, help_text="Only tick this for the initial value of new "
        "odometer or after resetting the odometer reading.")
    comment = models.CharField(max_length=100, null=True, blank=True)
    bike = models.ForeignKey(Bike, on_delete=models.CASCADE,
                             related_name='odometer_readings')
    date = models.DateTimeField(default=timezone.now)
    adjustment_ride = models.OneToOneField(Ride, on_delete=models.SET_NULL,
                                           null=True, blank=True)

    class Meta:
        verbose_name = 'Odometer reading'

    def __str__(self):
        reset = "reset to " if self.initial else ""
        return (f"{self.bike} odometer {reset}"
                f"{self.distance} {self.distance_units_display}"
                f" on {self.date.date()}")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_adjustment_rides()

    @classmethod
    def ride_updated(cls, ride):
        """ called when a ride is saved, to allow adjustment of following
        odometer adjustment ride, if any.  Most times there will be none """
        next_odo = cls.next_odo(ride.bike_id, ride.date)
        if next_odo is None:
            return
        prev_odo = cls.previous_odo(ride.bike_id, ride.date)
        if prev_odo is None:
            return
        cls.update_adjustment_ride(next_odo, prev_odo)

    def update_adjustment_rides(self):
        """ create or update adjustment rides between this odo reading and
        previous/next odo readings, so that the rides mileage totals to the
        same as the difference between the odo readings.
        Mileage before a "reset" odo reading is not adjusted """
        if self.initial:  # after resetting odo: no adjustment ride
            if self.adjustment_ride:
                self.adjustment_ride.delete()
                self.refresh_from_db()
        else:
            prev_odo = self.previous_odo(self.bike_id, self.date)
            if prev_odo:
                self.update_adjustment_ride(self, prev_odo)

        # update following adjustment ride, if necessary
        next_odo = self.next_odo(self.bike_id, self.date)
        if next_odo and not next_odo.initial:
            self.update_adjustment_ride(next_odo, self)

    @classmethod
    def update_adjustment_ride(cls, current_odo, prev_odo):
        """ create or update the adjustment ride for current_odo """
        rides_between = Ride.objects.filter(bike_id=current_odo.bike_id,
                                            date__gt=prev_odo.date,
                                            date__lte=current_odo.date,
                                            is_adjustment=False)
        distances = list(rides_between.values('distance_units')
                         .annotate(distance=Sum('distance')))
        # log.info("update_adjustment_ride: ride distances=%s", distances)
        distances.append({'distance_units': prev_odo.distance_units,
                          'distance': prev_odo.distance})
        distances.append({'distance_units': current_odo.distance_units,
                          'distance': -current_odo.distance})
        # distances is now prev_odo + rides - current_odo, maybe in mixed units
        # which is the NEGATIVE of what we need for the adjustment ride
        total_distance = -DistanceUnits.sum(
            distances, target_units=current_odo.distance_units)
        # log.info("update_adjustment_ride: total_distance=%s", total_distance)
        adj_ride = current_odo.adjustment_ride
        if adj_ride is None:
            adj_ride = Ride(
                bike=current_odo.bike, rider=current_odo.rider,
                is_adjustment=True)
        adj_ride.date = current_odo.date
        adj_ride.distance = total_distance
        adj_ride.distance_units = current_odo.distance_units
        adj_ride.description = "Adjustment for odometer reading %0.1f %s" % (
            current_odo.distance, prev_odo.distance_units_display)
        adj_ride.save()
        # log.info("adj_ride=%s, distance %s", adj_ride, adj_ride.distance)
        if current_odo.adjustment_ride is None:
            current_odo.adjustment_ride = adj_ride
            # log.info("saving current_odo=%s", current_odo)
            # log.info("current_odo.adjustment_ride=%s",
            #          current_odo.adjustment_ride)
            current_odo.save()

    @classmethod
    def previous_odo(cls, bike_id, date):
        """ return the previous odometer reading for this bike, or None """
        return (Odometer.objects
                .filter(bike=bike_id, date__lt=date)
                .order_by('-date')
                .first())

    @classmethod
    def next_odo(cls, bike_id, date):
        """ return the next odometer reading for this bike, or None """
        return (Odometer.objects
                .filter(bike=bike_id, date__gt=date)
                .order_by('date')
                .first())


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
    description = models.CharField(max_length=200, null=True, blank=True)
    subtype_of = models.ForeignKey('ComponentType', related_name='subtypes',
                                   on_delete=models.PROTECT,
                                   blank=True, null=True)
    maintenance_type = models.ManyToManyField('MaintenanceType')

    def __str__(self):
        return str(self.type)

    def get_absolute_url(self):
        return reverse('bike:component_type', kwargs={'pk': self.id})

    def clean(self):
        if self.maintenance_interval and not self.maint_interval_units:
            raise ValidationError("Maintenance interval units not specified.")


class Component(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='components')
    bike = models.ForeignKey(
        Bike, related_name='components', null=True,
        blank=True, on_delete=models.SET_NULL,
        help_text="Leave blank if this is a subcomponent of another part of a "
        "bike.")
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
    date_acquired = models.DateField(default=dt.date.today, null=True,
                                     blank=True)
    supplier = models.CharField(max_length=200, null=True, blank=True)
    notes = models.CharField(max_length=400, null=True, blank=True)

    def __str__(self):
        return f"{self.type}: {self.name} on {self.bike}"

    def get_absolute_url(self):
        return reverse('bike:component', kwargs={'pk': self.id})


class MaintenanceType(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='maintenance_types')
    component_type = models.ForeignKey(ComponentType, on_delete=models.CASCADE)
    activity = models.CharField(max_length=200)
    reference_info = models.CharField(max_length=300, blank=True, null=True)
    recurring = models.BooleanField(default=False)
    maintenance_interval = models.PositiveIntegerField(null=True, blank=True)
    maint_interval_units = models.PositiveSmallIntegerField(
        choices=IntervalUnits.CHOICES, null=True, blank=True)

    class Meta:
        unique_together = ['component_type', 'activity']

    def __str__(self):
        return f'{self.activity} - {self.component_type}'

    def get_absolute_url(self):
        return reverse('bike:maint_type', kwargs={'pk': self.id})


class MaintenanceAction(DistanceMixin):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='maintenance_actions')
    bike = models.ForeignKey(Bike, related_name="maint_actions",
                             on_delete=models.SET_NULL,
                             null=True, blank=True)
    component = models.ForeignKey(
        Component, on_delete=models.CASCADE, null=True, blank=True,
        help_text='you only need to specify one of bike or component.')
    maint_type = models.ForeignKey(MaintenanceType, on_delete=models.SET_NULL,
                                   blank=True, null=True)
    description = models.CharField(max_length=100, blank=True, null=True)
    due_date = models.DateField(null=True, blank=True,
                                default=dt.date.today)
    completed = models.BooleanField(default=False)
    completed_date = models.DateField(null=True, blank=True)
    completed_distance = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'bike', 'component', 'maint_type',
                           'description', 'due_date', 'distance')

    def __str__(self):
        return f"{self.description or self.maint_type}"

    def get_absolute_url(self):
        return reverse('bike:maint', kwargs={'pk': self.id})


class ComponentChange(DistanceMixin):
    date = models.DateField(default=dt.date.today, null=True, blank=True)
    changed_component = models.ForeignKey(Component, on_delete=models.CASCADE,
                                          related_name='component_history')
    parent_component = models.ForeignKey(Component, on_delete=models.CASCADE,
                                         related_name='subcomponent_history')
    description = models.CharField(max_length=200)
