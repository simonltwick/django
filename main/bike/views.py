from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.urls import reverse, reverse_lazy
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from .models import Bike, MaintenanceAction, Ride, ComponentType, Component, \
    Preferences, DistanceUnits
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')


@login_required
def home(request):
    preferences_set = Preferences.objects.filter(user=request.user).exists()
    return render(request, 'bike/home.html',
                  context={'preferences_set': preferences_set})


@login_required
def bikes(request):
    bikes = (Bike.objects.values('id', 'name', 'rides__distance_units')
             .annotate(distance=Sum('rides__distance'))
             .filter(owner=request.user))
    # change distance_units into distance
    bikes = [row for row in bikes.all()]  # QuerySet -> List
    for row in bikes:
        if row['rides__distance_units'] is None:
            row['rides__distance_units'] = ''
        else:
            row['rides__distance_units'] = DistanceUnits(
                row['rides__distance_units']).name.lower()
    log.info("bikes=%s", bikes)
    return render(request, 'bike/bikes.html',
                  context={'bikes': bikes})


class PreferencesCreate(LoginRequiredMixin, CreateView):
    model = Preferences
    fields = ['distance_units', 'ascent_units']

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        return super(PreferencesCreate, self).form_valid(form)


class PreferencesUpdate(LoginRequiredMixin, UpdateView):
    model = Preferences
    fields = ['distance_units', 'ascent_units']

    def dispatch(self, request, *args, **kwargs):
        log.info("PreferencesUpdate called with kwargs=%s", kwargs)
        if 'pk' not in kwargs:
            try:
                kwargs['pk'] = Preferences.objects.get(user=request.user).pk
            except Preferences.DoesNotExist:
                return HttpResponseRedirect(reverse('bike:preferences_new'))
        return super(PreferencesUpdate, self).dispatch(request, *args,
                                                       **kwargs)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(PreferencesUpdate, self).get_success_url()


class BikeCreate(LoginRequiredMixin, CreateView):
    model = Bike
    fields = ['name', 'description']

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user
        return super(BikeCreate, self).form_valid(form)


class BikeUpdate(LoginRequiredMixin, UpdateView):
    model = Bike
    fields = ['name', 'description']

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(BikeUpdate, self).get_success_url()


class BikeDelete(LoginRequiredMixin, DeleteView):
    model = Bike
    fields = ['name', 'description']
    success_url = reverse_lazy('bike:bikes')


def components(request):
    components = Component.objects.filter(owner=request.user).all()
    return render(request, 'bike/components.html',
                  context={'components': components})


class ComponentCreate(LoginRequiredMixin, CreateView):
    model = Component
    fields = ['bike', 'type', 'subcomponent_of', 'name', 'specification',
              'notes', 'supplier', 'date_acquired']

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user
        return super(ComponentCreate, self).form_valid(form)


class ComponentUpdate(LoginRequiredMixin, UpdateView):
    model = Component
    fields = ['bike', 'type', 'subcomponent_of', 'name', 'specification',
              'notes', 'supplier', 'date_acquired']

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(ComponentUpdate, self).get_success_url()


class ComponentDelete(LoginRequiredMixin, DeleteView):
    model = Component
    success_url = reverse_lazy('bike:components')


def rides(request):
    rides = Ride.objects.filter(rider=request.user).order_by('-date')[:20]
    return render(request, 'bike/rides.html', context={'rides': rides})


class RideCreate(LoginRequiredMixin, CreateView):
    model = Ride
    fields = ['bike', 'date', 'description', 'distance', 'distance_units',
              'ascent', 'ascent_units']

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.rider = self.request.user
        return super(RideCreate, self).form_valid(form)


class RideUpdate(LoginRequiredMixin, UpdateView):
    model = Ride
    fields = ['bike', 'date', 'description', 'distance', 'distance_units',
              'ascent', 'ascent_units']

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(RideUpdate, self).get_success_url()


@login_required
def maint(request, pk=None):
    # maintenance activities, maintenance schedule ...
    return HttpResponse("maintenance activities, maintenance schedule ... "
                        "not yet implemented.")


@login_required
def mileage(request, pk=None):
    # odometer and recent mileage stuff for bikes / a bike ...
    return HttpResponse("odometer and recent mileage stuff for bikes / a bike "
                        "...not yet implemented.")
