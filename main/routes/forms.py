""" forms for the routes app """
import logging

from django import forms
from django.template.defaultfilters import filesizeformat
#from .models import RawGpx
from .models import Place, PlaceType, Preference, Track


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class UploadGpxForm2(forms.Form):
    """ a form to upload a gpx file.  Not a model form. """
    error_css_class = "error"
    required_css_class = "required"
    gpx_file = forms.FileField()

    def clean_gpx_file(self):
        """ ensure valid content type and size.  ref:
        http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
        """
        uploaded_file = self.cleaned_data['gpx_file']
        log.info("uploaded file content_type=%s", uploaded_file.content_type)

        content_type = uploaded_file.content_type
        allowed_content_types = ['text/xml', 'application/octet-stream',
                                 'application/gpx+xml']
        if content_type not in allowed_content_types:
            raise forms.ValidationError('Filetype not supported.')

        if uploaded_file.size > 2621440:
            raise forms.ValidationError(
                'Please keep filesize under 2.5 MB. Current filesize %s'
                f'{filesizeformat(uploaded_file.size)}')

        return uploaded_file


class PlaceForm(forms.ModelForm):
    error_css_class = "error"
    required_css_class = "required"
    class Meta:
        model = Place
        fields=["name", "type"]


class CustomSelectWidget(forms.widgets.Select):
    option_template_class = "routes/place_type_icon_option.html"


class PreferenceForm(forms.ModelForm):
    error_css_class = "error"
    required_css_class = "required"
    class Meta:
        model = Preference
        exclude = ["pk", "user"]



class PlaceTypeForm(forms.ModelForm):
    error_css_class = "error"
    required_css_class = "required"

    class Meta:
        model = PlaceType
        fields = ["name", "icon"]
        widgets = {"icon": CustomSelectWidget}


track_years = [
    dt.year for dt in Track.objects.dates('start_time', 'year', order='DESC')]


class TrackSearchForm(forms.Form):
    start_date = forms.DateField(
        required=False, widget=forms.SelectDateWidget(years=track_years))
    end_date = forms.DateField(
        required=False, widget=forms.SelectDateWidget(years=track_years))

    def clean(self):
        cleaned_data = super().clean()
        try:
            if not (cleaned_data["start_date"] or cleaned_data["end_date"]):
                raise forms.ValidationError(
                    "At least one of start_date or end_date must be specified.")
        except KeyError:
            return


class TestCSRFForm(forms.Form):
    yesno = forms.BooleanField(required=False)


class PlaceSearchForm(forms.Form):
    name = forms.CharField(max_length=40, required=False)
    type = forms.ModelMultipleChoiceField(
        queryset=PlaceType.objects,
        widget=forms.CheckboxSelectMultiple)
