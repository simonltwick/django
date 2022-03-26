'''
Handle Django signals
This module is executed from apps.py.AppConfig.ready()

Created on 26 Mar 2022

@author: simon
'''


from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Ride


# connect handler for post_delete signal for Ride instances
@receiver(post_delete, sender=Ride)
def on_ride_post_delete(sender, instance, **kwargs):
    Ride.on_post_delete(sender, instance, **kwargs)
