from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Q, Max
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
# from django.views.generic.dates import MonthArchiveView

import csv
import datetime as dt
import logging
from typing import List, Tuple, Optional, Dict

from .models import (
    Bike, Ride, ComponentType, Component, Preferences, MaintenanceAction,
    DistanceUnits, MaintenanceActionHistory, MaintenanceType, Odometer,
    # MaintActionLink
    )
from .forms import (
    RideSelectionForm, RideForm, PreferencesForm,
    MaintenanceActionUpdateForm, MaintCompletionDetailsForm,
    OdometerFormSet, OdometerAdjustmentForm, DateTimeForm,
    MaintActionLinkFormSet)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

LOGIN_URL = '/bike/login?next=/bike'
CURRENT_TIMEZONE = timezone.get_current_timezone()


class BikeLoginRequiredMixin(LoginRequiredMixin):
    login_url = LOGIN_URL


@login_required(login_url=LOGIN_URL)
def home(request):
    preferences_set = Preferences.objects.filter(user=request.user).exists()
    maint = (upcoming_maint(request.user) if preferences_set else None)
    return render(request, 'bike/home.html',
                  context={'preferences_set': preferences_set,
                           'upcoming_maint': maint})


@login_required(login_url=LOGIN_URL)
def bikes(request):
    today = timezone.now()
    sum_year = Sum('rides__distance', filter=Q(rides__date__year=today.year))
    sum_month = Sum('rides__distance', filter=(
        Q(rides__date__month=today.month) & Q(rides__date__year=today.year)))
    # rides_year = (Ride.objects.filter(rider=request.user)
    #               .filter(date__year=today.year).all())
    # log.info("rides_year=\n\t%s", '\n\t'.join(
    #     f"{ride.bike.name}: {ride.date.date()} {ride.distance:0.1f}"
    #     for ride in rides_year))
    maint = (MaintenanceAction.objects
             .filter(user=request.user, bike__isnull=False, completed=False)
             .order_by('bike_id')
             .all())
    bikes = Bike.objects.filter(owner=request.user)
    mileage = (bikes
               .filter(rides__distance_units__isnull=False)
               .values('id', 'rides__distance_units')
               .annotate(
                   distance=Sum('rides__distance'),
                   distance_year=sum_year,
                   distance_month=sum_month,
                         )
               )
    bikes = bikes.annotate(
        last_ridden=Max('rides__date', filter=Q(rides__is_adjustment=False))
        ).order_by('-last_ridden').all()
    # bikes is a queryset of dicts, one for each bike/distance_unit combo
    for entry in mileage:
        entry['distance_units'] = DistanceUnits(  # km or miles
            entry['rides__distance_units']).name.lower()
    # log.info("mileage=%s", mileage)
    # log.info("maint=%s", maint)
    # add maint details to bike entries
    bikes_by_id = {bike.id: bike for bike in bikes}
    for entry in mileage:
        bike = bikes_by_id[entry['id']]
        try:
            bike.mileage.append(entry)
        except AttributeError:
            bike.mileage = [entry]
    for entry in maint:
        bike = bikes_by_id[entry.bike_id]
        # log.info("maint %s for bike %s", maint, bike)
        try:
            bike.maint_upcoming.append(entry)
        except AttributeError:
            bike.maint_upcoming = [entry]
    monthname = today.strftime('%b')  # eg. Jan
    return render(request, 'bike/bikes.html',
                  context={'bikes': bikes, 'today': today,
                           'monthname': monthname})


class PreferencesCreate(BikeLoginRequiredMixin, CreateView):
    form_class = PreferencesForm
    model = Preferences
    # fields = ['distance_units', 'ascent_units',
    #           'maint_distance_limit', 'maint_time_limit']

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        return super(PreferencesCreate, self).form_valid(form)


class PreferencesUpdate(BikeLoginRequiredMixin, UpdateView):
    form_class = PreferencesForm
    model = Preferences
    # fields = PreferencesCreate.fields

    def dispatch(self, request, *args, **kwargs):
        if 'pk' not in self.kwargs:
            try:
                prefs_pk = Preferences.objects.get(user=request.user).pk
                self.kwargs['pk'] = prefs_pk
            except Preferences.DoesNotExist:
                return HttpResponseRedirect(reverse('bike:preferences_new'))
        elif not Preferences.objects.filter(pk=self.kwargs['pk'],
                                            user=request.user).exists():
            return HttpResponse("Unauthorised preferences", status=401)
        return super(PreferencesUpdate, self).dispatch(request, *args,
                                                       **kwargs)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(PreferencesUpdate, self).get_success_url()


class BikeDetail(BikeLoginRequiredMixin, DetailView):
    model = Bike

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_url"] = (
            self.request.GET["next"] if "next" in self.request.GET
            else reverse("bike:home"))
        preferences = Preferences.objects.get(user=self.request.user)
        context['distance_units'] = preferences.get_distance_units_display()
        pk = self.kwargs['pk']
        context['components'] = Component.objects.filter(bike_id=pk)
        return add_maint_context(context, self.request.user, bike_id=pk)


class BikeCreate(BikeLoginRequiredMixin, CreateView):
    model = Bike
    fields = ['name', 'description']

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user
        return super(BikeCreate, self).form_valid(form)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(RideCreate, self).get_success_url()


class BikeUpdate(BikeLoginRequiredMixin, UpdateView):
    model = Bike
    fields = ['name', 'description']

    def dispatch(self, request, *args, **kwargs):
        if not Bike.objects.filter(pk=kwargs['pk'],
                                   owner=request.user).exists():
            return HttpResponse("Unauthorised bike", status=401)
        return super(BikeUpdate, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BikeUpdate, self).get_context_data(**kwargs)
        pk = self.kwargs['pk']
        context['components'] = Component.objects.filter(bike_id=pk)
        return add_maint_context(context, self.request.user, bike_id=pk)

    def form_valid(self, form):
        resp = super(BikeUpdate, self).form_valid(form)
        return resp

    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return super(BikeUpdate, self).get_success_url()


def add_maint_context(context: dict, user, bike_id=None, component_id=None):
    """ add upcoming maintenance & maintenance history for a bike or cpt """
    distance_units = user.preferences.get_distance_units_display()
    context['distance_units'] = distance_units
    if bike_id is None and component_id is None:
        return context

    context['maint_upcoming'] = upcoming = MaintenanceAction.upcoming(
        user=user, bike_id=bike_id, component_id=component_id,
        filter_by_limits=False).all()
    for ma in upcoming:
        ma.due = ma.due_in(distance_units)

    context['maint_history'] = MaintenanceAction.history(
        user=user, bike_id=bike_id, component_id=component_id)
    return context


class BikeDelete(BikeLoginRequiredMixin, DeleteView):
    model = Bike
    fields = ['name', 'description']
    success_url = reverse_lazy('bike:bikes')

    def dispatch(self, request, *args, **kwargs):
        if not Bike.objects.filter(pk=kwargs['pk'],
                                   owner=request.user).exists():
            return HttpResponse("Unauthorised bike", status=401)
        return super(BikeDelete, self).dispatch(request, *args, **kwargs)


@login_required(login_url=LOGIN_URL)
def components(request):
    components = (Component.objects
                  .filter(owner=request.user)
                  .order_by('type')
                  .select_related('type', 'bike')
                  .all())
    return render(request, 'bike/components.html',
                  context={'components': components})


class ComponentCreate(BikeLoginRequiredMixin, CreateView):
    model = Component
    fields = ['type', 'name', 'bike', 'subcomponent_of', 'specification',
              'notes', 'supplier', 'date_acquired']

    def get_initial(self):
        # Get the initial dictionary from the superclass method
        initial = super(ComponentCreate, self).get_initial()
        # Copy the dictionary so we don't accidentally change a mutable dict
        bike_id = self.request.GET.get('bike')
        subcomp_of_id = self.request.GET.get('subcomponent_of')
        component_type_id = self.request.GET.get('component_type')
        if bike_id or subcomp_of_id or component_type_id:
            initial = initial.copy()
            if bike_id is not None:
                bike = get_object_or_404(
                    Bike, pk=bike_id, owner=self.request.user)
                initial['bike'] = bike
            if subcomp_of_id is not None:
                subcomp_of = get_object_or_404(
                    Component, pk=subcomp_of_id, owner=self.request.user)
                initial['subcomponent_of'] = subcomp_of
            if component_type_id is not None:
                ctype = get_object_or_404(ComponentType, pk=component_type_id,
                                          user=self.request.user)
                initial['type'] = ctype
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
        ret = super(ComponentCreate, self).form_valid(form)  # save inst
        self.copy_maintenance_types(form.instance)
        return ret

    def get_success_url(self):
        if self.request.method == 'POST':
            success_url = self.request.GET.get('success')
            if success_url:
                return success_url
        return super(ComponentCreate, self).get_success_url()

    def copy_maintenance_types(self, cpt):
        """ if this cpt has a cpt_type, create new MaintenanceActions for this
        cpt, based on the MaintenanceTypes for the cpt_type """
        cpt_type = cpt.type
        if cpt_type is None:
            return
        for maint_type in cpt_type.maintenance_types.filter(
                user=cpt.owner).all():
            ma = MaintenanceAction(
                user=cpt.owner, bike=cpt.bike, component=cpt,
                maint_type=maint_type, recurring=maint_type.recurring,
                maintenance_interval_distance=(
                    maint_type.maintenance_interval_distance),
                maint_interval_days=maint_type.maint_interval_days)
            ma.save()


class ComponentUpdate(BikeLoginRequiredMixin, UpdateView):
    model = Component
    fields = ['type', 'name', 'bike', 'subcomponent_of', 'specification',
              'notes', 'supplier', 'date_acquired']

    def dispatch(self, request, *args, **kwargs):
        if not Component.objects.filter(
                pk=kwargs['pk'], owner=request.user).exists():
            return HttpResponse("Unauthorised component", status=401)
        return super(ComponentUpdate, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """ save the form and redirect to get_success_url() """
        instance = form.instance
        old_instance = Component.objects.get(pk=instance.pk)
        instance.update_bike_info(old_instance)
        return super().form_valid(form)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(ComponentUpdate, self).get_success_url()

    def get_context_data(self):
        context = super(ComponentUpdate, self).get_context_data()
        subcomponents = Component.objects.filter(
            subcomponent_of=self.object).all()
        context['subcomponents'] = subcomponents
        return add_maint_context(
            context, self.request.user, component_id=self.object.id)


class ComponentDelete(BikeLoginRequiredMixin, DeleteView):
    model = Component
    success_url = reverse_lazy('bike:components')

    def dispatch(self, request, *args, **kwargs):
        if not Component.objects.filter(pk=kwargs['pk'],
                                        owner=request.user).exists():
            return HttpResponse("Unauthorised component", status=401)
        return super(ComponentDelete, self).dispatch(request, *args, **kwargs)


@login_required(login_url=LOGIN_URL)
def component_types(request):
    component_types = ComponentType.objects.filter(user=request.user).all()
    return render(request, 'bike/component_types.html',
                  context={'component_types': component_types})


class ComponentTypeCreate(BikeLoginRequiredMixin, CreateView):
    model = ComponentType
    fields = ['type', 'subtype_of', 'description']

    def get_initial(self):
        # Get the initial dictionary from the superclass method
        initial = super(ComponentTypeCreate, self).get_initial()
        # Copy the dictionary so we don't accidentally change a mutable dict
        subtype_of = self.request.GET.get('subtype_of')
        if subtype_of is not None:
            initial = initial.copy()
            get_object_or_404(
                ComponentType, pk=subtype_of, user=self.request.user)
            initial['subtype_of'] = subtype_of
        return initial

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super(ComponentTypeCreate, self).form_valid(form)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(ComponentTypeCreate, self).get_success_url()


class ComponentTypeUpdate(BikeLoginRequiredMixin, UpdateView):
    model = ComponentType
    fields = ['type', 'subtype_of', 'description', ]

    def dispatch(self, request, *args, **kwargs):
        if not ComponentType.objects.filter(pk=kwargs['pk'],
                                            user=request.user).exists():
            return HttpResponse("Unauthorised component", status=401)
        return super(ComponentTypeUpdate, self).dispatch(
            request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ComponentTypeUpdate, self).get_context_data(**kwargs)
        context['components'] = self.object.components.all()
        return context

    def get_success_url(self):
        if 'success' in self.request.GET:
            return self.request.GET['success']
        return super(ComponentTypeUpdate, self).get_success_url()


class ComponentTypeDelete(BikeLoginRequiredMixin, DeleteView):
    model = ComponentType
    success_url = reverse_lazy('bike:component_types')

    def dispatch(self, request, *args, **kwargs):
        if not ComponentType.objects.filter(pk=kwargs['pk'],
                                            user=request.user).exists():
            return HttpResponse("Unauthorised component", status=401)
        return super(ComponentTypeDelete, self).dispatch(
            request, *args, **kwargs)


class RideCreate(BikeLoginRequiredMixin, CreateView):
    model = Ride
    form_class = RideForm

    def get_initial(self):
        initial = super(RideCreate, self).get_initial()
        self.bike = Bike.objects.filter(
            owner=self.request.user).order_by('-rides__date').first()
        # copy, so we don't accidentally change a mutable dict
        initial = initial.copy()
        initial['bike'] = self.bike
        return initial

    def get_context_data(self, **kwargs):
        context = super(RideCreate, self).get_context_data(**kwargs)
        context['bike_id'] = self.bike.id
        return context

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.rider = self.request.user
        return super(RideCreate, self).form_valid(form)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(RideCreate, self).get_success_url()


class RideUpdate(BikeLoginRequiredMixin, UpdateView):
    model = Ride
    form_class = RideForm

    def dispatch(self, request, *args, **kwargs):
        if not Ride.objects.filter(pk=kwargs['pk'],
                                   rider=request.user).exists():
            return HttpResponse("Unauthorised ride", status=401)
        return super(RideUpdate, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(RideUpdate, self).get_context_data(**kwargs)
        context['bike_id'] = self.object.bike_id
        return context

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(RideUpdate, self).get_success_url()


class RideDelete(BikeLoginRequiredMixin, DeleteView):
    model = Ride
    success_url = reverse_lazy('bike:rides')

    def dispatch(self, request, *args, **kwargs):
        if not Ride.objects.filter(pk=kwargs['pk'],
                                   rider=request.user).exists():
            return HttpResponse("Unauthorised ride", status=401)
        return super(RideDelete, self).dispatch(request, *args, **kwargs)


@login_required(login_url=LOGIN_URL)
def rides_month(request, year, month):
    """ display rides for a particular month, using the same template as
    RidesList below, which can then be used to refine the query """
    entries = Ride.objects.filter(rider=request.user, date__year=year,
                                  date__month=month)
    # initialise filter form
    start_date = dt.date(year=year, month=month, day=1)
    if month > 11:
        end_date = dt.date(year=year+1, month=1, day=1)
    else:
        end_date = dt.date(year=year, month=month + 1, day=1)
    end_date -= dt.timedelta(days=1)
    initial = {'start_date': start_date, 'end_date': end_date,
               'max_entries': None}
    form = RideSelectionForm(
        bikes=Bike.objects.filter(owner=request.user).all(),
        initial=initial)
    return render(request, 'bike/rides.html',
                  context={'form': form, 'form_action': reverse('bike:rides'),
                           'entries': entries})


class RidesList(BikeLoginRequiredMixin):
    """ this class is also used for OdometerList """
    # TODO: implement search rides with QuerySet.(description_icontains=xx)
    # TODO: search for year/month with Queryset.filter(date__year=xx)
    entries = Ride.objects
    plural_name = 'rides'
    template_name = 'bike/rides.html'

    @classmethod
    def as_view(cls):
        return cls.dispatch

    @classmethod
    def dispatch(cls, request, bike_id=None):
        inst = cls()
        inst.request = request
        inst.bike_id = bike_id
        if request.method == 'POST':
            return inst.POST()
        elif request.method == 'GET':
            return inst.GET()
        raise ValueError(f"Invalid method {request.method}")

    def POST(self):
        self.form = form = RideSelectionForm(
            self.request.POST,
            bikes=Bike.objects.filter(owner=self.request.user).all())
        if form.is_valid():
            entries = (self.entries.filter(rider=self.request.user)
                       .exclude(distance__range=(-0.01, 0.01)))
            bike = form.cleaned_data['bike']
            if bike:
                entries = entries.filter(bike=bike)
            start_date = form.cleaned_data['start_date']
            if start_date:
                start_date = dt.datetime.combine(start_date, dt.time(0),
                                                 tzinfo=CURRENT_TIMEZONE)
                entries = entries.filter(date__gte=start_date)
            end_date = form.cleaned_data['end_date']
            if end_date:
                end_date = dt.datetime.combine(end_date, dt.time(23, 59, 59),
                                               tzinfo=CURRENT_TIMEZONE)
                entries = entries.filter(date__lte=end_date)
            entries = entries.order_by('-date').all()
            num_entries = form.cleaned_data['max_entries']
            if num_entries:
                # log.info("Applying filter num_rides=%d", num_rides)
                entries = entries[:num_entries]
            # log.info("request.GET=%s", request.GET)
            self.entries = entries

            if not self.entries.exists():
                form.add_error(
                    None,
                    f"No {self.plural_name} found matching those criteria.")
            elif self.request.GET.get('action') == 'download_as_csv':
                log.info("csv download requested")
                if self.plural_name != 'rides':
                    return HttpResponse(
                        "CSV download not supported for {plural_name}",
                        status=501)
                fields = ['date', 'bike', 'distance', 'distance_units_display',
                          'ascent', 'ascent_units_display', 'description']
                return csv_data_response(
                    self.request, 'rides.csv', entries, fields)
        else:
            self.entries = self.entries.order_by('-date').all()[:20]
        return render(self.request, self.template_name,
                      context={'form': self.form, 'entries': self.entries})

    def GET(self):
        if self.bike_id is not None:
            self.entries = self.entries.filter(bike_id=self.bike_id)
        entries = self.entries = self.entries.order_by('-date')[:20]

        if entries:
            start_date = entries[len(entries) - 1].date
            end_date = max(entries[0].date, timezone.now())
        else:
            start_date = end_date = None

        initial = {'start_date': start_date, 'end_date': end_date}
        if self.bike_id is not None:
            initial['bike'] = self.bike_id
        self.form = RideSelectionForm(
            bikes=Bike.objects.filter(owner=self.request.user).all(),
            initial=initial)
        return render(self.request, self.template_name,
                      context={'form': self.form, 'entries': self.entries})


def csv_data_response(request, filename, queryset, fields):
    log.info("csv_data_response: request.headers[accept]=%s",
             request.headers['accept'])
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    log.info("csv_data_response: sending %d records for %s", len(queryset),
             filename)
    writer = csv.writer(response)
    writer.writerow(fields)  # header row
    for row in queryset.all():
        csv_row = [getattr(row, field_name) for field_name in fields]
        writer.writerow(csv_row)
    log.info("csv_data_response: response=%s, headers=%s", response,
             response.headers)
    return response


class OdometerList(RidesList):
    """ display a list of Odometer readings, optionally selected by bike_id
    and by start/end date """
    # TODO: implement search rides with QuerySet.(description_icontains=xx)
    # TODO: search for year/month with Queryset.filter(date__year=xx)
    entries = Odometer.objects
    plural_name = 'odometer readings'
    template_name = 'bike/odometer_readings.html'


@login_required(login_url=LOGIN_URL)
def odometer_readings_new(request, bike_id=None):
    """ enter new odometer readings for one or all bikes """
    bikes = (Bike.objects.filter(owner=request.user)
             .annotate(last_ride=Max('rides__date'))
             .order_by('-last_ride'))
    if bike_id is not None:
        bikes = bikes.filter(pk=bike_id, owner=request.user)
    if not bikes.exists():
        return HttpResponse(
            "No bikes found." if bike_id is None else "Bike not found.",
            status=404)

    initial_values = get_odometer_readings_initial_values(request, bikes)

    if request.method == 'POST':
        # process date/time form
        dt_form = DateTimeForm(request.POST)
        if dt_form.is_valid():
            reading_dtime = dt_form.cleaned_data['reading_date_time']
        formset = OdometerFormSet(
            request.POST, initial=initial_values,
            form_kwargs={'user': request.user, 'reading_dtime': reading_dtime})

        # retrieve user & check it hasn't changed
        orig_user = request.POST.get("user")
        if orig_user != str(request.user):
            log.error("Userid mismatch in odometer_readings_new: orig_user=%r,"
                      " request.user=%r", orig_user, request.user)
            return HttpResponse("User id mismatch", status=403)

        # process odo readings
        if formset.is_valid():
            # want to only validate & save forms with odo reading entered
            # ?custom validation & save: ignore unchanged forms even if invalid
            formset.save()
            next_url = request.GET.get('next') or reverse('bike:home')
            return HttpResponseRedirect(next_url)

    else:
        # Initial GET.  Populate the formset, one form for each bike
        dt_form = DateTimeForm()
        formset = OdometerFormSet(queryset=Odometer.objects.none(),
                                  initial=initial_values,
                                  form_kwargs={'user': request.user})
        formset.extra = len(initial_values)
        user_bikes = request.user.bikes  # initialise the choice field
        for form in formset:
            form.fields['bike'].queryset = user_bikes
            # OR:
            form.fields['bike'].widget.attrs['readonly'] = True
    return render(request, 'bike/odometer_readings_new.html',
                  context={'formset': formset, 'dt_form': dt_form,
                           'bike_id': bike_id, 'user': request.user})


def get_odometer_readings_initial_values(request, bikes):
    """ return values for bikes, with user and distance units for each bike """
    initial_values = [{'bike': bike, 'rider': request.user}
                      for bike in bikes]
    try:
        preferences = Preferences.objects.get(user=request.user)
        for i in initial_values:
            i['distance_units'] = preferences.distance_units
    except Preferences.DoesNotExist:
        pass
    return initial_values


@login_required(login_url=LOGIN_URL)
def odometer_adjustment(request, ride_id=None, odo_reading_id=None,
                        success=reverse_lazy('bike:rides')):
    if request.method == 'GET':
        if ride_id is None:
            if odo_reading_id is None:
                return HttpResponse(
                    "Missing ride_id or odo_reading_id", status=400)
            odo_reading = Odometer.objects.select_related('bike').get(
                pk=odo_reading_id, rider=request.user)
        else:
            odo_reading = Odometer.objects.select_related('bike').get(
                adjustment_ride=ride_id, rider=request.user)
        odo_form = OdometerAdjustmentForm(instance=odo_reading)
    else:
        if odo_reading_id is None:
            return HttpResponse("Missing odo_reading_id", status=400)
        odo_reading = Odometer.objects.select_related('bike').get(
            pk=odo_reading_id, rider=request.user)
        odo_form = OdometerAdjustmentForm(request.POST, instance=odo_reading)
        if odo_form.is_valid():
            odo_form.save()
            return HttpResponseRedirect(success)
    return render(request, 'bike/odometer_adjustment.html',
                  context={"odo_reading": odo_reading, "form": odo_form,
                           "success_url": success})


class OdometerDelete(BikeLoginRequiredMixin, DeleteView):
    model = Odometer
    fields = ['bike', 'date', 'comment']
    success_url = reverse_lazy('bike:odometer_readings')

    def dispatch(self, request, *args, **kwargs):
        if not Odometer.objects.filter(pk=kwargs['pk'],
                                       rider=request.user).exists():
            return HttpResponse("Invalid odometer reading", status=401)
        return super(OdometerDelete, self).dispatch(request, *args, **kwargs)


class MaintActionList(BikeLoginRequiredMixin, ListView):
    model = MaintenanceAction
    ordering = ('bike', 'component', 'distance', 'due_date')

    def get_queryset(self):
        # passed in context as object_list
        return upcoming_maint(self.request.user)


def upcoming_maint(user, filter_by_limits=True):
    distance_units = user.preferences.get_distance_units_display()
    upcoming = MaintenanceAction.upcoming(
        user=user, filter_by_limits=filter_by_limits).select_related('bike')
    for ma in upcoming:
        ma.due = ma.due_in(distance_units)
    return upcoming


class MaintActionCreate(BikeLoginRequiredMixin, CreateView):
    model = MaintenanceAction
    # template_name_suffix = '_create_form'
    fields = ['bike', 'component', 'maint_type', 'description', 'due_date',
              'due_distance', 'completed', 'recurring',
              'maintenance_interval_distance', 'maint_interval_days']

    def get_form(self, *args, **kwargs):
        form = super(MaintActionCreate, self).get_form(*args, **kwargs)
        form.fields['bike'].queryset = self.request.user.bikes
        form.fields['component'].queryset = self.request.user.components
        form.fields['maint_type'].queryset = \
            self.request.user.maintenance_types
        return form

    def get_initial(self):
        initial = super(MaintActionCreate, self).get_initial()
        bike_id = self.request.GET.get('bike')
        component_id = self.request.GET.get('component_id')
        if bike_id or component_id:
            # copy, so we don't accidentally change a mutable dict
            initial = initial.copy()
            if bike_id:
                initial['bike'] = bike_id
            if component_id:
                initial['component'] = component_id
        return initial

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        if obj.completed:
            obj.mark_completed(obj.completed_date, obj.completed_distance)
            if obj.recurring:
                obj.completed = False
        return super(MaintActionCreate, self).form_valid(form)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(MaintActionCreate, self).get_success_url()

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context['distance_units'] = (self.request.user.preferences
                                     .get_distance_units_display())
        # context['link_formset'] = MaintActionLinkFormSet(
        #     instance=MaintenanceAction.objects.none())
        return context


@login_required
def maint_action_update(request, pk: int):
    maintenanceaction = get_object_or_404(MaintenanceAction, pk=pk,
                                          user=request.user)
    if request.method == 'GET':
        form = MaintenanceActionUpdateForm(instance=maintenanceaction)
        link_formset = MaintActionLinkFormSet(instance=maintenanceaction)
    elif request.method == 'POST':
        form = MaintenanceActionUpdateForm(
            request.POST, instance=maintenanceaction)
        link_formset = MaintActionLinkFormSet(
            request.POST, instance=maintenanceaction)
        if form.is_valid():
            maintenanceaction = form.save()
            if link_formset.is_valid():
                link_formset.save(commit=False)
                for link_form in link_formset:
                    link_form.instance.maint_action = maintenanceaction
                link_formset.save()

                if 'next' in request.GET:
                    return HttpResponseRedirect(request.GET['next'])

    completion_form = MaintCompletionDetailsForm(initial={
        'completed_date': timezone.now().date(),
        'distance': maintenanceaction.current_bike_odo()})
    distance_units = request.user.preferences.get_distance_units_display()
    return render(
        request, 'bike/maintenanceaction_form.html',
        context={'form': form, 'maintenanceaction': maintenanceaction,
                 'completion_form': completion_form,
                 'distance_units': distance_units,
                 'link_formset': link_formset})


@login_required
def maint_action_complete(request, pk: int):
    """ mark a maintenance action as complete """
    if request.method == "GET":
        return HttpResponse("Invalid method", status=405)

    maint_action = get_object_or_404(
        MaintenanceAction, pk=pk, user=request.user)
    maint_action_form = MaintenanceActionUpdateForm(
        request.POST, instance=maint_action)
    completion_form = MaintCompletionDetailsForm(request.POST)
    distance_units = request.user.preferences.get_distance_units_display()
    if maint_action_form.is_valid() and completion_form.is_valid():
        comp_date = completion_form.cleaned_data['completed_date']
        comp_distance = completion_form.cleaned_data['distance']
        maint_history = maint_action.maint_completed(comp_date, comp_distance)
        completion_form = MaintCompletionDetailsForm(initial={
            'completed_date': timezone.now().date(),
            'distance': maint_action.current_bike_odo(),
            'distance_units': distance_units})
        # or maint_action_form.data[field_name]=new_value
        # for due_distance and for completed
        maint_action_form = MaintenanceActionUpdateForm(instance=maint_action)
    else:
        maint_history = ''

    return render(
        request, 'bike/maintenanceaction_form.html',
        context={'form': maint_action_form, 'maintenanceaction': maint_action,
                 'completion_form': completion_form,
                 'completion_msg': maint_history,
                 'distance_units': distance_units})


class MaintActionDetail(BikeLoginRequiredMixin, DetailView):
    model = MaintenanceAction

    def get_queryset(self):
        return MaintenanceAction.objects.filter(
            user=self.request.user, pk=self.kwargs["pk"]
                ).annotate(
                due_in_distance=MaintenanceAction.due_in_distance,
                due_in_duration=MaintenanceAction.due_in_duration
                ).select_related("bike", "component", "component__type",
                                 "maint_type", "user__preferences")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_url"] = (
            self.request.GET["next"] if "next" in self.request.GET
            else reverse("bike:home"))
        # preferences = Preferences.objects.get(user=self.request.user)
        distance_units = (
            self.object.user.preferences.get_distance_units_display())
        context['distance_units'] = distance_units
        context["due_in"] = self.object.due_in(distance_units)
        context['completion_form'] = MaintCompletionDetailsForm(initial={
            'completed_date': timezone.now().date(),
            'distance': self.object.current_bike_odo()})
        return context


class MaintActionDelete(BikeLoginRequiredMixin, DeleteView):
    model = MaintenanceAction
    success_url = reverse_lazy('bike:maint_actions')

    def dispatch(self, request, *args, **kwargs):
        if not MaintenanceAction.objects.filter(
                pk=kwargs['pk'], user=request.user).exists():
            return HttpResponse("Unauthorised maint. action", status=401)
        return super(
            MaintActionDelete, self).dispatch(request, *args, **kwargs)


class MaintHistoryUpdate(BikeLoginRequiredMixin, UpdateView):
    model = MaintenanceActionHistory
    fields = ['description', 'completed_date', 'distance']

    def get_success_url(self):
        try:
            return self.request.GET['success']
        except KeyError:
            return super(MaintHistoryUpdate, self).get_success_url()

    def dispatch(self, request, *args, **kwargs):
        if not MaintenanceActionHistory.objects.filter(
                pk=kwargs['pk'], action__user=request.user).exists():
            return HttpResponse("Unauthorised maint. history", status=401)
        return super(
            MaintHistoryUpdate, self).dispatch(request, *args, **kwargs)


class MaintHistoryDelete(BikeLoginRequiredMixin, DeleteView):
    model = MaintenanceActionHistory

    def dispatch(self, request, *args, **kwargs):
        if not MaintenanceActionHistory.objects.filter(
                pk=kwargs['pk'], action__user=request.user).exists():
            return HttpResponse("Unauthorised maint. history", status=401)
        return super(
            MaintHistoryDelete, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        try:
            return self.request.GET['success']
        except KeyError:
            return super(MaintHistoryDelete, self).get_success_url()


class MaintTypeList(BikeLoginRequiredMixin, ListView):
    model = MaintenanceType
    ordering = ('component_type', 'recurring', 'description',)

    def get_queryset(self):
        return (MaintenanceType.objects.filter(user=self.request.user)
                .order_by(*self.ordering))


class MaintTypeCreate(BikeLoginRequiredMixin, CreateView):
    model = MaintenanceType
    fields = ('component_type', 'description', 'reference_info', 'recurring',
              'maintenance_interval_distance', 'maint_interval_days')

    def get_form(self, *args, **kwargs):
        form = super(MaintTypeCreate, self).get_form(*args, **kwargs)
        form.fields['component_type'].queryset = \
            self.request.user.component_types
        if 'component_type' in self.request.GET:
            form.fields['component_type'].initial = \
                self.request.GET['component_type']
        return form

    def get_initial(self):
        initial = super(MaintTypeCreate, self).get_initial()
        ctype_id = self.request.GET.get('component_type')
        if ctype_id:
            ctype = get_object_or_404(ComponentType, user=self.request.user,
                                      pk=ctype_id)
            # copy, so we don't accidentally change a mutable dict
            initial = initial.copy()
            initial['component_type'] = ctype
        return initial

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context['distance_units'] = (
            self.request.user.preferences.get_distance_units_display())
        return context

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.user = self.request.user
        return super(MaintTypeCreate, self).form_valid(form)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(MaintTypeCreate, self).get_success_url()


class MaintTypeUpdate(BikeLoginRequiredMixin, UpdateView):
    model = MaintenanceType
    fields = MaintTypeCreate.fields

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super(MaintTypeUpdate, self).get_success_url()

    def dispatch(self, request, *args, **kwargs):
        if not MaintenanceType.objects.filter(
                pk=kwargs['pk'], user=request.user).exists():
            return HttpResponse("Unauthorised maint. type", status=401)
        return super(
            MaintTypeUpdate, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        context['distance_units'] = (
            self.request.user.preferences.get_distance_units_display())
        return context


class MaintTypeDelete(BikeLoginRequiredMixin, DeleteView):
    model = MaintenanceType
    success_url = reverse_lazy('bike:maint_types')

    def dispatch(self, request, *args, **kwargs):
        if not MaintenanceType.objects.filter(
                pk=kwargs['pk'], user=request.user).exists():
            return HttpResponse("Unauthorised maint. type", status=401)
        return super(
            MaintTypeDelete, self).dispatch(request, *args, **kwargs)


@login_required(login_url=LOGIN_URL)
def mileage(request, year: Optional[int]=None, bike_id=None):
    """ show a monthly summary of mileage, with detail if requested
    if year provided, show details for that year and the preceding year. """
    # retrieve available years with rides recorded, for pagination
    years_dt = Ride.objects.dates('date', "year")
    years = [y_dt.year for y_dt in years_dt]
    if year is None:
        # or use Queryset.latest() to retrieve latest ride on db
        sel_yrs = years[-2:]
    else:
        prev_yr = next((yr for yr in reversed(years) if yr < year), None)
        sel_yrs = [year] if prev_yr is None else [prev_yr, year]
    sel_yrs.sort()
    if all((yr not in years for yr in sel_yrs),):
        log.warning("mileage requested for a year with no recorded rides.")
    log.info("years=%s, sel sel_yrs=%s", years, sel_yrs)
    prev_yr, next_yr = get_prev_next_yr(sel_yrs, years)
    if bike_id is not None:
        bike = get_object_or_404(Bike, pk=bike_id, owner=request.user)
    else:
        bike = None
    monthly_mileage = Ride.mileage_by_month(request.user, sel_yrs, bike_id)
    totals = annual_mileage_totals(monthly_mileage, years)
    sel_yrs = [str(yr) for yr in sel_yrs]
    for month, month_summary in monthly_mileage.items():
        for yr in sel_yrs:
            if yr not in month_summary:
                month_summary[yr] = {}
        monthly_mileage[month] = dict(sorted(month_summary.items()))
    # log.info("monthly_mileage=%s, sel_yrs=%r, prev_yr=%s, next_yr=%s",
    #          monthly_mileage, sel_yrs, prev_yr, next_yr)
    return render(request, 'bike/mileage_monthly.html',
                  context={'monthly_mileage': monthly_mileage,
                           'bike': bike, 'bike_id': bike_id,
                           'sel_yrs': sel_yrs, 'totals': totals,
                           'prev_yr': prev_yr, 'next_yr': next_yr})


def annual_mileage_totals(
        monthly_mileage: Dict[int, Dict[str, Dict[str, int]]], years: List[int]
        ) -> Dict[str, Dict[str, int]]:
    """ calculate totals by year for included years
    monthly_mileage is {month: {year: {distance_unit: mileage}}}
    totals is {year: {distance_unit: mileage}} """
    totals = {str(year): {} for year in years}
    # year is a string in monthly_mileage
    for mileage in monthly_mileage.values():
        for year, units_and_dist in mileage.items():
            for distance_unit, dist in units_and_dist.items():
                try:
                    totals[str(year)][distance_unit] += dist
                except KeyError:
                    totals[str(year)][distance_unit] = dist
    return totals


def get_prev_next_yr(sel_years: List[int], years: List[int]
                     ) -> Tuple[Optional[int], Optional[int]]:
    """ return the previous and next year in years, or None
    years must be sorted in ascending order"""
    log.info("get_prev_next_yr: sel_years=%s, years=%s", sel_years, years)
    assert sel_years, "sel_years parameter must be provided"
    if not years:
        return None, None  # no years to choose from

    if not isinstance(sel_years, list):
        sel_years = list[sel_years]
    else:
        sel_years.sort()
    next_yr = next((x for x in years if x > max(sel_years)), None)
    if len(sel_years) > 1:
        prev_yr = sel_years[0]
    else:
        prev_yr = next(
            (x for x in reversed(years) if x < min(sel_years)), None)
    # log.info("get_prev_next_yr -> prev_yr=%s, next_yr=%s", prev_yr, next_yr)
    return prev_yr, next_yr
