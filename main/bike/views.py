#! /usr/bin/env python3

import csv
import datetime as dt
import logging
from typing import List, Tuple, Optional, Dict, Union, Any, TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Sum, Q, Max, Subquery, OuterRef
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.generic import (
    View, CreateView, UpdateView, DeleteView, ListView, DetailView)
# from django.views.generic.dates import MonthArchiveView

from .models import (
    Bike, Ride, ComponentType, Component, Preferences, MaintenanceAction,
    DistanceUnits, MaintenanceActionHistory, MaintenanceType, Odometer,
    # MaintActionLink
    )
from .forms import (
    RideSelectionForm, RideForm, DistanceInputWidget,
    PreferencesForm, PreferencesForm2, PreferencesForm3,
    MaintenanceActionUpdateForm, MaintCompletionDetailsForm,
    OdometerFormSet, OdometerAdjustmentForm, DateTimeForm,
    MaintActionLinkFormSet, ComponentForm)

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from django import forms

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
    latest_ride = (Ride.objects.filter(rider=request.user)
                   .order_by("-date").first())
    return render(request, 'bike/home.html',
                  context={'preferences_set': preferences_set,
                           'upcoming_maint': maint,
                           'latest_ride': latest_ride})


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
               .filter(rides__distance__isnull=False)
               .annotate(
                   distance=Sum('rides__distance'),
                   distance_year=sum_year,
                   distance_month=sum_month,
                         )
               )
    latest_ride = Subquery(Ride.objects.filter(
        bike_id=OuterRef("id"), is_adjustment=False, rider=request.user,
        ).order_by("-date").values('pk')[:1])

    bikes = bikes.annotate(
        last_ridden=Max('rides__date', filter=Q(rides__is_adjustment=False)),
        last_ride_id=latest_ride  # pk of latest ride
        ).order_by('-last_ridden').all()
    # bikes is a queryset of dicts, one for each bike/distance_unit combo
    # log.info("mileage=%s", mileage)
    # log.info("maint=%s", maint)
    # add maint details to bike entries
    bikes_by_id = {bike.id: bike for bike in bikes}
    for entry in mileage:
        bike = bikes_by_id[entry.id].mileage = [entry]
    for entry in maint:
        bike = bikes_by_id[entry.bike_id]
        # log.info("maint %s for bike %s", maint, bike)
        try:
            bike.maint_upcoming.append(entry)
        except AttributeError:
            bike.maint_upcoming = [entry]
    monthname = today.strftime('%b')  # eg. Jan
    return render(
        request, 'bike/bikes.html', context={
            'bikes': bikes, 'today': today, 'monthname': monthname,
            'distance_units': 
            request.user.preferences.distance_units_label.lower()})


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "POST"])
def preferences(request, pk: Optional[int]=None):
    """ allow creation & editing of the user's preferences instance,
    using three forms to separate distance units, bike settings and 
    route settings """
    if pk is not None and request.user.is_superuser:
        # superuser can access any preferences
        prefs = get_object_or_404(Preferences, pk=pk)
    else:
        prefs = Preferences.objects.get_or_create(user=request.user)[0]
    if request.method == "GET":
        prefs_form1 = PreferencesForm(instance=prefs)
        prefs_form2 = PreferencesForm2(instance=prefs)
        prefs_form3 = PreferencesForm3(instance=prefs)

    else:  # POST
        prefs_form1 = PreferencesForm(request.POST, instance=prefs)
        prefs_form2 = PreferencesForm2(request.POST, instance=prefs)
        prefs_form3 = PreferencesForm3(request.POST, instance=prefs)
        try:
            submitted_form = get_submitted_prefs_form(
                request, prefs_form1, prefs_form2, prefs_form3)
        except ValueError as e:
            return HttpResponse(e.args[0], status=400)
        if submitted_form.is_valid():
            instance = submitted_form.save()
            prefs_page = request.GET["prefs_page"]
            if prefs_page == '1':  # in case units have changed
                prefs_form2 = PreferencesForm2(instance=prefs)
                prefs_form3 = PreferencesForm3(instance=prefs)
            messages.success(request, "Preferences updated.")
            if request.GET.get("action") != "apply":
                if (next_url := request.GET.get("next")):
                    return HttpResponseRedirect(next_url)

    return render(request, 'bike/preferences.html', context={
        "form1": prefs_form1, "form2": prefs_form2, "form3": prefs_form3,
        "instance": prefs, "prefs_page": request.GET.get("prefs_page", "1"),
        "next": request.GET.get("next") or reverse_lazy("bike:home")})


def get_submitted_prefs_form(request, prefs_form1, prefs_form2, prefs_form3):
    try:
        prefs_page = request.GET["prefs_page"]
    except KeyError as e:
        log.error("preferences POST request with missing prefs_page:"
                  " request.GET=%s", request.GET)
        raise ValueError("Missing prefs_page parameter") from e
    if prefs_page not in {'1', '2', '3'}:
        log.error("preferences POST request has invalid prefs_page=%s",
                  prefs_page)
        raise ValueError("Invalid prefs_page parameter") from e
    return (prefs_form1 if prefs_page == '1'
            else prefs_form2 if prefs_page == '2'
            else prefs_form3)  # if prefs_page == '3'


class BikeComponentsMixin:
    def get_queryset(self) -> "QuerySet":
        return (Bike.objects
                .filter(owner=self.request.user)
                .prefetch_related('components'))


class BikeDetail(BikeLoginRequiredMixin, BikeComponentsMixin, DetailView):
    """ get_queryset from BikeComponentsMixin """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["distance_units"] = (
            self.request.user.preferences.distance_units_label.lower())
        context["next_url"] = (
            self.request.GET["next"] if "next" in self.request.GET
            else reverse("bike:home"))
        pk = self.kwargs['pk']
        return add_maint_context(context, self.request.user, bike_id=pk)


class BikeCreate(BikeLoginRequiredMixin, CreateView):
    model = Bike
    fields = ['name', 'description']

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        if 'next' in self.request.GET:
            return self.request.GET['next']
        return super().get_success_url()


class BikeUpdate(BikeLoginRequiredMixin, BikeComponentsMixin, UpdateView):
    """ get_queryset from BikeComponentsMixin """
    fields = ['name', 'description']

    def dispatch(self, request, *args, **kwargs):
        if not Bike.objects.filter(pk=kwargs['pk'],
                                   owner=request.user).exists():
            return HttpResponse("Unauthorised bike", status=401)
        return super(BikeUpdate, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(BikeUpdate, self).get_context_data(**kwargs)
        context["distance_units"] = (
            self.request.user.preferences.distance_units_label.lower())
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
    if bike_id is None and component_id is None:
        return context

    context['maint_upcoming'] = upcoming = MaintenanceAction.upcoming(
        user=user, bike_id=bike_id, component_id=component_id,
        filter_by_limits=False).all()
    for ma in upcoming:
        ma.due = ma.due_in()

    context['maint_history'] = MaintenanceAction.history(
        user=user, bike_id=bike_id, component_id=component_id).first()
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
                  .order_by('bike', 'type')
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
        context["distance_units"] = (
            self.request.user.preferences.distance_units_label.lower())
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
def component_replace(request, pk: int):
    """ record replacement of a component AND ALL SUBCOMPONENTS.
    And transfer all maintenance actions to new component."""
    old_cpt = get_object_or_404(Component, pk=pk, owner=request.user)
    subcomponents = Component.objects.filter(
            subcomponent_of=old_cpt).all()
    # TODO: allow user to update timezone
    if request.method == 'GET':
        # create old_form and new_form with duplicate info & present
        old_cpt_form = ComponentForm(instance=old_cpt, prefix='old')
        new_cpt_form = ComponentForm(instance=old_cpt, prefix='new')

    elif request.method == 'POST':
        # save old_cpt (blank out bike & parent cpt) & new_cpt,
        # and create maintenance action
        old_cpt_form = ComponentForm(request.POST, instance=old_cpt,
                                     prefix='old')
        new_cpt_form = ComponentForm(request.POST, prefix='new')

        if old_cpt_form.is_valid() and new_cpt_form.is_valid():
            new_cpt = new_cpt_form.save(commit=False)
            old_cpt_form.save(commit=False)  # update instance
            # collect all maint actions from old to new cpt, to transfer later
            maint_actions_for_cpt = MaintenanceAction.objects.filter(
                component=old_cpt).all()

            repl_maint_action = MaintenanceAction(
                user=request.user,
                bike=old_cpt.bike,
                component=old_cpt,
                description=(f'Replaced after {old_cpt.current_distance()} '
                             f'{old_cpt.distance_units_label.lower()}')
                )
            # complete missing fields in new_cpt
            # form covers name, specification, date_acquired, supplier, notes
            new_cpt.owner = old_cpt.owner
            new_cpt.type = old_cpt.type
            new_cpt.bike = old_cpt.bike
            new_cpt.subcomponent_of = old_cpt.subcomponent_of


            old_cpt.bike = None
            old_cpt.subcomponent_of = None

            old_cpt.save()
            new_cpt.save()
            log.info("Replace component:\n%s: %s\n->%s: %s",
                     old_cpt.id, old_cpt, new_cpt.id, new_cpt)
            # transfer maint actions (after saving new_cpt)
            for maint_action in maint_actions_for_cpt:
                maint_action.component = new_cpt
                maint_action.save()

            repl_maint_action.save()
            repl_maint_action.mark_completed()  # saves maint_action & history

            next_url = request.GET.get('next') or reverse('bike:home')
            return HttpResponseRedirect(next_url)

    else:
        return HttpResponse("Invalid HTTP method", status=405)

    log.info("old_cpt=%s, pk=%s", old_cpt, old_cpt.id)
    return render(request, 'bike/component_replace.html',
              context={'pk': pk, 'cpt': old_cpt,
                       'subcomponents': subcomponents,
                       'old_cpt_form': old_cpt_form,
                       'new_cpt_form': new_cpt_form}) 


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


@login_required(login_url=LOGIN_URL)
@require_http_methods(["GET", "POST"])
def ride(request, pk: int=None):
    ride = (None if pk is None else
        get_object_or_404(Ride, rider=request.user, pk=pk))
    if request.method == "GET":
        if pk is None:
            bikes = Bike.objects.filter(
                owner=request.user).order_by('-rides__date').first()
            initial={"bike": bikes, "date": dt.datetime.now(tz=CURRENT_TIMEZONE),
                     }
            form = RideForm(initial=initial, user=request.user)
        else:
            form = RideForm(instance=ride)
    else: # (POST)
        form = RideForm(request.POST, instance=ride, user=request.user)
        log.info("ride: form is_valid=%s", form.is_valid())
        if form.is_valid():
            ride = form.save(commit=False)
            log.info("ride: ride.pk=%s", ride.pk)
            ride.rider = request.user
            try:
                # catch duplicate ride exception
                form.save()
                success_url = request.GET.get("next") or reverse("bike:home")
                messages.success(request, "Ride saved.")
                return HttpResponseRedirect(success_url)
            except IntegrityError as e:
                log.error("Failed to save ride: %r", e)
                if e.args[0].startswith("UNIQUE constraint failed"):
                    msg = "This ride has already been saved."
                else:
                    msg = f"Error saving ride: {e}"
                form.add_error(None, msg)
    return render(request, "bike/ride_form.html", context={
        "form": form, "ride": ride,
        "bike_id": (None if ride is None else ride.bike.id)
        # bike_id is used for "Add Maint. Action" url 
        })
#
#
# class RideUpdate(BikeLoginRequiredMixin, UpdateView):
#     model = Ride
#     form_class = RideForm
#
#     def dispatch(self, request, *args, **kwargs):
#         if not Ride.objects.filter(pk=kwargs['pk'],
#                                    rider=request.user).exists():
#             return HttpResponse("Unauthorised ride", status=401)
#         return super(RideUpdate, self).dispatch(request, *args, **kwargs)
#
#     def get_form(self, form_class=None):
#         """Return an instance of the form to be used in this view."""
#         if form_class is None:
#             form_class = self.get_form_class()
#         # add user as kwarg
#         return form_class(user=self.request.user, **self.get_form_kwargs())
#
#     def get_context_data(self, **kwargs):
#         context = super(RideUpdate, self).get_context_data(**kwargs)
#         context['bike_id'] = self.object.bike_id
#         return context
#
#     def get_success_url(self):
#         if 'next' in self.request.GET:
#             return self.request.GET['next']
#         return super(RideUpdate, self).get_success_url()


class RideDelete(BikeLoginRequiredMixin, DeleteView):
    model = Ride
    success_url = reverse_lazy('bike:rides')

    def dispatch(self, request, *args, **kwargs):
        if not Ride.objects.filter(pk=kwargs['pk'],
                                   rider=request.user).exists():
            return HttpResponse("Unauthorised ride", status=401)
        return super().dispatch(request, *args, **kwargs)


class RidesList(BikeLoginRequiredMixin, View):
    """ this class is also used for OdometerList """
    # TODO: implement search rides with QuerySet.(description_icontains=xx)
    # TODO: search for year/month with Queryset.filter(date__year=xx)
    entries = Ride.objects
    plural_name = 'rides'
    template_name = 'bike/rides.html'
    form: "forms.Form"
    csv_fields = ['date', 'bike', 'distance', 'distance_units_label',
                  'ascent', 'ascent_units_label', 'description']
    csv_filename = 'rides.csv'

    def get(self, request, *args, bike_id: Optional[int] = None, **kwargs):
        self.get_initial_queryset(bike_id)
        if 'year' in kwargs:
            initial = self.get_monthly_entries(**kwargs)
        else:
            initial = {"bike": bike_id}
        self.form = RideSelectionForm(
            bikes=Bike.objects.filter(owner=request.user).all(),
            initial=initial)
        return self.complete_response()

    def post(self, request, *args, **kwargs):
        # bike_id kwarg is ignored on a POST because it's selected in the form.
        self.form = form = RideSelectionForm(
            self.request.POST,
            bikes=Bike.objects.filter(owner=request.user).all())

        if form.is_valid():
            self.get_initial_queryset(form.cleaned_data["bike"])
            if (start_date := form.cleaned_data['start_date']):
                start_date = dt.datetime.combine(start_date, dt.time(0),
                                                 tzinfo=CURRENT_TIMEZONE)
                self.entries = self.entries.filter(date__gte=start_date)
            if (end_date := form.cleaned_data['end_date']):
                end_date = dt.datetime.combine(end_date, dt.time(23, 59, 59),
                                               tzinfo=CURRENT_TIMEZONE)
                self.entries = self.entries.filter(date__lte=end_date)
            max_entries = form.cleaned_data['max_entries']
            # log.info("request.GET=%s", request.GET)

            if not self.entries.exists():
                form.add_error(
                    None,
                    f"No {self.plural_name} found matching those criteria.")
            elif self.request.GET.get('action') == 'download_as_csv':
                return csv_data_response(self.request, self.csv_filename,
                                         self.entries, self.csv_fields)

            return self.complete_response(max_entries)

        # else:  # form not valid
        return self.complete_response()


    def get_initial_queryset(self, bike_id: Optional[int]):
        """ as for rides but don't exclude small distance readings """
        if bike_id not in {None, ''}:
            self.entries = self.entries.filter(bike_id=bike_id)
        self.entries = (self.entries.filter(rider=self.request.user)
            .exclude(distance__range=(-0.01, 0.01))
            .order_by('-date'))

    def get_monthly_entries(self, *_args, year: int, month: Optional[int]=None,
                            **_kwargs) -> Dict[str, Any]:
        """ create filter and selection form initial values for a month's
        entries, or a year's entries if month is not specified """
        self.entries = self.entries.filter(rider=self.request.user,
                                           date__year=year)
        if month is not None:
            self.entries = self.entries.filter(date__month=month)
        # initialise filter form
        start_date = dt.date(year=year, month=month or 1, day=1)
        if month is None or month > 11:
            end_date = dt.date(year=year+1, month=1, day=1)
        else:
            end_date = dt.date(year=year, month=month + 1, day=1)
        end_date -= dt.timedelta(days=1)
        return {'start_date': start_date, 'end_date': end_date,
                'max_entries': None}

    def complete_response(self, max_entries: Optional[int]=None):
        paginator = Paginator(
            self.entries, max_entries or RideSelectionForm.INITIAL_MAX_ENTRIES)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)
        totals = self.get_ride_totals()
        return render(self.request, self.template_name,
                      context={'form': self.form, 'page_obj': page_obj,
                               'totals': totals, 'user': self.request.user})

    def get_ride_totals(self) -> Dict[str, Union[float,int]]:
        """ compute sum & count of entries  - only for Rides
        for Odometer entries, an empty dict is returned. """
        # uses self.entries already filtered & sliced by GET/POST for rider & bike

        if self.entries.exists() and hasattr(self.entries.first(), 'ascent'):
            # check entries are Rides (not Odometer readings)
            totals = self.entries.aggregate(Sum('distance'), Sum('ascent'))
            if totals["distance__sum"] or totals["ascent__sum"]:
                return {'total_distance': totals["distance__sum"],
                        'total_ascent': totals["ascent__sum"],
                        'count': self.entries.count()}
        return {}


def csv_data_response(request, filename, queryset, fields):
    # log.info("csv_data_response: request.headers[accept]=%s",
    #          request.headers['accept'])
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    log.info("csv_data_response: sending %d records for %s", len(queryset),
             filename)
    writer = csv.writer(response)
    writer.writerow(fields)  # header row
    for row in queryset.all():
        csv_row = [getattr(row, field_name) for field_name in fields]
        writer.writerow(csv_row)
    # log.info("csv_data_response: response=%s, headers=%s", response,
    #          response.headers)
    return response


class OdometerList(RidesList):
    """ display a list of Odometer readings, optionally selected by bike_id
    and by start/end date """
    # TODO: implement search rides with QuerySet.(description_icontains=xx)
    # TODO: search for year/month with Queryset.filter(date__year=xx)
    entries = Odometer.objects
    plural_name = 'odometer readings'
    template_name = 'bike/odometer_readings.html'
    csv_fields = ['date', 'bike', 'distance', 'distance_units_label',
                  'initial_value', 'comment']
    csv_filename = 'odometer readings.csv'

    def get_initial_queryset(self, bike_id: Optional[int]):
        """ as for rides but don't exclude small distance readings """
        if bike_id not in {None, ''}:
            self.entries = self.entries.filter(bike_id=bike_id)
        self.entries = (self.entries.filter(rider=self.request.user)
            .order_by('-date'))


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

    initial_values = [{'bike': bike, 'rider': request.user} for bike in bikes]

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


def upcoming_maint(user, filter_by_limits=True) -> "QuerySet":
    upcoming = MaintenanceAction.upcoming(
        user=user, filter_by_limits=filter_by_limits).select_related('bike')
    for ma in upcoming:
        ma.due = ma.due_in()
    return upcoming


class MaintActionCreate(BikeLoginRequiredMixin, CreateView):
    model = MaintenanceAction
    # template_name_suffix = '_create_form'
    fields = ['bike', 'component', 'maint_type', 'description',
              'due_date', 'due_distance', 'completed', 'recurring',
              'maintenance_interval_distance', 'maint_interval_days']
    # specifying widgets here doesn't seem to work
    # widgets = {'due_distance': DistanceInputWidget(attrs={"size": 8}),
    #            'maintenance_interval_distance':
    #            DistanceInputWidget(attrs={"size": 8})}

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        form.fields['bike'].queryset = self.request.user.bikes
        form.fields['component'].queryset = self.request.user.components
        form.fields['maint_type'].queryset = \
            self.request.user.maintenance_types
        for field_name in ('due_distance', 'maintenance_interval_distance'):
            f = form.fields[field_name]
            f.widget = DistanceInputWidget(attrs={"size": 8})
            f.widget.distance_units = (
                self.request.user.preferences.distance_units_label.lower())
        form.distance_units = (
            self.request.user.preferences.distance_units_label.lower())
        return form

    def get_initial(self):
        initial = super().get_initial()
        bike_id = self.request.GET.get('bike')
        component_id = self.request.GET.get('component_id')
        if bike_id or component_id:
            # copy, so we don't accidentally change a mutable dict
            initial = initial.copy()
            if bike_id:
                initial['bike'] = bike_id
            if component_id:
                initial['component'] = component_id
            initial['user'] = self.request.user
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
        return self.request.GET.get('next') or super().get_success_url()

    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        context['distance_units'] = (self.request.user.preferences
                                     .distance_units_label.lower())
        # context['link_formset'] = MaintActionLinkFormSet(
        #     instance=MaintenanceAction.objects.none())
        return context


@login_required
@require_http_methods(["GET", "POST"])
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
        'distance': maintenanceaction.current_bike_odo(),
        'action': maintenanceaction})
    return render(
        request, 'bike/maintenanceaction_form.html',
        context={'form': form, 'maintenanceaction': maintenanceaction,
                 'completion_form': completion_form,
                 'link_formset': link_formset})


@login_required
@require_http_methods(["POST"])
def maint_action_complete(request, pk: int):
    """ mark a maintenance action as complete """
    maint_action = get_object_or_404(
        MaintenanceAction, pk=pk, user=request.user)
    completion_form = MaintCompletionDetailsForm(
        request.POST, initial={"action": maint_action})
    if "mark-complete-from-maint-details" not in request.POST:
        # a MaintenanceActionUpdateForm was submitted: validate that first
        maint_action_form = MaintenanceActionUpdateForm(
            request.POST, instance=maint_action)
        link_formset = MaintActionLinkFormSet(
            request.POST, instance=maint_action)
        if not maint_action_form.is_valid() and link_formset.is_valid():
            return render(
                request, 'bike/maintenanceaction_form.html',
                context={'form': maint_action_form,
                         'maintenanceaction': maint_action,
                         'completion_form': completion_form,
                         'link_formset': link_formset})
        # else:  # MaintenanceActionUpdateForm is valid
        maint_action = save_maint_action_form(maint_action_form, link_formset)

    return handle_maint_action_completion_form(
        request, completion_form, maint_action)


def handle_maint_action_completion_form(request, completion_form, maint_action):
    """ validate the completion form and mark complete """
    if completion_form.is_valid():
        maint_action_history = maint_action.mark_completed(
            comp_date=completion_form.cleaned_data['completed_date'],
            comp_distance=completion_form.cleaned_data['distance'])
        messages.success(request, "Marked as completed.")
    else:
        log.error("completion form was not valid: %s", completion_form.errors)
        maint_action_history = None

    # refresh maint_action in order to recalculate due_in_distance/duration
    maint_action = get_maint_action_detail_queryset(
        request.user, maint_action.pk).first()
    return render(
        request, 'bike/maintenanceaction_detail.html', context={
           'maintenanceaction': maint_action,
           'completion_form': completion_form,
           'completion_msg': maint_action_history,
           'next_url': request.POST.get("next", reverse_lazy("bike:home"))
           })


def save_maint_action_form(maint_action_form, link_formset
                           ) -> MaintenanceAction:
    """ save a validated maintenance action form, and any links """
    maint_action = maint_action_form.save()
    link_formset.save(commit=False)
    for link_form in link_formset:
        link_form.instance.maint_action = maint_action
    link_formset.save()
    return maint_action


class MaintenanceActionHistoryList(BikeLoginRequiredMixin, ListView):
    """ return a list of maintenanceHistory items according to bikeId, cptID
     and pagination variables page_max and page """
    model = MaintenanceActionHistory
    paginate_by = 20
    template_name = "bike/maint_history_list.html"

    def get_queryset(self) -> "QuerySet":
        qs = MaintenanceActionHistory.objects.select_related('action').order_by("completed_date")
        if (bike_id := self.request.GET.get('bike_id')):
            qs = qs.filter(bike_id=bike_id, bike__owner=self.request.user)
        if (cpt_id := self.request.GET.get('cpt_id')):
            qs = qs.filter(component=cpt_id, component__owner=self.request.user)
        return qs

    def get_context_data(self) -> Dict[str, Any]:
        """ add distance units to the context """
        ctx = super().get_context_data()
        ctx |= {"distance_units":
            self.request.user.preferences.distance_units_label.lower(),
            "bike_id": self.request.GET.get('bike_id'),
            "cpt_id": self.request.GET.get('cpt_id')}
        return ctx


class MaintActionDetail(BikeLoginRequiredMixin, DetailView):
    model = MaintenanceAction

    def get_queryset(self):
        return get_maint_action_detail_queryset(
            self.request.user, self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next_url"] = (
            self.request.GET["next"] if "next" in self.request.GET
            else reverse("bike:home"))
        context['completion_form'] = MaintCompletionDetailsForm(initial={
            'completed_date': timezone.now().date(),
            'distance': self.object.current_bike_odo(),
            'action': self.object})
        return context


def get_maint_action_detail_queryset(user, pk) -> "QuerySet":
    """ return a queryset (of one entry) of maintenanceaction matching user,pk
    """
    return MaintenanceAction.objects.filter(
        user=user, pk=pk
        ).annotate(
            due_in_distance=MaintenanceAction.due_in_distance,
            due_in_duration=MaintenanceAction.due_in_duration
            ).select_related("bike", "component", "component__type",
                             "maint_type", "user__preferences")


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
    # widgets = {'distance': DistanceInputWidget(attrs={'size': 8})}

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        f = form.fields["distance"]
        f.widget = DistanceInputWidget(attrs={'size': 8})
        f.widget.distance_units = form.instance.distance_units_label.lower()
        return form

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
            self.request.user.preferences.distance_units_label.lower())
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
            self.request.user.preferences.distance_units_label.lower())
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
    prev_yr, next_yr, sel_yrs = get_mileage_years(year)
    if bike_id is not None:
        bike = get_object_or_404(Bike, pk=bike_id, owner=request.user)
    else:
        bike = None
    monthly_mileage = Ride.mileage_by_month(request.user, sel_yrs, bike_id)
    totals = annual_mileage_totals(monthly_mileage, sel_yrs)
    mileage_ytd = Ride.mileage_ytd(request.user, sel_yrs, bike_id)
    sel_yrs_str = [str(yr) for yr in sel_yrs]
    for month, month_summary in monthly_mileage.items():
        for yr in sel_yrs_str:
            if yr not in month_summary:
                month_summary[yr] = {}
        monthly_mileage[month] = dict(sorted(month_summary.items()))
    # log.info("monthly_mileage=%s, sel_yrs=%r, prev_yr=%s, next_yr=%s",
    #          monthly_mileage, sel_yrs, prev_yr, next_yr)
    distance_units = request.user.preferences.distance_units_label.lower()
    return render(request, 'bike/mileage_monthly.html',
                  context={'monthly_mileage': monthly_mileage,
                           'bike': bike, 'bike_id': bike_id,
                           'sel_yrs': sel_yrs_str, 'totals': totals,
                           'mileage_ytd': mileage_ytd,
                           'distance_units': distance_units,
                           'prev_yr': prev_yr, 'next_yr': next_yr})


def get_mileage_years(year: Optional[int]=None
                      ) -> Tuple[Optional[int], Optional[int], List[int]]:
    # retrieve available years with rides recorded, for pagination
    years_dt: List[dt.date] = Ride.objects.dates('date', "year")
    years: List[int] = [y_dt.year for y_dt in years_dt]
    if year is None:
        # or use Queryset.latest() to retrieve latest ride on db
        sel_yrs = years[-2:]
    else:
        prev_yr = next((yr for yr in reversed(years) if yr < year), None)
        sel_yrs = [year] if prev_yr is None else [prev_yr, year]
    sel_yrs.sort()
    if all((yr not in years for yr in sel_yrs),):
        log.warning("mileage requested for a year with no recorded rides.")
    # log.info("years=%s, sel sel_yrs=%s", years, sel_yrs)
    prev_yr, next_yr = get_prev_next_yr(sel_yrs, years)
    return prev_yr, next_yr, sel_yrs


@login_required(login_url=LOGIN_URL)
def mileage_graph(request, year: Optional[int]=None):
    """ plot a cumulative mileage graph for selected year & prev year.  ref: 
    https://stackoverflow.com/questions/9627686/plotting-dates-on-the-x-axis
    """
    prev_yr, next_yr, sel_yrs = get_mileage_years(year)
    rides_cum_total = Ride.cumulative_mileage(request.user, sel_yrs)
    # create cum mileage dict (this version has int keys, need str for template)
    # also convert ride.datetime to a dt.date object
    cumulative_mileage: Dict[int, Dict[dt.date, float]] = {}
    #             {year: {ride.date.date(): ride.cum_distance}}
    for ride in rides_cum_total:
        year = ride.date.year
        if year not in cumulative_mileage:
            cumulative_mileage[year] = {}
        cumulative_mileage[year][ride.date.date()] = (
            ride.cum_distance)

    #log.info("cum_mileage=%s", convert_cum_mileage_keys_to_strings(
    #    cumulative_mileage))
    plot = get_cum_mileage_plot(
        cumulative_mileage,
        request.user.preferences.distance_units_label.lower())
    plot_string = plot_as_string(plot)

    sel_yrs_str = [str(yr) for yr in sel_yrs]

    return render(request, 'bike/mileage_graph.html',
                  context={'graphic': plot_string,
                           'graphic_type': 'svg',
                           'sel_yrs': sel_yrs_str,
                           'prev_yr': prev_yr, 'next_yr': next_yr})


def get_cum_mileage_plot(
        cumulative_mileage: Dict[int, Dict[dt.date, float]],
        distance_units: str):
    """return a plot of cumulative mileage.
    The different years are rebased to a single year: a leap year if there's
    one in the range
    Use the "agg" backend for non interactive use, to avoid thread errors
    agg supports png filetype; use "svg" backend for svg graphics
    ref: https://matplotlib.org/stable/users/explain/figure/backends.html """
    import matplotlib
    from matplotlib import pyplot as plt, dates as mdates
    matplotlib.use("agg")
    plt.clf()  # clear previous data in the figure / plot.

    # convert years of cum_mileage into a series
    base_year = get_plot_base_year(list(cumulative_mileage.keys()))
    for year, distance_dict in cumulative_mileage.items():
        series_name = str(year)
        distance_series = [
            round(cum_distance, 1)
            for cum_distance in distance_dict.values()]
        # rebase dates to base_year
        date_series = [dt.date(base_year, date.month, date.day)
                       for  date in distance_dict.keys()]
        # date_strings = [date.strftime("%d/%m/%y")  # for logging only
        #                for date in date_series]
        # log.info("plot series %s: %s",
        #         series_name, list(zip(date_strings, distance_series)))

        ensure_jan1_data(date_series, distance_series)
        plt.plot(date_series, distance_series, label=series_name)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%-d %b'))
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator())
    x_labels = plt.gca().get_xticklabels()
    plt.ylabel(distance_units)
    plt.setp(x_labels, rotation=60)  # , horizontalalignment='right')
    plt.grid(which='both')
    plt.legend()
    return plt


def ensure_jan1_data(dates: List[dt.date], distances: List[float]):
    """ if there is no jan 1 distance info, add it at zero distance """
    if not dates or (dates[0].month == 1 and dates[0].day == 1):
        return
    dates.insert(0, dt.date(dates[0].year, 1, 1))
    distances.insert(0, 0.0)


def plot_as_string(plt) -> str:
    """ save a plot to a BytesIO file & return it as a string
    if an svg, this is straightforward, png image is encoded as a Base64 string.
    Ref:
    https://stackoverflow.com/questions/30531990/matplotlib-into-a-django-template
    Embed in template as <img src="data:image/png;base64,{{ graphic|safe }}">
    """
    from io import BytesIO
    buffer = BytesIO()
    plt.savefig(buffer, format='svg', bbox_inches='tight')  # or png
    buffer.seek(0)
    image = buffer.getvalue()
    buffer.close()

    # png images
    # import base64
    # graphic = base64.b64encode(image)
    # return graphic.decode('utf-8')

    # svg image
    return image.decode('utf-8')


def get_plot_base_year(years: List[int]):
    """ return the first leap year if there is one, else the first year """
    for year in years:
        if is_leap_year(year):
            return year
    return years[0]


def is_leap_year(yr: int) -> bool:
    """ not divisible by 4: False
        else: not divisible by 100: True
        else: not divisible by 400: False
        else: True """
    if yr % 4:
        return False
    if yr % 100:
        return True
    if yr % 400:
        return False
    return True


def convert_cum_mileage_keys_to_strings(
        cumulative_mileage) -> Dict[str, Dict[str, Dict[dt.date, float]]]:
    # convert year and distance_units to strings, for template formatting
    cumulative_mileage_str: Dict[str, Dict[str, Dict[dt.date, float]]] = {}
    years = [y for y in cumulative_mileage]
    for year in years:
        distance_units = [du for du in cumulative_mileage[year]]
        str_yr = str(year)
        if str_yr not in cumulative_mileage_str:
            cumulative_mileage_str[str_yr] = {}
        for distance_unit in distance_units:
            str_du = str(DistanceUnits(distance_unit).name.lower())
            cumulative_mileage_str[str_yr][str_du] = (
                cumulative_mileage[year][distance_unit])
    return cumulative_mileage_str


def annual_mileage_totals(
        monthly_mileage: Dict[int, Dict[str, float]], years: List[int]
        ) -> Dict[str, float]:
    """ calculate totals by year for included years
    monthly_mileage is {month: {year: mileage}}
    totals is {year: mileage} """
    # year is a string in monthly_mileage
    totals: Dict[str, float] = {}
    for mileage in monthly_mileage.values():
        for year, dist in mileage.items():
            try:
                totals[str(year)] += dist
            except KeyError:
                totals[str(year)] = dist
    return totals


def get_prev_next_yr(sel_years: List[int], years: List[int]
                     ) -> Tuple[Optional[int], Optional[int]]:
    """ return the previous and next year in years, or None
    years must be sorted in ascending order"""
    # log.info("get_prev_next_yr: sel_years=%s, years=%s", sel_years, years)
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
