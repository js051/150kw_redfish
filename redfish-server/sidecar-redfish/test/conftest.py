'''
conftest.py 是 pytest 的特殊設定檔，用來集中定義「測試共用的 fixture 或 hook function」，
不需要在每個測試檔案中 import 就可以自動套用，這是它的主要用途與優勢。
'''
import os
import sys
import json
from dotenv import load_dotenv
proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(proj_root)

# env_filename = ".env-test"
# print(f"Testing with {env_filename}: {os.path.join(proj_root, env_filename)}")
# load_dotenv(dotenv_path=f"{os.path.join(proj_root, env_filename)}", verbose=True, override=True)
# os.environ['IS_TESTING_MODE'] = 'True'

import base64
from typing import List, Dict, Any
import pytest
import logging
from enum import Enum
from pytest_metadata.plugin import metadata_key


# 讓 logging 輸出到 stdout，pytest-html 才能接收到docstring
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    

def pytest_addoption(parser):
    """
    Parse command line options for config.getoption() use.
    ex: pytest test.py --env=test
    """
    print(f"pytest parser addoption: --env-file")
    parser.addoption("--env-file", action="store", default="")
    print(f"pytest parser addoption: --env")
    parser.addoption("--env", action="store", default="test") # ex: "test-macos"

def pytest_configure(config):
    """在測試開始前讀取並設置環境變數"""

    env_filename = config.getoption("--env-file")
    env = config.getoption("--env") # ex: "test-macos"
    env_filepath = None
    if env_filename:
        env_filepath = os.path.join(proj_root, env_filename)
    elif env:
        env_filename = f".env-{env}" if env else ".env-test"
        env_filepath = os.path.join(proj_root, env_filename)
    else:
        env_filename = ".env-test"
        env_filepath = os.path.join(proj_root, env_filename)
    print(f"Testing with {env_filepath}")
    load_dotenv(dotenv_path=f"{env_filepath}", verbose=True, override=True)
    os.environ['IS_TESTING_MODE'] = 'True'

    """
    會顯示在 html report 的 Environment 部分
    """
    for key, value in os.environ.items():
        if key.startswith("ITG_") or key.startswith("REDFISH_"):
            logging.info(f"{key}: {value}")
            # config._metadata[key] = value # Deprecated
            config.stash[metadata_key][key] = value



@pytest.fixture
def basic_auth_header():
    def make_basic_auth_header(username, password):
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json"
        }
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "Supermicro")
    return make_basic_auth_header(username, password)

@pytest.fixture(autouse=True)
def log_docstring_for_testcase(request):
    """
    自動印出每個test case的docstring
    """
    doc = request.function.__doc__
    if doc:
        logging.info(f"{doc.strip()}")
    else:
        logging.info("<無 docstring>")



@pytest.fixture
def common_payload():
    """Fixture: Generates a payload."""
    payload = {}
    return payload

def print_response_details(response, **kwargs):
    """Print response details."""
    print(f"Request Method: {response.request.method}")
    print(f"Request URL: {response.request.url}")
    print(f"Request Headers: ")
    for header in response.request.headers:
        print(f"  * {header[0]}: {header[1]}")
    
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Headers: ")
    for header in response.headers:
        print(f"  * {header[0]}: {header[1]}")
    print(f"Response Body: ")
    print(json.dumps(response.json, indent=2, ensure_ascii=False))
    # print(json.dumps(json.loads(response.data.decode('utf-8')), indent=2))

    print(f"Other information: ")
    if kwargs:
        for key, value in kwargs.items():
            print(f"  * {key}: {value}")


@pytest.fixture
def client():
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class AssertType(str, Enum):
    CONSTANT     = "constant" # assert的值是常數(ex: redfish schema version)
    CONFIGURABLE = "configurable" # assert的值是可配置的(ex: 網路設定存於sqlite)
    DYNAMIC      = "dynamic" # assert的值是動態的(ex: sensor的讀值)
    LENGTH_GT_0  = "length_gt_0" # 陣列的長度要大於0 (很多`Members`會需要這樣測)

class TestcaseFinder:
    """
    很多testcase是定義成如下的json:
    {
        "id": "operation-mode-automatic",
        "endpoint": "/redfish/v1/Chassis/{chassis_id}/Controls/OperationMode",
        "description": "自動模式",
        "payload": {
            ...
        }
    }
    為了能有效的複用testcase，因此可用id來找testcase
    """

    def __init__(self, testcases: List[Dict[str, Any]]):
        self.testcases = testcases
    
    def find_testcase_by_id(self, _id: str) -> Dict[str, Any]:
        for testcase in self.testcases:
            if testcase.get('id') == _id:
                return testcase
        return None