""" forms for the routes app """
import logging

from django import forms
from django.template.defaultfilters import filesizeformat
#from .models import RawGpx
from .models import Place



log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


# class UploadGpxForm(forms.ModelForm):
#     """ a form to upload a gpx file.
#
#     To allow multiple files to be uploaded, see
#     https://docs.djangoproject.com/en/5.1/topics/http/file-uploads/ """
#
#     class Meta:
#         model=RawGpx
#         fields=["content"]
#
#     def clean_content(self):
#         """ ensure valid content type and size.  ref:
#         http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
#         """
#         uploaded_file = self.cleaned_data['gpx_file']
#         log.info("uploaded file content_type=%s", uploaded_file.content_type)
#
#         content_type = uploaded_file.content_type
#         allowed_content_types = ['text/xml', 'application/octet-stream',
#                                  'application/gpx+xml']
#         if content_type in allowed_content_types:
#             if uploaded_file._size > 2621440:
#                 raise forms.ValidationError(
#                     'Please keep filesize under 2.5 MB. Current filesize %s'
#                     f'{filesizeformat(uploaded_file._size)}')
#
#         else:
#             raise forms.ValidationError('Filetype not supported.')
#
#         return uploaded_file

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
        fields=["name"]

