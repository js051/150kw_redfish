'''
## Step1: Run python http.server at port 5300
$ cd test/
$ python -m http.server 5300 --bind 127.0.0.1

## Step2: Test your server
$ curl 'http://127.0.0.1:5300/testcase-updateservice-example.zip.gpg' -o test.gpg
$ wget 'http://127.0.0.1:5300/testcase-updateservice-example.zip.gpg'

## Step3: Run pytest
'''
import os
import json
import pytest
import sys
import time
from io import BytesIO
test_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(test_root)
from .conftest import print_response_details

image_domain_path = "127.0.0.1:5300/testcase-updateservice-example.zip.gpg"
image_url = f"http://{image_domain_path}"
endpoint = "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate"

updateservice_testcases = [
    {
        "endpoint": f"/redfish/v1/UpdateService",
        "assert_cases": { 
            "@odata.id": f"/redfish/v1/UpdateService",
            "@odata.type": "#UpdateService.v1_14_0.UpdateService",
            "Id": "UpdateService",
            # "FirmwareInventory": {
            #     "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory"
            # },
            # "Actions": {
            #     "#UpdateService.SimpleUpdate": {
            #         "target": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            #         "@Redfish.ActionInfo": "/redfish/v1/UpdateService/SimpleUpdateActionInfo"
            #     }
            # }
        }
    },
    # {
    #     "endpoint": "/redfish/v1/UpdateService/FirmwareInventory",
    #     "assert_cases": { 
    #         "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory",
    #         "@odata.type": "#SoftwareInventoryCollection.SoftwareInventoryCollection",
    #         "Name": "Firmware Inventory",
    #         "Members@odata.count": 2,
    #         "Members": [
    #             {
    #                 "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/System_Software"
    #             },
    #             {
    #                 "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/Control_Firmware"
    #             }
    #         ],
    #     }
    # },
]

updateservice_firmwareinventory_testcases = [
    {
        "endpoint": "/redfish/v1/UpdateService/FirmwareInventory/Control_Firmware",
        "assert_cases": { 
            "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/Control_Firmware",
            "@odata.type": "#SoftwareInventory.v1_12_0.SoftwareInventory",
            "Updateable": False,
            "Version": "0103", # MUST equals to the display version of webUI plc_version (prefix: '0')
            "SoftwareId": "PLC-VERSION"
        }
    },
    {
        "endpoint": "/redfish/v1/UpdateService/FirmwareInventory/System_Software",
        "assert_cases": { 
            "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/System_Software",
            "@odata.type": "#SoftwareInventory.v1_12_0.SoftwareInventory",
            "Updateable": True,
            "Version": "0117", # MUST equals to the display version of webUI version
            "SoftwareId": "WEB-INTERFACE"
        }
    },
    
]

updateservice_simpleupdate_by_imageuri_testcases = [
    {
        "endpoint": f"/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "payload": {
            "ImageURI": image_url
        },
        "assert_cases": { 
        }
    },
    {
        "endpoint": f"/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "payload": {
            "ImageURI": image_url,
            "TransferProtocol": "HTTP"
        },
        "assert_cases": { 
        }
    },

    {
        "endpoint": f"/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "payload": {
            "ImageURI": image_domain_path,
            "TransferProtocol": "HTTP"
        },
        "assert_cases": { 
        }
    },
]

updateservice_simpleupdate_by_imageuri_fail_testcases = [
    {
        "endpoint": f"/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "payload": {
            "ImageURI": image_url,
            "TransferProtocol": "http" # only Upper case allowed in Redfish
        },
        "assert_cases": { 
        }
    },
    {
        "endpoint": f"/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "payload": {
            "ImageURI": image_domain_path,
            "TransferProtocol": "http://"
        },
        "assert_cases": { 
        }
    },
    {
        "endpoint": f"/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "payload": {
            "ImageURI": image_domain_path,
            "TransferProtocol": "hTTP"
        },
        "assert_cases": { 
        }
    },
    {
        "endpoint": f"/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "payload": {
            "ImageURI": image_domain_path,
            "TransferProtocol": "FTP"
        },
        "assert_cases": { 
        }
    },
    {
        "endpoint": f"/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "payload": {
            "ImageURI": image_domain_path,
            "TransferProtocol": "ftp"
        },
        "assert_cases": { 
        }
    },
    {
        "endpoint": f"/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
        "payload": {
            "ImageURI": image_domain_path,
            "TransferProtocol": "://"
        },
        "assert_cases": { 
        }
    },
]

@pytest.mark.parametrize('testcase', updateservice_simpleupdate_by_imageuri_testcases)
def test_update_service_SimpleUpdate_by_ImageUri(client, basic_auth_header, testcase):
    """[TestCase] /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate (by ImageUri)"""
    
    print(f"POST {testcase['endpoint']}")
    print(f"Payload: {testcase['payload']}")
    
    t1 = time.time()
    response = client.post(
        testcase['endpoint'],
        headers=basic_auth_header,
        json=testcase['payload'],
    )
    t2 = time.time()

    print_response_details(response)

    assert response.status_code == 200 # 200代表上傳&更新韌體成功 (這邊是sync.的設計)
    assert t2 - t1 < 120 # 120秒內完成
    print(f"PASS: POST {testcase['endpoint']} with payload {testcase['payload']} is expected to return 200")

@pytest.mark.parametrize('testcase', updateservice_simpleupdate_by_imageuri_fail_testcases)
def test_update_service_SimpleUpdate_by_ImageUri_fail(client, basic_auth_header, testcase):
    """[TestCase] /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate (by ImageUri) fail"""
    print(f"POST {testcase['endpoint']}")
    print(f"Payload: {testcase['payload']}")
    
    response = client.post(
        testcase['endpoint'],
        headers=basic_auth_header,
        json=testcase['payload'],
    )
    
    print_response_details(response)

    assert response.status_code != 200
    print(f"PASS: POST {testcase['endpoint']} with payload {testcase['payload']} is NOT return 200")

def test_update_service_upload(client, basic_auth_header):
    """[TestCase] update_service API: /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate"""
    print(f"Endpoint: {endpoint}")
    
    file = None
    filename = "testcase-updateservice-example.zip.gpg"
    filepath = os.path.join(test_root, filename)
    with open(filepath, "rb") as f:
        file = BytesIO(f.read())
        file.name = filename
        # file.seek(0)  
    
    data = {
        "File": (file, filename)
    }
    t1 = time.time()
    # response = client.post(endpoint, headers=basic_auth_header, data={"File": file})
    response = client.post(
        endpoint,
        headers=basic_auth_header,
        data=data,
        content_type="multipart/form-data"
    )
    t2 = time.time()

    print_response_details(response)

    assert response.status_code == 200 # 200代表上傳&更新韌體成功 (這邊是sync.的設計)
    assert t2 - t1 < 120 # 120秒內完成
    
def test_update_service_upload_noPassword(client, basic_auth_header):
    """[TestCase] update_service API: /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate (noPassword)
    Expect:
        Http status: 400
        Response json:
            {
                "message": "ZIP file must be password-protected"
            }
    """
    print(f"Endpoint: {endpoint}")
    file = None
    filename = "testcase-updateservice-example-noPassword.zip.gpg"
    filepath = os.path.join(test_root, filename)
    

    with open(filepath, "rb") as f:
        file = BytesIO(f.read())
        file.name = filename
    
    data = {
        "File": (file, filename)
    }    
    # response = client.post(endpoint, headers=basic_auth_header, data={"File": file})
    response = client.post(
        endpoint,
        headers=basic_auth_header,
        data=data,
        content_type="multipart/form-data"
    )
    print_response_details(response)
    assert response.status_code == 400
    
def test_update_service_upload_noSpareDir(client, basic_auth_header):
    """[TestCase] update_service API: /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate (noSpareDir)"""
    print(f"Endpoint: {endpoint}")
    
    file = None
    filename = "testcase-updateservice-example-noSpareDir.zip.gpg"
    filepath = os.path.join(test_root, filename)
    with open(filepath, "rb") as f:
        file = BytesIO(f.read())
        file.name = filename
    
    data = {
        "File": (file, filename)
    }
    t1 = time.time()
    # response = client.post(endpoint, headers=basic_auth_header, data={"File": file})
    response = client.post(
        endpoint,
        headers=basic_auth_header,
        data=data,
        content_type="multipart/form-data"
    )
    t2 = time.time()
    print_response_details(response, **data)
    # assert response.status_code != 200 # 200代表上傳&更新韌體成功
    assert response.status_code == 200 # why要設計成資料不完整也能更新成功？
            
 
@pytest.mark.parametrize('testcase', updateservice_testcases)
def test_updateservice_api(client, basic_auth_header, testcase):
    """[TestCase] updateservice API"""
    print(f"Endpoint: {testcase['endpoint']}")
    response = client.get(testcase['endpoint'], headers=basic_auth_header)
    assert response.status_code == 200
    
    resp_json = response.json
    print_response_details(response)
    for key, value in testcase['assert_cases'].items():
        # Members比較特殊，排序後確認內容
        if key == "Members":
            resp_json[key] = sorted(resp_json[key], key=lambda x: x['@odata.id'])
            assert resp_json[key] == value
        elif key == "Status":
            assert isinstance(resp_json["Status"], dict)
            # assert resp_json["Status"]["State"] in ["Absent", "Enabled", "Disabled"]
            assert resp_json["Status"]["Health"] in ["OK", "Warning", "Critical"]
        else:
            assert resp_json[key] == value

@pytest.mark.parametrize('testcase', updateservice_firmwareinventory_testcases)
def test_updateservice_firmwareinventory_api(client, basic_auth_header, testcase):
    """[TestCase] updateservice firmwareinventory API"""
    print(f"GET {testcase['endpoint']}")
    response = client.get(testcase['endpoint'], headers=basic_auth_header)
    print_response_details(response)
    assert response.status_code == 200
    
    resp_json = response.json
    for key, value in testcase['assert_cases'].items():
        # Version比較特殊，因為webUI的plc_version會補0，但version不會補0
        if key == "SoftwareId":
            if value == "WEB-INTERFACE":
                assert resp_json["Version"] != ""
                print(f"PASS: Version({resp_json['Version']}) is expected to be non-empty")
            elif value == "PLC-VERSION":
                assert resp_json["Version"].startswith("0")
                print(f"PASS: Version({resp_json['Version']}) is expected to start with 0")
        else:
            assert resp_json[key] == value
            print(f"PASS: resp_json[{key}] is expected to be {value}, actual: {resp_json[key]}")