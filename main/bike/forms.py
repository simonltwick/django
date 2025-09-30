from django import forms
from django.forms import modelformset_factory, inlineformset_factory
from django.utils.dateparse import parse_duration
import datetime as dt
import logging
from typing import Dict

from .models import (
    Component, Ride, Odometer, MaintenanceAction, MaintenanceActionHistory,
    Preferences, MaintActionLink)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class DaysDurationInput(forms.TextInput):
    """ custom widget for DurationField.
        Ignores hh:mm:ss, simply returns dd days """

    def format_value(self, value):
        if not value:
            return ''

        duration = parse_duration(value)
        return f'{duration.days} days'


class RideSelectionForm(forms.Form):
    error_css_class = "text-danger"
    max_entries = forms.IntegerField(
        required=False, initial=20, min_value=1,
        label="Maximum number to display",
        help_text="Leave blank for all.")
    bike = forms.ChoiceField(required=False, choices=[])  # set in constructor
    start_date = forms.DateField(required=False)
    end_date = forms.DateField(required=False)

    def __init__(self, *args, bikes, **kwargs):
        super(RideSelectionForm, self).__init__(*args, **kwargs)
        choices = [(None, '-All-')]
        choices += [(bike.id, bike.name) for bike in bikes]
        self.fields['bike'].choices = choices


ComponentFormSet = modelformset_factory(
    Component,
    fields=('bike', 'subcomponent_of', 'name', 'type'))


class ComponentForm(forms.ModelForm):
    error_css_class = "text-danger"
    class Meta:
        model = Component
        fields = ['name', 'specification', 'date_acquired', 'supplier', 'notes']
        widgets = {
            "date_acquired": forms.DateInput(attrs={"size": 10}),
            "notes": forms.Textarea(attrs={"cols": 40, "rows": 2})}


class DistanceInputWidget(forms.NumberInput):
    """ expects & renders a variable {{ distance_units }} after the input field
    self.distance_units has to be initialised by the form's __init__ """
    template_name = "distance_input_widget.html"
    distance_units = "(distance_units unset)"

    def get_context(self, name, value, attrs) -> Dict:
        ctx = super().get_context(name, value, attrs)
        ctx["distance_units"] = self.distance_units
        return ctx


class PreferencesForm(forms.ModelForm):
    error_css_class = "text-danger"

    class Meta:
        model = Preferences
        fields = ('distance_units', 'ascent_units')



class PreferencesForm2(forms.ModelForm):
    error_css_class = "text-danger"

    class Meta:
        model = Preferences
        fields = ('maint_distance_limit', 'maint_time_limit')
        widgets = {
            "maint_distance_limit": DistanceInputWidget(attrs={"size": 6}),
            'maint_time_limit': DaysDurationInput(attrs={"size": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['maint_distance_limit'].widget.distance_units = (
            self.instance.distance_units_label.lower())


class PreferencesForm3(forms.ModelForm):
    error_css_class = "text-danger"

    class Meta:
        model = Preferences
        fields = ('track_nearby_search_distance', 'track_search_result_limit',
                  'place_nearby_search_distance', 'place_search_result_limit')
        widgets = {'track_nearby_search_distance':
                   DistanceInputWidget(attrs={"size": 6}),
                   'place_nearby_search_distance':
                   DistanceInputWidget(attrs={"size": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('track_nearby_search_distance',
                           'place_nearby_search_distance'):
            self.fields[field_name].widget.distance_units = (
                self.instance.distance_units_label.lower())



class RideForm(forms.ModelForm):
    error_css_class = "text-danger"

    class Meta:
        model = Ride
        fields = ['bike', 'date', 'distance',
                  'ascent', 'description', ]
        widgets = {
            'distance': forms.TextInput(attrs={"size": 6}),
            'ascent': forms.TextInput(attrs={"size": 6}),
            'description': forms.Textarea()}


class OdometerAdjustmentForm(forms.ModelForm):
    error_css_class = "text-danger"

    class Meta:
        model = Odometer
        fields = ['distance', 'initial_value', 'comment']
        widgets = {
            "distance": forms.TextInput(attrs={"class": 'odometer'}),
            }


class OdometerForm(forms.ModelForm):
    error_css_class = "text-danger"
    model = Odometer
    # fields are defined in OdometerFormSet factory call

    def __init__(self, *args, user=None, reading_dtime=None, **kwargs):
        self.user = user
        self.reading_dtime = reading_dtime
        super().__init__(*args, **kwargs)
        # css class odometer is defined as width 8
        self.fields['distance'].widget.attrs['class'] = 'odometer'
        self.fields['distance'].widget.distance_units = (
            user.preferences.distance_units_label.lower())

    # specialised handling of is_valid and save: forms with no distance data
    # are ignored (no validation, and no save)
    def distance_data(self):
        """ return the _raw_ distance data, if any """
        return self['distance'].value()

    def is_valid(self):
        if self.distance_data():
            return super(OdometerForm, self).is_valid()
        return True  # an empty form is valid, but won't be saved

    def save(self, *args, **kwargs):
        if not self.distance_data():
            return None
        # add rider field to the Odometer instance before saving
        kwargs2 = dict(kwargs, commit=False)
        obj = super(OdometerForm, self).save(*args, **kwargs2)
        obj.rider = self.user
        obj.date = self.reading_dtime
        if kwargs.get('commit'):
            obj.save()
        return obj


class BaseOdometerFormSet(forms.BaseModelFormSet):
    error_css_class = "text-danger"
    def clean(self):
        """ check that at least one formset has a distance entered """
        distance_entries = sum(
            1 for form in self
            if form.cleaned_data.get('distance') is not None)
        if not distance_entries:
            raise forms.ValidationError(
                "No odometer readings have been entered.")


OdometerFormSet = modelformset_factory(
    Odometer,
    formset=BaseOdometerFormSet,
    form=OdometerForm,
    fields=[  # 'rider',
            'bike', 'distance', 'initial_value', 'comment', ],
    #       'date'],
    widgets={"distance": DistanceInputWidget(attrs={"size": 8})},
    extra=1  # overridden in view
    )


MaintActionLinkFormSet = inlineformset_factory(
    MaintenanceAction, MaintActionLink,
    fields=('description', 'link_url'), extra=1)  # , can_delete=True)


class DateTimeForm(forms.Form):
    error_css_class = "text-danger"
    reading_date_time = forms.DateTimeField(
        label='Reading date & time', initial=dt.datetime.now)


class MaintenanceActionUpdateForm(forms.ModelForm):
    error_css_class = "text-danger"
    class Meta:
        model = MaintenanceAction
        fields = ['description', 'due_date', 'due_distance',
                  'recurring', 'maintenance_interval_distance',
                  'maint_interval_days',
                  ]
        widgets = {
            "due_date": forms.DateInput(attrs={"size": 10}),
            "due_distance": DistanceInputWidget(attrs={"size": 8}),
            "maintenance_interval_distance": DistanceInputWidget(attrs={"size": 8}),
            "maint_interval_days":  DaysDurationInput(attrs={"size": 6}),
           }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = (self.instance.user if hasattr(self, 'instance')
                else self.initial['user'])
        distance_units = user.preferences.distance_units_label.lower()
        self.fields["due_distance"].widget.distance_units = distance_units
        self.fields["maintenance_interval_distance"].widget.distance_units = (
            distance_units)


class MaintCompletionDetailsForm(forms.ModelForm):
    error_css_class = "text-danger"
    class Meta:
        model = MaintenanceActionHistory
        fields = ['completed_date', 'distance']
        widgets = {
            "completed_date": forms.DateInput(attrs={"size": 10}),
            "distance": DistanceInputWidget(attrs={"size": 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        maint_action = self.initial["action"]
        self.fields['distance'].widget.distance_units = (
            maint_action.distance_units_label.lower())
