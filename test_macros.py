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

import logging
import sys
# import msgbox  # this is provided when launched as a macro

sys.path.append('/home/simon/code/kitten')
from utils import list_to_str
from line import Line
from incident import IncidentResponses, IncidentTypes
from game import NetworkGame
from sheetdb import get_model, message_box, get_data_range, put_data_range, \
    clear_data_range

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


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
    def __init__(self, msg='', level=logging.DEBUG):
        log = logging.getLogger(__name__)
        log.setLevel(level)
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


# ---- Macro commands ----
def update_line(*_args):
    """ update the status of all trains on the line """
    global log
    with LoggingSetup('update_line') as log:
        line = Line()
        line.update_trains()
        line.save()


def reset_line(*_args):
    """ reset trains and incidents on the line to the starting value """
    global log
    with LoggingSetup('reset_line') as log:
        line = Line()
        line.reset()


def overall_response_impacts(*_args):
    global log
    with LoggingSetup('overall_response_impacts') as log:
        incident_responses = IncidentResponses()
        # log.info("Incident Responses = %s", incident_responses)
        overall_impact = incident_responses.calculate_impacts()
        log.info("Overall impact = %s", overall_impact)
        incident_responses.save()


def incident_types_likelihood(*_args):
    global log
    with LoggingSetup('incident_types_likelihood') as log:
        incident_responses = IncidentResponses()
        incident_types = IncidentTypes(incident_responses)
        incident_types.save()


def do_stage(*_args):
    """  """
    global log
    with LoggingSetup('do_stage') as log:
        game = NetworkGame()
        game.do_stage()
        log.info("Trains: %s", list_to_str(game.places['Train']))
        game.save()


def clear_incidents(*_args):
    """ clear the incidents page """
    global log
    with LoggingSetup("clear_incidents") as log:
        range1 = get_data_range('Incidents', 'Data_Range')[0][0]
        headings = get_data_range('Incidents', range1)[:1]
        new_data_range = range1[:4]+range1[1]  # eg.A6:G20 -> A6:G6
        log.info('data_range changed from %s to %s, headings=%s',
                 range1, new_data_range, headings)
        clear_data_range('Incidents', range1)
        put_data_range('Incidents', new_data_range, headings)
        put_data_range('Incidents', 'Data_Range', [[new_data_range]])


def test_range(*_args):
    global log
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


g_exportedScripts = update_line, reset_line, overall_response_impacts, \
    incident_types_likelihood, do_stage, test_range, clear_incidents
