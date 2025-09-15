#!/usr/bin/env python3

from collections import defaultdict
import datetime as dt
from functools import cache
import logging
from typing import Optional, List, Dict, Union

# from django import contrib
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum, F, Q, ExpressionWrapper, fields
from django.db.models.functions import Now, TruncDate
from django.urls import reverse
from django.utils import timezone

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

""" Migration to common stored distance unit:
Pilot using Ride.Ascent.  Steps:
      Standardise on Preferences.distance_units and .ascent_units: remove them
      from ride, odometer & ensure forms display distance units from prefs.
      (Done)
      The field in the Db has to be the same as what's in the form, so we cannot
      simply have the DB field in metres and the form field in a different unit.
      Try to define simpler ways of presenting distances with units
      - widget class for distance, with Widget.__init__ copying the instance or
        the distance_units_label (example:
        https://stackoverflow.com/questions/1226590/django-how-can-i-access-the-form-field-from-inside-a-custom-widget/2135739#2135739
        )
     Remove complicated summing & conversion of ride totals in different units
     from the view & the form, simply sum in regular units.
     Test that these work.
     Merge the Routes preferences properties (in a separate form tab) into
     the same Preferences model.   Distances have to be in a separate form tab
     from the distance units, in case units are changed.   And preferences
     distances will have to be auto-converted if distance units are changed,
     and the form redisplayed.
     Optimise DB calls to get preferences & pass to templates
"""


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

    """ handling of current_odo and adjustment rides:
        current_odo is intended to keep track of the calculated bike odometer,
        based on last odo reading plus any subsequent rides.  It's updated by
        Odometer.save, and by Ride.save, through update_current_odo which
        recalculates based on last odometer reading plus subsequent rides. """
    def update_current_odo(self):
        last_odo = Odometer.previous_odo(self.id, timezone.now())
        date_after = last_odo.date if last_odo else None
        distance_since = Ride.distance_after(date_after, self)
        distances = list(distance_since)  # also contains bike_id, but ignored
        if last_odo:
            distances.append({'distance': last_odo.distance,
                              'distance_units': last_odo.distance_units})
        target_units = self.owner.preferences.distance_units
        self.current_odo = DistanceUnits.sum(distances, target_units)
        # log.info("update_current_odo: new value=%s", self.current_odo)

    @classmethod
    def update_distance_units(cls, user, factor):
        """ bulk update current_odo values multiplying by conversion factor """
        log.warning("Updating %s.current_odo values * %s",
                    cls.__name__, factor)
        bikes = cls.objects.filter(owner=user, current_odo__isnull=False)
        bikes.update(current_odo=F('current_odo') * factor)

    @property
    def distance_units_label(self) -> str:
        return DistanceUnits(self.owner.preferences.distance_units).label


class DistanceUnits(models.IntegerChoices):
    MILES = 10
    KILOMETRES = 20

    # @classmethod
    # def Xchoices(cls):
    #     return [(key.value, key.name.lower()) for key in cls]

    @classmethod
    def sum(cls, distances_list, target_units):
        """ sum a list of distances (with units), and convert to target_units
        distance_list is a list of dicts [{'distance': d, 'distance_units': x}]
        where x is a DistanceUnits instance
        """
        # log.info("DistanceUnits.sum(%s, target_units=%s", distances_list,
        #          target_units)
        distances = defaultdict(lambda: 0)
        for item in distances_list:
            distances[item['distance_units']] += item['distance']
        # log.info("distances=%s", list(distances.items()))
        total_distance = sum(cls.convert(distance, from_units=units,
                                         to_units=target_units)
                             for units, distance in distances.items())
        return total_distance

    @classmethod
    def conversion_factor(cls, from_units, to_units):
        factors = {DistanceUnits.MILES: {DistanceUnits.MILES: 1,
                                         DistanceUnits.KILOMETRES: 1.60934},
                   DistanceUnits.KILOMETRES: {DistanceUnits.MILES: 0.621371,
                                              DistanceUnits.KILOMETRES: 1}}
        return factors[from_units][to_units]

    @classmethod
    def convert(cls, distance, from_units, to_units):
        if from_units == to_units:
            return distance
        # log.info("convert %s from %s to %s", distance, from_units, to_units)
        factor = cls.conversion_factor(from_units, to_units)
        return distance * factor

    @classmethod
    def display_name(cls, value: int) -> str:
        return cls(value).name.lower()

# TODO: remove DistanceMixin.distance_units_display
class DistanceMixin(models.Model):
    # distance = models.FloatField(null=True, blank=True)
    # distance_units = models.PositiveSmallIntegerField(
    #     choices=DistanceUnits, default=DistanceUnits.MILES)

    class Meta:
        abstract = True

    @property
    def distance_units_display(self):
        return self.get_distance_units_display().lower()

    def distance_units_label(self) -> str:
        return DistanceUnits(self.user.preferences.distance_units).label


class DistanceRequiredMixin(DistanceMixin):
    distance = models.FloatField()

    class Meta:
        abstract = True


class AscentUnits0:
    METRES = 1
    FEET = 2
    CHOICES = ((METRES, 'm'), (FEET, 'Ft'))

    @classmethod
    def conversion_factor(cls, from_units, to_units):
        factors = {AscentUnits0.METRES: {AscentUnits0.METRES: 1.0,
                                        AscentUnits0.FEET: 3.28084},
                   AscentUnits0.FEET: {AscentUnits0.FEET: 1.0,
                                      AscentUnits0.METRES: 1.0/3.28084}
                   }
        return factors[from_units][to_units]

    @classmethod
    def to_metres(cls, former_unit: "AscentUnits0", value: float) -> float:
        if value is None:
            return None
        factor = cls.conversion_factor(former_unit, AscentUnits0.METRES)
        return value * factor


class AscentUnits2(models.IntegerChoices):
    METRES = 1
    FEET = 2

    @classmethod
    def conversion_factor(cls, from_units, to_units):
        factors = {AscentUnits2.METRES: {AscentUnits2.METRES: 1.0,
                                        AscentUnits2.FEET: 3.28084},
                   AscentUnits2.FEET: {AscentUnits2.FEET: 1.0,
                                      AscentUnits2.METRES: 1.0/3.28084}
                   }
        return factors[from_units][to_units]

    def to_metres(self, value: float) -> float:
        if value is None:
            return None
        factor = self.conversion_factor(self, AscentUnits2.METRES)
        return value * factor

    def from_metres(self, value: float) -> float:
        if value is None:
            return None
        factor = self.conversion_factor(AscentUnits2.METRES, self)
        return value * factor


class Preferences(models.Model):
    __original_distance_units = None
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                primary_key=True, related_name='preferences')
    distance_units = models.PositiveSmallIntegerField(
        choices=DistanceUnits, default=DistanceUnits.MILES)
    ascent_units = models.PositiveSmallIntegerField(
        choices=AscentUnits2, default=AscentUnits2.METRES)
    maint_distance_limit = models.PositiveSmallIntegerField(
        default=100, blank=True, null=True,
        verbose_name='Upcoming maintenance distance limit')
    maint_time_limit = models.DurationField(
        default=dt.timedelta(days=10), blank=True, null=True,
        verbose_name='Upcoming maintenance time limit')

    class Meta:
        verbose_name_plural = 'preferences'

    def __init__(self, *args, **kwargs):
        super(Preferences, self).__init__(*args, **kwargs)
        self.__original_distance_units = self.distance_units

    @property
    def distance_units_label(self) -> str:
        return DistanceUnits(self.distance_units).label

    def get_absolute_url(self):
        return reverse('bike:preferences', kwargs={'pk': self.pk})

    def __str__(self):
        return f"Preferences for {self.user.username}"

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        if self.distance_units != self.__original_distance_units:
            factor = DistanceUnits.conversion_factor(
                self.__original_distance_units, self.distance_units)
            log.warning(
                "Preferences.distance_units changed from %s to %s: applying "
                "conversion factor=%s", self.__original_distance_units,
                self.distance_units, factor)
            Bike.update_distance_units(self.user, factor)
            MaintenanceType.update_distance_units(self.user, factor)
            MaintenanceAction.update_distance_units(self.user, factor)
        super(Preferences, self).save(
            force_insert=force_insert, force_update=force_update,
            *args, **kwargs)

    @staticmethod
    def conversion_factor_distance(user: User) -> float:
        """ return the conversion factor from metres to user's chosen distance
        unit """
        pref_distance_unit = user.preferences.distance_units
        conv_factor = DistanceUnits.conversion_factor(
            from_units=DistanceUnits.KILOMETRES, to_units=pref_distance_unit
            ) / 1000.0
        return conv_factor

    @staticmethod
    def conversion_factor_ascent(user: User) -> float:
        """ return the conversion factor from metres to user's chosen ascent
        unit """
        pref_ascent_unit = user.preferences.ascent_units
        conv_factor = AscentUnits0.conversion_factor(
            from_units=AscentUnits0.METRES, to_units=pref_ascent_unit)
        return conv_factor


class Link(models.Model):
    """ abstract model for concrete classes with foreign key to owning model
    """
    link_url = models.URLField()
    description = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        abstract = True


class Ride(models.Model):
    rider = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='rides')
    date = models.DateTimeField(default=timezone.now)
    is_adjustment = models.BooleanField(
        default=False, help_text="If true, signifies this is not a real ride"
        " but a ride distance adjustment between odometer readings.")
    description = models.TextField(max_length=400, null=False, blank=False)
    distance = models.FloatField(null=True, blank=True)  # units as prefs
    ascent = models.FloatField(null=True, blank=True)
    # ascent_units = models.PositiveSmallIntegerField(
    #     choices=AscentUnits0.CHOICES, default=AscentUnits0.METRES)
    ascent_metres = models.FloatField(null=True, blank=True)
    bike = models.ForeignKey(Bike, on_delete=models.SET_NULL, null=True,
                             blank=True, related_name='rides')

    # @property
    # def ascent(self) -> Optional[float]:
    #     """ take a value in user's preference units and store as ascent_metres
    #     """
    #     return  self.ascent_units.from_metres(self.ascent_metres)
    #
    # @ascent.setter
    # def ascent(self, value: Optional[float]):
    #     self.ascent_metres = self.ascent_units.to_metres(value)

    class Meta:
        unique_together = ('rider', 'date', 'bike', 'description')

    @property
    def ascent_units(self):
        return self.rider.preferences.ascent_units

    @property
    def ascent_units_label(self):
        return AscentUnits2(self.rider.preferences.ascent_units).label

    # TODO: is this ever used?
    @property
    def distance_units(self):
        return self.rider.preferences.distance_units

    @property
    def distance_units_label(self):
        return DistanceUnits(self.rider.preferences.distance_units).label

    def __str__(self):
        return f"{self.date.date()}: {self.description}"

    def get_absolute_url(self):
        return reverse('bike:ride', kwargs={'pk': self.id})

    def save(self, *args, **kwargs):
        """ update odometer adjustment ride(s), if any """
        # update odo adj ride for "old" bike if bike has been changed
        try:
            old_ride = Ride.objects.get(id=self.id)
            old_bike = old_ride.bike
        except Ride.DoesNotExist:
            old_bike = None
        super().save(*args, **kwargs)
        if not self.is_adjustment:
            if self.bike_id:
            # allow updating of following odometer adjustment ride, if any
                Odometer.ride_updated(self.date, self.bike_id)
                self.bike.update_current_odo()
                self.bike.save()
            if old_bike and old_bike != self.bike:
                Odometer.ride_updated(self.date, old_bike.id)
                old_bike.update_current_odo()
                old_bike.save()

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
        # log.info("Ride.distance_after(when=%s, bike=%s", when, bike)
        query = Ride.objects
        # log.info("distance_after(1). query=%s", query)
        if bike is not None:
            query = query.filter(bike=bike)
            # log.info("distance_after(2). query=%s", query)
        if when is not None:
            query = query.filter(date__gt=when)
            # log.info("distance_after(3). query=%s", query)
        return (query
                .order_by('bike_id', 'distance_units')
                .values('bike_id', 'distance_units')
                .annotate(distance=Sum('distance'))
                )

    @classmethod
    def mileage_by_month(cls, user, years: Union[int, List[int]], bike_id=None
                         ) -> Dict[int, Dict[str, Dict[str, float]]]:
        """ return total mileage by month, by year and by mileage unit,
        for a given year [and optionally bike] """
        rides = cls.rides_for_years(user, years, bike_id)

        rides = rides.order_by(
            'date__month', 'date__year', 'distance_units').all()
        # monthly mileage: {month: {year: {distanceunit: distance}}}

        # monthly_mileage = defaultdict(lambda: defaultdict(Counter))
        # use long-winded approach rather than defaultdict:
        # templates won't iterate over defaultdict
        # also template dict lookup doesn't work with numeric keys (year)
        # but iteration over dict.items does work with numeric keys (month)
        monthly_mileage: Dict[int, Dict[str, Dict[str, float]]] = {}
        for ride in rides:
            if ride.distance is not None:
                month = ride.date.month
                # template dict lookup doesn't work with numeric keys
                year = str(ride.date.year)
                units = ride.distance_units_display
                if month not in monthly_mileage:
                    monthly_mileage[month] = {}
                if year not in monthly_mileage[month]:
                    monthly_mileage[month][year] = {}
                if units not in monthly_mileage[month][year]:
                    monthly_mileage[month][year][units] = 0.0
                monthly_mileage[month][year][units] += ride.distance

        return monthly_mileage

    @classmethod
    def mileage_ytd(cls, user, years: Union[int, List[int]], bike_id=None, 
                    date_now: Optional[dt.datetime] = None  # for testing
                    ) -> Dict[int, Dict[str, float]]:
        rides = cls.rides_for_years(user, years, bike_id)
        now = date_now or dt.datetime.utcnow()
        ytd_filter = Q(date__month__lt=now.month)| Q(
            date__month=now.month, date__day__lte=now.day)
        rides = rides.filter(ytd_filter)
        mileage_ytd: Dict[int, Dict[str, float]] = {}
        for ride in rides:
            if ride.distance is None:
                continue
            year = ride.date.year
            units = ride.distance_units_display
            if year not in mileage_ytd:
                mileage_ytd[year] = {}
            if units not in mileage_ytd[year]:
                mileage_ytd[year][units] = 0.0
            mileage_ytd[year][units] += ride.distance
        return mileage_ytd

    @classmethod
    def rides_for_years(cls, user, years: Union[int, List[int]],
                        bike_id: Optional[int]=None):
        # return a queryset of rides
        if not isinstance(years, (int, list)):
            raise TypeError(
                f"years parameter must be list or int, not {type(years)}")
        if isinstance(years, list):
            rides = cls.objects.filter(rider=user, date__year__in=years)
        else:
            rides = cls.objects.filter(rider=user, date__year=years)
        if bike_id is not None:
                rides = rides.filter(bike_id=bike_id)
        return rides


    @classmethod
    def cumulative_mileage(cls, user, years: Union[int, List[int]]
                           ) -> List["Ride"]:
        rides = cls.rides_for_years(user, years).order_by("date").all()
        #  annotate each ride with cum_mileage in ride distance units
        # if there's more than one distance unit per year, results won't be
        # converted.
        prev_year = None
        cum_total: Dict[int, float]
        for ride in rides:
            if ride.date.year != prev_year:
                if prev_year is not None and len(cum_total) > 1:
                    log.warning("cumulative mileage for rides with mixed "
                                "distance units")
                prev_year = ride.date.year
                cum_total = {}
            if ride.distance_units not in cum_total:
                cum_total[ride.distance_units] = 0.0
            if ride.distance is not None:
                cum_total[ride.distance_units] += ride.distance
            ride.cum_distance = cum_total[ride.distance_units]
        if len(cum_total) > 1:
            log.warning("cumulative mileage for rides with mixed distance units")
        return rides


    @staticmethod
    def on_post_delete(_sender, instance, **_kwargs):
        """ signal handler: handle ride delete & update odometer readings
        This is connected to the post_delete signal in signals.py """
        # log.info("handling post_delete for ride %s", instance)
        Odometer.ride_updated(instance.date, instance.bike_id)
        instance.bike.update_current_odo()


class Odometer(models.Model):
    rider = models.ForeignKey(User, on_delete=models.CASCADE)
    distance = models.FloatField()  # distance units as prefs
    initial_value = models.BooleanField(default=False)
    # , help_text="Only tick this for the initial value of new "
    #    "odometer or after resetting the odometer reading.")
    comment = models.CharField(max_length=100, null=True, blank=True)
    bike = models.ForeignKey(Bike, on_delete=models.CASCADE,
                             related_name='odometer_readings')
    date = models.DateTimeField(default=timezone.now)
    adjustment_ride = models.OneToOneField(Ride, on_delete=models.CASCADE,
                                           null=True, blank=True)

    @property
    def distance_units_label(self) -> str:
        return DistanceUnits(self.rider.preferences.distance_units).label

    class Meta:
        verbose_name = 'Odometer reading'

    def __str__(self):
        reset = "reset to " if self.initial_value else ""
        return (f"{self.bike} odometer {reset}"
                f"{self.distance:0.1f} {self.distance_units_label.lower()}"
                f" on {self.date.date()}")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_adjustment_rides()
        self.bike.update_current_odo()
        self.bike.save()

    def delete(self):
        if self.adjustment_ride:
            self.adjustment_ride.delete()
        super(Odometer, self).delete()

    @classmethod
    def ride_updated(cls, ride_date, bike_id):
        """ called when a ride is saved, to allow adjustment of following
        odometer adjustment ride, if any.  Most times there will be none """
        next_odo = cls.next_odo(bike_id, ride_date)
        if next_odo is None:
            return
        prev_odo = cls.previous_odo(bike_id, ride_date)
        if prev_odo is None:
            return
        cls.update_adjustment_ride(next_odo, prev_odo)

    def update_adjustment_rides(self):
        """ create or update adjustment rides between this odo reading and
        previous/next odo readings, so that the rides mileage totals to the
        same as the difference between the odo readings.
        Mileage before a "reset" odo reading is not adjusted """
        # log.debug("Odometer.update_adjustment_rides(%s): initial_value=%s, "
        #           "adjustment_ride=%s", self, self.initial_value,
        #           self.adjustment_ride)
        if self.initial_value:  # after resetting odo: no adjustment ride
            if self.adjustment_ride:
                self.adjustment_ride.delete()
                # log.debug(" >Odometer.update_adjustment_rides: adjustment "
                #           "ride deleted")
                self.refresh_from_db()
        else:
            prev_odo = self.previous_odo(self.bike_id, self.date)
            if prev_odo:
                # log.debug(" >Odometer.update_adjustment_rides: adjustment "
                #           "ride updated")
                self.update_adjustment_ride(self, prev_odo)

        # update following adjustment ride, if necessary
        next_odo = self.next_odo(self.bike_id, self.date)
        if next_odo and not next_odo.initial_value:
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
        # log.info("update_adjustment_ride(current_odo=%s (adj_ride=%s), "
        #          "prev_odo=%s, ", current_odo, adj_ride, prev_odo)
        if adj_ride is None:
            adj_ride = Ride(
                bike=current_odo.bike, rider=current_odo.rider,
                is_adjustment=True)
        # else:
            # log.info(">update_adjustment_ride: adj_ride_id=%s", adj_ride.id)
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


class ComponentType(models.Model):
    type = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='component_types')
    description = models.CharField(max_length=200, null=True, blank=True)
    subtype_of = models.ForeignKey('ComponentType', related_name='subtypes',
                                   on_delete=models.PROTECT,
                                   blank=True, null=True)

    class Meta:
        # INVALID: causes infinite loop ordering = ['subtype_of']
        pass

    def __str__(self):
        return str(self.type)

    def get_absolute_url(self):
        return reverse('bike:component_type', kwargs={'pk': self.id})


class Component(models.Model):
    """ IMPORTANT: you must save() after updating bike or subcomponent_of,
    otherwise mileage tracking won't work """
    owner = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='components')
    bike = models.ForeignKey(
        Bike, related_name='components', null=True,
        blank=True, on_delete=models.SET_NULL,
        help_text="Leave blank if this is a subcomponent of another part of a "
        "bike.")
    name = models.CharField(max_length=100)
    type = models.ForeignKey(ComponentType, related_name='components',
                             on_delete=models.PROTECT)
    specification = models.CharField(max_length=200, null=True, blank=True)
    subcomponent_of = models.ForeignKey(
        'Component', related_name='components', on_delete=models.PROTECT,
        null=True, blank=True,
        help_text="Leave blank if this is a direct subcomponent of a bike")
    HIERARCHY_LIMIT = 10  # max chain of cpt -> cpt relationships
    # fk maintenance history
    # fk component history
    # fk subcomponent history
    date_acquired = models.DateField(default=dt.date.today, null=True,
                                     blank=True)
    supplier = models.CharField(max_length=200, null=True, blank=True)
    notes = models.TextField(max_length=400, null=True, blank=True)
    previous_distance = models.FloatField(
        default=0, help_text="odometer from previous bikes, in distance "
        "units from preferences.")
    start_odo = models.FloatField(
        default=0, help_text="odometer when added to this bike, in distance "
        "units from preferences.")

    def __str__(self):
        return f"{self.type}: {self.name}"

    def get_absolute_url(self):
        return reverse('bike:component', kwargs={'pk': self.id})

    def current_distance(self) -> float:
        """ return distance travelled by this cpt, current + prev bikes """
        return self.previous_distance + self.bike_distance()

    def bike_distance(self) -> float:
        """ return distance travelled on current bike, which may be through
        a parent component """
        current_bike = self.current_bike()
        if current_bike is not None:
            return current_bike.current_odo - self.start_odo
        return 0.0

    def current_bike(self, depth=0) -> Optional[Bike]:
        """ return bike, which may be through a parent component """
        # log.debug("%scpt.current_bike for %s: .bike=%s, subcomponent_of=%s",
        #           depth * '>', self, self.bike, self.subcomponent_of)
        if self.bike is not None:
            return self.bike
        parent_component = self.subcomponent_of
        if parent_component is None:
            return None
        if depth > self.HIERARCHY_LIMIT:
            raise RecursionError("Suspected circular component hierarchy "
                                 f"for {self}, id={self.id}")
        return parent_component.current_bike(depth+1)

    def update_bike_info(self, old_self):
        old_bike = old_self.current_bike()
        current_bike = self.current_bike()
        # log.debug("cpt.update_bike_info for %s:%s bike=%s->%s",
        #           self.pk, self, old_bike, current_bike)
        if (old_bike == current_bike
                and old_self.subcomponent_of == self.subcomponent_of):
            return
        old_bike_odo = old_bike.current_odo if old_bike else None
        current_bike_odo = current_bike.current_odo if current_bike else 0.0
        self.update_distances(old_bike_odo, current_bike_odo)
        self.update_subcomponent_distances(old_bike_odo, current_bike_odo)

    def update_distances(self, old_bike_odo, current_bike_odo):
        # log.debug("updating %d:%s from bike odo %s to %s",
        #           self.pk, self, old_bike_odo, current_bike_odo)
        if old_bike_odo:
            self.previous_distance += old_bike_odo - self.start_odo
        self.start_odo = current_bike_odo
        # force save so we don't increment previous_distance twice
        self.save(update_fields=[
            'bike', 'subcomponent_of', 'start_odo', 'previous_distance'])

    def update_subcomponent_distances(
            self, old_bike_odo, current_bike_odo, depth=0):
        """ update distances for all subcomponents unless they are attached
        directly to a bike """
        for subcomponent in self.components.all():
            if subcomponent.bike_id is not None:
                continue
            subcomponent.update_distances(old_bike_odo, current_bike_odo)
            if depth > self.HIERARCHY_LIMIT:
                raise RecursionError("Suspected circular component hierarchy "
                                     f"for {self}, id={self.id}")
            subcomponent.update_subcomponent_distances(
                old_bike_odo, current_bike_odo, depth+1)

    def save(self, *args, **kwargs):
        """ update start_odo if creating new instance """
        if not self.pk:
            current_bike = self.current_bike()
            if current_bike:
                self.start_odo = current_bike.current_odo
        super().save(*args, **kwargs)


class MaintIntervalMixin(models.Model):
    maintenance_interval_distance = models.PositiveIntegerField(
        null=True, blank=True)
    # distance units are set in preferences
    maint_interval_days = models.PositiveSmallIntegerField(
        null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def distance_units_label(self) -> str:
        return DistanceUnits(self.user.preferences.distance_units).label


class MaintenanceType(MaintIntervalMixin):
    # maintenance_interval_distance, maint_interval_days - MaintIntervalMixin
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='maintenance_types')
    component_type = models.ForeignKey(ComponentType, on_delete=models.CASCADE,
                                       related_name='maintenance_types')
    description = models.CharField(max_length=200)
    reference_info = models.CharField(max_length=300, blank=True, null=True)
    recurring = models.BooleanField(default=False)

    class Meta:
        unique_together = ['component_type', 'description']

    def __str__(self):
        return f'{self.component_type} - {self.description}'

    def get_absolute_url(self):
        return reverse('bike:maint_type', kwargs={'pk': self.id})

    @classmethod
    def update_distance_units(cls, user, factor):
        """ bulk update maint_interval_distance values multiplying by
        conversion factor """
        log.warning("Updating %s.maintenance_interval_distances * %s",
                    cls.__name__, factor)
        items = cls.objects.filter(
            user=user, maintenance_interval_distance__isnull=False)
        items.update(
            maintenance_interval_distance=F('maintenance_interval_distance') *
            factor)

    # @property  # @contrib.admin.display(ordering='user')
    def user_preferences_distance_units(self):
        return self.user.preferences.distance_units


class MaintenanceAction(MaintIntervalMixin):
    # maintenance_interval_distance, maint_interval_days - MaintIntervalMixin
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name='maintenance_actions')
    bike = models.ForeignKey(Bike, related_name="maint_actions",
                             on_delete=models.SET_NULL, null=True, blank=True)
    component = models.ForeignKey(
        Component, on_delete=models.CASCADE, null=True, blank=True,
        help_text='you only need to specify one of bike or component.')
    maint_type = models.ForeignKey(MaintenanceType, on_delete=models.SET_NULL,
                                   blank=True, null=True)
    description = models.CharField(max_length=200, blank=True, null=True)
    recurring = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True, default=dt.date.today)
    due_distance = models.FloatField(null=True, blank=True)
    # Expressions to be used in .annotate(...).  See upcoming()
    due_in_duration = ExpressionWrapper(
            F('due_date') - TruncDate(Now()),
            output_field=fields.DurationField()
            )
    due_in_distance = F('due_distance') - F('bike__current_odo')

    class Meta:
        unique_together = ('user', 'bike', 'component', 'maint_type',
                           'description', 'due_date', 'due_distance')

    def __str__(self):
        return (f"{self.description or self.maint_type}: "
                f"{self.component or self.bike}")

    def get_absolute_url(self):
        return reverse('bike:maint', kwargs={'pk': self.id})

    @classmethod
    def update_distance_units(cls, user, factor):
        """ bulk update maint_interval_distance and due_distance values,
        multiplying by conversion factor """
        # update maintenance_interval_distance
        log.warning("Updating %s.maintenance_interval_distances * %s",
                    cls.__name__, factor)
        items = cls.objects.filter(
            user=user, maintenance_interval_distance__isnull=False)
        items.update(
            maintenance_interval_distance=F('maintenance_interval_distance') *
            factor)
        # update due_distance
        log.warning("Updating %s.due_distances * %s", cls.__name__, factor)
        items = cls.objects.filter(
            user=user, due_distance__isnull=False)
        items.update(due_distance=F('due_distance') * factor)

    @classmethod
    def history(cls, user, bike_id=None, component_id=None,
                order_by='-completed_date'):
        """ return a list of maintenance action histories
        ordered by either date or maint action.
        """
        if order_by not in {'-completed_date', 'action_id'}:
            raise ValueError(f"order_by: invalid value '{order_by}'")
        actions = MaintenanceAction.objects.filter(user=user)
        if bike_id is not None:
            actions = actions.filter(bike_id=bike_id)
        if component_id is not None:
            actions = actions.filter(component_id=component_id)
        history = (MaintenanceActionHistory.objects
                   .filter(action__in=actions)
                   .select_related('action')  # populate action objects
                   .order_by(order_by)
                   .all())
        return history

    def maint_completed(
            self, comp_date: Optional[dt.date]=None,
            comp_distance: Optional[float]=None
            ) -> "MaintenanceActionHistory":
        """ record completion of a maintenance activity.
        This creates a MaintenanceActionHistory record.
        For non-recurring maintenance actions, the maint. action itself is
        also marked as complete.
        For recurring maint actions, the due date & distance are updated."""
        comp_date = comp_date or timezone.now().date()
        comp_distance = comp_distance or self.current_bike_odo()
        history = MaintenanceActionHistory(
            bike_id=self.bike_id, component_id=self.component_id, action=self,
            description=self.description or self.maint_type,
            completed_date=comp_date,
            distance=comp_distance,
            distance_units=self.user.preferences.distance_units)
        if not self.recurring:
            self.completed = True
        else:
            if self.maint_interval_days:
                self.due_date = comp_date + dt.timedelta(
                    self.maint_interval_days)
            else:
                self.due_date = None
            if self.maintenance_interval_distance:
                maint_interval_distance = self.maintenance_interval_distance
                self.due_distance = comp_distance + maint_interval_distance
            else:
                self.due_distance = None
        history.save()
        self.save()
        return history

    def current_bike_odo(self):
        bike = self.bike
        if bike:
            return bike.current_odo
        if self.component and self.component.bike:
            return self.component.bike.current_odo
        return None

    @classmethod
    def upcoming(cls, user, bike_id: Optional[int]=None,
                 component_id: Optional[int]=None, filter_by_limits=True):
        """ return a queryset of incomplete maintenance actions
            due_in_time is a datetime.timedelta object,
            due_in_distance is a float using preferences.distance_units
            if filter_by_limits is set, only maint actions within limits in
                prefs_limits are returned """
        upcoming = MaintenanceAction.objects.filter(completed=False, user=user)
        if bike_id is not None:
            upcoming = upcoming.filter(bike_id=bike_id)
        else:
            upcoming = upcoming.order_by('bike_id')
        if component_id is not None:
            upcoming = upcoming.filter(component_id=component_id)
        upcoming = (upcoming.annotate(
            due_in_duration=cls.due_in_duration,
            due_in_distance=cls.due_in_distance
            ))
        if filter_by_limits:
            return cls.apply_prefs_limits(upcoming, user)
        else:
            return upcoming

    @classmethod
    def apply_prefs_limits(cls, upcoming, user):
        prefs = user.preferences
        # maint actions with neither due date or distance always show up
        q = Q(due_in_distance__isnull=True, due_in_duration__isnull=True)
        if prefs and prefs.maint_distance_limit:
            q |= Q(due_in_distance__lte=prefs.maint_distance_limit)
        if prefs and prefs.maint_time_limit:
            q |= Q(due_in_duration__lte=prefs.maint_time_limit)
        return upcoming.filter(q)

    def due_in(self, distance_units):
        """ return a string with "Due in xxx days, xxx <distance units".
        Used after calling Maintaction.upcoming """
        # log.debug("Maintenanceaction.due_in: due_in_duration=%s",
        #           self.due_in_duration)
        try:
            return self._due_in
        except AttributeError:
            pass
        if not hasattr(self, 'due_in_distance'):
            self.due_in_distance = None
        # self.due_in_duration = ((self.due_date - timezone.now().date()).days
        #                         if self.due_date is not None else None)
        due = [
            (f"{self.due_in_duration.days} days"
             if self.due_in_duration else None),
            (f"{self.due_in_distance:0.0f} {distance_units}"
             if self.due_in_distance else None)]
        self._due_in = ', '.join(d for d in due if d is not None)
        return self._due_in


class MaintActionLink(Link):
    maint_action = models.ForeignKey(
        MaintenanceAction, on_delete=models.CASCADE, related_name='links')


class MaintenanceActionHistory(models.Model):
    bike = models.ForeignKey(Bike, related_name='maint_history',
                             on_delete=models.SET_NULL, null=True, blank=True)
    component = models.ForeignKey(
        Component, on_delete=models.CASCADE, null=True, blank=True,
        help_text='you only need to specify one of bike or component.')
    # TODO: action field will be removed after data migration
    action = models.ForeignKey(MaintenanceAction, on_delete=models.PROTECT,
                               related_name="maintenance_action")
    description = models.CharField(max_length=200, blank=True, null=True)
    distance = models.FloatField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)

    def clean(self):
        if self.completed_date is None and self.completed_distance is None:
            raise ValidationError(
                "Either completion date or distance is required.")

    class Meta:
        verbose_name_plural = "Maintenance action history"

    def __str__(self):
        when = (f" on {self.completed_date}" if self.completed_date else None,
                f"at {self.distance} {self.distance_units_label.lower()}"
                if self.distance else None)
        when = ' '.join(item for item in when
                        if item is not None)
        return f"{self.action} on {when}"

    def distance_units_label(self) -> str:
        if self.bike:
            return DistanceUnits(self.bike.rider.preferences.distance_units
                                 ).label
        if self.component:
            return DistanceUnits(self.component.owner.preferences.distance_units
                                 ).label
        return ''  # can't determine user for distance_units


class ComponentChange(models.Model):
    date = models.DateField(default=dt.date.today, null=True, blank=True)
    changed_component = models.ForeignKey(Component, on_delete=models.CASCADE,
                                          related_name='component_history')
    parent_component = models.ForeignKey(Component, on_delete=models.CASCADE,
                                         related_name='subcomponent_history')
    description = models.CharField(max_length=200)
    distance = models.FloatField(null=True, blank=True)


# ------ new version of preferences, under development ------
#
#
#
#
# UNIT_CONVERSION_FACTOR = {
#     AscentUnits2.METRES: {AscentUnits2.METRES: 1.0,
#                           AscentUnits2.FEET: 3.28084,
#                           DistanceUnits.KILOMETRES: .001,
#                           DistanceUnits.MILES: 0.000621371},
#     AscentUnits2.FEET: {AscentUnits2.FEET: 1.0,
#                         AscentUnits2.METRES: 1.0/3.28084},
#     DistanceUnits.MILES: {DistanceUnits.MILES: 1,
#                           DistanceUnits.KILOMETRES: 1.60934,
#                           AscentUnits2.METRES: 1609.34},
#     DistanceUnits.KILOMETRES: {DistanceUnits.MILES: 0.621371,
#                               DistanceUnits.KILOMETRES: 1,
#                               AscentUnits2.METRES: 1000}
#     }
#
#
# def from_metres(value: float, unit_type) -> float:
#     """ convert a value from metres to the chosen unit """
#     factor = UNIT_CONVERSION_FACTOR[AscentUnits2.METRES][unit_type]
#     return value * factor
#
# def to_metres(value: float, unit_type) -> float:
#     """ convert a value in the chosen unit to metres """
#     factor = UNIT_CONVERSION_FACTOR[unit_type][AscentUnits2.METRES]
#     return value * factor


# class Prefs2(models.Model):
#     distance_unit = models.SmallIntegerField(
#         choices=DistanceUnits, default=DistanceUnits.MILES)
#     # distance_unit.label gives a str representation
#     distance_metres = models.FloatField() # always stored in metres
#
#     # TODO: can these conversions be done as a DB function?
#     # https://stackoverflow.com/questions/17682567/how-to-add-a-calculated-field-to-a-django-model
#     @property
#     def distance(self) -> float:
#         """ return distance in preferred units """
#         return from_metres(self.distance_metres, self.distance_unit)
#
#     @distance.setter
#     def distance(self, value: float):
#         """ set distance from a value in preferred units """
#         self.distance_metres = to_metres(value, self.distance_unit)
#
#     @property
#     def distance_unit_label(self)-> str:
#         return DistanceUnits(self.distance_unit).label


# class Prefs3(models.Model):
#     distance_unit = models.SmallIntegerField(
#         choices=DistanceUnits, default=DistanceUnits.MILES)
#     distance = models.FloatField()  # in units of distance_unit
#     distance_metres = models.Expression(
#         to_metres(F('distance_unit'), F('distance')))
