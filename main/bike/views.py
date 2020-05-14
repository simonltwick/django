from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from .models import Bike, MaintenanceAction, Ride, ComponentType, Component, \
    Preferences
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')


@login_required
def home(request):
    preferences_set = Preferences.objects.filter(user=request.user).exists()
    bikes = request.user.bikes
    return render(request, 'bike/home.html',
                  context={'preferences_set': preferences_set,
                           'bikes': bikes})


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
                return HttpResponseRedirect(reverse('preferences_new'))
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
    success_url = reverse_lazy('home')


class ComponentCreate(LoginRequiredMixin, CreateView):
    model = Component
    fields = ['name', 'description']

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user
        return super(ComponentCreate, self).form_valid(form)


class ComponentUpdate(LoginRequiredMixin, UpdateView):
    model = Component
    fields = ['name', 'description']

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(ComponentUpdate, self).get_success_url()


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
    return HttpResponse("not yet implemented.")
