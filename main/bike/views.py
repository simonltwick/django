import csv
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.urls import reverse, reverse_lazy
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic.edit import CreateView, UpdateView, DeleteView
import logging

from .models import Bike, MaintenanceAction, Ride, ComponentType, Component, \
    Preferences, DistanceUnits
from .forms import RideSelectionForm

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
        if 'pk' not in kwargs:
            try:
                kwargs['pk'] = Preferences.objects.get(user=request.user).pk
            except Preferences.DoesNotExist:
                return HttpResponseRedirect(reverse('bike:preferences_new'))
        elif not Preferences.objects.filter(pk=kwargs['pk'],
                                            user=request.user).exists():
            return HttpResponse("Unauthorised preferences", status=401)
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

    def dispatch(self, request, *args, **kwargs):
        if not Bike.objects.filter(pk=kwargs['pk'],
                                   owner=request.user).exists():
            return HttpResponse("Unauthorised bike", status=401)
        return super(BikeUpdate, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(UpdateView, self).get_context_data(**kwargs)
        pk = self.kwargs['pk']
        context['components'] = Component.objects.filter(bike_id=pk)
        return context

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(BikeUpdate, self).get_success_url()


class BikeDelete(LoginRequiredMixin, DeleteView):
    model = Bike
    fields = ['name', 'description']
    success_url = reverse_lazy('bike:bikes')

    def dispatch(self, request, *args, **kwargs):
        if not Bike.objects.filter(pk=kwargs['pk'],
                                   owner=request.user).exists():
            return HttpResponse("Unauthorised bike", status=401)
        return super(BikeDelete, self).dispatch(request, *args, **kwargs)


def components(request):
    components = Component.objects.filter(owner=request.user).all()
    return render(request, 'bike/components.html',
                  context={'components': components})


class ComponentCreate(LoginRequiredMixin, CreateView):
    model = Component
    fields = ['bike', 'type', 'subcomponent_of', 'name', 'specification',
              'notes', 'supplier', 'date_acquired']

    def get_initial(self):
        # Get the initial dictionary from the superclass method
        initial = super(CreateView, self).get_initial()
        # Copy the dictionary so we don't accidentally change a mutable dict
        bike_id = self.request.GET.get('bike')
        subcomp_of_id = self.request.GET.get('subcomponent_of')
        if bike_id or subcomp_of_id:
            initial = initial.copy()
            if bike_id is not None:
                bike = get_object_or_404(
                    Bike, pk=bike_id, owner=self.request.user)
                initial['bike'] = bike
            if subcomp_of_id is not None:
                subcomp_of = get_object_or_404(
                    Component, pk=subcomp_of_id, owner=self.request.user)
                initial['subcomponent_of'] = subcomp_of
        return initial

    def form_valid(self, form):
        bike_id = self.request.GET.get('bike')
        if bike_id:
            if not Bike.objects.filter(
                    pk=bike_id, owner=self.request.user).exists():
                return HttpResponse("Unauthorised or non-existent bike.",
                                    status=401)
                form.instance.bike_id = bike_id
        form.instance.owner = self.request.user
        return super(ComponentCreate, self).form_valid(form)

    def get_success_url(self):
        if self.request.method == 'POST':
            success_url = self.request.GET.get('success')
            if success_url:
                return success_url
        return super(ComponentCreate, self).get_success_url()


class ComponentUpdate(LoginRequiredMixin, UpdateView):
    model = Component
    fields = ['bike', 'type', 'subcomponent_of', 'name', 'specification',
              'notes', 'supplier', 'date_acquired']

    def dispatch(self, request, *args, **kwargs):
        if not Component.objects.filter(pk=kwargs['pk'],
                                        owner=request.user).exists():
            return HttpResponse("Unauthorised component", status=401)
        return super(ComponentUpdate, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(ComponentUpdate, self).get_success_url()


class ComponentDelete(LoginRequiredMixin, DeleteView):
    model = Component
    success_url = reverse_lazy('bike:components')

    def dispatch(self, request, *args, **kwargs):
        if not Component.objects.filter(pk=kwargs['pk'],
                                        owner=request.user).exists():
            return HttpResponse("Unauthorised component", status=401)
        return super(ComponentDelete, self).dispatch(request, *args, **kwargs)


def component_types(request):
    component_types = ComponentType.objects.filter(user=request.user).all()
    return render(request, 'bike/component_types.html',
                  context={'component_types': component_types})


class ComponentTypeCreate(LoginRequiredMixin, CreateView):
    model = ComponentType
    fields = ['type', 'subtype_of', 'description', 'maintenance_interval',
              'maint_interval_units']

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(ComponentTypeCreate, self).form_valid(form)


class ComponentTypeUpdate(LoginRequiredMixin, UpdateView):
    model = ComponentType
    fields = ['type', 'subtype_of', 'description', 'maintenance_interval',
              'maint_interval_units']

    def dispatch(self, request, *args, **kwargs):
        if not ComponentType.objects.filter(pk=kwargs['pk'],
                                            user=request.user).exists():
            return HttpResponse("Unauthorised component", status=401)
        return super(ComponentTypeUpdate, self).dispatch(
            request, *args, **kwargs)

    def get_success_url(self):
        if 'success' in self.request.GET:
            return self.request.GET['success']
        return super(ComponentTypeUpdate, self).get_success_url()


class ComponentTypeDelete(LoginRequiredMixin, DeleteView):
    model = ComponentType
    success_url = reverse_lazy('bike:component_types')

    def dispatch(self, request, *args, **kwargs):
        if not ComponentType.objects.filter(pk=kwargs['pk'],
                                            user=request.user).exists():
            return HttpResponse("Unauthorised component", status=401)
        return super(ComponentTypeDelete, self).dispatch(
            request, *args, **kwargs)


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

    def dispatch(self, request, *args, **kwargs):
        if not Ride.objects.filter(pk=kwargs['pk'],
                                   rider=request.user).exists():
            return HttpResponse("Unauthorised ride", status=401)
        return super(RideUpdate, self).dispatch(request, *args, **kwargs)


@login_required
def rides(request):
    if request.method == 'POST':
        form = RideSelectionForm(
            request.POST, bikes=Bike.objects.filter(owner=request.user).all())
        if form.is_valid():
            rides = Ride.objects.filter(rider=request.user)
            bike = form.cleaned_data['bike']
            if bike:
                rides = rides.filter(bike=bike)
            start_date = form.cleaned_data['start_date']
            if start_date:
                rides = rides.filter(date__gte=start_date)
            end_date = form.cleaned_data['end_date']
            if end_date:
                rides = rides.filter(date__lte=end_date)
            rides = rides.order_by('-date').all()
            num_rides = form.cleaned_data['num_rides']
            if num_rides:
                log.info("Applying filter num_rides=%d", num_rides)
                rides = rides[:num_rides]
            log.info("request.GET=%s", request.GET)
            if not rides.exists():
                form.add_error(None, "No rides found matching those criteria.")
            elif request.GET.get('action') == 'download_as_csv':
                log.info("csv download requested")
                fields = ['date', 'bike', 'distance', 'distance_units_display',
                          'ascent', 'ascent_units_display', 'description']
                return csv_data_response(request, 'rides.csv', rides, fields)
        else:
            rides = Ride.objects.order_by('-date').all()[:20]
    else:
        form = RideSelectionForm(
            bikes=Bike.objects.filter(owner=request.user).all())
        rides = Ride.objects.order_by('-date').all()[:20]
    return render(request, 'bike/rides.html',
                  context={'form': form, 'rides': rides})


def csv_data_response(request, filename, queryset, fields):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(fields)  # header row
    for row in queryset.all():
        csv_row = [getattr(row, field_name) for field_name in fields]
        writer.writerow(csv_row)
    return response


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
