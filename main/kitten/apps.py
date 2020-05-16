from django.apps import AppConfig
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class KittenConfig(AppConfig):
    name = 'kitten'

    def ready(self):
        from . import signals  # which registers the handler
