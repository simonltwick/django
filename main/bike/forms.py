from django import forms
from django.forms import modelformset_factory, inlineformset_factory
from django.utils.dateparse import parse_duration
import datetime as dt
import logging

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
    class Meta:
        model=Component
        fields=['name', 'specification', 'date_acquired', 'supplier', 'notes']
        widgets={
            "notes": forms.Textarea(attrs={"cols": 40, "rows": 2})}


class PreferencesForm(forms.ModelForm):
    class Meta:
        model = Preferences
        fields = ('distance_units', 'ascent_units',
                  'maint_distance_limit', 'maint_time_limit')
        widgets = {
            'maint_time_limit': DaysDurationInput()}


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
        self.fields['distance'].widget.attrs['class'] = 'odometer'


class OdometerForm(forms.ModelForm):
    model = Odometer
    # fields are defined in OdometerFormSet factory call

    def __init__(self, *args, user=None, reading_dtime=None, **kwargs):
        self.user = user
        self.reading_dtime = reading_dtime
        super().__init__(*args, **kwargs)
        self.fields['distance'].widget.attrs['class'] = 'odometer'

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
                "No odometer readings have been entered.")


OdometerFormSet = modelformset_factory(
    Odometer,
    formset=BaseOdometerFormSet,
    form=OdometerForm,
    fields=[  # 'rider',
            'bike', 'distance', 'distance_units', 'initial_value',
            'comment', ],
    #       'date'],
    extra=1  # overridden in view
    )


MaintActionLinkFormSet = inlineformset_factory(
    MaintenanceAction, MaintActionLink,
    fields=('description', 'link_url'), extra=1)  # , can_delete=True)


class DateTimeForm(forms.Form):
    reading_date_time = forms.DateTimeField(
        label='Reading date & time', initial=dt.datetime.now)


class MaintenanceActionUpdateForm(forms.ModelForm):
    class Meta:
        model = MaintenanceAction
        fields = ['description', 'due_date', 'due_distance',
                  'recurring', 'maintenance_interval_distance',
                  'maint_interval_days',
                  ]


class MaintCompletionDetailsForm(forms.ModelForm):
    class Meta:
        model = MaintenanceActionHistory
        fields = ['completed_date', 'distance']
