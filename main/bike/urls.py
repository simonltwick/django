from django.conf.urls import url
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


app_name = 'bike'  # for url namespacing
urlpatterns = [
    path('', views.home, name='home'),

    path('rides', views.rides, name='rides'),
    path('ride/new', views.RideCreate.as_view(), name='ride_new'),
    path('ride', views.RideUpdate.as_view(), name='ride'),
    path('ride/<int:pk>', views.RideUpdate.as_view(), name='ride'),

    path('bikes', views.bikes, name='bikes'),
    path('bike/new', views.BikeCreate.as_view(), name='bike_new'),
    # path('bike', views.BikeUpdate.as_view(), name='bike'),
    path('bike/<int:pk>', views.BikeUpdate.as_view(), name='bike'),
    path('bike/<int:pk>/delete', views.BikeDelete.as_view(),
         name='bike_delete'),

    path('components', views.components, name='components'),
    path('component/new', views.ComponentCreate.as_view(),
         name='component_new'),
    path('component', views.ComponentUpdate.as_view(), name='component'),
    path('component/<int:pk>', views.ComponentUpdate.as_view(),
         name='component'),
    path(r'component/<int:pk>/delete', views.ComponentDelete.as_view(),
         name='component_delete'),

    path('maint/new', views.maint, name='maint_new'),
    path('maint', views.maint, name='maint'),
    path('maint/<int:pk>', views.maint, name='maint'),


    path('mileage/new', views.mileage, name='mileage_new'),
    path('mileage', views.mileage, name='mileage'),
    path('mileage/<int:pk>', views.mileage, name='mileage'),

    path('component_types', views.component_types, name='component_types'),
    path('component_type/new', views.ComponentTypeCreate.as_view(),
         name='component_type_new'),
    path('component_type', views.ComponentTypeUpdate.as_view(),
         name='component_type'),
    path('component_type/<int:pk>', views.ComponentTypeUpdate.as_view(),
         name='component_type'),
    path(r'component_type/<int:pk>/delete',
         views.ComponentTypeDelete.as_view(), name='component_type_delete'),

    path('preferences/new', views.PreferencesCreate.as_view(),
         name='preferences_new'),
    path('preferences', views.PreferencesUpdate.as_view(),
         name='preferences'),
    path('preferences/<int:pk>', views.PreferencesUpdate.as_view(),
         name='preferences'),

    path('admin/password_reset/', auth_views.PasswordResetView.as_view(),
         name='admin_password_reset'),
    path('admin/password_reset/done/',
         auth_views.PasswordResetDoneView.as_view()),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(),
         name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(),
         name='password_reset_complete'),
    ]
