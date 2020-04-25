'''
Incident related classes
Created on 25 Apr 2020

@author: simon
'''


from utils import get_int, list_to_str
from sheetdb import get_data_range_as_class, put_data_range, \
    clear_data_range, get_data_range, get_data_range_as_settings
from line import Train, Place

from collections import defaultdict
import random
import re
from typing import Union

import logging
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


# ----- Different response options to handle incidents -----
class ResponseOption:
    def __init__(self, fields, values):
        """ fields & values become the attributes of the instance """
        self._fields = fields  # keep for dumping again later
        for attrname, value in zip(fields, values):
            setattr(self, attrname.lower(), value)

    def calculate_overall_impact(self):
        """ calculate and return overall impact of this response option """
        fix_time = self.time_to_fix or 5
        self.overall_impact = fix_time * (
            5 + abs(get_int(self.reputation_impact)) +
            abs(get_int(self.passenger_impact_percent)) / 30)
        return self.overall_impact

    def __str__(self):
        return f"R{self.response_option}. {self.response_name}"

    def __repr__(self):
        details = ', '.join(f"{k}={getattr(self, k)}" for k in self._fields
                            if k not in ('incident_example', 'response_option',
                                         'response_name') and getattr(self, k))
        return f"{str(self)[:-1]}: {details})"

    def as_list(self):
        """ return a list of all the fields """
        return [getattr(self, attrname.lower()) for attrname in self._fields]


class ResponseType:
    response_type = None
    incident_example = None

    def __init__(self):
        """ create a ResponseType with no Response Options """
        self.response_options = {}

    def add_option(self, option):
        if option.incident_example:
            self.incident_example = option.incident_example
        if self.response_type is None:
            self.response_type = option.response_type
        elif self.response_type != option.response_type:
            raise ValueError(
                f"{option} doesn't match response_type{self.response_type}")
        self.response_options[option.response_option] = option

    def get_option(self, response_option_number):
        """ return the response option corresponding to response_option """
        if response_option_number not in self.response_options:
            raise KeyError(f"unrecognized response_option_number "
                           f"{repr(response_option_number)}")
        return self.response_options[response_option_number]

    def calculate_overall_response_impacts(self):
        """ calculate the overall response impact of this response type
         as the average of all the response option impacts """
        assert self.response_options, "No response options defined"
        self.overall_impact = sum(
            option.calculate_overall_impact()
            for option in self.response_options.values())
        self.overall_impact /= len(self.response_options)
        # inverse impact is used to calculate chance of it occurring
        self.inverse_impact = 1/(1 + abs(self.overall_impact))
        return self.overall_impact

    def __str__(self):
        options = '\n  '.join(f'{k}: {v}'
                              for k, v in self.response_options.items())
        return f"ResponseType({self.response_type}. {self.incident_example}:" \
            f"\n  {options})"

    def as_rows(self):
        """ return a list of tuples, one per option """
        return [option.as_list() for option in self.response_options.values()]


class IncidentResponses:
    def __init__(self):
        """ create a dict of ResponseTypes indexed by Response_Type """
        self.response_types = defaultdict(ResponseType)
        self.fields, data = get_data_range_as_class(
            'Incident_Responses', 'Data', ResponseOption)
        for option in data:
                self.response_types[option.response_type].add_option(option)
        self.keys = list(self.response_types.keys())

    def calculate_impacts(self):
        assert self.response_types, "No response types defined"
        self.overall_impact = sum(
            response_type.calculate_overall_response_impacts()
            for response_type in self.response_types.values())
        self.overall_impact /= len(self.response_types)
        return self.overall_impact

    def __str__(self):
        responses = '\n  '.join(f'{k}: {v}'.replace('\n', '\n  ')
                                for k, v in self.response_types.items())
        return f"IncidentResponses(\n  {responses})"

    def __getitem__(self, key):
        """ convoluted to avoid creating a new ResponseType for a missing key
        """
        if key not in self.keys:
            raise KeyError("Undefined response_type {key}")
        rtype = self.response_types[key]
        assert hasattr(rtype, "response_type"), \
            f"invalid key {key} not caught in {rtype}"
        return rtype

    def save(self):
        rows = [self.fields]
        for response_type in self.response_types.values():
            rows.extend(response_type.as_rows())
        # log.info("rows dimensions = %d rows of %d columns", len(rows),
        #          len(rows[0]))
        # log.info("rows=%s", rows)
        put_data_range('Incident_Responses', 'Data', rows)


# ----- Different types of possible incident -----
class IncidentType:
    def __init__(self, fields, values):
        self._fields = fields  # keep for dumping again later
        for attrname, value in zip(fields, values):
            setattr(self, attrname.lower(), value)
        self.incident_type = int(self.incident_type)  # force int, not float

    def set_responsetype(self, responsetype: ResponseType):
        """ save the ResponseType, not the same field as response_type"""
        self.responsetype = responsetype
        try:
            self.expected_impact = self.responsetype.overall_impact
            self.inverse_impact = self.responsetype.inverse_impact
        except AttributeError as e:
            raise ValueError(f"Invalid ResponseType? {responsetype}") from e

    def as_list(self):
        return [getattr(self, attrname.lower()) for attrname in self._fields]

    def __str__(self):
        return self.incident_name

    def __repr__(self):
        return f"IncidentType({self.incident_type}. {self.incident_name}: " \
            f"response_type={self.response_type})"


class IncidentTypes:
    def __init__(self, response_types: IncidentResponses):
        self.incident_types = defaultdict(IncidentType)
        self.overall_impact = response_types.calculate_impacts()

        self.fields, incidents = get_data_range_as_class(
            "Incident_Types", "Data", IncidentType)
        for incident in incidents:
            self.incident_types[incident.incident_type] = incident
            incident.set_responsetype(response_types[incident.response_type])
        self.calculate_likelihoods()

    def calculate_likelihoods(self):
        """ calculate incident %likelihoods based on inverse impact
        The higher the impact (+ or -), the less chance of it happening"""
        total_inverse_impact = sum(
            incident_type.inverse_impact
            for incident_type in self.incident_types.values())
        for incident_type in self.incident_types.values():
            incident_type.likelihood_percentage = int(
                incident_type.inverse_impact * 100 / total_inverse_impact)

    def random_incident(self):
        """ return a random incident based on all incidentType likelihoods
        The incident doesn't have a start time or place specified yet """
        weights = [incident_type.inverse_impact
                   for incident_type in self.incident_types.values()]
        new_incident_type = random.choices(tuple(self.incident_types.values()),
                                           weights, k=1)[0]
        return Incident(new_incident_type)

    def save(self):
        rows = [self.fields]
        for incident_type in self.incident_types.values():
            rows.append(incident_type.as_list())
        # log.info("rows dimensions = %d rows of %d columns", len(rows),
        #          len(rows[0]))
        # log.info("rows=%s", rows)
        put_data_range('Incident_Types', 'Data', rows)

    def get_by_type(self, incident_type: int):
        """ return the IncidentType with this incident_type """
        if not isinstance(incident_type, int):
            raise TypeError(f"expecting int, not {repr(incident_type)}")
        if incident_type not in self.incident_types:
            raise KeyError(f"{incident_type} not found in incident_types "
                           f"({self.incident_types})")
        return self.incident_types[incident_type]

    def __str__(self):
        data = '\n  '.join(str(incident)
                           for incident in self.incident_types.values())
        return f"IncidentTypes(\n  {data})"


class Incident:
    start_time = None
    location = None
    severity = None
    response_option = None
    response_start = None
    incident_types = None  # used to lookup incident types by load()
    place_finder = None  # used to find places by load()

    def __init__(self, incident_type):
        self.incident_type = incident_type

    def __str__(self):
        if self.incident_type.type == 'Train':
            assert isinstance(self.location, Train), \
                f"Train type incident not on a train: {self.incident_type} " \
                f"at {self.location}"
        return f"{self.incident_type} at {self.location}"

    @classmethod
    def load(cls, fields, values):
        value_dir = dict(zip(fields, values))
        # create & set incident type first
        # log.info("Incident.load(%s)", value_dir)
        incident_type = cls.incident_types.get_by_type(
            int(value_dir.pop('Incident_Type')))
        incident = cls(incident_type)
        # now fill in the other fields
        for field_name, value in value_dir.items():
            if field_name == 'Incident_Name':
                assert value == incident_type.incident_name, \
                    f"Mismatch between Incident_Name={value} and " \
                    f"IncidentType.name={incident_type.incident_name}"
            elif field_name == 'Location':
                incident.location = cls.place_finder(value)
                if isinstance(incident.location, Train):
                    # put the incident on the train
                    incident.location.incidents.append(incident)
            elif field_name == 'Severity':
                incident.severity = float(value)
            elif field_name == 'Start_Time':
                incident.start_time = value
            elif field_name == 'Response_Option':
                if value == '':
                    incident.response_option = None
                else:
                    responsetype = incident_type.responsetype
                    incident.response_option = responsetype.get_option(
                        value)
            elif field_name == 'Response_Start':
                incident.response_start = value if value else None
            else:
                raise ValueError(f"Unrecognised field_name: {field_name}")
        return incident

    def as_list(self, fields):
        """ return the values of the specified fields as a list """
        """ value_sources maps field names to where the data can be found,
           either a string (attr name) or a callable """
        value_sources = {"Incident_Name": str(self.incident_type),
                         "Location": str(self.location),
                         "Incident_Type": self.incident_type.incident_type,
                         "Severity": self.severity,
                         "Start_Time": self.start_time,
                         "Response_Option": self.response_option or '',
                         "Response_Start": self.response_start or ''}
        values = [value_sources[field_name] for field_name in fields]
        return values


class GameIncidents:
    """ represent incidents in an operational game """
    def __init__(self, places):
        self.places = places  # used by find_place in load_incidents
        self.incidents_by_line = defaultdict(list)
        self.incident_responses = IncidentResponses()
        self.incident_types = IncidentTypes(self.incident_responses)
        self.get_incident_settings()
        self.load_incidents()

    def load_incidents(self):
        # initialise helper functions
        Incident.incident_types = self.incident_types  # used by load()
        Incident.place_finder = self.find_place
        self.train_pattern = re.compile(r'^\**Train \d+ at (.+) on (.+)$')
        self.place_pattern = re.compile(r'^.*, .* on .*$|^')
        # get address of incident table
        self.data_range = get_data_range('Incidents', 'Data_Range')[0][0]
        self.fields, self.incidents = get_data_range_as_class(
            'Incidents', self.data_range, Incident.load)
        log.debug("load_incidents loaded %s", list_to_str(self.incidents))

    def find_place(self, loc_name: str) -> Union[Place, Train]:
        train_match = self.train_pattern.fullmatch(loc_name)  # Train ?
        if train_match:
            # match on train location, not number
            for place in self.places['Train']:
                place_match = self.train_pattern.fullmatch(str(place))
                if place_match.groups() == train_match.groups():
                    return place
        else:
            if self.place_pattern.fullmatch(loc_name):
                key = 'Line'
            else:
                key = 'Station'
            log.debug("trying to find %s: %s in %s", key, loc_name,
                      list_to_str(self.places[key]))
            for place in self.places[key]:
                if loc_name == str(place):
                    return place
        raise ValueError(f"Unable to locate {loc_name}")

    def save(self):
        log.info("Incidents = %s", list_to_str(self.incidents))
        incident_data = [incident.as_list(self.fields)
                         for incident in self.incidents]
        data = [self.fields] + incident_data
        new_range = self.calc_new_data_range(len(self.fields), len(data))
        # empty_data = [self.fields] + \
        #     len(incident_data) * [len(self.fields)*['']]
        # put_data_range('Incidents', self.data_range, empty_data)
        clear_data_range("Incidents", self.data_range)
        put_data_range('Incidents', new_range, data)
        put_data_range('Incidents', 'Data_Range', [[new_range]])

    def calc_new_data_range(self, cols, rows):
        pattern = r'^\$?([A-Za-z]+)\$?(\d+):.*'  # [$]lettersnumbers:ignore
        match = re.match(pattern, self.data_range)
        if match is None:
            raise ValueError(
                f"Couldn't parse Incidents data_range {self.data_range}")
        start_col, start_row = match.groups()  # e.g. ('A', '6')
        end_row = int(start_row) + rows - 1
        # calc end col as a number, col A is 1
        end_col = ord(start_col.upper()) - ord('A') + cols  # as a number
        if end_col > 26:  # 2 letter row ids
            end_col = divmod(end_col-1, 26)  # now it starts at 0
            end_col = [chr(ord('A') + num) for num in end_col]  # eg (A, B)
            end_col = ''.join(end_col)  # eg. 'AA'
        else:
            end_col = chr(ord('A') + end_col - 1)
        new_data_range = f'{start_col}{start_row}:{end_col}{end_row}'
        return new_data_range

    def get_incident_settings(self):
        """ create a dict of the settings in Incident_Types """
        self.incident_settings = get_data_range_as_settings("Incident_Types",
                                                            "Settings")
        self.incident_freq = self.incident_settings['Incident_Frequency']

    def record(self, incident: Incident, line="Line"):
        """ record a new incident """
        if incident.start_time is None or not (incident.location and
                                               incident.severity):

            raise ValueError("Incident start_time, location or severity not "
                             f"specified in {incident}")
        self.incidents.append(incident)
        self.incidents_by_line[line].append(incident)
        log.warning("Time %d: %s", incident.start_time, incident)

    def generate_incidents(self):
        """ yield a random number of new incidents up to twice the average
        incident frequency.
        The new incidents need a place, start time and severity allocating
        (done by caller)
        and they need to added to the GameIncidents by GameIncidents.record

        generates up to 2*freq/100 incidents per call, with an average
        event frequency of freq/100 """
        num = random.randrange(200 * self.incident_freq + 10000) // 10000

        for _i in range(num):
            yield self.incident_types.random_incident()


class TestDataRange(GameIncidents):
    """ use for testing GameIncidents.calc_new_data_range """
    def __init__(self):
        self.data_range = "A5:b6"
        """>>> from test import TestDataRange;t=TestDataRange()
        >>> t.calc_new_data_range(2,1)
        'A5:B5'
        >>> t.calc_new_data_range(27,1)
        'A5:BA5'
        >>> t.calc_new_data_range(25,1)
        'A5:Y5'
        >>> t.calc_new_data_range(26,1)
        'A5:Z5'
        """
