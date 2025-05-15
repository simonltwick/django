import json
from django.shortcuts import render

# Create your views here.


from django.core.serializers import serialize
from django.views.generic import TemplateView
from routes.models import Marker


class MapView(TemplateView):
    template_name = "map.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["markers"] = json.loads(
            serialize(
                "geojson",
                Marker.objects.all(),
            )
        )
        return ctx
