from django.urls import path
# from django.views.generic import TemplateView

from routes.views import MapView
from . import views

# urlpatterns = [
#     path("map/", TemplateView.as_view(template_name="map.html")),
#     ]

urlpatterns = [
    path("map/", MapView.as_view()),
    path("track/upload", views.upload_file)
]
