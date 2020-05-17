from django import forms
import datetime as dt
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class RideSelectionForm(forms.Form):
    num_rides = forms.IntegerField(
        required=False, initial=20, min_value=1,
        label="Maximum number of rides",
        help_text="Leave blank for all rides.")
    bike = forms.ChoiceField(required=False, choices=[])  # set in constructor
    this_year_start = dt.date(year=dt.date.today().year, month=1, day=1)
    start_date = forms.DateField(required=False,
                                 initial=this_year_start)
    end_date = forms.DateField(required=False,
                               initial=dt.date.today())

    def __init__(self, *args, bikes, **kwargs):
        super(RideSelectionForm, self).__init__(*args, **kwargs)
        choices = [(None, '-All-')]
        choices += [(bike.id, bike.name) for bike in bikes]
        self.fields['bike'].choices = choices
