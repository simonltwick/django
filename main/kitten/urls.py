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
    url(r'^team/delete/(?P<pk>[0-9]+)$', views.TeamDelete.as_view(),
        name='team_delete'),
    url(r'^team/games/(?P<team_id>[0-9]+)$', views.team_games,
        name='team_games'),

    url(r'^team/invitation/new/(?P<team_id>[0-9]+)$',
        views.team_invitation_new, name='team_invitation_new'),
    url(r'^team/invitation/delete/(?P<team_id>[0-9]+)/'
        r'(?P<invitation_id>[0-9]+)',
        views.invitation_delete, name='invitation_delete'),
    url(r'^team/invitation/accept/(?P<invitation_id>[0-9]+)',
        views.invitation_accept, name='invitation_accept'),
    url(r'^team/member/remove/(?P<team_id>[0-9]+)/(?P<user_id>[0-9]+)',
        views.team_member_remove, name='team_member_remove'),

    url(r'^game/(?P<team_id>[0-9]+)$', views.game_new, name='game'),
    url(r'^game/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)$', views.game,
        name='game'),
    url(r'^game/delete/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_delete, name='game_delete'),
    url(r'^game/invitation/new/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_invitation_new, name='game_invitation_new'),
    url(r'^game/invitation/accept/(?P<team_id>[0-9]+)/'
        r'(?P<invitation_id>[0-9]+)',
        views.game_invitation_accept, name='game_invitation_accept'),
    url(r'^game/team/remove/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)'
        r'/(?P<remove_team_id>[0-9]+)',
        views.game_team_remove, name='game_team_remove'),
    url(r'^game/play/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_play, name='game_play'),
    url(r'^game/operations/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_operations, name='game_operations'),
    url(r'^game/scheduling/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_scheduling, name='game_scheduling'),
    url(r'^game/tick/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_tick, name='game_tick'),
    url(r'^game/incidents_clear/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_incidents_clear, name='game_incidents_clear'),
    url(r'^game/incident/(?P<team_id>[0-9]+)/(?P<incident_id>[0-9]+)',
        views.incident, name='incident'),
    url(r'game/boardroom/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_boardroom, name='game_boardroom'),
    url(r'game/hr/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_hr, name='game_hr'),
    url(r'game/engineering/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_engineering, name='game_engineering'),
]
