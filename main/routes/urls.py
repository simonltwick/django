from django.urls import path
# from django.views.generic import TemplateView

from . import views


app_name = 'routes'  # for url namespacing

urlpatterns = [
#     path("map/", TemplateView.as_view(template_name="map.html")),
    path("map/", views.map, name="map"),
    path("gpx/upload", views.upload_gpx, name="gpx_upload"),
    path("gpx/view", views.upload_gpx, {"save": False}, name="gpx_view"),
    # path("track/test", views.test_save_gpx),
    path("track/<int:pk>", views.track, name='track'),
    # path("track/<trackids>", views.TracksView.as_view(), name="tracks_view"),
    # path("csrf/", views.test_csrf),
    path("api/search/", views.search, name="search"),
    # path("api/search/<search_type>", views.search, name="search"),
    path("api/track", views.track_json),
    path("api/place", views.place_json),
    path("place/", views.place, name="place"),
    path("place/<int:pk>", views.place, name="place"),
    path("place/<int:pk>/delete", views.place_delete),
    path("place/<int:pk>/move", views.place_move),
    path("place/upload", views.upload_csv, name="upload_csv"),
    path("place/types", views.PlaceTypeListView.as_view(),
         name="place_types"),
    path("place/type/", views.PlaceTypeCreateView.as_view(),
         name="place_type"),
    path("place/type/<int:pk>", views.PlaceTypeUpdateView.as_view(),
         name="place_type"),
    path("place/type/<int:pk>/delete", views.PlaceTypeDeleteView.as_view(),
         name="place_type_delete"),
    path("api/place/types/icons", views.place_type_list_json,
         name="api_place_types"),
    path("tags/place/<int:pk>", views.place_tags),
    path("tags/track/<int:pk>", views.track_tags),
    path("preference", views.preference),
    path("api/preference", views.preference_as_json, name="api_preference"),
    path("logout/", views.do_logout, name="logout"),
]
