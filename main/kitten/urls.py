'''
Created on 25 Apr 2020

@author: simon
'''
from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.index, name='home'),
    url(r'^games/?$', views.games, name='games'),
    url(r'^games/(?P<team_id>[0-9]+)/?$', views.games, name='games'),
    url(r'^game/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)$', views.game,
        name='game'),
    url(r'^game/new/(?P<team_id>[0-9]+)$', views.game_new, name='game_new'),
    url(r'^game/delete/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_delete, name='game_delete'),
    url(r'^game/details/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_details, name='game_details'),
    url(r'^game/operations/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_details, name='game_operations'),
    url(r'^game/tick/(?P<game_id>[0-9]+)/(?P<team_id>[0-9]+)',
        views.game_tick, name='game_tick'),
    url(r'^team/join/?$', views.team_join, name='team_join'),
    url(r'^team/new/?$', views.team_new, name='team_new')
]
