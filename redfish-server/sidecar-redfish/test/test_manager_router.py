import os
import json
import pytest
import sys
import time
from io import BytesIO
test_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(test_root)
from .conftest import print_response_details, AssertType
from unittest.mock import MagicMock, patch
from http import HTTPStatus
from mylib.models.rf_resource_model import RfResetType
from mylib.models.rf_manager_model import RfResetToDefaultsType
from flask import Response



managers_testcases = [
    {
        "endpoint": f'/redfish/v1/Managers/CDU',
        "assert_cases": {
            "@odata.id": f"/redfish/v1/Managers/CDU",
            "@odata.type": "#Manager.v1_21_0.Manager",
            "@odata.context": "/redfish/v1/$metadata#Manager.v1_21_0.Manager",
            "Manufacturer": "Supermicro",
            "PartNumber": "LCS-SCDU-200AR001",
            # "Model": "200KW-SideCar-L/A-Colling-CDU",
            "Model": "200KW SideCar L/A Colling CDU",
            "ServiceIdentification": "ServiceRoot",
            "TimeZoneName": AssertType.CONFIGURABLE,
        },
        "assert_case_descriptions": {
            "TimeZoneName": "使用者可以設定os時區，此值會顯示成IANA格式，例如：Asia/Taipei"
        }
    } 
]

# WATCH OUT the `ITG_WEBAPP_JSON_ROOT` in .env-test file for MacOS!
managers_cdu_log_services_testcases = [
    {
        "endpoint": f'/redfish/v1/Managers/CDU/LogServices',
        "assert_cases": {
            "@odata.id": f"/redfish/v1/Managers/CDU/LogServices",
            "@odata.type": "#LogServiceCollection.LogServiceCollection",
            "@odata.context": "/redfish/v1/$metadata#LogServiceCollection.LogServiceCollection",
            "Members@odata.count": 1
        }
    },
    {
        "endpoint": f'/redfish/v1/Managers/CDU/LogServices/1',
        "assert_cases": {
            "@odata.id": f"/redfish/v1/Managers/CDU/LogServices/1",
            "@odata.type": "#LogService.v1_8_0.LogService",
            "@odata.context": "/redfish/v1/$metadata#LogService.v1_8_0.LogService",
            "LogEntryType": "OEM",
            # "MaxNumberOfRecords": 500,
            "OverWritePolicy": "WrapsWhenFull",
            "Status": {"State": "Enabled", "Health": "OK"}
        }
    },
    {
        "endpoint": f'/redfish/v1/Managers/CDU/LogServices/1/Entries',
        "assert_cases": {
            "@odata.id": "/redfish/v1/Managers/CDU/LogServices/1/Entries",
            "@odata.type": "#LogEntryCollection.LogEntryCollection",
            "@odata.context": "/redfish/v1/$metadata#LogEntryCollection.LogEntryCollection",
        }
    },
    {
        "endpoint": f'/redfish/v1/Managers/CDU/LogServices/1/Entries/1',
        "assert_cases": {
            "@odata.id": "/redfish/v1/Managers/CDU/LogServices/1/Entries/1",
            "@odata.type": "#LogEntry.v1_18_0.LogEntry",
            "@odata.context": "/redfish/v1/$metadata#LogEntry.LogEntry",
            "Id": "1",
            "EntryType": "Oem",
            "MessageId": "CDU001",
        }
    } 
]

managers_cdu_reset_to_defaults_testcases = [
    {
        "endpoint": f"/redfish/v1/Managers/CDU/Actions/Manager.ResetToDefaults",
        "payload": {
            "ResetType": RfResetToDefaultsType.ResetAll.value
        },
        "assert_cases": { 
            "status_code": HTTPStatus.OK,
        }
    },
    {
        "endpoint": f"/redfish/v1/Managers/CDU/Actions/Manager.ResetToDefaults",
        "payload": {
            "ResetType": "Invalid"
        },
        "assert_cases": { 
            "status_code": HTTPStatus.BAD_REQUEST,
        }
    }
]

managers_cdu_reset_testcases = [
    {
        "endpoint": f"/redfish/v1/Managers/CDU/Actions/Manager.Reset",
        "payload": {
            "ResetType": RfResetType.ForceRestart.value
        },
        "assert_cases": { 
            "status_code": HTTPStatus.OK,
        }
    },
    {
        "endpoint": f"/redfish/v1/Managers/CDU/Actions/Manager.Reset",
        "payload": {
            "ResetType": RfResetType.GracefulRestart.value
        },
        "assert_cases": { 
            "status_code": HTTPStatus.OK,
        }
    },
    {
        "endpoint": f"/redfish/v1/Managers/CDU/Actions/Manager.Reset",
        "payload": {
            "ResetType": "Invalid"
        },
        "assert_cases": { 
            "status_code": HTTPStatus.BAD_REQUEST,
        }
    }
]

managers_cdu_shutdown_testcases = [
    {
        "endpoint": f"/redfish/v1/Managers/CDU/Actions/Manager.Shutdown",
        "payload": {
            "ResetType": RfResetType.ForceOff.value
        },
        "assert_cases": { 
            "status_code": HTTPStatus.OK,
        }
    },
    {
        "endpoint": f"/redfish/v1/Managers/CDU/Actions/Manager.Shutdown",
        "payload": {
            "ResetType": RfResetType.ForceOff.value
        },
        "assert_cases": { 
            "status_code": HTTPStatus.OK,
        }
    },
    {
        "endpoint": f"/redfish/v1/Managers/CDU/Actions/Manager.Shutdown",
        "payload": {
            "ResetType": "Invalid"
        },
        "assert_cases": { 
            "status_code": HTTPStatus.BAD_REQUEST,
        }
    }
]

@pytest.mark.parametrize("testcase", managers_cdu_reset_to_defaults_testcases)
def test_manager_cdu_reset_to_defaults(client, basic_auth_header, testcase):
    """[TestCase] manager CDU reset_to_defaults"""
    endpoint = testcase["endpoint"]
    print(f"Endpoint: {endpoint}")
    print(f"Payload: {testcase['payload']}")
    
    with patch('mylib.adapters.webapp_api_adapter.WebAppAPIAdapter.reset_to_defaults') as mock:
        mock.return_value = Response(
            status=HTTPStatus.OK,
            response=json.dumps({"message": "Reset to defaults Successfully"}),
        )
    
        resp = client.post(endpoint, headers=basic_auth_header, json=testcase["payload"])
        print_response_details(resp)

        assert resp.status_code == testcase["assert_cases"]["status_code"]
        print(f"PASS: POST {endpoint} by MagicMock response HTTPStatus={testcase['assert_cases']['status_code']}")

@pytest.mark.parametrize("testcase", managers_cdu_reset_testcases)
def test_manager_cdu_reset(client, basic_auth_header, testcase):
    """[TestCase] manager CDU reset"""
    endpoint = testcase["endpoint"]
    print(f"Endpoint: {endpoint}")
    print(f"Payload: {testcase['payload']}")
    
    with patch('mylib.adapters.webapp_api_adapter.WebAppAPIAdapter.reset') as mock:
        mock.return_value = Response(
            status=HTTPStatus.OK,
            response=json.dumps({"message": "Reset Successfully"}),
        )
    
        resp = client.post(endpoint, headers=basic_auth_header, json=testcase["payload"])
        print_response_details(resp)

        assert resp.status_code == testcase["assert_cases"]["status_code"]
        print(f"PASS: POST {endpoint} by MagicMock response HTTPStatus={testcase['assert_cases']['status_code']}")

    
@pytest.mark.parametrize("testcase", managers_cdu_shutdown_testcases)
def test_manager_cdu_shutdown(client, basic_auth_header, testcase):
    """[TestCase] manager CDU shutdown"""
    endpoint = testcase["endpoint"]
    print(f"Endpoint: {endpoint}")
    print(f"Payload: {testcase['payload']}")
    
    with patch('mylib.adapters.webapp_api_adapter.WebAppAPIAdapter.shutdown') as mock:
        mock.return_value = Response(
            status=HTTPStatus.OK,
            response=json.dumps({"message": "Shutdown Successfully"}),
        )
    
        resp = client.post(endpoint, headers=basic_auth_header, json=testcase["payload"])
        print_response_details(resp)

        assert resp.status_code == testcase["assert_cases"]["status_code"]
        print(f"PASS: POST {endpoint} by MagicMock response HTTPStatus={testcase['assert_cases']['status_code']}")




##                                                                                                             
# NNNNNNNN        NNNNNNNN                                                                               lllllll 
# N:::::::N       N::::::N                                                                               l:::::l 
# N::::::::N      N::::::N                                                                               l:::::l 
# N:::::::::N     N::::::N                                                                               l:::::l 
# N::::::::::N    N::::::N   ooooooooooo   rrrrr   rrrrrrrrr      mmmmmmm    mmmmmmm     aaaaaaaaaaaaa    l::::l 
# N:::::::::::N   N::::::N oo:::::::::::oo r::::rrr:::::::::r   mm:::::::m  m:::::::mm   a::::::::::::a   l::::l 
# N:::::::N::::N  N::::::No:::::::::::::::or:::::::::::::::::r m::::::::::mm::::::::::m  aaaaaaaaa:::::a  l::::l 
# N::::::N N::::N N::::::No:::::ooooo:::::orr::::::rrrrr::::::rm::::::::::::::::::::::m           a::::a  l::::l 
# N::::::N  N::::N:::::::No::::o     o::::o r:::::r     r:::::rm:::::mmm::::::mmm:::::m    aaaaaaa:::::a  l::::l 
# N::::::N   N:::::::::::No::::o     o::::o r:::::r     rrrrrrrm::::m   m::::m   m::::m  aa::::::::::::a  l::::l 
# N::::::N    N::::::::::No::::o     o::::o r:::::r            m::::m   m::::m   m::::m a::::aaaa::::::a  l::::l 
# N::::::N     N:::::::::No::::o     o::::o r:::::r            m::::m   m::::m   m::::ma::::a    a:::::a  l::::l 
# N::::::N      N::::::::No:::::ooooo:::::o r:::::r            m::::m   m::::m   m::::ma::::a    a:::::a l::::::l
# N::::::N       N:::::::No:::::::::::::::o r:::::r            m::::m   m::::m   m::::ma:::::aaaa::::::a l::::::l
# N::::::N        N::::::N oo:::::::::::oo  r:::::r            m::::m   m::::m   m::::m a::::::::::aa:::al::::::l
# NNNNNNNN         NNNNNNN   ooooooooooo    rrrrrrr            mmmmmm   mmmmmm   mmmmmm  aaaaaaaaaa  aaaallllllll
##

managers_testcases += managers_cdu_log_services_testcases

@pytest.mark.parametrize("testcase", managers_testcases)
def test_manager_normal_api(client, basic_auth_header, testcase):
    """[TestCase] manager API"""
    # 獲取當前測試案例的序號
    index = managers_testcases.index(testcase) + 1
    print(f"Running test case {index}/{len(managers_testcases)}: {testcase}")

    print(f"Endpoint: {testcase['endpoint']}")
    response = client.get(testcase['endpoint'], headers=basic_auth_header)
    print(f"Response: {response.json}")
    assert response.status_code == 200
    
    resp_json = response.json
    print(f"Response json: {json.dumps(resp_json, indent=2, ensure_ascii=False)}")
    for key, value in testcase['assert_cases'].items():
        try:
            # Members比較特殊，排序後確認內容
            if key == "Members":
                resp_json[key] = sorted(resp_json[key], key=lambda x: x['@odata.id'])
                assert resp_json[key] == value
            elif key == "Status":
                assert isinstance(resp_json["Status"], dict)
                # assert resp_json["Status"]["State"] in ["Absent", "Enabled", "Disabled"]
                assert resp_json["Status"]["Health"] in ["OK", "Warning", "Critical"]
            elif isinstance(value, AssertType):
                pass
            else:
                assert resp_json[key] == value
            
            print(f"PASS: `{key}` of response json is expected to be {value}")
        except AssertionError as e:
            print(f"FAIL: AssertionError: {e}, key: {key}, value: {value}")
            raise e
