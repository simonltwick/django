'''
Created on 25 Apr 2020

@author: simon
'''
from django.conf.urls import url
from . import views


urlpatterns = [
    url(r'^$', views.home, name='home'),

    url(r'^team$', views.TeamNew.as_view(), name='team'),
    url(r'^team/(?P<pk>[0-9]+)$', views.TeamUpdate.as_view(),
        name='team'),
    url(r'^team/(?P<pk>[0-9]+)/delete$', views.TeamDelete.as_view(),
        name='team_delete'),
    url(r'^team/(?P<team_id>[0-9]+)/games$', views.team_games,
        name='team_games'),

    url(r'^team/(?P<team_id>[0-9]+)/invitation/new$',
        views.team_invitation_new, name='team_invitation_new'),
    url(r'^team/(?P<team_id>[0-9]+)/invitation/'
        r'(?P<invitation_id>[0-9]+)/delete',
        views.invitation_delete, name='invitation_delete'),
    url(r'^invitation/(?P<invitation_id>[0-9]+)/accept',
        views.invitation_accept, name='invitation_accept'),
    url(r'^team/(?P<team_id>[0-9]+)/member/(?P<user_id>[0-9]+)/remove',
        views.team_member_remove, name='team_member_remove'),

    url(r'^game/(?P<team_id>[0-9]+)$', views.game_new, name='game'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)$', views.game,
        name='game'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/delete',
        views.game_delete, name='game_delete'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/invitation/new',
        views.game_invitation_new, name='game_invitation_new'),
    url(r'^team/(?P<team_id>[0-9]+)/invitation/'
        r'(?P<invitation_id>[0-9]+)/accept',
        views.game_invitation_accept, name='game_invitation_accept'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)'
        r'/remove/(?P<remove_team_id>[0-9]+)',
        views.game_team_remove, name='game_team_remove'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/play',
        views.game_play, name='game_play'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/operations',
        views.game_operations, name='game_operations'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/scheduling',
        views.game_scheduling, name='game_scheduling'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/tick',
        views.game_tick, name='game_tick'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/incidents/clear',
        views.game_incidents_clear, name='game_incidents_clear'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/incident'
        r'/(?P<incident_id>[0-9]+)', views.incident, name='incident'),
    url(r'team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/boardroom',
        views.game_boardroom, name='game_boardroom'),
    url(r'team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/hr',
        views.game_hr, name='game_hr'),
    url(r'team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/engineering',
        views.game_engineering, name='game_engineering'),
]
