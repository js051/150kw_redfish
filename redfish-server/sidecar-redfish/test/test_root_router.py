import os
import json
import pytest
import sys
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from .conftest import print_response_details

'''
client定義在conftest.py裡
'''

def test_redfish_root(client):
    """[TestCase] /redfish """
    response = client.get('/redfish')
    print_response_details(response)
    assert response.status_code == 200

def test_redfish_v1_root(client):
    """[TestCase] /redfish/v1 """
    response = client.get('/redfish/v1/')
    resp_json = response.json
    print(f"response.json: {resp_json}") # should use `pytest -s`, or run with `pytest -v --html=report.html`
    assert response.status_code == 200
    assert resp_json["@odata.type"] == "#ServiceRoot.v1_18_0.ServiceRoot"
    assert resp_json["RedfishVersion"] == "1.14.0"
    assert resp_json["Id"] == "RootService"

def test_redfish_v1_odata(client):
    """[TestCase] /redfish/v1/odata """
    response = client.get('/redfish/v1/odata')
    resp_json = response.json
    print(f"response.json: {resp_json}") # should use `pytest -s`, or run with `pytest -v --html=report.html`
    assert response.status_code == 200
    assert resp_json["@odata.context"] == "/redfish/v1/$metadata"


def test_redfish_v1_metadata(client):
    """[TestCase] /redfish/v1/$metadata """
    response = client.get('/redfish/v1/$metadata')
    print_response_details(response)
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/xml; charset=utf-8'
    assert response.text.startswith('<?xml version="1.0" encoding="utf-8"?>') == True