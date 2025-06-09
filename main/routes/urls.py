from django.urls import path
# from django.views.generic import TemplateView

from . import views


app_name = 'routes'  # for url namespacing

urlpatterns = [
#     path("map/", TemplateView.as_view(template_name="map.html")),
    path("map/", views.MapView.as_view()),
    path("gpx/upload", views.upload_file, name="upload_gpx"),
    path("gpx/view", views.upload_file, {"save": False}, name="view_gpx"),
    # path("track/test", views.test_save_gpx),
    path("track/<trackids>", views.TracksView.as_view(), name="tracks_view")
]
