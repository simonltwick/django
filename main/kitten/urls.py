'''
Created on 25 Apr 2020

@author: simon
'''
from django.conf.urls import url
from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

app_name = 'kitten'  # for url namespacing
urlpatterns = [
    path('', views.home, name='home'),

    # team crud
    path('team/<int:pk>', views.TeamUpdate.as_view(),
         name='team'),
    path('team/<int:pk>/delete', views.TeamDelete.as_view(),
         name='team_delete'),
    path('team/<int:team_id>/games', views.team_games,
         name='team_games'),
    path('team', views.TeamNew.as_view(), name='team'),

    # team members invite/accept/remove
    url(r'^team/(?P<team_id>[0-9]+)/invitation/new$',
        views.team_invitation_new, name='team_invitation_new'),
    url(r'^team/(?P<team_id>[0-9]+)/invitation/'
        r'(?P<invitation_id>[0-9]+)/delete',
        views.invitation_delete, name='invitation_delete'),
    url(r'^invitation/(?P<invitation_id>[0-9]+)/accept',
        views.invitation_accept, name='invitation_accept'),
    url(r'^team/(?P<team_id>[0-9]+)/member/(?P<user_id>[0-9]+)/remove',
        views.team_member_remove, name='team_member_remove'),

    # game crud
    path('team/<int:team_id>/game/new', views.game_new, name='game'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)$', views.game,
        name='game'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/delete',
        views.game_delete, name='game_delete'),

    # game team invite/accept/remove
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/invitation/new',
        views.game_invitation_new, name='game_invitation_new'),
    url(r'^team/(?P<team_id>[0-9]+)/invitation/'
        r'(?P<invitation_id>[0-9]+)/accept',
        views.game_invitation_accept, name='game_invitation_accept'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)'
        r'/remove/(?P<remove_team_id>[0-9]+)',
        views.game_team_remove, name='game_team_remove'),

    # game play management
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/play',
        views.game_play, name='game_play'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/pause',
        views.game_pause, name='game_pause'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/status$',
        views.game_status, name='game_status'),

    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/tick',
        views.game_tick, name='game_tick'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/debug/'
        '(?P<code>[0-9]+)', views.game_debug, name='game_debug'),

    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/incident'
        r'/(?P<incident_id>[0-9]+)$', views.incident, name='incident'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/incidents/clear',
        views.game_incidents_clear, name='game_incidents_clear'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/incident'
        r'/(?P<incident_id>[0-9]+)/debug/(?P<code>[0-9]+)',
        views.incident_debug, name='incident_debug'),

    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/operations',
        views.game_operations, name='game_operations'),
    url(r'^team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/scheduling',
        views.game_scheduling, name='game_scheduling'),
    url(r'team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/boardroom',
        views.game_boardroom, name='game_boardroom'),
    url(r'team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/marketing',
        views.game_marketing, name='game_marketing'),
    url(r'team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/hr',
        views.game_hr, name='game_hr'),
    url(r'team/(?P<team_id>[0-9]+)/game/(?P<game_id>[0-9]+)/engineering',
        views.game_engineering, name='game_engineering'),

    path('team/<int:team_id>/network/new', views.network_new,
         name='network_new'),
    path('team/<int:team_id>/network/<int:network_id>', views.network_update,
         name='network'),
    path('team/<int:team_id>/network/<int:pk>/delete',
         views.NetworkDelete.as_view(), name='network_delete'),
    path('team/<int:team_id>/network/<int:pk>/debug/<int:code>',
         views.network_debug, name='network_debug'),

    url(r'network/(?P<network_id>[0-9]+)/linetemplate/new',
        views.linetemplate, name='linetemplate'),
    url(r'network/(?P<network_id>[0-9]+)/linetemplate/'
        r'(?P<linetemplate_id>[0-9]+)', views.linetemplate,
        name='linetemplate'),
    url(r'linetemplate/(?P<pk>[0-9]+)/delete',
        views.LineTemplateDelete.as_view(), name='linetemplate_delete'),

    url(r'network/(?P<network_id>[0-9]+)/gametemplate/new',
        views.GameTemplateNew.as_view(), name='gametemplate'),
    url(r'network/(?P<network_id>[0-9]+)/gametemplate/(?P<pk>[0-9]+)',
        views.GameTemplateUpdate.as_view(),
        name='gametemplate'),
    url(r'gametemplate/(?P<pk>[0-9]+)/delete',
        views.GameTemplateDelete.as_view(), name='gametemplate_delete'),

    url(r'linetemplate/(?P<linetemplate_id>[0-9]+)/linelocation/new',
        views.linelocation, name='linelocation'),
    url(r'linetemplate/(?P<linetemplate_id>[0-9]+)/linelocation/'
        r'(?P<linelocation_id>[0-9]+)',
        views.linelocation, name='linelocation'),

    url(r'^admin/password_reset/$',
        auth_views.PasswordResetView.as_view(), name='admin_password_reset'),
    url(r'^admin/password_reset/done/$',
        auth_views.PasswordResetDoneView.as_view(),
        name='password_reset_done'),
    url(r'^reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$',
        auth_views.PasswordResetConfirmView.as_view(),
        name='password_reset_confirm'),
    url(r'^reset/done/$', auth_views.PasswordResetCompleteView.as_view(),
        name='password_reset_complete'),
]
