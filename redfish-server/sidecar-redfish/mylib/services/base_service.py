import os, re
from cachetools import cached, LRUCache, TTLCache
from mylib.utils.HttpRequestUtil import HttpRequestUtil
from mylib.utils.StatusUtil import StatusUtil
from werkzeug.exceptions import HTTPException, BadRequest
from flask import abort
from typing import Dict, List
from mylib.adapters.sensor_api_adapter import SensorAPIAdapter
from mylib.utils.system_info import get_system_uuid
from mylib.utils.SystemCommandUtil import SystemCommandUtil

class BaseService:

    @classmethod
    def exec_command(cls, linux_cmd: str) -> Dict[str, List[str]]:
        """
        執行Linux命令
        """
        return SystemCommandUtil.exec(linux_cmd)

    @classmethod
    def send_get(cls, url, params={}):
        return HttpRequestUtil.send_get(url, params)

    @classmethod
    def send_get_as_json(cls, url, params={}):
        return HttpRequestUtil.send_get_as_json(url, params)

    @classmethod
    def send_post(cls, url, req_body, opts={}):
        return HttpRequestUtil.send_post(url, req_body, opts)

    @classmethod
    def send_post_as_json(cls, url, req_body, opts={}):
        return HttpRequestUtil.send_post_as_json(url, req_body, opts)

    @classmethod
    @cached(cache=TTLCache(maxsize=30, ttl=1))
    def _read_components_chassis_summary_from_cache(cls) -> dict:
        """
        @note api response from /api/v1/cdu/components/chassis/summary
            {
                "fan1": {
                    "status": {
                    "state": "Absent",
                    "health": "Critical"
                    },
                    "reading": 0,
                    "ServiceHours": 100,
                    "ServiceDate": 100,
                    "HardWareInfo": {}
                },
                ...
                "power12v2": {
                    "status": {
                    "state": "Absent",
                    "health": "Critical"
                    },
                    "reading": 0,
                    "ServiceHours": 100,
                    "ServiceDate": 100,
                    "HardWareInfo": {}
                },
                ...
            }
        """
        return SensorAPIAdapter.fetch_components_chassis_summary()

    @classmethod
    @cached(cache=TTLCache(maxsize=30, ttl=1))
    def _read_components_thermal_equipment_summary_from_cache(cls) -> dict:
        """
        @note api response from /api/v1/cdu/components/thermal_equipment/summary
            {
                "temperature_dew_point": {
                    "status": {
                        "state": "Disabled",
                        "health": "OK"
                    },
                    "reading": 0,
                    "ServiceHours": 100,
                    "ServiceDate": 100,
                    "HardWareInfo": {}
                },
                "leak_detector": {
                    "status": {
                        "state": "Enabled",
                        "health": "OK"
                    },
                    "reading": null,
                    "ServiceHours": 100,
                    "ServiceDate": 100,
                    "HardWareInfo": {}
                }, 
                ...
            }
        """
        return SensorAPIAdapter.fetch_components_thermal_equipment_summary()

    @classmethod
    @cached(cache=TTLCache(maxsize=30, ttl=1))
    def _read_sensor_value_from_cache(cls) -> dict:
        """
        @note api response from /cdu/status/sensor_value is
            {
                "temp_coolant_supply": 0,
                " temp_coolant_supply_spare": 0,
                "temp_coolant_return": 0,
                "temp_coolant_return_spare": 0,
                "pressure_coolant_supply": -125,
                "pressure_coolant_supply_spare": -125,
                "pressure_coolant_return": -125,
                "pressure_coolant_return_spare": -125,
                "pressure_filter_in": -125,
                "pressure_filter_out": -125,
                "coolant_flow_rate": -70,
                "temperature_ambient": 0,
                "humidity_relative": 0,
                "temperature_dew_point": 0,
                "ph_level": 0,
                "conductivity": 0,
                "turbidity": 0,
                "power_total": 0,
                "cooling_capacity": 0,
                "heat_capacity": 0,
                "fan1_speed": 0,
                "fan2_speed": 0,
                "fan3_speed": 0,
                "fan4_speed": 0,
                "fan5_speed": 0,
                "fan6_speed": 0,
                "fan7_speed": 0,
                "fan8_speed": 0
            }
        """
        # url = f"{os.environ['ITG_REST_HOST']}/api/v1/cdu/components/chassis/summary"
        url = f"{os.environ['ITG_REST_HOST']}/api/v1/cdu/status/sensor_value"
        response = cls.send_get(url)
        sensor_value_json = response.json()
        return sensor_value_json
    
    @classmethod
    @cached(cache=TTLCache(maxsize=30, ttl=1))
    def _read_version_from_cache(cls) -> dict:
        """
        @note api response from /api/v1/cdu/components/display/version
        "version": {
            "WebUI": "0112",
            "SCC_API": "0104",
            "SNMP": "0103",
            "Redfish_API": "0101",
            "Redfish_Server": "0101",
            "Modbus_Server": "0101",
            "PLC": "0107D"
        },
        "fw_info": {
            "SN": "130001",
            "Model": "CDU 150kW",
            "Version": "1",
            "PartNumber": "LCS-SCDU-1K3LR001"
        }
        
        """
        url = f"{os.environ['ITG_REST_HOST']}/api/v1/cdu/components/display/version"
        response = cls.send_get(url)
        version_json = response.json()
        return version_json
    
    @classmethod
    def get_uuid(cls) -> str:
        return get_system_uuid()
    
    # @classmethod
    # @cached(cache=TTLCache(maxsize=3, ttl=1))
    # def _read_getdata_from_webapp(cls) -> dict:
    #     """
    #     讀取webapp ui的/get_data api
    #     格式可參考 webUI/web/json/sensor_data.json
    #     """
    #     url = f"{os.environ['ITG_WEBAPP_HOST']}/get_data"
    #     response = cls.send_get(url)
    #     data_json = response.json()
    #     return data_json

    def _calc_delta_value(self, sensor_value: dict, fieldNameToFetchSensorValue: str ) -> float:
        """
        如果有兩欄(欄位含',')，則計算兩個sensor value的差值
        """
        if "," in fieldNameToFetchSensorValue: 
            fieldNames = fieldNameToFetchSensorValue.split(",")
            return sensor_value[ fieldNames[0] ]["reading"] - sensor_value[ fieldNames[1] ]["reading"]
        else:
            return sensor_value[ fieldNameToFetchSensorValue ]["reading"]

    def _calc_delta_value_status(self, sensor_value: dict, fieldNameToFetchSensorValue: str ) -> float:
        """
        如果有兩欄(欄位含',')，則計算兩個sensor value的差值
        """
        if "," in fieldNameToFetchSensorValue: 
            fieldNames = fieldNameToFetchSensorValue.split(",")
            status_list = sensor_value[ fieldNames[0] ]["status"], sensor_value[ fieldNames[1] ]["status"]
            # print("status_list: ", status_list)
            status = StatusUtil.get_worst_health_dict(status_list)
            # print("status: ", status)
            return round(sensor_value[ fieldNames[0] ]["reading"] - sensor_value[ fieldNames[1] ]["reading"], 2), status
        else:
            return round(sensor_value[ fieldNameToFetchSensorValue ]["reading"], 2), sensor_value[ fieldNameToFetchSensorValue ]["status"]        

    
    
    def _camel_to_words(self, name: str) -> str:
        """
        將 camelCase 轉換為 words
        Example:
            "TemperatureCelsius" -> "Temperature Celsius"
        Edge Case:
            str ends with: "kPa", "PH", "Celsius", "Percent", "kW"
        """
        suffix_whitelist = ["kPa", "PH", "Celsius", "Percent", "kW"]
        left_str = name
        right_str = None
        for suffix in suffix_whitelist:
            if name.endswith(suffix):
                left_str = name[:-len(suffix)]
                right_str = suffix
                break
        
        if right_str:
            return re.sub(r'(?<!^)(?=[A-Z])', ' ', left_str) + " " + right_str
        else:
            return re.sub(r'(?<!^)(?=[A-Z])', ' ', name)