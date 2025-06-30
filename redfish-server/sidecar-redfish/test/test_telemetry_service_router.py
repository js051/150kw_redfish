import os
import json
import pytest
import sys
import time
test_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(test_root)
from .conftest import print_response_details
from unittest.mock import MagicMock, patch
from http import HTTPStatus
from mylib.models.rf_resource_model import RfResetType
from mylib.models.rf_manager_model import RfResetToDefaultsType
from mylib.utils.DateTimeUtil import DateTimeUtil
from mylib.services.rf_telemetry_service import RfTelemetryService

# telemetry_service_testcases = [
#     {
#         "endpoint": f'/redfish/v1/TelemetryService',
#         "assert_cases": {
#             "@odata.id": "/redfish/v1/TelemetryService",
#             "@odata.type": "#TelemetryService.v1_3_4.TelemetryService",
#             "@odata.context": "/redfish/v1/$metadata#TelemetryService.v1_3_4.TelemetryService",
#             "Id": "TelemetryService",
#         }
#     },
#     {
#         "endpoint": f'/redfish/v1/TelemetryService/MetricReports',
#         "assert_cases": {
#             "@odata.id": "/redfish/v1/TelemetryService/MetricReports",
#             "@odata.type": "#MetricReportCollection.MetricReportCollection",
#             "Name": "CDU Metric Reports Collection",
#             "Members@odata.count": 3,
#             "Members": [
#                 {
#                 "@odata.id": "/redfish/v1/TelemetryService/MetricReports/CDU_Report_1"
#                 },
#                 {
#                 "@odata.id": "/redfish/v1/TelemetryService/MetricReports/CDU_Report_2"
#                 },
#                 {
#                 "@odata.id": "/redfish/v1/TelemetryService/MetricReports/CDU_Report_3"
#                 }
#             ]
#         }
#     },
#     {
#         "endpoint": "/redfish/v1/TelemetryService/MetricReports/<string:report_id>",
#         "assert_cases": {
#             "@odata.id": "/redfish/v1/TelemetryService/MetricReports/<string:report_id>",
#             "Id": "<string:report_id>",
#             "Timestamp": "2025-03-31T08:00:00Z",
#             "MetricValues": [
#                 {
#                     "MetricId": "Coolant Supply Temperature (T1)",
#                     "MetricValue": "62.5",
#                     "Timestamp": "2025-06-10T00:15:15+00:00"
#                 },
#                 {
#                     "MetricId": "Coolant Supply Temperature Spare (T1sp)",
#                     "MetricValue": "21.0",
#                     "Timestamp": "2025-06-10T00:15:15+00:00"
#                 },
#                 {
#                     "MetricId": "Coolant Return Temperature (T2)",
#                     "MetricValue": "423.0",
#                     "Timestamp": "2025-06-10T00:15:15+00:00"
#                 }
#             ]
#         }
#     },
# ]

telemetry_service_testcases = [
    {
        "endpoint": '/redfish/v1/TelemetryService',
        "assert_cases": {
            "@odata.id": "/redfish/v1/TelemetryService",
            "@odata.type": "#TelemetryService.v1_3_4.TelemetryService",
            "@odata.context": "/redfish/v1/$metadata#TelemetryService.v1_3_4.TelemetryService",
            "Id": "TelemetryService",
            "Name": "CDU Telemetry Service",
        }
    },
    {
        "endpoint": f'/redfish/v1/TelemetryService/MetricReports',
        "assert_cases": {
            "@odata.id": "/redfish/v1/TelemetryService/MetricReports",
            "@odata.type": "#MetricReportCollection.MetricReportCollection",
            "Name": "CDU Metric Reports Collection",
            "Members": [ # TODO: 如果Members沒有要assert值，不要寫以下三行會比較看的懂。
                {"@odata.id": "/redfish/v1/TelemetryService/MetricReports/CDU_Report_1"},
                {"@odata.id": "/redfish/v1/TelemetryService/MetricReports/CDU_Report_2"},
                {"@odata.id": "/redfish/v1/TelemetryService/MetricReports/CDU_Report_3"}
            ],
            "Members@odata.count": 3, 
        }
    },
    {
        "endpoint": '/redfish/v1/TelemetryService/MetricReports/CDU_Report_1',
        "assert_cases": {
            "Id": "CDU_Report_1",
            "@odata.id": "/redfish/v1/TelemetryService/MetricReports/CDU_Report_1",
            "MetricValues": [
                {
                    "MetricId",
                    "MetricValue",
                    "Timestamp"
                }
            ]
        }
    },
    {
        "endpoint" : f'/redfish/v1/TelemetryService/MetricDefinitions',
        "assert_cases": {
            "@odata.id": "/redfish/v1/TelemetryService/MetricDefinitions",
            "@odata.type": "#MetricDefinitionCollection.MetricDefinitionCollection",
            "@odata.context": "/redfish/v1/$metadata#MetricDefinitionCollection.MetricDefinitionCollection",
            "Name": "Metric Definition Collection",
            "Members":[ # TODO: 同上
                {"@odata.id": "/redfish/v1/TelemetryService/MetricDefinitions/time"},
                {"@odata.id": "/redfish/v1/TelemetryService/MetricDefinitions/coolant_supply_temperature"}
            ],
            "Members@odata.count": 2,
        }
    },
    {
        "endpoint" : f'/redfish/v1/TelemetryService/MetricDefinitions/time',
        "assert_cases" : {
            "@odata.id" : "/redfish/v1/TelemetryService/MetricDefinitions/time",
            "@odata.type" : "#MetricDefinition.v1_0_0.MetricDefinition",
            "@odata.context" : "/redfish/v1/$metadata#MetricDefinition.MetricDefinition",
            "Id" : "time",
            "Name" : "time",
            "MetricDataType": "DateTime",
        }
    }
]



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
# @pytest.mark.parametrize("testcase", telemetry_service_testcases)
# def test_telemetry_service_normal_api(client, basic_auth_header, testcase):
#     """[TestCase] TelemetryService API"""
#     # 獲取當前測試案例的序號
#     index = telemetry_service_testcases.index(testcase) + 1
#     print(f"Running test case {index}/{len(telemetry_service_testcases)}: {testcase}")

#     print(f"Endpoint: {testcase['endpoint']}")
#     response = client.get(testcase['endpoint'], headers=basic_auth_header)
#     resp_json = response.json
#     print(f"Response: {resp_json}")
#     assert response.status_code == 200
    
#     print(f"Response json: {json.dumps(resp_json, indent=2, ensure_ascii=False)}")
#     for key, value in testcase['assert_cases'].items():
#         try:
#             if key == "MetricValues":
#                 assert len(resp_json[key]) > 3
#             elif key == "Members":
#                 assert len(resp_json[key]) == resp_json["Members@odata.count"]
#             elif key == "Timestamp":
#                 assert DateTimeUtil.is_match_format(resp_json[key], os.getenv("DATETIME_FORMAT"))
#             elif key == "Status":
#                 assert isinstance(resp_json["Status"], dict)
#                 # assert resp_json["Status"]["State"] in ["Absent", "Enabled", "Disabled"]
#                 assert resp_json["Status"]["Health"] in ["OK", "Warning", "Critical"]
#             else:
#                 assert resp_json[key] == value
            
#             print(f"PASS: `{key}` of response json is expected to be {value}")
#         except AssertionError as e:
#             print(f"AssertionError: {e}, key: {key}, value: {value}")
#             raise e

@pytest.mark.parametrize("testcase", telemetry_service_testcases)
def test_telemetry_service_api(client, basic_auth_header, testcase):
    """測試 TelemetryService 相關 API 是否正確回應預期的欄位與值"""
    response = client.get(testcase["endpoint"], headers=basic_auth_header)
    resp_json = response.json

    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"

    for key, value in testcase["assert_cases"].items():

        # TODO: 只有MetricReports的數量限定在2048筆，但/MetricDefinitions沒有限制
        if key == "Members@odata.count" :
            actual_count = resp_json.get("Members@odata.count", 0)
            assert 0 < actual_count <= 2048, f"Members@odata.count out of range: {actual_count}"

        elif key == "Members":
            assert isinstance(resp_json["Members"], list), "Members 應為 list"
            count = len(resp_json["Members"])
            assert 0 < count <= 2048 , f"Members count out of range: {count}"

        elif key == "MetricValues":
            assert isinstance(resp_json["MetricValues"], list), "MetricValues 應為 list"
            for item in resp_json["MetricValues"]:
                for field in ["MetricId", "MetricValue", "Timestamp"]:
                    assert field in item, f"MetricValues 缺少欄位：{field}，內容：{item}"

        else:
            assert resp_json[key] == value