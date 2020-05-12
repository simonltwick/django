from django.conf.urls import url
from . import views


urlpatterns = [
    url(r'^$', views.home, name='home'),

    url(r'^ride/new$', views.RideCreate.as_view(), name='ride_new'),
    url(r'^ride/$', views.RideUpdate.as_view(), name='ride'),
    url(r'^ride/(?P<pk>[0-9]+)$', views.RideUpdate.as_view(), name='ride'),

    url(r'^bike/new$', views.BikeCreate.as_view(), name='bike_new'),
    url(r'^bike/$', views.BikeUpdate.as_view(), name='bike'),
    url(r'^bike/(?P<pk>[0-9]+)$', views.BikeUpdate.as_view(), name='bike'),

    url(r'^maint/new$', views.maint, name='maint'),
    url(r'^maint/(?P<pk>[0-9]+)$', views.maint, name='maint'),
    ]
