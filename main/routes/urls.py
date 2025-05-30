from django.urls import path
# from django.views.generic import TemplateView

from routes.views import MapView
from . import views


app_name = 'routes'  # for url namespacing

urlpatterns = [
#     path("map/", TemplateView.as_view(template_name="map.html")),
    path("map/", MapView.as_view()),
    path("track/upload", views.upload_file),
    path("track/test", views.test_save_gpx),
    path("tracks/view/<trackids>", views.show_tracks, name="tracks_view")
]
