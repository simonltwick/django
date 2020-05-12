from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic.edit import CreateView, UpdateView
from .models import Bike, MaintenanceAction, Ride
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')


@login_required
def home(request):
    return render(request, 'bike/home.html')


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
