'''
這是Redfish的chassis service
'''
import os, re
import requests
from typing import Optional
from datetime import datetime
from mylib.models.rf_sensor_model import (
    RfSensorCollectionModel, 
    RfSensorModel, 
)
from mylib.services.base_service import BaseService
from mylib.models.rf_environment_metrics_model import RfEnvironmentMetricsModel
from mylib.models.rf_leak_detector import RfLeakDetectorModel
from mylib.models.rf_status_model import RfStatusModel
from mylib.models.rf_primary_coolant_connector_model import RfPrimaryCoolantConnectorCollectionModel
from mylib.models.rf_cdu_model import RfCduModel, RfCduCollectionModel
from mylib.models.rf_pump_collection_model import RfPumpCollectionModel
from mylib.models.rf_pump_model import RfPumpModel
from mylib.utils.load_api import load_raw_from_api, CDU_BASE
from mylib.models.rf_sensor_model import RfSensorPumpExcerpt
from mylib.models.rf_control_model import RfControlSingleLoopExcerptModel
from mylib.models.rf_filter_model import RfFilterModel
from mylib.models.rf_leak_detection_model import RfLeakDetectionModel
from mylib.models.rf_leak_detector_id import RfLeakDetectionIdModel
from mylib.common.proj_error import ProjRedfishError, ProjRedfishErrorCode


from load_env import hardware_info
from mylib.routers.Chassis_router import GetControlMode
from mylib.utils.StatusUtil import StatusUtil
from mylib.utils.controlUtil import ControlMode_change
from mylib.utils.system_info import get_uptime

class RfThermalEquipmentService(BaseService):
    def fetch_CDUs(self, cdu_id: Optional[str] = None) -> dict:
        """
        對應 "/redfish/v1/ThermalEquipment/CDUs/1"

        :param cdu_id: str
        :return: dict
        """
        if cdu_id is None:
            m = RfCduCollectionModel()
        else:
            m = RfCduModel(
                cdu_id=cdu_id,
                **hardware_info["CDU"]
            )
            status = {
                "State": "Enabled",
                "Health": "OK"
            }
            m.Status = RfStatusModel.from_dict(status)
            m.FirmwareVersion = self._read_version_from_cache()["version"]["WebUI"]
            m.Version = self._read_version_from_cache()["fw_info"]["Version"]
            m.SerialNumber = self._read_version_from_cache()["fw_info"]["SN"]
            m.CoolingCapacityWatts = hardware_info.get("CDU", {}).get("CoolingCapacityWatts", -1)
            m.Oem = {}
            
        return m.to_dict()
    
    def fetch_CDUs_SetMode(self, cdu_id: str, body: dict) -> dict:
        ControlMode = body["Mode"]
        if ControlMode == "Enabled": 
            ControlMode = "auto"
        else:
            ControlMode = "stop"    
        try:
            r = requests.patch(
                f"{CDU_BASE}/api/v1/cdu/status/op_mode",
                json={"mode": ControlMode},  
                timeout=3
            )
            r.raise_for_status()
        except requests.HTTPError as e:
            # 如果 CDU 回了 4xx/5xx，直接把它的 status code 和 body 回來
            raise ProjRedfishError(
                code=ProjRedfishErrorCode.INTERNAL_ERROR,
                message=f"PATCH {CDU_BASE}/api/v1/cdu/status/op_mode FAIL: details={str(e)}"
            )

        except requests.RequestException as e:
            # 純粹網路／timeout／連線失敗
            # return {
            #     "error": "Forwarding to the CDU control service failed",
            #     "details": str(e)
            # }, 502
            raise ProjRedfishError(
                ProjRedfishErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE, 
                f"Forwarding to the CDU control service failed: {str(e)}"
            )
        return body, 200
    
    def fetch_CDUs_EnvironmentMetrics(self, cdu_id: str) -> dict:
        """
        對應 "/redfish/v1/ThermalEquipment/CDUs/1/EnvironmentMetrics"

        :param cdu_id: str
        :return: dict
        """
        m = RfEnvironmentMetricsModel(cdu_id=cdu_id)
        boot_time_h = get_uptime()[0]
        # print(f"CDU boot time: {boot_time_h} hours")
        m.TemperatureCelsius["Reading"] = self._read_reading_value_by_sensor_id("TemperatureCelsius")
        m.DewPointCelsius["Reading"] = self._read_reading_value_by_sensor_id("DewPointCelsius")
        m.HumidityPercent["Reading"] = self._read_reading_value_by_sensor_id("HumidityPercent")
        m.PowerWatts["Reading"] = self._read_reading_value_by_sensor_id("PowerConsume")
        m.EnergykWh["Reading"] = round(self._read_reading_value_by_sensor_id("PowerConsume") * boot_time_h / 1000, 2)
        
        # m.AbsoluteHumidity["Reading"] = self._read_reading_value_by_sensor_id("AbsoluteHumidity")
        return m.to_dict()
    
    def fetch_CDUs_LeakDetection(self, cdu_id: str) -> dict:
        """
        對應 "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection"

        :param cdu_id: str
        :return: dict
        """
        leakgroup = [
            {
                "GroupName": "LeakDetectorGroup1",
                "Detectors": [
                    {"DataSourceUri":   "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectors/1",}
                ],
                # 必要
                "HumidityPercent": {
                    "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/HumidityPercent",
                    "Reading": self._read_reading_value_by_sensor_id("HumidityPercent")
                },
                # "Status": {
                #     "State": "Enabled",
                #     "Health": "OK"
                # },
                "Status": self._read_leak_detector_status("leak_detector")
            }
        ]
        
        m = RfLeakDetectionModel(cdu_id=cdu_id)
        m.Status = self._read_leak_detector_status("leak_detector")
        m.LeakDetectorGroups = leakgroup
        m.LeakDetectors = {
            "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectors"
        }
        
        return m.to_dict()
    
    def fetch_CDUs_LeakDetection_LeakDetectors(self, cdu_id: str) -> dict:
        """
        對應 "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectors"
        Response Example:
        {
            "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectors",
            "@odata.type": "#LeakDetectors.v1_3_0.LeakDetectors",
            "Id": "1",
            "Name": "LeakDetectors",
            "Status": {
                "State": "Enabled",
                "Health": "Critical"
            },
        }

        :param cdu_id: str
        """
        m = RfLeakDetectorModel(cdu_id=cdu_id)
        # m.Status = self._read_leak_detector_status()
        return m.to_dict()

    def fetch_CDUs_LeakDetection_LeakDetectors_id(self, cdu_id: str, leak_detector_id: str) -> dict:
        m = RfLeakDetectionIdModel(cdu_id=cdu_id, leak_detector_id=leak_detector_id)
        
        leak_mapping = {
            "Device1" : "leak_detector",
            "Rack1" : "rack_leak_detector_1",
            "Rack2" : "rack_leak_detector_2",
        }
        
        leak_mapping_result = leak_mapping.get(leak_detector_id, "leak_detector")
        # status
        m.Status = self._read_leak_detector_status(leak_mapping_result)
        m.DetectorState = m.Status.Health
        return m.to_dict()

    def _read_reading_value_by_sensor_id(self, sensor_id: str) -> float:
        """
        @return Reading & ReadingUnits
        """
        id_readingInfo_map = {
            "PrimaryFlowLitersPerMinute": {
                "ReadingUnits": "L/min", 
                "fieldNameToFetchSensorValue": "coolant_flow_rate"
            },
            "PrimaryHeatRemovedkW": {
                "ReadingUnits": "kW", 
                "fieldNameToFetchSensorValue": "heat_capacity"
            },
            "PrimarySupplyTemperatureCelsius": {
                "ReadingUnits": "Celsius", 
                "fieldNameToFetchSensorValue": "temp_coolant_supply"
            },
            "PrimaryReturnTemperatureCelsius": {
                "ReadingUnits": "Celsius", 
                "fieldNameToFetchSensorValue": "temp_coolant_return"
            }, 
            "PrimaryDeltaTemperatureCelsius": {
                "ReadingUnits": "Celsius", 
                "fieldNameToFetchSensorValue": "temp_coolant_supply,temp_coolant_return"
            },
            "PrimarySupplyPressurekPa": {
                "ReadingUnits": "kPa", 
                "fieldNameToFetchSensorValue": "pressure_coolant_supply"
            },
            "PrimaryReturnPressurekPa": {
                "ReadingUnits": "kPa", 
                "fieldNameToFetchSensorValue": "pressure_coolant_return"
            },
            "PrimaryDeltaPressurekPa": {
                "ReadingUnits": "kPa", 
                "fieldNameToFetchSensorValue": "pressure_coolant_supply,pressure_coolant_return"
            },
            "TemperatureCelsius": {
                "ReadingUnits": "Celsius", 
                "fieldNameToFetchSensorValue": "temperature_ambient"
            },
            "DewPointCelsius": {
                "ReadingUnits": "Celsius", 
                "fieldNameToFetchSensorValue": "temperature_dew_point"
            },
            "HumidityPercent": {
                "ReadingUnits": "Percent", 
                "fieldNameToFetchSensorValue": "humidity_relative"
            },
            "WaterPH": {
                "ReadingUnits": "pH", 
                "fieldNameToFetchSensorValue": "ph_level"
            },
            "Conductivity": {
                "ReadingUnits": "μs/cm", 
                "fieldNameToFetchSensorValue": "conductivity"
            },
            "Turbidity": {
                "ReadingUnits": "NTU", 
                "fieldNameToFetchSensorValue": "turbidity"
            },
            "PowerConsume": {
                "ReadingUnits": "kW", 
                "fieldNameToFetchSensorValue": "power_total"
            },
        }
        reading_info = id_readingInfo_map.get(sensor_id, {})
        if reading_info:
            sensor_value_json = self._read_components_chassis_summary_from_cache()
            reading_info["Reading"] = self._calc_delta_value(sensor_value_json, reading_info["fieldNameToFetchSensorValue"])
        else:
            reading_info["Reading"] = 0.0
        return reading_info["Reading"]
    
    def _read_leak_detector_status(self, leak_detector_id: str) -> RfStatusModel:
        """
        目前的設計：UI會讀web app的/get_data，js判斷如下
            if (data["error"]["leakage1_broken"]) {
                $("#leakage1")
                    .css("color", "red")
                    .text("Broken");
            } else if (
                !data["error"]["leakage1_broken"] &&
                data["error"]["leakage1_leak"]
            ) {
                $("#leakage1").css("color", "red").text("Leak");
            } else {
                $("#leakage1").css("color", "black").text("OK");
            }
        以上直接去讀 {project_root}/webUI/web/json/sensor_data.json的`error`欄位
        (註) 20250505 如果未來webUI和redfish佈署在不同機器，直接讀json檔是不通的。
        (註) 20250509 改統一由RestAPI取資料
        (註) 20250701 改使用leak_detector_id指定取得檢測器的狀態
        """
        ret_status_model = None
        try:
            summary_json = self._read_components_thermal_equipment_summary_from_cache()
            leak_detector_info = summary_json[leak_detector_id]
            ret_status_model = RfStatusModel.from_dict(leak_detector_info["status"])
        except Exception as e:
            print(e)
            ret_status_model = RfStatusModel.from_dict({"State": "Disabled", "Health": "Critical"})
        return ret_status_model
            
    def _read_oem_by_cdu_id(self, cdu_id: str):
        return self._read_components_thermal_equipment_summary_from_cache().get("Oem")
        
    
    def fetch_CDUs_PrimaryCoolantConnectors(self, cdu_id: str) -> dict:
        """
        對應 "/ThermalEquipment/CDUs/1/PrimaryCoolantConnectors"

        :param cdu_id: str
        :return: dict
        """
        m = RfPrimaryCoolantConnectorCollectionModel(cdu_id=cdu_id)
        return m.to_dict()
    
    # REDFISH_PUMP_COLLECTION_CNT
    def fetch_CDUs_Pumps(self, cdu_id: str) -> dict:
        """
        對應 "/ThermalEquipment/CDUs/1/Pumps"

        :param cdu_id: str
        :return: dict
        """
        m = RfPumpCollectionModel(cdu_id=cdu_id)
        # for i in range(m.Members_odata_count):
        #     m.Members.append({
        #         "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{cdu_id}/Pumps/{i+1}"
        #     })
        return m.to_dict()
    
    def fetch_CDUs_Pumps_Pump_get(self, cdu_id: str, pump_id: str) -> dict:
        """
        對應 "/ThermalEquipment/CDUs/<cdu_id>/Pumps/<pump_id>"

        :param cdu_id: str
        :param pump_id: str
        :return: dict
        """
        pump_max_speed = 16000  # 最大速度為16000 RPM
        m = RfPumpModel(cdu_id=cdu_id, pump_id=pump_id)
        # speed
        pump_speed = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/pump_speed")[f"pump{pump_id}_speed"]
        m.PumpSpeedPercent = RfSensorPumpExcerpt(**{
            "Reading": pump_speed,
            "SpeedRPM": pump_speed * pump_max_speed / 100            
        })
        # control
        m.SpeedControlPercent = RfControlSingleLoopExcerptModel(**{
            "SetPoint": load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/control/pump_speed")[f"pump{pump_id}_speed"],  
            "AllowableMin": hardware_info["Pumps"][pump_id]["AllowableMin"],
            "AllowableMax": hardware_info["Pumps"][pump_id]["AllowableMax"],
            "ControlMode": GetControlMode()  
        })
        # status
        state = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/pump_state")[f"pump{pump_id}_state"]
        health = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/pump_health")[f"pump{pump_id}_health"]
        if state == "Disable": state = "Disabled"
        if state == "Enable": state = "Enabled"
        status = {
            "State": state,
            "Health": health
        }
        m.Status = RfStatusModel.from_dict(status)
        # service time
        service_hours = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/pump_service_hours")[f"pump{pump_id}_service_hours"]
        m.ServiceHours = service_hours
        # location
        # m.Location = hardware_info["Pumps"][pump_id]["Location"]
        # oem
        m.Oem["supermicro"][f"Inventer {pump_id} MC"]["Switch"] = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/mc")[f"mc{pump_id}_sw"]
        return m.to_dict()
    
    def fetch_CDUs_Pumps_Pump_patch(self, cdu_id: str, pump_id: str, body: dict) -> dict:
        """
        對應 "/ThermalEquipment/CDUs/<cdu_id>/Pumps/<pump_id>"

        :param cdu_id: str
        :param pump_id: str
        :param body: dict
        :return: dict
        """
        m = RfPumpModel(cdu_id=cdu_id, pump_id=pump_id)
        pump_setpoint = body["SpeedControlPercent"]['SetPoint']
        pump_controlmode = body["SpeedControlPercent"]['ControlMode']
        pump_controlmode = ControlMode_change(pump_controlmode)
        # 驗證範圍
        scp = hardware_info["Pumps"][pump_id]
        if not (scp["AllowableMin"] <= pump_setpoint <= scp["AllowableMax"]) and pump_setpoint != 0:
            # return {
            #     "error": f"pump_speed needs to be between {scp['AllowableMin']} and {scp['AllowableMax']} or 0"
            # }, 400
            raise ProjRedfishError(
                code=ProjRedfishErrorCode.GENERAL_ERROR,
                message=f"pump_speed needs to be between {scp['AllowableMin']} and {scp['AllowableMax']} or 0"
            )
            
        # 轉發到內部控制 API
        try:
            r = requests.patch(
                f"{CDU_BASE}/api/v1/cdu/status/op_mode",
                json={"mode": pump_controlmode, "pump_speed": pump_setpoint},
                timeout=5
            )
        except requests.HTTPError as e:
            # 如果 CDU 回了 4xx/5xx，直接把它的 status code 和 body 回來
            raise ProjRedfishError(
                code=ProjRedfishErrorCode.INTERNAL_ERROR,
                message=f"PATCH {CDU_BASE}/api/v1/cdu/status/op_mode FAIL: details={str(e)}"
            )

        except requests.RequestException as e:
            # 純粹網路／timeout／連線失敗
            # return {
            #     "error": "Forwarding to the CDU control service failed",
            #     "details": str(e)
            # }, 502  
            raise ProjRedfishError(
                code=ProjRedfishErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE,
                message=f"Forwarding to the CDU control service failed: {str(e)}"
            )  
        
        # 更新內存資料
        m.SpeedControlPercent = RfControlSingleLoopExcerptModel(**{
            "SetPoint": pump_setpoint, #if new_sw else 0,
            "AllowableMin": scp["AllowableMin"],
            "AllowableMax": scp["AllowableMax"],
            "ControlMode": ControlMode_change(pump_controlmode)
        })
        m.Oem["supermicro"][f"Inventer {pump_id} MC"]["Switch"] = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/mc")[f"mc{pump_id}_sw"]
        return m.to_dict(), 200
        # 因為儲存時間問題setpoint無法即時更新
        # return self.fetch_CDUs_Pumps_Pump_get(cdu_id, pump_id), 200
    
    def fetch_CDUs_Filters_id(self, cdu_id: str, filter_id: str) -> dict:
        """
        對應 "/redfish/v1/ThermalEquipment/CDUs/<cdu_id>/Filters/<filter_id>"

        :param cdu_id: str
        :param filter_id: str
        :return: dict
        
        @note 
            p3, p4其中一個broken他就broken
            warning, alert抓p4
        """
        m = RfFilterModel(cdu_id=cdu_id, filter_id=filter_id)
        
        # ServicedDate
        m.ServicedDate = hardware_info["Filters"][filter_id]["ServicedDate"]
        m.ServiceHours = int(load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/thermal_equipment/summary")["Filter_run_time"])
        
        # location
        # raw_location = hardware_info["Filters"][filter_id]["Location"]
        # m.Location = RfLocationModel(raw_location)
        
        # Status
        all_data = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/chassis/summary")
        health_data = (all_data["pressure_filter_in"]["status"], all_data["pressure_filter_out"]["status"])
        
        status = StatusUtil().get_worst_health_dict(health_data)
        # print("health: ", health)
        # state = "Enabled" if health is "OK" else "Disabled"
        # status = {
        #     "State": state,
        #     "Health": health
        # }
        m.Status = RfStatusModel.from_dict(status)

        return m.to_dict(), 200
    
    
    def fetch_CDUs_Pumps_SetMode(self, cdu_id: str, pump_id: str, body: dict) -> dict:
        """
        對應 "/redfish/v1/ThermalEquipment/CDUs/<cdu_id>/Pumps/<pump_id>"

        :param cdu_id: str
        :param pump_id: str
        :param body: dict
        :return: dict
        """
        mode = True if body["Mode"] == "Enabled" else False
        print(f"pump{pump_id}_switch:", mode)
        # 轉發到內部控制 API
        try:
            r = requests.patch(
                f"{CDU_BASE}/api/v1/cdu/status/op_mode",
                json={"mode": "manual", f"pump{pump_id}_switch": mode},
                timeout=5
            )
            
            return {"message": f"Pump{pump_id} Update Success"}, r.status_code
        except requests.HTTPError as e:
            # 如果 CDU 回了 4xx/5xx，直接把它的 status code 和 body 回來
            raise ProjRedfishError(
                code=ProjRedfishErrorCode.INTERNAL_ERROR,
                message=f"PATCH {CDU_BASE}/api/v1/cdu/status/op_mode FAIL: details={str(e)}"
            )

        except requests.RequestException as e:
            # 純粹網路／timeout／連線失敗
            # return {
            #     "error": "Forwarding to the CDU control service failed",
            #     "details": str(e)
            # }, 502  
            raise ProjRedfishError(
                code=ProjRedfishErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE,
                message=f"Forwarding to the CDU control service failed: {str(e)}"
            )
