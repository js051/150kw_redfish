import os
import json
import pytest
import sys
import time
import logging
import copy
import random
import string
test_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(test_root)

# tmp_account_name = f"tmp-redfish-account-{int(time.time())}"
random_str = ''.join(random.choices(string.ascii_letters, k=3))
tmp_account_name = f"tmp-account-{random_str}"
create_account_post_body = {
    "UserName": tmp_account_name,
    "Password": "Redfish1234!",
    "RoleId": "ReadOnly"
}

accountservice_testcases = [
    {
        "endpoint": f"/redfish/v1/AccountService",
        "assert_cases": { 
            "@odata.type": "#AccountService.v1_18_0.AccountService",
            "@odata.context": "/redfish/v1/$metadata#AccountService.v1_18_0.AccountService",
            "Id": "AccountService",
            "Name": "Account Service",
            "ServiceEnabled": True,
            "Accounts": {
                "@odata.id": "/redfish/v1/AccountService/Accounts"
            },
            "Roles": {
                "@odata.id": "/redfish/v1/AccountService/Roles"
            },
            "@odata.id": "/redfish/v1/AccountService"
        }
    },
    {
        "endpoint": "/redfish/v1/AccountService/Accounts",
        "assert_cases": { 
            "@odata.id": "/redfish/v1/AccountService/Accounts",
            "@odata.type": "#ManagerAccountCollection.ManagerAccountCollection",
            "Name": "Accounts Collection",
            "Members@odata.count": 3,
            "Members": [
                {
                    "@odata.id": "/redfish/v1/AccountService/Accounts/admin"
                },
                {
                    "@odata.id": "/redfish/v1/AccountService/Accounts/root"
                },
                {
                    "@odata.id": "/redfish/v1/AccountService/Accounts/superuser"
                }
            ]
        }
    },
    {
        "endpoint": f"/redfish/v1/AccountService/Accounts/admin",
        "assert_cases": { 
            "@odata.id": f"/redfish/v1/AccountService/Accounts/admin",
            "@odata.type": "#ManagerAccount.v1_12_1.ManagerAccount",
            "AccountTypes": [
                "Redfish"
            ],
            "Id": "admin",
            "Password": None,
            "PasswordChangeRequired": False,
            "UserName": "admin",
            "RoleId": "Administrator",
            "Enabled": True,
            # "Links": {
            #     "Role": {
            #         "@odata.id": "/redfish/v1/AccountService/Roles/Administrator"
            #     }
            # },
            # "@odata.etag": "\"0x580a304fd23d7d1\""
        }
    },
]
    

# @pytest.fixture()
# def tmp_account_name():
#     return tmp_account_name

def test_create_account_with_invalid_password(client, basic_auth_header):
    """[TestCase] create_account API (invalid password): /redfish/v1/AccountService/Accounts"""
    endpoint = "/redfish/v1/AccountService/Accounts" 
    logging.info(f"Endpoint: {endpoint}")

    # test: invalid password
    post_body = copy.deepcopy(create_account_post_body)
    post_body['Password'] = "easy"
    logging.info(f"Post body: {post_body}")
    response = client.post(endpoint, headers=basic_auth_header, json=post_body)
    logging.info(f"Response: {response.json}")
    assert response.status_code == 400 # invalid password

@pytest.mark.dependency()
def test_create_account(client, basic_auth_header):
    """[TestCase] create_account API: /redfish/v1/AccountService/Accounts/
    @Http request : 
        curl --location 'https://127.0.0.1:5101/redfish/v1/AccountService/Accounts/' 
        --header 'Content-Type: application/json' 
        --data '{
            "UserName":"tmp-redfish-account-{random_str}",
            "Password":"Redfish1234!",
            "RoleId":"ReadOnly"
        }'
    """
    endpoint = "/redfish/v1/AccountService/Accounts" 
    logging.info(f"Endpoint: {endpoint}")

    post_body = copy.deepcopy(create_account_post_body)
    logging.info(f"Post body: {post_body}")
    response = client.post(endpoint, headers=basic_auth_header, json=post_body)
    logging.info(f"Response: {response.json}")
    assert response.status_code == 201 or response.status_code == 200

@pytest.mark.dependency(depends=["test_create_account"])
def test_create_account_again(client, basic_auth_header):
    """[TestCase] create_account API (account already exists): /redfish/v1/AccountService/Accounts
    """
    endpoint = "/redfish/v1/AccountService/Accounts"
    logging.info(f"Endpoint: {endpoint}")

    post_body = copy.deepcopy(create_account_post_body)
    logging.info(f"Post body: {post_body}")
    response = client.post(endpoint, headers=basic_auth_header, json=post_body)
    logging.info(f"Response: {response.json}")

    assert response.status_code == 400 
    
@pytest.mark.dependency(depends=["test_create_account"])
def test_get_account(client, basic_auth_header):
    """[TestCase] get_account API: /redfish/v1/AccountService/Accounts/<account_id>"""
    endpoint = f"/redfish/v1/AccountService/Accounts/{tmp_account_name}"
    logging.info(f"Endpoint: {endpoint}")

    response = client.get(endpoint, headers=basic_auth_header)
    resp_json = response.json
    logging.info(f"Response: {resp_json}")

    assert response.status_code == 200
    assert resp_json["@odata.id"] == f"/redfish/v1/AccountService/Accounts/{tmp_account_name}"
    assert resp_json["Id"] == tmp_account_name
    assert resp_json["UserName"] == tmp_account_name
    assert resp_json["RoleId"] == "ReadOnly"
    
# @pytest.mark.dependency(depends=["test_get_account"])
# def test_update_account(client, basic_auth_header):
#     """[TestCase] update_service API: /redfish/v1/AccountService/Accounts/<account_id>"""
#     endpoint = f"/redfish/v1/AccountService/Accounts/{tmp_account_name}"
#     print(f"Endpoint: {endpoint}")
    

            
@pytest.mark.dependency(depends=["test_get_account"])
def test_delete_account(client, basic_auth_header):
    """[TestCase] delete_account API: /redfish/v1/AccountService/Accounts/<account_id>"""
    endpoint = f"/redfish/v1/AccountService/Accounts/{tmp_account_name}"
    logging.info(f"Endpoint: {endpoint}")
    
    response = client.delete(endpoint, headers=basic_auth_header)
    logging.info(f"Response: {response}")

    assert response.status_code in [204, 200]

@pytest.mark.dependency(depends=["test_delete_account"])
def test_get_deleted_account(client, basic_auth_header):
    """[TestCase] get_account API (deleted account): /redfish/v1/AccountService/Accounts/<account_id>"""
    endpoint = f"/redfish/v1/AccountService/Accounts/{tmp_account_name}"
    logging.info(f"Endpoint: {endpoint}")
    
    response = client.get(endpoint, headers=basic_auth_header)
    resp_json = response.json
    logging.info(f"Response: {resp_json}")

    assert response.status_code == 404

def test_delete_nonexistaccount(client, basic_auth_header):
    """[TestCase] delete_account API (non exist account): /redfish/v1/AccountService/Accounts/<account_id>"""
    endpoint = f"/redfish/v1/AccountService/Accounts/{tmp_account_name}-nonexist"
    logging.info(f"Endpoint: {endpoint}")
    
    response = client.delete(endpoint, headers=basic_auth_header)
    resp_json = response.json
    logging.info(f"Response: {resp_json}")

    assert response.status_code == 404
 
@pytest.mark.parametrize('testcase', accountservice_testcases)
def test_accountservice_api(client, basic_auth_header, testcase):
    """[TestCase] accountservice GET API"""
    print(f"Endpoint: {testcase['endpoint']}")
    response = client.get(testcase['endpoint'], headers=basic_auth_header)
    assert response.status_code == 200
    
    resp_json = response.json
    print(f"Response json: {json.dumps(resp_json, indent=2, ensure_ascii=False)}")
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