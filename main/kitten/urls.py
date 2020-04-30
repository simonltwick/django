'''
Created on 25 Apr 2020

@author: simon
'''
from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.index, name='home'),
    url(r'^team/(?P<team_id>[0-9]+)/?$', views.team, name='team'),
    url(r'^game/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)$', views.game,
        name='game'),
    url(r'^game/new/(?P<team_id>[0-9]+)$', views.game_new, name='game_new'),
    url(r'^game/delete/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_delete, name='game_delete'),
    url(r'^game/details/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_operations, name='game_operations'),
    url(r'^game/operations/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_operations, name='game_operations'),
    url(r'^game/tick/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_tick, name='game_tick'),
    url(r'^game/clear_incidents/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_incidents_clear, name='game_incidents_clear'),
    url(r'^team/join/?$', views.team_join, name='team_join'),
    url(r'^team/new/?$', views.team_new, name='team_new')
]
