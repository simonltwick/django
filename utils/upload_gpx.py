#!/usr/bin/env python3
'''
Upload GPX files to bike routes website
Created on 1 Jul 2025

@author: simon
Ref (uploading files from Python):
https://stackoverflow.com/questions/22567306/how-to-upload-file-with-python-requests
'''
import argparse
import logging
from pathlib import Path
import sys
from typing import Dict
from urllib.parse import urlparse

from lxml import etree

from login_session import (
    login_session, get_credentials, headers, get_form_by_action)


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

file_headers = headers | {"Content-Type": "application/gpx+xml"}
# if content-type is added, then we get a csrf failure, so leave blank

def main():
    args = parse_args()

    with login_session(args.login_url, args.logout_url,
                       credentials=get_credentials('~/.credentials/bike')
                       ) as session:
        if upload_gpx_file(session, args, args.gpx_file):
            log.info("GPX upload succeeded")
        log.error("GPX upload failed")
        sys.exit(1)

def upload_gpx_file(session, args, file: Path) -> bool:
    """ upload a gpx file specified in args, to server urls specified in args
        Session is a logged-in session to the server """
    response = session.get(args.upload_url, headers=headers)
    if response.status_code != 200:
        log.error("GET upload_url failed, status=%d, text=%s",
                  response.status_code, response.text)
        return False

    upload_html = etree.HTML(response.text)
    form = get_form_by_action(upload_html, args.upload_path)
    if form is None:
        raise ValueError(
            f"failed to find form with action {args.upload_path}"
            " in html response")
    log.debug("form found")  #\n%s", etree.tostring(form, pretty_print=True).decode())

    # setup info for POST
    csrf = get_field_value(form, 'csrfmiddlewaretoken')
    with open(file, 'rb') as gpx_file:
        files = {'gpx_file': gpx_file}
        # log.info("POST: %s", requests.Request(
        #     'POST', args.upload_url, files=files
        #     ).prepare().body.decode('ascii'))
        response = session.post(args.upload_url, data=csrf, files=files,
                                params={"map": False})  #, headers=file_headers)
    if response.status_code == 500:
        log.error("Server error: please see server log")
        return False
    if response.status_code != 200:
        log.error("POST upload_url failed, status=%d, text=%s",
                  response.status_code, response.text)
        return False

    response_html = etree.HTML(response.text)
    resp_form = get_form_by_action(response_html, args.upload_path)
    if resp_form is None:
        log.info("GPX upload succeeded")
        return True

    # TODO: write check_errors routine, check for form and print any
    # TODO: sections with class=error/errorlist
    log.error("upload failed: form = %s",
              etree.tostring(resp_form, pretty_print=True).decode())
    return False


def get_field_value(form: etree.HTML, name: str) -> Dict[str, str]:
    for field in form.iter('input'):
        if field.get("name") == name:
            return {name: field.get("value")}
    raise ValueError(f"field {name!r} not found in form")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gpx_file", help="gpx file to upload")
    parser.add_argument(
        "--login_url", help="url to login to server (default=%(default))",
                    default="http://localhost:8000/accounts/login/")
    parser.add_argument(
        "--logout_path", help="the PATH only part of the logout url"
                    " (the host name is assumed to be the same).  "
                    "Default:%(default)",
                    default="/routes/logout/")
    parser.add_argument(
        "--upload_path", help="the PATH only part of the upload url"
                    " (the host name is assumed to be the same).  "
                    "Default:%(default)",
                    default="/routes/gpx/upload")
    # add a few derived arguments: upload_path
    args = parser.parse_args()
    url = urlparse(args.login_url)
    args.upload_url = url._replace(path=args.upload_path).geturl()
    args.logout_url = url._replace(path=args.logout_path).geturl()
    return args


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
