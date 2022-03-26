from django.apps import AppConfig


class BikeConfig(AppConfig):
    name = 'bike'

    def ready(self):
        from . import signals
