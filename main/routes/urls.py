from django.urls import path
# from django.views.generic import TemplateView

from . import views


app_name = 'routes'  # for url namespacing

urlpatterns = [
#     path("map/", TemplateView.as_view(template_name="map.html")),
    path("map/", views.MapView.as_view()),
    path("track/upload", views.upload_file),
    # path("track/test", views.test_save_gpx),
    path("track/<trackids>", views.TracksView.as_view(), name="tracks_view")
]
