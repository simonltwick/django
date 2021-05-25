from django import forms
from django.forms import modelformset_factory
import datetime as dt
import logging

from .models import (
    Component, Ride, Odometer, MaintenanceAction, MaintenanceActionHistory)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class RideSelectionForm(forms.Form):
    num_rides = forms.IntegerField(
        required=False, initial=20, min_value=1,
        label="Maximum number of rides",
        help_text="Leave blank for all rides.")
    bike = forms.ChoiceField(required=False, choices=[])  # set in constructor
    this_year_start = dt.date(year=dt.date.today().year, month=1, day=1)
    start_date = forms.DateField(required=False, initial=this_year_start)
    end_date = forms.DateField(required=False, initial=dt.date.today())

    def __init__(self, *args, bikes, **kwargs):
        super(RideSelectionForm, self).__init__(*args, **kwargs)
        choices = [(None, '-All-')]
        choices += [(bike.id, bike.name) for bike in bikes]
        self.fields['bike'].choices = choices


ComponentFormSet = modelformset_factory(
    Component,
    fields=('bike', 'subcomponent_of', 'name', 'type'))


class RideForm(forms.ModelForm):
    class Meta:
        model = Ride
        fields = ['bike', 'date', 'distance', 'distance_units',
                  'ascent', 'ascent_units', 'description', ]
        widgets = {'description': forms.Textarea()}


class OdometerAdjustmentForm(forms.ModelForm):
    class Meta:
        model = Odometer
        fields = ['distance', 'initial_value', 'comment']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['distance'].widget.attrs['class']='odometer'


class OdometerForm(forms.ModelForm):
    model = Odometer
    # fields are defined in OdometerFormSet factory call

    def __init__(self, *args, user=None, reading_dtime=None, **kwargs):
        self.user = user
        self.reading_dtime = reading_dtime
        super().__init__(*args, **kwargs)
        self.fields['distance'].widget.attrs['class']='odometer'

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
    def clean(self):
        """ check that at least one formset has a distance entered """
        distance_entries = sum(
            1 for form in self
            if form.cleaned_data.get('distance') is not None)
        if not distance_entries:
            raise forms.ValidationError(
                "You must enter at least one odometer reading.")


OdometerFormSet = modelformset_factory(
    Odometer,
    formset=BaseOdometerFormSet,
    form=OdometerForm,
    fields=[# 'rider', 
            'bike', 'distance', 'distance_units', 'initial_value',
            'comment',], 
            # 'date'],
    extra=1  # overridden in view
    )


class DateTimeForm(forms.Form):
    reading_date_time = forms.DateTimeField(
        label='Reading date & time', initial=dt.datetime.now)


class MaintenanceActionUpdateForm(forms.ModelForm):
    class Meta:
        model = MaintenanceAction
        fields = ['description', 'due_date', 'due_distance',
                  # 'distance_units',
                  'recurring', 'maintenance_interval_distance',
                  'maint_interval_distance_units', 'maint_interval_days',
                  # 'distance', 'completed_distance', 'completed_date'
                  ]


class MaintCompletionDetailsForm(forms.ModelForm):
    class Meta:
        model = MaintenanceActionHistory
        fields = ['completed_date', 'distance']
