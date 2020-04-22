'''
Test libreoffice macro
must be linked (ln -s) from ~/.config/libreoffice/4/user/Scripts/python
Created on 18 Apr 2020

ref: http://christopher5106.github.io/office/2015/12/06/openoffice-libreoffice-automate-your-office-tasks-with-python-macros.html
api for ranges (in basic)
 https://wiki.documentfoundation.org/Macros/Basic/Calc/Ranges
Python developer guide, inc. api for documents/sheets
 https://wiki.documentfoundation.org/Macros/Python_Guide
Help resources on macros:
 https://wiki.documentfoundation.org/Macros
Base ranges api (in C/Java?)
 https://api.libreoffice.org/docs/idl/ref/servicecom_1_1sun_1_1star_1_1sheet_1_1NamedRange.html
Useful Functions (msgbox)
 https://wiki.documentfoundation.org/Macros/Python_Guide/Useful_functions
Msgbox specifically:
 https://wiki.documentfoundation.org/Macros/General/IO_to_Screen#Using_the_API
Importing libreoffice functions into python scripts: (see
 Installation Modules for Applications):
 https://help.libreoffice.org/6.3/en-US/text/sbasic/python/python_import.html
@author: simon
'''
from collections import defaultdict
import logging
import random
import re
import sys
import uno
import msgbox  # this is provided when launched as a macro
global XSCRIPTCONTEXT, Session, log
# -*- coding: utf-8 -*-


def message_box(message, title='My Message Box'):
    box = msgbox.MsgBox(uno.getComponentContext())
    box.addButton("OK")
    box.renderFromButtonSize()
    box.numberOflines = 2
    return box.show(message, 0, title)


def get_model():
    """ get the doc from the scripting context,
    which is made available to all scripts """
    desktop = XSCRIPTCONTEXT.getDesktop()
    model = desktop.getCurrentComponent()
    # check whether there's already an opened calc document.
    if not hasattr(model, "Sheets"):
        # Otherwise, create a new one
        model = desktop.loadComponentFromURL(
            "private:factory/scalc", "_blank", 0, ())
    return model


def validate_sheet_name(model, sheet_name):
    if sheet_name not in model.Sheets.ElementNames:
        raise ValueError(f"Invalid sheet_name: {sheet_name}")
    return model.Sheets.getByName(sheet_name)


def get_data_range(sheet_name, data_range="Data"):
    """ get the range "Data" in sheet, and return it as a
    list of lists """
    model = get_model()
    sheet = validate_sheet_name(model, sheet_name)
    try:
        range1 = sheet.getCellRangeByName(data_range)
    except Exception as e:
        log.error('%r in get_data_range(%s, %s)', e, sheet_name, data_range)
        raise
    return range1.getDataArray()


def put_data_range(sheet_name, data_range, data):
    """ put data (in rows) in data_range """
    assert isinstance(data, (tuple, list)), f'Invalid data type: {data}'
    model = get_model()
    sheet = validate_sheet_name(model, sheet_name)
    try:
        if ':' not in data_range:
            range1 = sheet.getCellRangeByName(data_range)
            range1.setDataArray(data)
        else:
            ccrr = data_range.split(':', 1)
            cols = [chr(i)
                    for i in range(ord(ccrr[0][0]), ord(ccrr[1][0]) + 1)]
            rows = range(int(ccrr[0][1:]), int(ccrr[1][1:])+1)
            for row, row_data in zip(rows, data):
                for col, cell_data in zip(cols, row_data):
                    cell = f'{col}{row}'
                    tRange = sheet.getCellRangeByName(cell)
                    tRange.String = cell_data
    except Exception as e:
        log.error("%r in put_data_range(%s, %s, %s)", e, sheet_name,
                  data_range, data)
        raise


def clear_data_range(sheet_name, data_range):
    """ remove all values (not formulas, styling etc) from range """
    model = get_model()
    sheet = validate_sheet_name(model, sheet_name)
    range1 = sheet.getCellRangeByName(data_range)
    # 7: see https://www.openoffice.org/api/docs/common/ref/com/sun/star/sheet/CellFlags.html
    range1.clearContents(7)


def PythonVersion(*_args):
    """Prints the Python version into the current document in cells c4 & c5"""
    model = get_model()
    # get the XText interface
    sheet = model.Sheets.getByIndex(0)
    # create an XTextRange at the end of the document
    tRange = sheet.getCellRangeByName("C4")
    # and set the string
    tRange.String = "The Python version is %s.%s.%s" % sys.version_info[:3]
    # do the same for the python executable path
    tRange = sheet.getCellRangeByName("C5")
    tRange.String = sys.executable
    return None


class LoggingSetup():
    def __init__(self, msg=''):
        log = logging.getLogger(__name__)
        log.setLevel(logging.DEBUG)
        logging.basicConfig(filename='/home/simon/code/kitten/test.log',
                            filemode='w',
                            level=logging.DEBUG,
                            format='%(levelname)s: %(message)s')
        if msg:
            log.info(msg)
        self.log = log

    def __enter__(self):
        return self.log

    def __exit__(self, exc_type, _exc_value, _exc_traceback):
        if exc_type is not None:
            self.log.exception('Exception:')
        logging.shutdown()


def train_can_move(prev_pos, pos, trains, last_train_time, current_time,
                   wait, is_last_stop: bool):
    """ train can move if there is a train there to move,
        the line ahead is clear,
        and it's waited long enough at the current place """
    global log
    if not trains[prev_pos]:
        return False
    if trains[pos] and not is_last_stop:  # multiple trains ok at end of line
        return False
    # so we know there is a train at i-1, and none at i.
    if not last_train_time[prev_pos]:  # no last train time recorded
        return True
    # how long has the train been here?
    log.info("Considering whether to move train at %d to %d: current_time=%d, "
             "last_train_time=%d, wait=%d", prev_pos, pos, current_time,
             last_train_time[prev_pos], wait[prev_pos])
    if current_time - last_train_time[prev_pos] >= wait[prev_pos]:
        log.info("* Train at %d can move", prev_pos)
        return True
    return False


def move_train(prev_pos, pos, trains, last_train_time, current_time):
    """ move a train from i to i+1, updating trains and last_train_time """
    log.info("Moving train from %d to %d at t=%d, trains=%s",
             prev_pos, pos, current_time, trains)
    assert trains[prev_pos], f'no train to move at position {prev_pos}'
    trains[prev_pos] -= 1
    trains[pos] += 1
    log.info("updated trains = %s", trains)
    last_train_time[prev_pos] = current_time  # departure time, for depot
    last_train_time[pos] = current_time  # arrival time


def make_ints(values, keys):
    for key in keys:
        values[key] = [int(v) if v else 0 for v in values[key]]


def get_int(value):
    return int(value) if value else 0


def get_data_range_as_dict(sheet_name, range_name):
    """ return contents of data range as a dict, with keys = first column """
    info = get_data_range(sheet_name, range_name)
    # transform to dict
    return {title: list(values) for title, *values in info}


def put_data_range_from_dict(sheet_name, range_name, data):
    """ update a data range from a dict of values """
    data_array = [[key] + value for key, value in data.items()]
    put_data_range(sheet_name, range_name, data_array)


def get_data_range_as_class(sheet_name, range_name, cls):
    """ return a list instances of cls, one per row,
        cls signature is cls(keys, values) with keys = row[0]
        Also return the first row, which should be a list of fields"""
    info = get_data_range(sheet_name, range_name)
    fields = info[0]
    # global log
    # log.info('get_data_range_as_class: info=%s', info)
    return fields, [cls(fields, row) for row in info[1:]]


def get_data_range_as_settings(sheet_name, range_name):
    """ return a dict of settings.  The range must be two columns wide,
    col0 is the key and col1 is the value.
    NB the key will be in the same case (upper/lower/mixed) as the spreadsheet.
    """
    info = get_data_range(sheet_name, range_name)
    if len(info[0]) != 2:
        raise TypeError(
            f"range {range_name} should have 2 columns, not {len(info[0])}.")
    return dict(info)


class Line():
    def __init__(self):
        self.info = get_data_range_as_dict("Line", 'Data')
        self.place_names = self.info['Place']
        self.train_directions = [key for key in self.info
                                 if key.startswith('Trains')]
        self.directions = [train_direction[6:]
                           for train_direction in self.train_directions]
        assert 0 < len(self.directions) < 3, \
            f"Invalid number of Trains...rows: {self.directions}"
        self.last_train_times = [key for key in self.info
                                 if key.startswith('Last_Train_Time')]
        assert len(self.train_directions) == len(self.last_train_times), \
            f"mismatch between train_directions {self.train_directions} and " \
            f"last_train_times {self.last_train_times}"
        self.setup_places()
        make_ints(self.info,
                  self.train_directions + self.last_train_times + ['Wait'])
        self.setup_trains()
        self.wait = self.info['Wait']
        self.current_time = int(self.info['Current_Time'][0])
        self.delay = int(self.info['Delays'][0])
        self.name = self.info['Line_Name'][0]

    def __str__(self):
        return self.name

    def reset(self):
        size = len(self.info['Place'])
        for direction in self.directions:
            self.info["Trains" + direction] = size * ['']
            self.info['Last_Train_Time' + direction] = size * ['']
        # override turnaround at depots
        turnaround0 = self.info['Turnaround%'+self.directions[0]]
        turnaround0[0] = ''
        turnaround0[-1] = 100
        turnaround1 = self.info['Turnaround%'+self.directions[1]]
        turnaround1[0] = 100
        turnaround1[-1] = ''
        self.info[self.train_directions[0]] = self.info['Initial_Trains']
        self.info['Incident_ID'] = size * ['']
        self.info['Incident_Start'] = size * ['']
        self.info['Wait'][0] = self.info['Train_Freq'][0]
        self.info['Wait'][-1] = self.info['Train_Freq'][0]
        self.current_time = 0
        self.delay = 0
        put_data_range_from_dict("Line", "Data", self.info)

    def save(self):
        self.info['Current_Time'][0] = self.current_time
        self.info['Delays'][0] = self.delay
        put_data_range_from_dict("Line", "Data", self.info)

    def update_trains(self):
        """ update the status of all trains on the line """
        self.current_time += 1
        self.turnaround_trains()
        self.move_trains()

    def turnaround_trains(self):
        if len(self.directions) < 2:
            return

        # train turnaround at depots and where turnaround specified
        # move trains from end-of-line depots to start-of-line depots in
        # opposite direction
        # TODO: implement train turnarounds where Turnaround% > 0
        end1, end2 = 0, len(self.info[self.train_directions[0]]) - 1
        trains_dir0 = self.info[self.train_directions[0]]
        trains_dir1 = self.info[self.train_directions[1]]
        # should really update last_train_time at depots too
        last_train_time_dir0 = self.info['Last_Train_Time' +
                                         self.directions[0]]
        last_train_time_dir1 = self.info['Last_Train_Time' +
                                         self.directions[1]]

        # update last_train_time at depot if no trains already there
        if not trains_dir0[end1]:
            last_train_time_dir0[end1] = max(last_train_time_dir1[end1],
                                             last_train_time_dir0[end1])
        if not trains_dir1[end2]:
            last_train_time_dir1[end2] = max(last_train_time_dir0[end2],
                                             last_train_time_dir1[end2])
        trains_dir0[end1] += trains_dir1[end1]
        trains_dir1[end1] = 0
        trains_dir1[end2] += trains_dir0[end2]
        trains_dir0[end2] = 0

    def move_trains(self):
        # move trains: run through places in reverse order
        for i, train_direction in enumerate(self.train_directions):
            direction = train_direction[6:]  # cut out Trains prefix
            last_train_time = self.info['Last_Train_Time' + direction]
            trains = self.info[train_direction]
            # log.info("calculating train moves %s, trains=%s", direction,
            #          trains)
            if i:  # second train direction
                pos_iterator = range(len(self.place_names)-1)
                prev_pos = +1
                last_stop = 0
                first_stop = len(self.place_names) - 1
            else:
                pos_iterator = reversed(range(1, len(self.place_names)))
                prev_pos = -1
                last_stop = len(self.place_names) - 1
                first_stop = 0
            for i in pos_iterator:
                # loop through places where trains could move to
                # log.info("  %d(%d) -> %d(%d)", i+prev_pos,
                #          trains[i+prev_pos], i, trains[i])
                if trains[i + prev_pos]:
                    is_last_stop = i == last_stop
                    if train_can_move(i + prev_pos, i, trains,
                                      last_train_time, self.current_time,
                                      self.wait, is_last_stop):
                        move_train(i + prev_pos, i, trains,
                                   last_train_time, self.current_time)
                        log.info("move_train returned trains=%s", trains)
                    elif prev_pos != first_stop:
                        self.delay += 1  # increment delay if not depot

    def stations(self):
        """ return a list of stations and their positions """
        return [Place("Station", name, self, pos=pos)
                for pos, name in enumerate(self.place_names)
                if name not in ('Line', 'Depot', 'Depot2')]

    def train_quantities(self):
        """ return a list of trains and their positions (including direction)
        """
        return [(qty, self.place_name(pos, dirn))
                for dirn, direction in enumerate(self.train_directions)
                for pos, qty in enumerate(self.info[direction])
                if qty]

    def setup_trains(self):
        """ create a list of train instances for this line """
        self.trains = [Train(self, place)
                       for qty, place in self.train_quantities()
                       for _i in range(qty)]

    # TODO: restructure use of self.place_names
    def place_name(self, pos, direction):
        """ return the name of the place at pos.  If it's a station or
        depot, just return the name, else return 'Line between x and y'
        (or Line between y and x if direction is 1)
        """
        assert direction in (0, 1), \
            f"Invalid value {direction} for direction"
        place_name = self.place_names[pos]
        if place_name == 'Line':
            a, b = self.place_names[pos-1], self.place_names[pos+1]
            if direction:
                a, b = b, a  # switch direction
            place_name = f'Between {a} and {b}'
        return f"{place_name}, {self.directions[direction]}"

    def setup_places(self):
        """ return the list of places on the line """
        self.places = []
        for direction in (0, 1):
            for pos in range(len(self.place_names)):
                place = Place("Place", self.place_name(pos, direction), self,
                              pos=pos, direction=direction)
                self.places.append(place)


def update_line(*_args):
    """ update the status of all trains on the line """
    global current_time, log
    with LoggingSetup('update_line') as log:
        line = Line()
        line.update_trains()
        line.save()


def list_to_str(l: list):
    """ return a string version with str(item) for items in list """
    return ', '.join(str(item) for item in l)


def reset_line(*_args):
    """ reset trains and incidents on the line to the starting value """
    global current_time, log
    with LoggingSetup('reset_line') as log:
        line = Line()
        log.info("Stations for %s: %s", line.name, line.stations())
        log.info("Places for %s: %s", line.name,
                 list_to_str(line.get_places()))
        log.info("Trains for %s: %s", line.name, list_to_str(line.trains))
        line.reset()
        line.save()
        return


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
            5 - get_int(self.reputation_impact) -
            get_int(self.passenger_impact_percent) / 30)
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


def overall_response_impacts(*_args):
    global log
    with LoggingSetup('overall_response_impacts') as log:
        incident_responses = IncidentResponses()
        # log.info("Incident Responses = %s", incident_responses)
        overall_impact = incident_responses.calculate_impacts()
        log.info("Overall impact = %s", overall_impact)
        incident_responses.save()


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
    place_finder = lambda x: f'Place({x})'

    def __init__(self, incident_type):
        self.incident_type = incident_type

    def __str__(self):
        return f"{self.incident_type} at {self.location}"

    @classmethod
    def load(cls, fields, values):
        value_dir = dict(zip(fields, values))
        # create & set incident type first
        log.info("Incident.load(%s)", value_dir)
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
                         "Severity": f'{self.severity:0.2f}',
                         "Start_Time": self.start_time,
                         "Response_Option": self.response_option or '',
                         "Response_Start": self.response_start or ''}
        values = [value_sources[field_name] for field_name in fields]
        return values


class GameIncidents:
    """ represent incidents in an operational game """
    def __init__(self):
        self.incidents_by_line = defaultdict(list)
        self.incident_responses = IncidentResponses()
        self.incident_types = IncidentTypes(self.incident_responses)
        Incident.incident_types = self.incident_types  # used by load()
        self.get_incident_settings()
        self.load_incidents()

    def load_incidents(self):
        # get address of incident table
        self.data_range = get_data_range('Incidents', 'Data_Range')[0][0]
        self.fields, self.incidents = get_data_range_as_class(
            'Incidents', self.data_range, Incident.load)
        self.incidents = []
        log.info("load_incidents: self.incidents is now %s", self.incidents)
        # TODO: now link them back to places etc

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
        """ return a dict of the settings in Incident_Types """
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


class Place:
    def __init__(self, place_type, name, line, pos=None, direction=None):
        self.place_type = place_type
        self.name = name
        self.line = line
        self.pos = pos
        self.direction = None

    def __str__(self):
        return f"{self.name} on {self.line}"


class Train:
    train_number = 0

    def __init__(self, line, place):
        self.line = line
        self.location = place
        self.number = self.__class__.allocate_train_number()
        self.incidents = []  # allow incidents to move with the train

    @classmethod
    def allocate_train_number(cls):
        cls.train_number += 1
        return cls.train_number

    def __str__(self):
        flag = '*' * len(self.incidents)
        return f"{flag}Train {self.number} at {self.location}"


class NetworkGame:
    """ represent the characteristics of whole network,
    with lines, incidents, responses, and status.   """
    current_time = 0

    def __init__(self):
        self.line = Line()
        self.incidents = GameIncidents()
        self.catalog_places()

    def save(self):
        self.line.save()
        self.incidents.save()

    def catalog_places(self):
        # need to link each of these to the relevant line
        self.places = {
            'Station': self.line.stations(),
            'Line': self.line.places,
            'Train': self.line.trains  # NB incidents move with trains!
            }

    def random_place(self, place_type):
        """ find a place at random.  Place type could be station, line or train
        """
        return random.choice(self.places[place_type])

    def sprinkle_incidents(self):
        for incident in self.incidents.generate_incidents():
            incident.location = self.random_place(incident.incident_type.type)
            if isinstance(incident.location, Train):
                incident.location.incidents.append(incident)
            incident.start_time = self.current_time
            # severity in range 0.5-1.5
            incident.severity = 0.5 + random.random()
            self.incidents.record(incident, incident.location)

    def do_stage(self):
        """ generate incidents, update trains, accumulate impacts """
        self.sprinkle_incidents()
        self.current_time += 1


def incident_types_likelihood(*_args):
    global log
    with LoggingSetup('incident_types_likelihood') as log:
        incident_responses = IncidentResponses()
        incident_types = IncidentTypes(incident_responses)
        incident_types.save()


def generate_incidents(*_args):
    """  """
    global log
    with LoggingSetup('generate_incidents') as log:
        game = NetworkGame()
        for k in game.places:
            log.info("%d %ss: %s", len(game.places[k]), k,
                     [str(p) for p in game.places[k]])
        for _j in range(10):
            game.sprinkle_incidents()
        log.info("Trains: %s", list_to_str(game.places['Train']))
        game.incidents.save()  # see if this works...


def test_range(*_args):
    with LoggingSetup('test_range') as log:
        model = get_model()
        sheet = model.Sheets.getByName('Incidents')
        range1 = sheet.getCellRangeByName('data')
        log.info("Absolute name is %s", range1.AbsoluteName)
        # this one returns the contents (perhaps if they were formulas,
        # it would return an array of formulas
        log.info("getFormulaArray returned %s", range1.getFormulaArray())
        log.info("getArrayFormula returned %s", range1.getArrayFormula())
        range1.AbsoluteName = "$A1:$C7"
        log.info("New Absolute name is %s", range1.AbsoluteName)
        log.info("getFormulaArray returned %s", range1.getFormulaArray())
        message_box("hello")


def test(*_args):
    global log
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    logging.basicConfig(filename='/home/simon/code/kitten/test.log',
                        filemode='w',
                        level=logging.DEBUG,
                        format='%(levelname)s: %(message)s')
    log.warning("Hello, Libreoffice")


if __name__ == '__main__':
    try:
        test()
    except Exception as e:
        log.exception('%s in %s', e, __name__)

g_exportedScripts = update_line, reset_line, overall_response_impacts, \
    incident_types_likelihood, generate_incidents, test_range
