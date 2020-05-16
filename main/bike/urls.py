from django.conf.urls import url
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


app_name = 'bike'  # for url namespacing
urlpatterns = [
    url(r'^$', views.home, name='home'),

    url(r'^rides$', views.rides, name='rides'),
    url(r'^ride/new$', views.RideCreate.as_view(), name='ride_new'),
    url(r'^ride$', views.RideUpdate.as_view(), name='ride'),
    url(r'^ride/(?P<pk>[0-9]+)$', views.RideUpdate.as_view(), name='ride'),

    url(r'^bikes$', views.bikes, name='bikes'),
    url(r'^bike/new$', views.BikeCreate.as_view(), name='bike_new'),
    url(r'^bike$', views.BikeUpdate.as_view(), name='bike'),
    url(r'^bike/(?P<pk>[0-9]+)$', views.BikeUpdate.as_view(), name='bike'),
    url(r'^bike/(?P<pk>[0-9]+)/delete$', views.BikeDelete.as_view(),
        name='bike_delete'),

    url(r'^components$', views.components, name='components'),
    url(r'^component/new$', views.ComponentCreate.as_view(),
        name='component_new'),
    url(r'^component$', views.ComponentUpdate.as_view(), name='component'),
    url(r'^component/(?P<pk>[0-9]+)$', views.ComponentUpdate.as_view(),
        name='component'),
    path(r'component/<int:pk>/delete', views.ComponentDelete.as_view(),
         name='component_delete'),

    url(r'^maint/new$', views.maint, name='maint_new'),
    url(r'^maint$', views.maint, name='maint'),
    url(r'^maint/(?P<pk>[0-9]+)$', views.maint, name='maint'),


    url(r'^mileage/new$', views.mileage, name='mileage_new'),
    url(r'^mileage$', views.mileage, name='mileage'),
    url(r'^mileage/(?P<pk>[0-9]+)$', views.mileage, name='mileage'),

    url(r'^preferences/new$', views.PreferencesCreate.as_view(),
        name='preferences_new'),
    url(r'^preferences$', views.PreferencesUpdate.as_view(),
        name='preferences'),
    url(r'^preferences/(?P<pk>[0-9]+)$', views.PreferencesUpdate.as_view(),
        name='preferences'),

    
    url(
        r'^admin/password_reset/$',
        auth_views.PasswordResetView.as_view(),
        name='admin_password_reset',
    ),
    url(
        r'^admin/password_reset/done/$',
        auth_views.PasswordResetDoneView.as_view(),
        name='password_reset_done',
    ),
    url(
        r'^reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>.+)/$',
        auth_views.PasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    url(
        r'^reset/done/$',
        auth_views.PasswordResetCompleteView.as_view(),
        name='password_reset_complete',
    ),
    ]
