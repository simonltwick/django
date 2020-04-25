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

import sys
sys.path.append('/home/simon/code/kitten')
from test_macros import update_line, reset_line, overall_response_impacts, \
    incident_types_likelihood, do_stage, test_range, clear_incidents

g_exportedScripts = update_line, reset_line, overall_response_impacts, \
    incident_types_likelihood, do_stage, test_range, clear_incidents
