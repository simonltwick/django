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
@author: simon
'''
from collections import defaultdict
import logging
import random
import sys
global XSCRIPTCONTEXT


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


def get_data_range(sheet_name, data_range="Data"):
    """ get the range "Data" in sheet, and return it as a
    list of lists """
    model = get_model()
    sheet = model.Sheets.getByName(sheet_name)
    range1 = sheet.getCellRangeByName(data_range)
    return range1.getDataArray()


def put_data_range(sheet_name, data_range, data):
    """ put data (in rows) in data_range """
    global log
    assert isinstance(data, (tuple, list)), 'Invalid data type'
    model = get_model()
    sheet = model.Sheets.getByName(sheet_name)
    if ':' not in data_range:
        range1 = sheet.getCellRangeByName(data_range)
        range1.setDataArray(data)
    else:
        ccrr = data_range.split(':', 1)
        cols = [chr(i) for i in range(ord(ccrr[0][0]), ord(ccrr[1][0]) + 1)]
        rows = range(int(ccrr[0][1:]), int(ccrr[1][1:])+1)
        for row, row_data in zip(rows, data):
            for col, cell_data in zip(cols, row_data):
                cell = f'{col}{row}'
                tRange = sheet.getCellRangeByName(cell)
                tRange.String = cell_data


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


def train_can_move(prev_pos, pos, trains, last_train_time, wait,
                   is_last_stop: bool):
    """ train can move if there is a train there to move,
        the line ahead is clear,
        and it's waited long enough at the current place """
    global current_time, log
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


def move_train(prev_pos, pos, trains, last_train_time):
    """ move a train from i to i+1, updating trains and last_train_time """
    global current_time
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
        self.places = self.info['Place']
        self.train_directions = [key for key in self.info
                                 if key.startswith('Trains')]
        self.last_train_times = [key for key in self.info
                                 if key.startswith('Last_Train_Time')]
        assert 0 < len(self.train_directions) < 3, \
            f"Invalid number of Trains...rows: {self.train_directions}"
        assert len(self.train_directions) == len(self.last_train_times), \
            f"mismatch between train_directions {self.train_directions} and " \
            f"last_train_times {self.last_train_times}"
        make_ints(self.info,
                  self.train_directions + self.last_train_times + ['Wait'])
        self.wait = self.info['Wait']
        self.current_time = int(self.info['Current_Time'][0])
        self.delay = int(self.info['Delays'][0])

    def reset(self):
        size = len(self.info['Place'])
        for train_direction in self.train_directions:
            self.info[train_direction] = size * ['']
            self.info['Last_Train_Time' + train_direction[6:]] = size * ['']
        # override turnaround at depots
        turnaround0 = self.info['Turnaround%'+self.train_directions[0][6:]]
        turnaround0[0] = ''
        turnaround0[-1] = 100
        turnaround1 = self.info['Turnaround%'+self.train_directions[1][6:]]
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
        if len(self.train_directions) < 2:
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
                                         self.train_directions[0][6:]]
        last_train_time_dir1 = self.info['Last_Train_Time' +
                                         self.train_directions[1][6:]]

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
                pos_iterator = range(len(self.places)-1)
                prev_pos = +1
                last_stop = 0
                first_stop = len(self.places) - 1
            else:
                pos_iterator = reversed(range(1, len(self.places)))
                prev_pos = -1
                last_stop = len(self.places) - 1
                first_stop = 0
            for i in pos_iterator:
                # loop through places where trains could move to
                # log.info("  %d(%d) -> %d(%d)", i+prev_pos,
                #          trains[i+prev_pos], i, trains[i])
                if trains[i + prev_pos]:
                    is_last_stop = i == last_stop
                    if train_can_move(i + prev_pos, i, trains, last_train_time,
                                      self.wait, is_last_stop):
                        move_train(i + prev_pos, i, trains,
                                   last_train_time)
                        log.info("move_train returned trains=%s", trains)
                    elif prev_pos != first_stop:
                        self.delay += 1  # increment delay if not depot


def update_line(*_args):
    """ update the status of all trains on the line """
    global current_time, log
    with LoggingSetup('update_line') as log:
        line = Line()
        line.update_trains()
        line.save()


def reset_line(*_args):
    """ reset trains and incidents on the line to the starting value """
    global current_time, log
    with LoggingSetup('update_line') as log:
        line = Line()
        line.reset()
        line.save()
        return


def update_line_old(*_args):
    """ update the status of all trains on the line """
    global current_time, log
    with LoggingSetup('update_line') as log:
        line_info = get_data_range_as_dict("Line", 'Data')
        places = line_info['Place']
        train_directions = [key for key in line_info
                            if key.startswith('Trains')]
        last_train_times = [key for key in line_info
                            if key.startswith('Last_Train_Time')]
        assert 0 < len(train_directions) < 3, \
            f"Invalid number of Trains...rows: {train_directions}"
        assert len(train_directions) == len(last_train_times), \
            f"mismatch between train_directions {train_directions} and " \
            f"last_train_times {last_train_times}"
        make_ints(line_info, train_directions + last_train_times + ['Wait'])
        wait = line_info['Wait']
        current_time = int(line_info['Current_Time'][0])
        delay = int(line_info['Delays'][0])

        # do an update step
        current_time += 1
        if len(train_directions) > 1:
            # train turnaround at depots and where turnaround specified
            # move trains from end-of-line depots to start-of-line depots in
            # opposite direction
            # TODO: implement train turnarounds where Turnaround% > 0
            end1, end2 = 0, len(line_info[train_directions[0]]) - 1
            trains_dir0 = line_info[train_directions[0]]
            trains_dir1 = line_info[train_directions[1]]
            # should really update last_train_time at depots too
            last_train_time_dir0 = line_info['Last_Train_Time' +
                                             train_directions[0][6:]]
            last_train_time_dir1 = line_info['Last_Train_Time' +
                                             train_directions[1][6:]]

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

        # move trains: run through places in reverse order
        for i, train_direction in enumerate(train_directions):
            direction = train_direction[6:]  # cut out Trains prefix
            last_train_time = line_info['Last_Train_Time' + direction]
            trains = line_info[train_direction]
            # log.info("calculating train moves %s, trains=%s", direction,
            #          trains)
            if i:  # second train direction
                pos_iterator = range(len(places)-1)
                prev_pos = +1
                last_stop = 0
                first_stop = len(places) - 1
            else:
                pos_iterator = reversed(range(1, len(places)))
                prev_pos = -1
                last_stop = len(places) - 1
                first_stop = 0
            for i in pos_iterator:
                # loop through places where trains could move to
                # log.info("  %d(%d) -> %d(%d)", i+prev_pos,
                #          trains[i+prev_pos], i, trains[i])
                if trains[i + prev_pos]:
                    is_last_stop = i == last_stop
                    if train_can_move(i + prev_pos, i, trains,
                                      last_train_time, wait, is_last_stop):
                        move_train(i + prev_pos, i, trains,
                                   last_train_time)
                        log.info("move_train returned trains=%s", trains)
                    elif prev_pos != first_stop:
                        delay += 1  # increment delay if not depot

        line_info['Current_Time'][0] = current_time
        line_info['Delays'][0] = delay
        put_data_range_from_dict("Line", "Data", line_info)


def reset_line_old(*_args):
    """ reset trains and incidents on the line to the starting value """
    global log
    with LoggingSetup('reset_line') as log:
        line_info = get_data_range_as_dict("Line", "Data")
        size = len(line_info['Place'])
        train_directions = [key for key in line_info
                            if key.startswith('Trains')]
        for train_direction in train_directions:
            line_info[train_direction] = size * ['']
            line_info['Last_Train_Time' + train_direction[6:]] = size * ['']
        # override turnaround at depots
        turnaround0 = line_info['Turnaround%'+train_directions[0][6:]]
        turnaround0[0] = ''
        turnaround0[-1] = 100
        turnaround1 = line_info['Turnaround%'+train_directions[1][6:]]
        turnaround1[0] = 100
        turnaround1[-1] = ''
        line_info[train_directions[0]] = line_info['Initial_Trains']
        line_info['Incident_ID'] = size * ['']
        line_info['Incident_Start'] = size * ['']
        line_info['Wait'][0] = line_info['Train_Freq'][0]
        line_info['Wait'][-1] = line_info['Train_Freq'][0]
        line_info['Current_Time'][0] = 0
        line_info['Delays'][0] = 0
        put_data_range_from_dict("Line", "Data", line_info)


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
        return f"ResponseOption({self.response_option}. " \
            f"{self.response_name})"

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

    def save(self):
        rows = [self.fields]
        for incident_type in self.incident_types.values():
            rows.append(incident_type.as_list())
        # log.info("rows dimensions = %d rows of %d columns", len(rows),
        #          len(rows[0]))
        # log.info("rows=%s", rows)
        put_data_range('Incident_Types', 'Data', rows)

    def __str__(self):
        data = '\n  '.join(str(incident)
                           for incident in self.incident_types.values())
        return f"IncidentTypes(\n  {data})"


def get_incident_settings():
    """ return a dict of the settings in Incident_Types """
    return get_data_range_as_settings("Incident_Types", "Settings")


def incident_types_likelihood(*_args):
    global log
    with LoggingSetup('incident_types_likelihood') as log:
        incident_responses = IncidentResponses()
        incident_types = IncidentTypes(incident_responses)
        log.info("Incident Types = %s", incident_types)
        for incident in incident_types.incident_types.values():
            log.info("%: impact=%d, inverse_impact=%0.2f, likelihood=%d",
                     incident.incident_name, incident.expected_impact,
                     incident.inverse_impact, incident.likelihood_percentage)
        incident_types.save()


def generate_incidents(*_args):
    """ generate a random number of incidents up to twice the average incident
    frequency """
    with LoggingSetup('generate_incidents') as log:
        incident_settings = get_incident_settings()
        incident_freq = incident_settings['Incident_Frequency']

        def num_incidents():
            """ generates up to 2*f/100 incidents per go, with an average
            event frequency of f/100 """
            return random.randrange(200 * incident_freq + 10000) // 10000

        for j in range(10):
            log.info("Round %d: %d incidents", j, num_incidents())


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
    incident_types_likelihood, generate_incidents
