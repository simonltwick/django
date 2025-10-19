from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.urls import reverse
import logging

from ..models import (
    Bike, ComponentType, Ride, Component, MaintenanceAction, DistanceUnits,
    MaintenanceType, Preferences, Odometer
    )


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class BikeUrlTest(TestCase):
    """ check urls work """

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

        self.odo = Odometer.objects.create(rider=self.user, bike=self.bike,
                                           distance=0.0, initial_value=True)
        self.odo.save()
        self.assertIsNone(
            self.odo.adjustment_ride,
            "initial odo reading doesn't create an adjustment ride")
        self.ride = Ride.objects.create(
            rider=self.user, bike=self.bike, distance=5,
            description="Test ride", distance_units=DistanceUnits.MILES)
        self.ride.save()
        self.odo2 = Odometer.objects.create(
            rider=self.user, bike=self.bike, distance=5.0)
        self.odo2.save()
        self.adjustment_ride = self.odo2.adjustment_ride
        self.assertIsNotNone(self.adjustment_ride)

        self.ct = ComponentType.objects.create(
            user=self.user, type="Test type")
        self.ct.save()
        self.maint = MaintenanceAction.objects.create(
            bike=self.bike, user=self.user, recurring=True)
        self.maint.save()
        self.maint_history = self.maint.mark_completed(comp_distance=99.0)

        self.client = Client(raise_request_exception=True)
        self.client.login(username='tester', password='testpw')

    def test_home(self):
        self.try_url(reverse('bike:home'), context={'preferences_set': True})

    def test_bike(self):
        bid = self.bike.id
        self.try_url(reverse('bike:bikes'))
        self.try_url(reverse('bike:bike', kwargs={'pk': bid}),
                     context={'bike': self.bike})
        self.try_url(reverse('bike:bike_delete', kwargs={'pk': bid}))
        self.try_url(reverse('bike:bike_new'),)

    def test_ride(self):
        rid = self.ride.id
        self.try_url(reverse('bike:rides'),
                     context={'entries': [self.adjustment_ride, self.ride]})
        self.try_url(reverse('bike:ride', kwargs={'pk': rid}),
                     context={'ride': self.ride})
        self.try_url(reverse('bike:ride_delete', kwargs={'pk': rid}),
                     context={'ride': self.ride})
        self.try_url(reverse('bike:ride'))

    def test_maint_action(self):
        maint = self.maint
        self.try_url(reverse('bike:maint_actions'),
                     context={'object_list': [maint]})
        self.try_url(reverse('bike:maint', kwargs={'pk': maint.id}),
                     context={'maintenanceaction': maint})
        self.try_url(reverse('bike:maint_delete',
                             kwargs={'pk': maint.id}),
                     context={'maintenanceaction': maint})
        self.try_url(reverse('bike:maint_new'),)
        # maint_complete requires POST method
        """self.try_url(reverse('bike:maint_complete',
                             kwargs={'pk': maint.id}),
                     context={'maintenanceaction': maint})"""

    def test_maint_history(self):
        history = self.maint_history
        self.try_url(reverse('bike:maint_history', kwargs={'pk': history.id}),
                     context={'maintenanceactionhistory': history})
        self.try_url(reverse('bike:maint_history_delete',
                             kwargs={'pk': history.id}),
                     context={'maintenanceactionhistory': history})

    def test_maint_type(self):
        maint = MaintenanceType.objects.create(
            user=self.user, component_type=self.ct)
        maint.save()
        self.try_url(reverse('bike:maint_types'),
                     context={'object_list': [maint]})
        self.try_url(reverse('bike:maint_type', kwargs={'pk': maint.id}),
                     context={'maintenancetype': maint})
        self.try_url(reverse('bike:maint_type_delete',
                             kwargs={'pk': maint.id}),
                     context={'maintenancetype': maint})
        self.try_url(reverse('bike:maint_type_new'),)

    def test_mileage(self):
        self.try_url(
            reverse('bike:mileage'),
            context={
                'monthly_mileage':
                    {self.ride.date.month: {self.ride.distance_units_display:
                                            self.ride.distance}}
                    }
            )
        self.try_url(
            reverse('bike:mileage', kwargs={'year': self.ride.date.year}),
            context={'monthly_mileage': {
                self.ride.date.month: {self.ride.distance_units_display:
                                       self.ride.distance}
                }
            })
        self.try_url(
            reverse('bike:mileage', kwargs={'bike_id': self.bike.id}),
            context={'monthly_mileage': {
                self.ride.date.month: {self.ride.distance_units_display:
                                       self.ride.distance}
                }
            })
        self.try_url(
            reverse('bike:mileage', kwargs={'bike_id': self.bike.id,
                                            'year': self.ride.date.year}),
            context={'monthly_mileage': {
                self.ride.date.month: {self.ride.distance_units_display:
                                       self.ride.distance}
                }
            })
        self.try_url(reverse('bike:rides_month',
                             kwargs={'month': self.ride.date.month,
                                     'year': self.ride.date.year}),
                     context={'entries': [self.ride, self.adjustment_ride]}
                     )

    def test_odometer(self):
        self.try_url(reverse('bike:odometer_readings'))
        self.try_url(reverse('bike:odometer_readings',
                             kwargs={'bike_id': self.bike.id}))
        self.try_url(reverse('bike:odometer_readings_new'))
        self.try_url(reverse('bike:odometer_readings_new',
                             kwargs={'bike_id': self.bike.id}))
        self.try_url(reverse('bike:odometer_adjustment_ride',
                             kwargs={'ride_id': self.adjustment_ride.id}))
        self.try_url(reverse('bike:odometer_adjustment',
                             kwargs={'odo_reading_id': self.odo.id}))
        self.try_url(reverse('bike:odometer_delete',
                             kwargs={'pk': self.odo.id}))
        # add odometer_adjustment_ride <adj_ride_id>
        # can't add odometer_adjustment as requires POST method

    def test_component(self):
        comp = Component.objects.create(type=self.ct, name='Test component',
                                        owner=self.user)
        self.try_url(reverse('bike:components'))
        self.try_url(reverse('bike:component', kwargs={'pk': comp.id}),
                     context={'component': comp})
        self.try_url(reverse('bike:component_delete', kwargs={'pk': comp.id}),
                     context={'component': comp})
        self.try_url(reverse('bike:component_new'),)
        self.try_url(reverse('bike:component_replace', kwargs={'pk': comp.id}))

    def test_component_type(self):
        ct = self.ct
        self.try_url(reverse('bike:component_types'))
        self.try_url(reverse('bike:component_type', kwargs={'pk': ct.id}),
                     context={'componenttype': ct})
        self.try_url(reverse('bike:component_type_delete',
                             kwargs={'pk': ct.id}))
        self.try_url(reverse('bike:component_type_new'),)

    def test_preferences(self):
        prefs = Preferences(user=self.user)
        prefs.save()
        self.try_url(reverse('bike:preferences_new'))
        self.try_url(reverse('bike:preferences'),
                     context={'preferences': prefs})
        self.try_url(reverse('bike:preferences', kwargs={'pk': prefs.pk}),
                     context={'preferences': prefs})

    def try_url(self, url, status=200, context=None, redirect=None):
        follow = redirect is not None
        with self.subTest(url=url):
            resp = self.client.get(url, follow=follow)
            if redirect is not None:
                if isinstance(redirect, str):
                    redirect = (redirect, 302)
                self.assertEqual(resp.redirect_chain[0], redirect)
            self.assertEqual(resp.status_code, status)
            if context is None:
                return

            # print("Context=", resp.context)  # lots of stuff in context...
            # a list of contexts, one per template that was rendered
            for key, value in context.items():
                with self.subTest(key=key, msg='check context'):
                    self.assertIn(key, resp.context)
                    key_value = resp.context[key]
                    if isinstance(value, list):
                        # key_value is a QuerySet
                        self.assertEqual(len(key_value), len(value),
                                         'len(values) matches')
                        self.assertEqual(list(key_value), value)
                    else:
                        self.assertEqual(key_value, value)
