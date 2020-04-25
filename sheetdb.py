'''
Utilities for using a spreadsheet as a database
Created on 25 Apr 2020

@author: simon
'''

import logging
import msgbox  # provided in environment of call
import uno
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

global XSCRIPTCONTEXT


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
        range1 = sheet.getCellRangeByName(data_range)
        if ':' not in data_range:  # single cell
            range1.setDataArray(data)
        else:
            range1.setDataArray(data)
    except Exception as e:
        log.error("%r in put_data_range(%s, %s, %s)", e, sheet_name,
                  data_range, data)
        log.info("data size is %d rows of %d columns", len(data), len(data[0]))
        raise


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


def clear_data_range(sheet_name, data_range):
    """ remove all values (not formulas, styling etc) from range """
    model = get_model()
    sheet = validate_sheet_name(model, sheet_name)
    range1 = sheet.getCellRangeByName(data_range)
    # 7: see https://www.openoffice.org/api/docs/common/ref/com/sun/star/sheet/CellFlags.html
    range1.clearContents(7)
