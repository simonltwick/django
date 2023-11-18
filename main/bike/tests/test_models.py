'''
Test of model functions
Created on 29 May 2020

@author: simon
'''
from django.test import TestCase, override_settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import F, ExpressionWrapper, fields
from django.db.models.functions import Now, TruncDate

from copy import deepcopy
import datetime as dt
import logging

from ..models import (
    Bike, ComponentType, Component,  # MaintenanceAction,
    DistanceUnits, Odometer, Ride, Preferences, MaintenanceAction,
    )


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


class TestDistanceUnits(TestCase):
    def test_convert(self):
        Dconv = DistanceUnits.convert
        m = DistanceUnits.MILES
        km = DistanceUnits.KILOMETRES

        self.assertEqual(Dconv(1, m, m), 1, "convert miles to miles")
        self.assertEqual(Dconv(1, km, km), 1, "convert km to km")
        self.assertEqual(Dconv(1, km, m), 1/1.60934, "convert km to miles")
        self.assertEqual(Dconv(1, m, km), 1.60934, "convert miles to km")

    def test_sum(self):
        Dsum = DistanceUnits.sum
        m = DistanceUnits.MILES
        km = DistanceUnits.KILOMETRES
        self.assertEqual(Dsum([{'distance': 1, 'distance_units': m}],
                              target_units=m), 1, "no conversion")
        self.assertEqual(Dsum([{'distance': 1, 'distance_units': m},
                               {'distance': 2, 'distance_units': m}],
                              target_units=m), 3, "no conversion")
        self.assertEqual(Dsum([{'distance': 1, 'distance_units': km}],
                              target_units=m), 1/1.60934, "km to miles")
        self.assertEqual(Dsum([{'distance': 1, 'distance_units': m}],
                              target_units=km), 1.60934, "miles to km")
        self.assertEqual(Dsum([{'distance': 4, 'distance_units': m},
                               {'distance': 2, 'distance_units': m},
                               {'distance': 1, 'distance_units': km}],
                              target_units=m), 6 + 1/1.60934,
                         "mixed units sum")


class TestOdometerAdjustment(TestCase):

    @override_settings(
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', ])
    def setUp(self):
        self.user = User.objects.create(
            username='tester', password=make_password('testpw'))
        _preferences = Preferences.objects.create(user=self.user)
        self.bike = Bike.objects.create(
            name='Test bike', description="test", owner=self.user)
        self.bike2 = Bike.objects.create(
            name='Test bike 2', description="test2", owner=self.user)
        self.now = timezone.now()
        self.yr = dt.timedelta(days=365)
        # odo before ride
        self.odo1 = Odometer.objects.create(
            bike=self.bike, rider=self.user,
            distance=20, distance_units=DistanceUnits.MILES,
            date=self.now-self.yr)
        self.odo3 = Odometer.objects.create(
            bike=self.bike2, rider=self.user,
            distance=100, distance_units=DistanceUnits.MILES,
            date=self.now-self.yr)

        self.ride = Ride.objects.create(rider=self.user, bike=self.bike,
                                        distance=1,
                                        date=self.now,
                                        distance_units=DistanceUnits.MILES)

        # odo after ride
        self.odo2 = Odometer.objects.create(
            bike=self.bike, rider=self.user,
            distance=40, distance_units=DistanceUnits.MILES,
            date=self.now+self.yr)
        self.odo4 = Odometer.objects.create(
            bike=self.bike2, rider=self.user,
            distance=150, distance_units=DistanceUnits.MILES,
            date=self.now+self.yr)


class TestRide(TestOdometerAdjustment):
    """ changing bike for a ride automatically updates odo adjustment ride
    AND bike_odo for both old & new bike, unless they are null """
    def test0_change_bike_adjustment_rides(self):
        """ change the bike for self.ride to bike2
            -> adjusts both adjustment rides """
        odo2_adjustment_ride = self.odo2.adjustment_ride
        odo4_adjustment_ride = self.odo4.adjustment_ride
        self.assertEqual(odo2_adjustment_ride.distance, 19,
                         "odo2: 19 miles adjustment before changing bike")
        self.assertEqual(odo4_adjustment_ride.distance, 50,
                         "odo2: 50 miles adjustment before changing bike")

        self.ride.bike_id = self.bike2.id
        self.ride.save()
        
        odo2_adjustment_ride.refresh_from_db()
        odo4_adjustment_ride.refresh_from_db()

        self.assertEqual(odo2_adjustment_ride.distance, 20,
                         "odo2: 20 miles adjustment after changing bike")
        self.assertEqual(odo4_adjustment_ride.distance, 49,
                         "odo4: 49 miles adjustment after changing bike")

    def test1_change_bike_current_odo(self):
        """ change the bike for self ride (after last odo reading) to bike2
            --> adjusts both bike.current_odo """
        ride2 = Ride.objects.create(rider=self.user, bike=self.bike,
                                        distance=7,
                                        date=self.now + 2 * self.yr,
                                        distance_units=DistanceUnits.MILES)

        self.assertEqual(self.bike.current_odo, 47,
                         "bike odo: 47 before changing bike (odo2+ride2)")
        self.assertEqual(self.bike2.current_odo, 150,
                         "bike2 odo: 150 before changing bike (odo4)")

        ride2.bike_id = self.bike2.id
        ride2.save()
        self.bike.refresh_from_db()
        self.bike2.refresh_from_db()

        self.assertEqual(self.bike.current_odo, 40,
                         "bike odo: 40 after changing bike (odo2)")
        self.assertEqual(self.bike2.current_odo, 157,
                         "bike2 odo: 157 after changing bike (odo4+ride2)")


class TestOdometerAdjustmentRides(TestOdometerAdjustment):

    """ adding an odo reading automatically calls update_adjustment_rides
        adding/deleting/updating a ride between two odo readings
            updates adjustment ride
        """

    def test0_prev_next_odo(self):
        self.assertEqual(
            self.odo1.next_odo(self.odo1.bike_id, self.odo1.date), self.odo2)
        self.assertEqual(
            self.odo1.previous_odo(self.odo1.bike_id, self.odo1.date), None)
        self.assertEqual(
            self.odo2.next_odo(self.odo2.bike_id, self.odo2.date), None)
        self.assertEqual(
            self.odo2.previous_odo(self.odo2.bike_id, self.odo2.date),
            self.odo1)

    def test1_update_adjustment_rides_same_units1(self):
        """1 of 4 cases,  **odo1 when updating odo2, odo2 when updating odo1,
                     odo1=reset with odo2, odo1 with odo2=reset """
        self.assertIsNone(self.odo1.adjustment_ride, 'unchanged')
        self.assertIsNotNone(self.odo2.adjustment_ride)
        self.assertEqual(self.odo2.adjustment_ride.distance, 19)
        self.assertEqual(self.odo2.adjustment_ride.distance_units,
                         DistanceUnits.MILES)

    def test1_update_adjustment_rides_same_units2(self):
        """2 of 4 cases,  odo1 when updating odo2, **odo2 when updating odo1,
                     odo1=reset with odo2, odo1 with odo2=reset """
        self.odo1.distance = 10
        self.odo1.save()
        self.odo1.refresh_from_db()
        self.odo2.refresh_from_db()
        self.assertIsNone(self.odo1.adjustment_ride, 'unchanged')
        self.assertIsNotNone(self.odo2.adjustment_ride)
        self.assertEqual(self.odo2.adjustment_ride.distance, 29)
        self.assertEqual(self.odo2.adjustment_ride.distance_units,
                         DistanceUnits.MILES)

    def test1_update_adjustment_rides_same_units3(self):
        """3 of 4 cases,  odo1 with odo2, odo2 with odo1,
                     **odo1=reset with odo2, odo1 with odo2=reset
            should be the same as case 1 & 2 """

        self.assertIsNone(self.odo1.adjustment_ride)
        self.assertIsNotNone(self.odo2.adjustment_ride)
        self.odo1.initial_value = True
        self.odo1.save()
        self.odo1.refresh_from_db()
        self.odo2.refresh_from_db()
        self.assertIsNone(self.odo1.adjustment_ride, 'unchanged')
        self.assertIsNotNone(self.odo2.adjustment_ride, 'unchanged')
        self.assertEqual(self.odo2.adjustment_ride.distance, 19)
        self.assertEqual(self.odo2.adjustment_ride.distance_units,
                         DistanceUnits.MILES)

    def test1_update_adjustment_rides_same_units4(self):
        """4 of 4 cases,  odo1 with odo2, odo2 with odo1,
                     odo1=reset with odo2, **odo1 with odo2=reset
            should NOT create an adjustment ride """

        self.assertIsNone(self.odo1.adjustment_ride)
        self.assertIsNotNone(self.odo2.adjustment_ride)
        self.odo2.initial_value = True
        self.odo2.save()
        self.odo1.refresh_from_db()
        self.odo2.refresh_from_db()
        self.assertTrue(self.odo2.initial_value,
                        "check initial_value set to True")
        self.assertIsNone(self.odo1.adjustment_ride, 'check unchanged')
        self.assertIsNone(self.odo2.adjustment_ride, 'check deleted')

    def test2_mixed_distance_adjustment_rides1(self):
        """ mixture of km and miles: odo1 in km """
        self.odo1.distance_units = DistanceUnits.KILOMETRES
        self.odo1.distance = 10  # = 6.21371 miles
        self.odo1.save()

        self.odo1.refresh_from_db()
        self.odo2.refresh_from_db()
        self.assertIsNone(self.odo1.adjustment_ride, 'unchanged')
        expected_distance = 40 - 1 - 6.21371
        self.assertAlmostEqual(self.odo2.adjustment_ride.distance,
                               expected_distance, places=3)
        self.assertEqual(self.odo2.adjustment_ride.distance_units,
                         DistanceUnits.MILES)

    def test2_mixed_distance_adjustment_rides2(self):
        """ mixture of km and miles: odo2 in km """
        self.odo2.distance_units = DistanceUnits.KILOMETRES
        self.odo2.distance = 100  # = 62.1371 miles
        self.odo2.save()

        self.odo1.refresh_from_db()
        self.odo2.refresh_from_db()
        self.assertIsNone(self.odo1.adjustment_ride, 'unchanged')
        expected_distance = (62.1371 - 1 - 20) * 1.60934
        self.assertAlmostEqual(self.odo2.adjustment_ride.distance,
                               expected_distance, places=3)
        self.assertEqual(self.odo2.adjustment_ride.distance_units,
                         DistanceUnits.KILOMETRES)

    def test2_mixed_distance_adjustment_rides3(self):
        """ mixture of km and miles: ride in km """
        self.ride.distance_units = DistanceUnits.KILOMETRES
        self.ride.distance = 1  # = .621371 miles
        self.ride.save()

        self.odo1.refresh_from_db()
        self.odo2.refresh_from_db()
        self.assertIsNone(self.odo1.adjustment_ride, 'unchanged')
        expected_distance = 40 - .621371 - 20
        self.assertAlmostEqual(self.odo2.adjustment_ride.distance,
                               expected_distance, places=3)
        self.assertEqual(self.odo2.adjustment_ride.distance_units,
                         DistanceUnits.MILES)

    def test3_alter_odo_initial_setting(self):
        """ setting Odometer.initial_value to True deletes the adjustment ride
        """
        self.odo1.refresh_from_db()
        self.odo2.refresh_from_db()
        self.assertIsNone(self.odo1.adjustment_ride, 'unchanged')
        self.assertIsNotNone(self.odo2.adjustment_ride)

        self.odo2.initial_value = True
        self.odo2.save()
        self.assertIsNone(self.odo2.adjustment_ride,
                          msg="no adjustment ride if initial=True")

        self.odo2.initial_value = False
        self.odo2.save()
        self.assertIsNotNone(self.odo2.adjustment_ride,
                             msg="restore adjustment ride if initial=False")


class TestMaintenanceAction(TestCase):
    @override_settings(
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', ])
    def setUp(self):
        self.user = User.objects.create(
            username='tester', password=make_password('testpw'))
        self.maint_action = MaintenanceAction.objects.create(
            user=self.user, due_date=timezone.now()+dt.timedelta(days=1))

    def test1(self):
        # from django import get_version
        # print(f"django version is {get_version()}")
        due_in = ExpressionWrapper(
            F('due_date') - TruncDate(Now()),
            output_field=fields.DurationField()
            )
        # due_in_days = ExtractDay(due_in)  # error - requires native DB
        #                                   # DurationField support
        ma = MaintenanceAction.objects.annotate(due_in=due_in).first()

        # today = dt.datetime.now().date()
        # print(f"{ma=}, {today=!r}, {ma.due_date=!r}, {ma.due_in=!r}, "
        #       f"{ma.due_in.days=!r}")
        self.assertIsInstance(ma.due_in, dt.timedelta)
        self.assertEqual(ma.due_in.days, 1)


class TestComponent(TestCase):
    @override_settings(
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', ])
    def setUp(self):
        self.user = User.objects.create(
            username='tester', password=make_password('testpw'))
        self.bike = Bike.objects.create(
            name='Test bike', description="test", owner=self.user,
            current_odo=1000)
        self.bike2 = Bike.objects.create(
            name='Test bike2', description="test", owner=self.user,
            current_odo=2000)
        self.user.save()
        self.bike.save()
        cpt_type = ComponentType(user=self.user, type="Test cpt_type")
        cpt_type.save()
        self.cpt_type = cpt_type
        self.cpt = Component.objects.create(
            owner=self.user, name="Test component", type=cpt_type)
        self.cpt.save()
        self.subcpt = Component.objects.create(
            owner=self.user, name="Test sub_component", type=cpt_type,
            subcomponent_of=self.cpt)
        self.subcpt.save()
        self.subcpt2 = Component.objects.create(
            owner=self.user, name="Test sub_component 2", type=cpt_type,
            bike=self.bike2, subcomponent_of=self.cpt)
        self.subcpt2.save()
        self.subcpt3 = Component.objects.create(
            owner=self.user, name="Test sub_sub_component 3", type=cpt_type,
            subcomponent_of=self.subcpt)
        self.subcpt3.save()

    def test0_current_bike(self):
        self.assertIsNone(self.cpt.current_bike(),
                          "check no bike defined for cpt")
        self.assertIsNone(self.subcpt.current_bike(),
                          "check no bike defined for subcpt")
        self.assertEqual(self.subcpt2.current_bike(), self.bike2,
                         "check bike2 defined for subcpt2")
        self.assertIsNone(self.subcpt3.current_bike(),
                          "check no bike defined for subcpt3")
        subcpt4 = Component.objects.create(
            owner=self.user, name="Test sub_sub_component 4",
            type=self.cpt_type, subcomponent_of=self.subcpt2)
        self.assertEqual(subcpt4.current_bike(), self.bike2,
                         "check bike2 defined for subcpt4")
        # check that we can move a cpt and new bike is picked up
        self.subcpt3.subcomponent_of = self.subcpt2
        self.subcpt3.save()
        self.assertEqual(self.subcpt3.current_bike(), self.bike2,
                         "check bike2 is now defined for subcpt3")

    def test1_create_with_bike(self):
        """cpts created with a bike, have start_odo set."""
        self.assertEqual(self.subcpt2.start_odo, 2000,
                         "check subcpt created with a bike has start_odo set")

    def test2_add_remove_bike(self):
        """ add bike: cpt.start_odo set to bike.current_odo
                      subcpts.start_odo  --- " ---
            remove bike:  cpt.prev_odo set to bike.current_odo - cpt.start_odo
                          cpt.start_odo set to zero
                          same for subcpts.
            subcomponents which belong to a different bike, are not updated.
        """
        # add bike
        old_cpt = deepcopy(self.cpt)
        self.cpt.bike = self.bike
        self.cpt.update_bike_info(old_cpt)
        self.subcpt.refresh_from_db()
        self.subcpt2.refresh_from_db()
        self.assertEqual(self.cpt.start_odo, self.bike.current_odo,
                         "add bike: check start_odo is updated")
        self.assertEqual(self.subcpt.start_odo, self.bike.current_odo,
                         "add bike: check subcpt start_odo is updated")
        self.assertEqual(self.subcpt2.start_odo, 2000,
                         "add bike: check subcpt2 start_odo is NOT updated"
                         " as it belongs to a different bike")
        self.assertEqual(self.cpt.current_distance(), 0,
                         "add bike: check cpt distance hasn't changed")
        # go for a ride
        RIDE_DISTANCE = 5
        self.bike.current_odo += RIDE_DISTANCE
        self.bike.save()
        self.assertEqual(self.cpt.current_distance(), RIDE_DISTANCE,
                         "ride bike: check cpt distance is updated")
        # remove bike
        old_cpt1 = deepcopy(self.cpt)
        self.cpt.bike = None
        self.cpt.update_bike_info(old_cpt1)
        self.subcpt.refresh_from_db()
        self.subcpt2.refresh_from_db()
        self.assertEqual(self.cpt.start_odo, 0,
                         "remove bike: check start_odo set to zero")
        self.assertEqual(self.subcpt.start_odo, 0,
                         "add bike: check subcpt start_odo set to zero")
        self.assertEqual(self.cpt.previous_distance, RIDE_DISTANCE,
                         "remove bike: check prev_dist set to ride distance")
        self.assertEqual(self.subcpt.previous_distance, RIDE_DISTANCE,
                         "remove bike: check subcpt prev_dist set to "
                         "ride distance")
        self.assertEqual(self.subcpt2.start_odo, 2000,
                         "remove bike: check subcpt2 start_odo is NOT updated"
                         " as it belongs to a different bike")
        self.assertEqual(self.subcpt2.previous_distance, 0,
                         "remove bike: check subcpt2 previous_distance is NOT "
                         "updated as it belongs to a different bike")
        self.assertEqual(self.cpt.current_distance(), RIDE_DISTANCE,
                         "remove bike: check cpt distance hasn't changed")

    def test3_move_subcpt(self):
        """ move subcpt3 between cpts, as for move between bikes """
        self.assertEqual(self.subcpt3.start_odo, 0,
                         "start_odo not initially set")
        # move to subcpt2 (attached to bike2)
        old_subcpt3 = deepcopy(self.subcpt3)
        self.assertIsNone(self.subcpt3.current_bike(),
                          "subcpt3 before update has no bike")
        self.subcpt3.subcomponent_of = self.subcpt2
        self.subcpt3.save()
        self.assertEqual(self.subcpt3.current_bike(), self.bike2,
                         "subcpt3 after update has bike2")
        self.subcpt3.update_bike_info(old_subcpt3)
        self.assertEqual(self.subcpt3.start_odo, 2000,
                         "check start_odo updated to match bike2")
        # move back to subcpt (no bike defined)
        old_subcpt3b = deepcopy(self.subcpt3)
        self.subcpt3.subcomponent_of = self.subcpt
        self.subcpt3.save()
        self.subcpt3.update_bike_info(old_subcpt3b)
        self.assertEqual(self.subcpt3.start_odo, 0,
                         "check start_odo updated to match no bike")

    def test3_change_units(self):
        """ check that if preferences.distance_units changed, distances are
        converted in components """
        ...
