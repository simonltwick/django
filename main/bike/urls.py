from django.conf.urls import url
from . import views


urlpatterns = [
    url(r'^$', views.home, name='home'),

    url(r'^ride/new$', views.RideCreate.as_view(), name='ride_new'),
    url(r'^ride$', views.RideUpdate.as_view(), name='ride'),
    url(r'^ride/(?P<pk>[0-9]+)$', views.RideUpdate.as_view(), name='ride'),

    url(r'^bike/new$', views.BikeCreate.as_view(), name='bike_new'),
    url(r'^bike$', views.BikeUpdate.as_view(), name='bike'),
    url(r'^bike/(?P<pk>[0-9]+)$', views.BikeUpdate.as_view(), name='bike'),
    url(r'^bike/(?P<pk>[0-9]+)/delete$', views.BikeDelete.as_view(),
        name='bike_delete'),

    url(r'^component/new$', views.ComponentCreate.as_view(),
        name='component_new'),
    url(r'^component$', views.ComponentUpdate.as_view(), name='component'),
    url(r'^component/(?P<pk>[0-9]+)$', views.ComponentUpdate.as_view(),
        name='component'),

    url(r'^maint/new$', views.maint, name='maint_new'),
    url(r'^maint$', views.maint, name='maint'),
    url(r'^maint/(?P<pk>[0-9]+)$', views.maint, name='maint'),

    url(r'^preferences/new$', views.PreferencesCreate.as_view(),
        name='preferences_new'),
    url(r'^preferences$', views.PreferencesUpdate.as_view(),
        name='preferences'),
    url(r'^preferences/(?P<pk>[0-9]+)$', views.PreferencesUpdate.as_view(),
        name='preferences'),
    ]
