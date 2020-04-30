'''
Classes for Game and Network
Created on 25 Apr 2020

@author: simon
'''
from .line import Line, Train
from .incident import GameIncidents
from .utils import list_to_str

import logging
import random
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class NetworkGame:
    """ represent the characteristics of whole network,
    with lines, incidents, responses, and status.   """
    INCIDENT_LIMIT = 1  # per place
    INCIDENT_SEVERITY_VARIATION = 0.5  # in range  +/- variation

    def __init__(self):
        self.line = Line()
        self.current_time = self.line.current_time
        self.catalog_places()
        self.incidents = GameIncidents(self.places)
        assert self.INCIDENT_SEVERITY_VARIATION < 1  # or negative severity

    def save(self):
        self.line.save()
        self.incidents.save()

    def catalog_places(self):
        # need to link each of these to the relevant line
        self.places = {
            'Station': self.line.stations,
            'Line': [place
                     for dirn in self.line.places
                     for place in self.line.places[dirn]
                     ],
            # NB incidents move with trains!
            'Train': [train
                      for dirn in self.line.trains
                      for pos_list in self.line.trains[dirn]
                      for train in pos_list
                      ]
            }

    def random_place(self, place_type):
        """ find a place at random.  Place type could be station, line or train
        """
        return random.choice(self.places[place_type])

    def dump_places(self):
        for k, place_list in self.places.items():
            log.info("%d %ss: %s", len(place_list), k, list_to_str(place_list))

    def sprinkle_incidents(self):
        for incident in self.incidents.generate_incidents():
            for _i in range(10):  # try 10 times for an incident-free place
                incident.location = self.random_place(
                    incident.incident_type.type)
                if self.can_place_incident(incident):
                    break
            else:
                log.warning("Unable to find available location for incident: "
                            f"discarding it")
                return
            incident.start_time = self.current_time
            # severity in range 0.5-1.5
            incident.severity = 0.5 + random.uniform(
                1-self.INCIDENT_SEVERITY_VARIATION,
                1+self.INCIDENT_SEVERITY_VARIATION)
            self.incidents.record(incident, incident.location)

    def can_place_incident(self, incident):
        """ update the incident location so it knows it has an incident
        Return False if there is already an incident there
        Currently only limits number of Incidents on Trains"""
        if isinstance(incident.location, Train):
            if len(incident.location.incidents) >= self.INCIDENT_LIMIT:
                return False  # already has an incident
            incident.location.incidents.append(incident)
        return True  # successfully placed incident

    def do_stage(self):
        """ generate incidents, update trains, accumulate impacts """
        self.sprinkle_incidents()
        self.current_time += 1
        self.line.update_trains()
