""" forms for the routes app """
import logging

from django import forms
from django.forms import ModelForm
from django.template.defaultfilters import filesizeformat
from .models import RawGpx



log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class UploadGpxForm(ModelForm):
    """ a form to upload a gpx file.
    
    To allow multiple files to be uploaded, see
    https://docs.djangoproject.com/en/5.1/topics/http/file-uploads/ """

    class Meta:
        model=RawGpx
        fields=["content"]

    def clean_gpx_file(self):
        """ ensure valid content type and size.  ref:
        http://ipasic.com/article/uploading-parsing-and-saving-gpx-data-postgis-geodjango
        """
        uploaded_file = self.cleaned_data['gpx_file']
        log.info("uploaded file content_type=%s", uploaded_file.content_type)

        content_type = uploaded_file.content_type
        allowed_content_types = ['text/xml', 'application/octet-stream']
        if content_type in allowed_content_types:
            if uploaded_file._size > 2621440:
                raise forms.ValidationError(
                    'Please keep filesize under 2.5 MB. Current filesize %s'
                    f'{filesizeformat(uploaded_file._size)}')

        else:
            raise forms.ValidationError('Filetype not supported.')

        return uploaded_file
