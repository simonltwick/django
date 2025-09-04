""" forms for the routes app """
import logging

from django import forms
from django.template.defaultfilters import filesizeformat
#from .models import RawGpx
from .models import Place, PlaceType, Preference, Track, Boundary
from django.contrib.gis import forms as geoforms
from django.contrib.gis.forms.widgets import OpenLayersWidget


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


# ref for multiple file uploads:
# https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class UploadGpxForm2(forms.Form):
    """ a form to upload a gpx file.  Not a model form. """
    error_css_class = "text-danger"
    required_css_class = "required"
    # TODO: use a custom widget to allow <input ... accept=".gpx">
    gpx_file = MultipleFileField()

    def clean_gpx_file(self):
        """ ensure valid content type and size.  ref:
        http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
        """
        uploaded_files = self.cleaned_data['gpx_file']
        for i, f in enumerate(uploaded_files):
            log.info("gpx file #%d: %s content_type=%s",
                     i+1, f.name, f.content_type)

            content_type = f.content_type
            allowed_content_types = ['text/xml', 'application/octet-stream',
                                     'application/gpx+xml']
            if content_type not in allowed_content_types:
                pass
                #raise forms.ValidationError(
                #    f'Content-Type {content_type!r} not supported.')

            if f.size > 2621440:
                raise forms.ValidationError(
                    'Please keep filesize under 2.5 MB. Current filesize %s'
                    f'{filesizeformat(f.size)}')

        return uploaded_files




class UploadBoundaryForm(forms.Form):
    """ a form to upload a gpx file.  Not a model form. """
    error_css_class = "text-danger"
    required_css_class = "required"
    # TODO: use a custom widget to allow <input ... accept=".gpx">
    category = forms.CharField(max_length=40, help_text="A category for the "
                               "uploaded boundary or boundaries, for example, "
                               "English Counties")
    gpx_file = MultipleFileField()


# class BoundaryForm(forms.ModelForm):
#     error_css_class = "text-danger"
#     polygon = geoforms.PolygonField(widget=geoforms.OSMWidget(attrs={'map_width': 800, 'map_height': 500}))
#     class Meta:
#         model = Boundary
#         fields = ('category', 'name', 'polygon')


class PlaceForm(forms.ModelForm):
    error_css_class = "text-danger"
    required_css_class = "required"
    class Meta:
        model = Place
        fields=["name", "type"]  # , "tag"]
        widgets = {"type": forms.RadioSelect}


class PlaceUploadForm(forms.Form):
    error_css_class = "text-danger"
    required_css_class = "required"
    # TODO: use a custom widget to allow <input ... accept=".csv">
    csv_file = forms.FileField()

    def clean_csv_file(self):
        """ ensure valid content type and size.  ref:
        http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
        """
        uploaded_file = self.cleaned_data['csv_file']
        content_type = uploaded_file.content_type
        log.info("uploaded file content_type=%s", content_type)

        if content_type != 'text/csv':
            raise forms.ValidationError(
                f'Content-Type {content_type!r} not supported.')

        if uploaded_file.size > 2621440:
            raise forms.ValidationError(
                'Please keep filesize under 2.5 MB. Current filesize %s'
                f'{filesizeformat(uploaded_file.size)}')

        return uploaded_file


class CustomSelectWidget(forms.widgets.Select):
    option_template_class = "routes/place_type_icon_option.html"


class PreferenceForm(forms.ModelForm):
    error_css_class = "text-danger"
    required_css_class = "required"
    class Meta:
        model = Preference
        exclude = ["pk", "user"]



class PlaceTypeForm(forms.ModelForm):
    error_css_class = "text-danger"
    required_css_class = "required"

    class Meta:
        model = PlaceType
        fields = ["name", "icon"]
        widgets = {"icon": CustomSelectWidget}

    def clean(self):
        """ check at least one search criteria is specified """
        cleaned_data = super().clean()
        print("PlaceTypeForm.cleaned_data=", cleaned_data)
        for value in cleaned_data.values():
            if value:
                return cleaned_data
        raise forms.ValidationError(
            "At least one search criteria must be specified.")


class TrackDetailForm(forms.ModelForm):
    error_css_class = "text-danger"
    class Meta:
        model = Track
        fields = ["description"]


track_years = [
    dt.year for dt in Track.objects.dates('start_time', 'year', order='DESC')]


class TrackSearchForm(forms.Form):
    error_css_class = "text-danger"
    start_date = forms.DateField(
        required=False, widget=forms.SelectDateWidget(years=track_years))
    end_date = forms.DateField(
        required=False, widget=forms.SelectDateWidget(years=track_years))
    track_tags = forms.CharField(
        max_length=50, required=False,
        help_text="Enter tag names separated by commas")

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data["start_date"] or cleaned_data["end_date"]
                or cleaned_data["track_tags"]):
            raise forms.ValidationError(
                "At least one of start date, end date or tags "
                "must be specified.")
        return cleaned_data


# class TestCSRFForm(forms.Form):
#     yesno = forms.BooleanField(required=False)


class PlaceSearchForm(forms.Form):
    error_css_class = "text-danger"
    name = forms.CharField(max_length=40, required=False)
    type = forms.ModelMultipleChoiceField(
        queryset=PlaceType.objects,
        widget=forms.CheckboxSelectMultiple,
        required=False)
    place_tags = forms.CharField(
        max_length=50, required=False,
        help_text="Enter tag names separated by commas")

    def clean(self):
        cleaned_data = super().clean()
        if not (cleaned_data["name"] or cleaned_data["type"]
                or cleaned_data["place_tags"]):
            raise forms.ValidationError(
                "At least one of name, type or tags must be specified.")
        return cleaned_data


class PlaceTagSelectForm(forms.ModelForm):
    model=Place

    class Meta:
        fields=["tag"]
