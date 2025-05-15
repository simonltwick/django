from django.urls import path
# from django.views.generic import TemplateView

from routes.views import MapView

# urlpatterns = [
#     path("map/", TemplateView.as_view(template_name="map.html")),
#     ]

urlpatterns = [
    path("map/", MapView.as_view()),
]
