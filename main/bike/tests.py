from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.urls import reverse

from .models import (
    Bike,
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
        self.client = Client(raise_request_exception=True)
        self.client.login(username='tester', password='testpw')

    def test_home(self):
        self.try_url(reverse('bike:home'), context={'preferences_set': False})

    def test_bike(self):
        bid = self.bike.id
        self.try_url(reverse('bike:bikes'))
        self.try_url(reverse('bike:bike', kwargs={'pk': bid}),
                     context={'team': self.team})
        self.try_url(reverse('bike:bike_delete', kwargs={'pk': bid}))
        self.try_url(reverse('bike:bike_new'),)

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
