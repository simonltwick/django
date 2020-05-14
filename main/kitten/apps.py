from django.apps import AppConfig
import logging
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class KittenConfig(AppConfig):
    name = 'kitten'

    def ready(self):
        from .signals import game_start_handler  # which registers the handler
        log.info("apps.KittenConfig.ready()")
