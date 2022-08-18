'''
Created on 25 Apr 2020

@author: simon
'''
from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

app_name = 'kitten'  # for url namespacing
urlpatterns = [
    path('', views.home, name='home'),

    # team crud
    path('team', views.TeamNew.as_view(), name='team'),
    path('team/<int:pk>', views.TeamUpdate.as_view(),
         name='team'),
    path('team/<int:pk>/delete', views.TeamDelete.as_view(),
         name='team_delete'),
    path('team/<int:team_id>/games', views.team_games,
         name='team_games'),

    # team members invite/accept/remove
    path('team/<int:team_id>/invitation/new',
         views.team_invitation_new, name='team_invitation_new'),
    path('team/<int:team_id>/invitation/<int:invitation_id>/delete',
         views.invitation_delete, name='invitation_delete'),
    path('invitation/<int:invitation_id>/accept',
         views.invitation_accept, name='invitation_accept'),
    path('team/<int:team_id>/member/<int:user_id>/remove',
         views.team_member_remove, name='team_member_remove'),

    # game crud
    path('team/<int:team_id>/game/new', views.game_new, name='game'),
    path('team/<int:team_id>/game/<int:game_id>', views.game, name='game'),
    path('team/<int:team_id>/game/<int:pk>/delete',
         views.GameDelete.as_view(), name='game_delete'),

    # game team invite/accept/remove
    path('team/<int:team_id>/game/<int:game_id>/invitation/new',
         views.game_invitation_new, name='game_invitation_new'),
    path('team/<int:team_id>/invitation/<int:invitation_id>/accept',
         views.game_invitation_accept, name='game_invitation_accept'),
    path('team/<int:team_id>/game/<int:game_id>/remove/<int:remove_team_id>',
         views.game_team_remove, name='game_team_remove'),

    # game play management
    path('team/<int:team_id>/game/(<int:game_id>/play',
         views.game_play, name='game_play'),
    path('team/<int:team_id>/game/<int:game_id>/pause',
         views.game_pause, name='game_pause'),
    path('team/<int:team_id>/game/<int:game_id>/status',
         views.game_status, name='game_status'),

    path('team/<int:team_id>/game/<int:game_id>/tick',
         views.game_tick, name='game_tick'),
    path('team/<int:team_id>/game/<int:game_id>/debug/<int:code>',
         views.game_debug, name='game_debug'),

    path('team/<int:team_id>/game/<int:game_id>/incident/<int:incident_id>',
         views.incident, name='incident'),
    path('team/<int:team_id>)/game/<int:game_id>/incidents/clear',
         views.game_incidents_clear, name='game_incidents_clear'),
    path('team/<int:team_id>/game/<int:game_id>/incident'
         '/<int:incident_id>/debug/<int:code>',
         views.incident_debug, name='incident_debug'),

    path('team/<int:team_id>/game/<int:game_id>/operations',
         views.game_operations, name='game_operations'),
    path('team/<int:team_id>/game/<int:game_id>/scheduling',
         views.game_scheduling, name='game_scheduling'),
    path('team/<int:team_id>/game/<int:game_id>/boardroom',
         views.game_boardroom, name='game_boardroom'),
    path('team/<int:team_id>/game/<int:game_id>/marketing',
         views.game_marketing, name='game_marketing'),
    path('team/<int:team_id>/game/<int:game_id>/hr',
         views.game_hr, name='game_hr'),
    path('team/<int:team_id>/game/<int:game_id>/engineering',
         views.game_engineering, name='game_engineering'),

    path('team/<int:team_id>/network/new', views.network_new,
         name='network_new'),
    path('team/<int:team_id>/network/<int:network_id>', views.network_update,
         name='network'),
    path('team/<int:team_id>/network/<int:pk>/delete',
         views.NetworkDelete.as_view(), name='network_delete'),
    path('team/<int:team_id>/network/<int:pk>/debug/<int:code>',
         views.network_debug, name='network_debug'),

    path('network/<int:network_id> /linetemplate/new',
         views.linetemplate, name='linetemplate'),
    path('network/<int:network_id>/linetemplate/<int:linetemplate_id>',
         views.linetemplate, name='linetemplate'),
    path('linetemplate/<int:pk>/delete',
         views.LineTemplateDelete.as_view(), name='linetemplate_delete'),

    path('network/<int:network_id>/gametemplate/new',
         views.GameTemplateNew.as_view(), name='gametemplate'),
    path('network/<int:network_id>/gametemplate/<int:pk>',
         views.GameTemplateUpdate.as_view(), name='gametemplate'),
    path('gametemplate/<int:pk>/delete',
         views.GameTemplateDelete.as_view(), name='gametemplate_delete'),

    path('linetemplate/<int:linetemplate_id>/linelocation/new',
         views.linelocation, name='linelocation'),
    path('linetemplate/<int:linetemplate_id>/linelocation/'
          '<int:linelocation_id>',
        views.linelocation, name='linelocation'),

    path('admin/password_reset/',
         auth_views.PasswordResetView.as_view(), name='admin_password_reset'),
    path('admin/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view(),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',   # pattern for uidb64 was [0-9A-Za-z_\-]+
         auth_views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(),
         name='password_reset_complete'),
]
