from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
from django.urls import reverse

from .models import (
    Team, GameLevel, Game, TeamInvitation,
    )


class UrlTest(TestCase):
    """ check urls work """

    @override_settings(
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', ])
    def setUp(self):
        self.user = User.objects.create(
            username='tester', password=make_password('testpw'))
        self.user.save()
        self.team = Team.objects.create(name='Test team',
                                        level=GameLevel.BASIC)
        self.team.save()
        self.team.members.add(self.user)
        self.game = Game.objects.create(
            name='Test game', network_name='network', level=GameLevel.BASIC)
        self.game.save()
        self.game.teams.add(self.team)
        self.client = Client(raise_request_exception=True)
        self.client.login(username='tester', password='testpw')

    def test_home(self):
        self.try_url(reverse('kitten:home'), context={'teams': [self.team]})

    def test_team(self):
        tid = self.team.id
        self.try_url(reverse('kitten:team'))
        self.try_url(reverse('kitten:team', kwargs={'pk': tid}),
                     context={'team': self.team})
        self.try_url(reverse('kitten:team_delete', kwargs={'pk': tid}),
                     context={'team': self.team})
        self.try_url(reverse('kitten:team_games', kwargs={'team_id': tid}),
                     context={'team': self.team, 'games': [self.game]})

    @override_settings(
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher', ])
    def test_team_invitation(self):
        # invite/accept/remove
        tid = self.team.id
        self.try_url(
            reverse('kitten:team_invitation_new', kwargs={'team_id': tid}),
            context={'team': self.team})

        user2 = User.objects.create(username='tester2',
                                    password=make_password('test2pw'))
        user2.save()
        inv = TeamInvitation.objects.create(team=self.team,
                                            invitee_username=user2,
                                            password='pass',
                                            invited_by=self.user)
        inv.save()
        self.client.login(username='tester2', password='test2pw')

        self.try_url(reverse('kitten:invitation_accept',
                             kwargs={'invitation_id': inv.id}),
                     context={'invitation': inv})
        self.client.login(username='tester', password='testpw')
        self.try_url(reverse('kitten:invitation_delete',
                             kwargs={'team_id': tid, 'invitation_id': inv.id}),
                     redirect=reverse('kitten:team', kwargs={'pk': tid}))
        self.team.members.add(user2)
        self.try_url(reverse('kitten:team_member_remove',
                             kwargs={'team_id': tid, 'user_id': user2.id}),
                     redirect=reverse('kitten:team', kwargs={'pk': tid}))
        self.team.members.remove(user2)
        inv.delete()
        user2.delete()

    def test_game_crud(self):
        tid = self.team.id
        gid = self.game.id
        self.try_url(reverse('kitten:game', kwargs={'team_id': tid}),
                     context={'team': self.team})
        self.try_url(reverse('kitten:game',
                             kwargs={'team_id': tid, 'game_id': gid}),
                     context={'team_id': tid, 'game': self.game})
        self.try_url(reverse('kitten:game_delete',
                             kwargs={'team_id': tid, 'pk': gid}),
                     context={'game': self.game})

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
