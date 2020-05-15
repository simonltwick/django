'''
signal handlers
Created on 14 May 2020

@author: simon
'''
from django.dispatch import receiver, Signal
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

signal_game_start = Signal(providing_args=['game'])


@receiver(signal_game_start)
def game_start_handler(game, **kwargs):
    """ start the game running until the end of the next stage_interval, or
        end of day """
    log.info("game_start signal received for %s", game)
    game.play_init()
