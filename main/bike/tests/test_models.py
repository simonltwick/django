'''
Test of model functions
Created on 29 May 2020

@author: simon
'''
from django.test import TestCase, override_settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.utils import timezone

import datetime as dt
import logging

from ..models import (
    Bike,  # ComponentType, Component, MaintenanceAction,
    DistanceUnits, Odometer, Ride, Preferences
    # MaintenanceType,
    )


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


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


class TestOdometerAdjustmentRides(TestCase):

    """ adding an odo reading automatically calls update_adjustment_rides
        adding/deleting/updating a ride between two odo readings
            updates adjustment ride
        """

    @override_settings(
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', ])
    def setUp(self):
        self.user = User.objects.create(
            username='tester', password=make_password('testpw'))
        self.user.save()
        preferences = Preferences.objects.create(user=self.user)
        preferences.save()
        self.bike = Bike.objects.create(
            name='Test bike', description="test", owner=self.user)
        self.bike.save()
        self.now = timezone.now()
        self.yr = dt.timedelta(days=365)
        self.ride = Ride.objects.create(rider=self.user, bike=self.bike,
                                        distance=1,
                                        date=self.now,
                                        distance_units=DistanceUnits.MILES)
        self.ride.save()
        self.odo1 = Odometer(bike=self.bike, rider=self.user,
                             distance=20, distance_units=DistanceUnits.MILES,
                             date=self.now-self.yr)
        self.odo1.save()
        self.odo2 = Odometer(bike=self.bike, rider=self.user,
                             distance=40, distance_units=DistanceUnits.MILES,
                             date=self.now+self.yr)
        self.odo2.save()

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
