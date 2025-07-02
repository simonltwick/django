'''
Created on 1 Jul 2025

login_session as a context manager

usage:

with login_session(login-url, userid, password) as session:
    do something ...

the session will be logged out afterwards
ref:
https://scrapeops.io/python-web-scraping-playbook/python-how-to-submit-forms/

@author: simon
'''
from contextlib import contextmanager
import logging
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse
from lxml import etree
import requests
from django.db.models.sql.where import OR

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


headers = {
    'Content-Type': 'application/x-www-form-urlencoded',
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/96.0.4664.110 '
                   'Safari/537.36')}


@contextmanager
def login_session(login_url:str, logout_url: str, credentials: Dict[str, str]):
    """ setup a logged in session using credentials, and logout afterwards
    credentials is a dict of the form input field names and values that need
    to be filled in """

    session = requests.Session()

    response = session.get(login_url, headers=headers)
    if response.status_code != 200:
        log.error("GET login_url failed: status=%s, text=%s",
                  response.status_code, response.text)
        raise ConnectionRefusedError(f"login failed: {response}")
    log.debug("GET request successful: status=%s", response.status_code)

    # find the login form
    login_html = etree.HTML(response.text)
    url_path = urlparse(login_url).path  # eg /login
    login_form = get_form_by_action(login_html, url_path)
    if login_form is None:
        raise ValueError("Unable to locate login form within login page")
    log.debug("found login form:")

    # prepare the POST fields to submit
    fields_to_submit = {field.get("name"): field.get("value")
                        for field in login_form.iter("input")
                        if (field.get("name") in credentials
                            or field.get("name") == "csrfmiddlewaretoken")}
    # log.debug("fields_to_submit= %s", fields_to_submit)
    missing_fields = set(credentials) - set(fields_to_submit)
    if missing_fields:
        raise ValueError(
            f"credential fields not found in login form: {missing_fields}")
    if "csrfmiddlewaretoken" not in fields_to_submit:
        raise ValueError("Unable to locate csrf token in login form")
    for key, value in credentials.items():
        fields_to_submit[key] = value

    response = session.post(login_url, data=fields_to_submit, headers=headers)
    if response.status_code != 200:
        log.error("POST login_url failed: status=%s, text=%s",
                  response.status_code, response.text)
        raise ConnectionRefusedError(f"login failed: {response}")
    log.debug("POST request successful: status=%s", response.status_code)

    # check if the login form was re-sent
    response_html = etree.HTML(response.text)
    login_form2 = get_form_by_action(response_html, url_path)
    if (login_form2 is not None or
        "Your username and password didn't match" in response.text):
        log.error("credentials rejected: form = %s",
                 etree.tostring(login_form2, pretty_print=True).decode())
        raise ValueError("login credentials rejected")

    log.info("login succeeded")
    #print(etree.tostring(response.text, pretty_print=True))

    yield session

    # and now logout
    response = session.get(logout_url, headers=headers)
    if response.status_code != 200:
        log.error("logout failed: status=%d, text=%s", response.status_code,
                  response.text)
        raise ConnectionRefusedError(f"logout request failed: {response}",
                                     response)
    log.info("logout request succeeded.")
    #print(etree.tostring(response.text, pretty_print=True))


def get_form_by_action(login_html, url_path):
    """ find and return the login form with action=url_path """
    for form in login_html.iter("form"):
        if form.get("action") == url_path:
            return form
        log.debug(">>found form action=%s\n%s", form.get("action"),
                 etree.tostring(form, pretty_print=True).decode())
    return None


def get_credentials(fname: str) -> Dict[str, str]:
    """ read the credentials from the credentials file & return a dict """
    with open(Path(fname).expanduser(), 'rt') as credentials_file:
        credentials = {}
        for line in credentials_file:
            if not line.strip():
                continue
            parts = line.strip().split('=',1)
            if len(parts) != 2:
                raise ValueError(f"unable to parse credentials line {line!r}")
            key, value = parts
            credentials[key] = value
    return credentials


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    URL = "http://localhost:8000/accounts/login/"
    LOGOUT_URL = "http://localhost:8000/routes/logout/"
    with login_session(
        URL, LOGOUT_URL, credentials=get_credentials('~/.credentials/bike')
                       ) as session:
        log.info("*** login succeeded.***")
    log.info("finished")
