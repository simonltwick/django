from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.urls import reverse

from .models import (
    Bike, ComponentType, Ride, Component, MaintenanceAction
    )


class BikeUrlTest(TestCase):
    """ check urls work """

    @override_settings(
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', ])
    def setUp(self):
        self.user = User.objects.create(
            username='tester', password=make_password('testpw'))
        self.user.save()
        self.bike = Bike.objects.create(
            name='Test bike', description="test", owner=self.user)
        self.bike.save()
        self.ct = ComponentType.objects.create(user=self.user, type="Test type")
        self.ct.save()
        self.client = Client(raise_request_exception=True)
        self.client.login(username='tester', password='testpw')

    def test_home(self):
        self.try_url(reverse('bike:home'), context={'preferences_set': False})

    def test_ride(self):
        ride = Ride.objects.create(rider=self.user, bike=self.bike)
        ride.save()
        rid = ride.id
        self.try_url(reverse('bike:rides'), context={'rides': [ride]})
        self.try_url(reverse('bike:ride', kwargs={'pk': rid}),
                     context={'ride': ride})
        self.try_url(reverse('bike:ride_delete', kwargs={'pk': rid}),
                     context={'ride': ride})
        self.try_url(reverse('bike:ride_new'))

    def test_bike(self):
        bid = self.bike.id
        self.try_url(reverse('bike:bikes'))
        self.try_url(reverse('bike:bike', kwargs={'pk': bid}),
                     context={'bike': self.bike})
        self.try_url(reverse('bike:bike_delete', kwargs={'pk': bid}))
        self.try_url(reverse('bike:bike_new'),)

    def test_component(self):
        comp = Component.objects.create(type=self.ct, name='Test component',
                                        owner=self.user)
        self.try_url(reverse('bike:components'))
        self.try_url(reverse('bike:component', kwargs={'pk': comp.id}),
                     context={'component': comp})
        self.try_url(reverse('bike:component_delete', kwargs={'pk': comp.id}),
                     context={'component': comp})
        self.try_url(reverse('bike:component_new'),)

    def test_component_type(self):
        ct = self.ct
        self.try_url(reverse('bike:component_types'))
        self.try_url(reverse('bike:component_type', kwargs={'pk': ct.id}),
                     context={'componenttype': ct})
        self.try_url(reverse('bike:component_type_delete',
                             kwargs={'pk': ct.id}))
        self.try_url(reverse('bike:component_type_new'),)

    def test_maint_action(self):
        maint = MaintenanceAction.objects.create(
            bike=self.bike, user=self.user)
        maint.save()
        self.try_url(reverse('bike:maint_actions'))
        self.try_url(reverse('bike:maint', kwargs={'pk': maint.id}),
                     context={'maintenanceaction': maint})
        self.try_url(reverse('bike:maint_delete',
                             kwargs={'pk': maint.id}))
        self.try_url(reverse('bike:maint_new'),)

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
                        self.assertEqual(len(key_value), len(value))
                        self.assertEqual(list(key_value), value)
                    else:
                        self.assertEqual(key_value, value)
