import os
from flask import request, abort
from flask_restx import Namespace, Resource, fields
from mylib.models.rf_environment_metrics_model import RfEnvironmentMetricsModel
from mylib.services.rf_ThermalEquipment_service import RfThermalEquipmentService
from mylib.utils.load_api import load_raw_from_api 
from mylib.utils.load_api import CDU_BASE
from mylib.routers.Chassis_router import GetControlMode
from mylib.utils.controlUtil import ControlMode_change
import requests
from http import HTTPStatus
from mylib.common.my_resource import MyResource
from mylib.common.proj_error import ProjRedfishError, ProjRedfishErrorCode
from load_env import hardware_info

ThermalEquipment_ns = Namespace('', description='ThermalEquipment Collection')

ThermalEquipment_data= {
    "@odata.id": "/redfish/v1/ThermalEquipment",
    "@odata.type": "#ThermalEquipment.v1_1_2.ThermalEquipment",
    "@odata.context": "/redfish/v1/$metadata#ThermalEquipmentCollection.ThermalEquipmentCollection",
    
    "Name": "Thermal Equipment",
    "Id": "ThermalEquipment",
    "Description": "List all thermal management equipment",
    
    "CDUs": {
        "@odata.id": "/redfish/v1/ThermalEquipment/CDUs"   
    },
}

# CDUs_data = {
#     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs",
#     "@odata.type": "#CoolingUnitCollection.CoolingUnitCollection",
#      "@odata.context": "/redfish/v1/$metadata#CoolingUnitCollection.CoolingUnitCollection",
     
#     "Name": "CDU Collection",
#     "Description": "中控分配單元（CDU）集合",
    
#     "Members@odata.count": 1,
#     "Members": [{"@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1"}],
#     "Oem": {}
# }
# CDUs_data_1 = {
#     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1",
#     "@odata.type": "#CoolingUnit.v1_2_0.CoolingUnit",
#     "@odata.context": "/redfish/v1/$metadata#CoolingUnit.v1_2_0.CoolingUnit",
    
#     "Name": "#1 Cooling Distribution Unit",
#     "Id": "1",
#     "Description": "First Cooling Distribution Unit for chassis liquid cooling",
    
#     # 資訊
#     "Manufacturer": "Supermicro",
#     "Model": "CoolingUnit",
#     # "UUID": "00000000-0000-0000-0000-e45f013e98f8",
#     "SerialNumber": "test_1",
#     "PartNumber": "test_1",
#     "FirmwareVersion": "1.0.0",
#     "Version": "test_1",
#     "ProductionDate": "2024-10-05T00:00:00Z",
    
#     "Status": {
#         "State": "Enabled",
#         "Health": "OK"
#     },
    
#     "CoolingCapacityWatts": 100,
#     "EquipmentType": "CDU",
    
#     # 底下服務
#     "Filters": {
#         "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Filters"
#     },
#     "PrimaryCoolantConnectors": {
#         "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/PrimaryCoolantConnectors"
#     },
#     "SecondaryCoolantConnectors": {
#         "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/SecondaryCoolantConnectors"
#     },
#     "Pumps": {
#         "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps"
#     },
#     "LeakDetection": {
#         "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection"
#     },
#     # 液冷劑參數    
#     "Coolant": {
#         "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Coolant",
#         "CoolantType": "Water",
#         "DensityKgPerCubicMeter": 1000,
#         "SpecificHeatkJoulesPerKgK": 4180
#     },
#     # 泵冗餘示例
#     "PumpRedundancy": [
#         {
#             "RedundancyType": "NPlusM",
#             "MinNeededInGroup": 1,
#             "RedundancyGroup": [
#                 {
#                     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/1"
#                 },
#                 {
#                     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/2"
#                 },                
#                 {
#                     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/3"
#                 }
#             ],
#             "Status": {
#                 "Health": "OK",
#                 "State": "Enabled"
#             }
#         }
#     ],
#     "Reservoirs": {
#         "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Reservoirs"
#     },
#     "EnvironmentMetrics": {
#         "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/EnvironmentMetrics"
#     },
#     "Actions": {
#         "#CoolingUnit.SetMode": {
#             "target": "/redfish/v1/ThermalEquipment/CDUs/1/Actions/CoolingUnit.SetMode",
#             "CoolingUnitMode@Redfish.AllowableValues": [
#                 "Enabled",
#                 "Disabled"
#             ],
#             "Mode@Redfish.AllowableValues": [
#                 "Enabled",
#                 "Disabled"
#             ]
#         }

#     },
    
#     "Links": {
#         "Chassis": [
#             {
#                 "@odata.id": "/redfish/v1/Chassis/1"
#             }
#         ],
#         "ManagedBy": [
#             {
#                 "@odata.id": "/redfish/v1/Managers/CDU"
#             }
#         ]
#     },
#     # 0513新增
#     "Oem": {
#         "Supermicro": {
#             # "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Oem/Supermicro",
#             # "DateTime": {                    
#             #     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Oem/Supermicro/DateTime"
#             # },
#             # "LedLight": {                  
#             #     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Oem/Supermicro/LedLight"
#             # },
#             # "Network": {                  
#             #     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Oem/Supermicro/Network"
#             # },
#             # "Device": {                
#             #     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Oem/Supermicro/Device"
#             # },
#             # "Unit": { 
#             #     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Oem/Supermicro/Unit"
#             # },
#             # "Operation": {                   
#             #     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Oem/Supermicro/Operation"
#             # }
#         }
#     }
# }

PrimaryCoolantConnectors_data = {
    "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/PrimaryCoolantConnectors",
    "@odata.type": "#CoolantConnectorCollection.CoolantConnectorCollection",
    "Name": "Primary (supply side) Cooling Loop Connection Collection",
    "Members@odata.count": 1,
    "Members": [
        {
            "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/PrimaryCoolantConnectors/1"
        }
    ],
}

PrimaryCoolantConnectors_data_1 ={
    "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/PrimaryCoolantConnectors/1",
    "@odata.type": "#CoolantConnector.v1_1_0.CoolantConnector",
    "@odata.context": "/redfish/v1/$metadata#CoolantConnector.v1_1_0.CoolantConnector",
    
    "Id": "1",
    "Name": "Mains Input from Chiller",
    "Description": "Primary input from facility chiller (no valve control)",
    # 額定流量
    "RatedFlowLitersPerMinute": 1000,
    # TBD
    "Status": {
        "Health": "OK",
        "State": "Enabled"
    },
    "Coolant": {
        "CoolantType": "Water",
        "DensityKgPerCubicMeter": 1030,
        "SpecificHeatkJoulesPerKgK": 3900,
        # "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Coolant"
    },
    "CoolantConnectorType": "Pair",
    "FlowLitersPerMinute": {
        "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryFlowLitersPerMinute",
        "Reading": "Null"
    },
    "HeatRemovedkW": {
        "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryHeatRemovedkW",
        "Reading": 0.2
    },
    "SupplyTemperatureCelsius": {
        "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimarySupplyTemperatureCelsius",
        "Reading": 23.32
    },
    "ReturnTemperatureCelsius": {
        "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryReturnTemperatureCelsius",
        "Reading": 23.45
    },
    "DeltaTemperatureCelsius": {
        "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryDeltaTemperatureCelsius",
        "Reading": 0.13
    },
    "SupplyPressurekPa": {
        "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimarySupplyPressurekPa",
        "Reading": 220.0
    },
    "ReturnPressurekPa": {
        "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryReturnPressurekPa",
        "Reading": 85.0
    },
    "DeltaPressurekPa": {
        "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryDeltaPressurekPa",
        "Reading": 135.0
    },
    "SupplyTemperatureControlCelsius":{
        "SetPoint": 30,
        "AllowableMax": 60,
        "AllowableMin": 20,
        "ControlMode": "Disabled"
    },
    "DeltaPressureControlkPa": {
        "SetPoint": 150,
        "AllowableMax": 200,
        "AllowableMin": 50,
        "ControlMode": "Disabled"
    },
    "Oem": {
        "supermicro": {  
            "PumpSwapTime": {
                "@odata.type": "#supermicro.PumpSwapTime.v1_0_0.PumpSwapTime", # 一定要放
                "SetPoint": {
                    "Value": 50,
                    "Units": "Hours"
                }
            }   
        }

    },
    
}

# cdus_pumps={
#     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps",
#     "@odata.type": "#PumpCollection.PumpCollection",
#     "Name": "Cooling Pump Collection",
#     "Members@odata.count": 3,
#     "Members": [
#         {
#             "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/1"
#         },
#         {
#             "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/2"
#         },
#         {
#             "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/3"
#         }
#     ],
# }

# cdus_pumps_1={
#     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/1",
#     "@odata.type": "#Pump.v1_2_0.Pump",
#     "Id": "1",
#     "PumpType": "Liquid",
#     "Name": "Pump Left",
#     "Status": {
#         "State": "Enabled",
#         "Health": "OK"
#     },
#     "PumpSpeedPercent": {
#         "Reading": 0,
#         "SpeedRPM": 0
#     },
#     "FirmwareVersion": "0",
#     "ServiceHours": 1340.3,
#     "Location": {
#         "PartLocation": {
#             "ServiceLabel": "Pump 1",
#             "LocationType": "Bay"
#         }
#     },
#     "SpeedControlPercent": {
#         "SetPoint": 0,
#         "AllowableMax": 100,
#         "AllowableMin": 25,
#         "ControlMode": "manual"
#     },
#     "Actions": {
#         "#Pump.SetMode": {
#             "target": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/1/Actions/Pump.SetMode"
#         }
#     },
#     "Oem": {
#         "supermicro": {  
#             "Inventer 1 MC": {
#                 "@odata.type": "#supermicro.Inventer.v1_0_0.Inventer", # 一定要放
#                 "Switch": "ON"
#             }   
#         }
        
#     }
    
# }

# cdus_pumps_2 = {
#     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/2",
#     "@odata.type": "#Pump.v1_2_0.Pump",
#     "Id": "2",
#     "PumpType": "Liquid",
#     "Name": "Pump Right",
#     "Status": {
#         "State": "Enabled",
#         "Health": "OK"
#     },
#     "PumpSpeedPercent": {
#         "Reading": 29,
#         "SpeedRPM": 2004
#     },
#     "FirmwareVersion": "0",
#     "ServiceHours": 1336.67,
#     "Location": {
#         "PartLocation": {
#             "ServiceLabel": "Pump 2",
#             "LocationType": "Bay"
#         }
#     },
#     "SpeedControlPercent": {
#         "SetPoint": 0,
#         "AllowableMax": 100,
#         "AllowableMin": 25,
#         "ControlMode": "Automatic"
#     },
#     "Actions": {
#         "#Pump.SetMode": {
#             "target": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/2/Actions/Pump.SetMode"
#         }
#     },
#     "Oem": {
#         "supermicro": {  
#             "Inventer 2 MC": {
#                 "@odata.type": "#supermicro.Inventer.v1_0_0.Inventer", # 一定要放
#                 "Switch": "ON"
#             }   
#         }
#     }
# }

# cdus_pumps_3 = {
#     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/3",
#     "@odata.type": "#Pump.v1_2_0.Pump",
#     "Id": "3",
#     "PumpType": "Liquid",
#     "Name": "Pump Right",
#     "Status": {
#         "State": "Enabled",
#         "Health": "OK"
#     },
#     "PumpSpeedPercent": {
#         "Reading": 29,
#         "SpeedRPM": 3004
#     },
#     "FirmwareVersion": "0",
#     "ServiceHours": 1336.67,
#     "Location": {
#         "PartLocation": {
#             "ServiceLabel": "Pump 3",
#             "LocationType": "Bay"
#         }
#     },
#     "SpeedControlPercent": {
#         "SetPoint": 0,
#         "AllowableMax": 100,
#         "AllowableMin": 25,
#         "ControlMode": "Automatic"
#     },
#     "Actions": {
#         "#Pump.SetMode": {
#             "target": "/redfish/v1/ThermalEquipment/CDUs/1/Pumps/3/Actions/Pump.SetMode"
#         }
#     },
#     "Oem": {
#         "supermicro": {  
#             "Inventer 3 MC": {
#                 "@odata.type": "#supermicro.Inventer.v1_0_0.Inventer", # 一定要放
#                 "Switch": "ON"
#             }   
#         }
#     }
# }

cdus_filters={
    "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Filters",
    "@odata.type": "#FilterCollection.FilterCollection",
    
    "Name": "Filter Collection",

    "Members@odata.count": 1,
    "Members": [
        {
            "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Filters/1"
        }
    ]
}

# cdus_filters_1 = {
#     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Filters/1",
#     "@odata.type": "#Filter.v1_0_2.Filter",
#     "@odata.context": "/redfish/v1/$metadata#Filter.v1_0_2.Filter",
    
#     "Id": "1",
#     "Name": "Cooling Loop Filter",
#     "Description": "Cooling Loop Filter",
#     # 設備資訊
#     "ServicedDate": "2020-12-24T08:00:00Z", # 先hardcode
#     # "Manufacturer": "Supermicro",
#     # "Model": "MrCoffee",
#     # "PartNumber": "Cone4",
#     "HotPluggable": False,
#     "Replaceable": False,
#     # 設備服務時間
#     "ServiceHours": -1,
#     "RatedServiceHours": 4320,
#     "Status": {
#         "State": "Enabled",
#         "Health": "OK"
#     },
#     # 實體位置
#     "Location": {
#         "Placement": {
#             "Row": "North 1"
#         },
#         "PartLocation": {
#             "ServiceLabel": "Filter 1",
#             "LocationType": "Bay"
#         }
#     },
# }

# environment_metrics = {
#     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/EnvironmentMetrics",
#     "@odata.type": "#EnvironmentMetrics.v1_3_2.EnvironmentMetrics",
#     "@odata.context": "/redfish/v1/$metadata#EnvironmentMetrics.v1_3_2.EnvironmentMetrics",
    
#     "Id": "EnvironmentMetrics",
#     "Name": "CDU Environment Metrics",
#     "Description":    "冷卻分配單元環境感測指標",

#     # 溫度（Celsius）
#     "TemperatureCelsius": {
#         "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/TemperatureCelsius",
#         "Reading": 19.81
#     },
#     # 露點（Celsius）
#     "DewPointCelsius": {
#         "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/DewPointCelsius",
#         "Reading": 13.53
#     },
#     # 相對濕度（百分比）
#     "HumidityPercent": {
#         "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/HumidityPercent",
#         "Reading": 67.11
#     },
#     # 絕對濕度（克／立方米)
#     "AbsoluteHumidity": {
#         "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/AbsoluteHumidity",
#         "Reading": 11.46
#     },
#     "Oem": {},
# }

reservoirs = {
    "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Reservoirs",
    "@odata.type": "#ReservoirCollection.ReservoirCollection",
    "@odata.context": "/redfish/v1/$metadata#ReservoirCollection.ReservoirCollection",
    
    "Name": "Reservoir Collection",
    "Description": "Reservoirs Collection",
    "Members@odata.count": 1,
    "Members": [
        {
            "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Reservoirs/1"
        },
    ],
    "Oem":{}
}

reservoirs_1 = {
    "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Reservoirs/1",
    "@odata.type": "#Reservoir.v1_0_0.Reservoir",
    "@odata.context": "/redfish/v1/$metadata#Reservoir.v1_0_0.Reservoir",
    
    "Id": "1",
    "Name": "Liquid Level",
    "Description": "Primary reserve reservoir for CDU 1",
    # 容量資訊
    "ReservoirType": "Reserve",
    "CapacityLiters": -1, # 最大容量 未有此功能填-1
    "FluidLevelStatus": "OK",
    # "FluidLevelPercent": { # 考慮要不要
    #     "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/ReservoirFluidLevelPercent",
    #     "Reading": 82.5
    # },
    
    # 設備資訊
    "Manufacturer": "supermicro",
    "Model": "ReservoirModelX",
    "PartNumber": "RES-100",
    "SparePartNumber": "SPN-100",
    "PhysicalContext": "LiquidInlet",
    # 狀態
    "Status": {
        "State": "Enabled",
        "Health": "OK"
    },
    
    # 實體位置
    "Location": {
        "PartLocation": {
            "ServiceLabel": "Reservoir 1",
            "LocationType": "Bay"
        }
    },
    "Oem": {}
}

LeakDetection_data = {
    "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection",
    "@odata.type": "#LeakDetection.v1_1_0.LeakDetection",
    "@odata.context": "/redfish/v1/$metadata#LeakDetection.v1_1_0.LeakDetection",
    
    "Id": "LeakDetection",
    "Name": "Leak Detection",
    "Description": "LeakDetection",
    # "Members@odata.count": 1,
    # ---------------------------
    "Status": {
        "State": "Enabled",
        "Health": "OK"
    },
    "LeakDetectorGroups": [
        {
            "GroupName": "LeakDetectorGroup1",
            "Detectors": [
                {
                    "DataSourceUri":   "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectors/1",
                    "DetectorState":   "OK"
                }
            ],
            # 必要
            "HumidityPercent": {
                "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/HumidityPercent",
                "Reading": "Null"
            },
            "Status": {
                "State": "Enabled",
                "Health": "OK"
            },
            # {"@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectorGroups"}  
        }
    ],
    "LeakDetectors": {
        "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectors"
    },
    # "Members": [
    #     {"@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectors"}
    # ], 
    "Oem": {}  
}

# LeakDetectionLeakDetectors_data = {
#     "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectors",
#     "@odata.type": "#LeakDetectors.v1_3_0.LeakDetectors",
#     "Id": "1",
#     "Name": "LeakDetectors",
#     "Status": {
#         "State": "Enabled",
#         "Health": "Critical"
#     },
# }
# -------------------------------------
# Automatic setting patch設置
# oem_supermicro = ThermalEquipment_ns.model('OemSupermicro', {
#             'TargetTemperature': fields.Integer(
#                 # required=True,
#                 description='temperature setting',
#                 default=50,
#             ),
#             "TargetPressure": fields.Integer(
#                 # required=True,
#                 description='pressure setting',
#                 default=50,
#             ),
#             "PumpSwapTime": fields.Integer(
#                 # required=True,
#                 description='pump swap time setting',
#                 default=50,
#             ),
# })
# # 再定義 Oem 物件，包含 supermicro 這個巢狀 model
# oem_model = ThermalEquipment_ns.model('PrimaryCoolantConnectorsOem', {
#     'Supermicro': fields.Nested(oem_supermicro, description='Supermicro OEM settings')
# })

# # 最後定義整個 patch payload
# PrimaryCoolantConnectors_patch = ThermalEquipment_ns.model('PrimaryCoolantConnectors1Patch', {
#     'Oem': fields.Nested(oem_model, required=False, description='OEM specific parameters')
# })
# ================================================================
# payload model設置
# ================================================================
# primarycoolantconnectors patch設置
setting = ThermalEquipment_ns.model('setting', {
    'SetPoint': fields.Float(
        # required=True,
        description='point setting',
        default=50,
    ),
    'ControlMode': fields.String(
        required=True,
        description='Switch_Mode',
        default=True,   # 是否設定預設值
        example="Manual",   # 讓 UI 顯示範例
        enum=['Automatic', 'Manual', 'Disabled']
    ),
})
pumpswattime = ThermalEquipment_ns.model('pumpswattime', {
    "PumpSwapTime": fields.Integer(
        # required=True,
        description='pump swap time setting',
        default=50,
    ),
})
oem_model = ThermalEquipment_ns.model('PrimaryCoolantConnectorsOem', {
    'Supermicro': fields.Nested(pumpswattime, description='Supermicro OEM settings')
})
PrimaryCoolantConnectors_model = ThermalEquipment_ns.model('PrimaryCoolantConnectors', {
    'SupplyTemperatureControlCelsius': fields.Nested(setting, description='PrimaryCoolantConnectors settings'),
    'DeltaPressureControlkPa': fields.Nested(setting, description='PrimaryCoolantConnectors settings'),
    'Oem': fields.Nested(oem_model, required=False, description='OEM specific parameters')
})

# pump patch設置
Pump_model = ThermalEquipment_ns.model('Pump', {
    'SpeedControlPercent': fields.Nested(setting, description='Pump settings'),
})


class MyBaseThermalEquipment(MyResource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cdu_count = int(os.getenv("REDFISH_CDUS_COLLECTION_CNT", 1))
        self.primary_coolant_connector_count = 1
        self.secondary_coolant_connector_count = 1
        self.leak_detector_count = len(hardware_info.get("leak_detectors", {}))
    
    def _validate_request(self):
        try:
            cdu_id = request.view_args.get("cdu_id")
            connector_id = request.view_args.get("connector_id")
            # leak_detector_id = request.view_args.get("leak_detector_id")

            if not self._is_valid_id(cdu_id, self.cdu_count):
                abort(HTTPStatus.NOT_FOUND, description=f"cdu_id, {cdu_id}, not found")
            
            if not self._is_valid_id(connector_id, self.primary_coolant_connector_count):
                abort(HTTPStatus.NOT_FOUND, description=f"connector_id, {connector_id}, not found")
            
            # if not self._is_valid_id(leak_detector_id, self.leak_detector_count):
            #     abort(HTTPStatus.NOT_FOUND, description=f"leak_detector_id, {leak_detector_id}, not found")
        except Exception as e:
            abort(HTTPStatus.NOT_FOUND, description=f"[Unexpected Error] {e}")
    
    def _is_valid_id(self, id: str, max_value: int):
        if id: # request有傳id進來才檢查
            if not id.isdigit():
                return False
            if not (0 < int(id) <= max_value):
                return False
        return True

@ThermalEquipment_ns.route("/ThermalEquipment")
class ThermalEquipment(Resource):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment")
    def get(self):
        """get thermal equipment"""
        return ThermalEquipment_data
            
@ThermalEquipment_ns.route("/ThermalEquipment/CDUs")
class ThermalEquipmentCdus(Resource):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment_cdus")
    def get(self):
        # return CDUs_data
        return RfThermalEquipmentService().fetch_CDUs()
    
@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<cdu_id>")
class ThermalEquipmentCdus1(MyBaseThermalEquipment):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment_cdus")
    def get(self, cdu_id: str):
        # return CDUs_data_1
        rep = RfThermalEquipmentService().fetch_CDUs(cdu_id)
        return rep
    
@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<cdu_id>/PrimaryCoolantConnectors")
class PrimaryCoolantConnectors(MyBaseThermalEquipment):
    # # @requires_auth
    @ThermalEquipment_ns.doc("primary_coolant_connectors")
    def get(self, cdu_id: str):
        return RfThermalEquipmentService().fetch_CDUs_PrimaryCoolantConnectors(cdu_id)
    
@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/1/PrimaryCoolantConnectors/1")
class PrimaryCoolantConnectors1(Resource):
    # # @requires_auth
    @ThermalEquipment_ns.doc("primary_coolant_connectors_1")
    def get(self):
        value_all = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/sensor_value")
        pump_swap_time = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/control/pump_swap_time")
        
        PrimaryCoolantConnectors_data_1["FlowLitersPerMinute"]["Reading"] = value_all["coolant_flow_rate"]
        PrimaryCoolantConnectors_data_1["HeatRemovedkW"]["Reading"] = value_all["heat_capacity"]
        
        SupplyTemperatureCelsius = PrimaryCoolantConnectors_data_1["SupplyTemperatureCelsius"]["Reading"] = value_all["temp_coolant_supply"]
        ReturnTemperatureCelsius = PrimaryCoolantConnectors_data_1["ReturnTemperatureCelsius"]["Reading"] = value_all["temp_coolant_return"]
        PrimaryCoolantConnectors_data_1["DeltaTemperatureCelsius"]["Reading"] = round(SupplyTemperatureCelsius - ReturnTemperatureCelsius, 2)
       
        SupplyPressurekPa = PrimaryCoolantConnectors_data_1["SupplyPressurekPa"]["Reading"] = value_all["pressure_coolant_supply"]
        ReturnPressurekPa = PrimaryCoolantConnectors_data_1["ReturnPressurekPa"]["Reading"] = value_all["pressure_coolant_return"]
        PrimaryCoolantConnectors_data_1["DeltaPressurekPa"]["Reading"] = round(SupplyPressurekPa - ReturnPressurekPa, 2)
        
        PrimaryCoolantConnectors_data_1["Oem"]["supermicro"]["PumpSwapTime"]["SetPoint"]["Value"] = pump_swap_time
        
        controlmode = GetControlMode()
        # if controlmode == "Automatic":
        #     controlmode = "Manual"
        PrimaryCoolantConnectors_data_1["SupplyTemperatureControlCelsius"]["ControlMode"] = controlmode
        PrimaryCoolantConnectors_data_1["DeltaPressureControlkPa"]["ControlMode"] = controlmode
        return PrimaryCoolantConnectors_data_1
    
    @ThermalEquipment_ns.expect(PrimaryCoolantConnectors_model, validate=True)
    def patch(self):
        body = request.get_json(force=True)
        # 驗證模式
        # if GetControlMode() != "Automatic": return "only Automatic can setting"
        
        temp_setpoint = body.get("SupplyTemperatureControlCelsius", {}).get("SetPoint")
        temp_controlmode = body.get("SupplyTemperatureControlCelsius", {}).get("ControlMode")
        pressure_setpoint = body.get("DeltaPressureControlkPa", {}).get("SetPoint")
        pressure_controlmode = body.get("DeltaPressureControlkPa", {}).get("ControlMode")
        pump_swap_time = body.get("Oem", {}).get("Supermicro", {}).get("PumpSwapTime")
        
        automatic_setting = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/op_mode")
        # 未填邏輯判斷
        if temp_setpoint is None:
            temp_setpoint = automatic_setting["temp_set"]
        if pressure_setpoint is None:
            pressure_setpoint = automatic_setting["pressure_set"]
        # controlmode判斷 
        if temp_controlmode is None and pressure_controlmode is None:
            controlmode = automatic_setting["mode"]
            controlmode = ControlMode_change(controlmode)
        elif  temp_controlmode is None: 
            controlmode = pressure_controlmode
        elif pressure_controlmode is None:
            controlmode = temp_controlmode
        else:
            controlmode = temp_controlmode    
        if temp_controlmode != pressure_controlmode:    
            controlmode = automatic_setting["mode"]
            controlmode = ControlMode_change(controlmode)
        if pump_swap_time is None:
            pump_swap_time = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/control/pump_swap_time")["pump_swap_time"]
        controlmode = ControlMode_change(controlmode)
        # 轉發到內部控制 API
        try:
            r = requests.patch(
                f"{CDU_BASE}/api/v1/cdu/status/op_mode",
                json={"mode": controlmode, "temp_set": temp_setpoint, "pressure_set": pressure_setpoint, "pump_swap_time": pump_swap_time},
                timeout=3
            )
            r.raise_for_status()

        except requests.HTTPError as e:
            # 如果 CDU 回了 4xx/5xx，直接把它的 status code 和 body 回來
            raise ProjRedfishError(
                ProjRedfishErrorCode.INTERNAL_ERROR, 
                f"PATCH {CDU_BASE}/api/v1/cdu/status/op_mode FAIL: details={str(e)}"
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
        

        if controlmode == "auto":
            controlmode = "manual"
        controlmode = ControlMode_change(controlmode)
        # 內部儲存
        PrimaryCoolantConnectors_data_1["SupplyTemperatureControlCelsius"]["SetPoint"] = temp_setpoint
        PrimaryCoolantConnectors_data_1["SupplyTemperatureControlCelsius"]["ControlMode"] = controlmode
        PrimaryCoolantConnectors_data_1["DeltaPressureControlkPa"]["SetPoint"] = pressure_setpoint
        PrimaryCoolantConnectors_data_1["DeltaPressureControlkPa"]["ControlMode"] = controlmode
        PrimaryCoolantConnectors_data_1["Oem"]["supermicro"]["PumpSwapTime"]["SetPoint"]["Value"] = pump_swap_time
        
        return PrimaryCoolantConnectors_data_1, 200
    
@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<string:cdu_id>/Pumps")
class ThermalEquipmentCdus1Pumps(Resource):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_pumps")
    def get(self, cdu_id):    
        rep = RfThermalEquipmentService().fetch_CDUs_Pumps(cdu_id)
        return rep
    
#--------------------------pumpId---------------------------------------- 
@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<string:cdu_id>/Pumps/<string:pump_id>")
class ThermalEquipmentCdus1PumpsPump(MyBaseThermalEquipment):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_pumps_pump")
    def get(self, cdu_id, pump_id):
        # 驗證 cdu_id 和 pump_id
        self._validate_request()
        
        # 取得 Pump 資源
        rep = RfThermalEquipmentService().fetch_CDUs_Pumps_Pump_get(cdu_id, pump_id)
        return rep
        
    # # @requires_auth
    @ThermalEquipment_ns.expect(Pump_model, validate=True)
    @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_pumps_pump")
    def patch(self, cdu_id, pump_id):
        # 驗證 cdu_id 和 pump_id
        self._validate_request()
        body = request.get_json(force=True)
        # 取得 Pump 資源
        rep = RfThermalEquipmentService().fetch_CDUs_Pumps_Pump_patch(cdu_id, pump_id, body)
        return rep

# pump_max_speed = 16000

# @ThermalEquipment_ns.route("/ThermalEquipment/CDUs/1/Pumps/1")
# class ThermalEquipmentCdus1Pumps1(Resource):
    # # @requires_auth
#     @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_pumps_1")
#     def get(self):
#         pump_speed = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/pump_speed")["pump1_speed"]
#         cdus_pumps_1["PumpSpeedPercent"]["Reading"] = pump_speed
#         cdus_pumps_1["PumpSpeedPercent"]["SpeedRPM"] = pump_speed * pump_max_speed / 100
#         cdus_pumps_1["SpeedControlPercent"]["SetPoint"] = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/control/pump_speed")["pump1_speed"]
        
#         state = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/pump_state")["pump1_state"]
#         health = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/pump_health")["pump1_health"]
#         service_hours = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/pump_service_hours")["pump1_service_hours"]
#         if state == "Disable": state = "Disabled"
#         cdus_pumps_1["Status"]["State"] = state
#         cdus_pumps_1["Status"]["Health"] = health
#         cdus_pumps_1["ServiceHours"] = service_hours
#         cdus_pumps_1["Oem"]["supermicro"]["Inventer 1 MC"]["Switch"] = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/mc")["mc1_sw"]
        
#         # rep = RfThermalEquipmentService().fetch_CDUs_Pumps_Pump(cdu_id, pump_id)
#         return cdus_pumps_1
#         # return rep
        
    # @requires_auth
    # @ThermalEquipment_ns.expect(pumpspeed_patch, validate=True)
    # def patch(self):
    #     body = request.get_json(force=True)
    #     # new_sp = body['pump_speed']
    #     # new_sw = body['pump_switch']
        
    #     # 驗證模式
    #     if GetControlMode() != "Manual": return "only Manual can setting"
        
    #     # 驗證範圍
    #     scp = cdus_pumps_1["SpeedControlPercent"]
    #     if not (scp["AllowableMin"] <= new_sp <= scp["AllowableMax"]):
    #         return {
    #             "error": f"pump_speed needs to be between {scp['AllowableMin']} and {scp['AllowableMax']}"
    #         }, 400

    #     # 轉發到內部控制 API
    #     try:
    #         r = requests.patch(
    #             f"{CDU_BASE}/api/v1/cdu/control/pump1_speed",
    #             json={"pump_speed": new_sp, "pump_switch": new_sw},
    #             timeout=3
    #         )
    #     except requests.HTTPError:
    #         # 如果 CDU 回了 4xx/5xx，直接把它的 status code 和 body 回來
    #         try:
    #             err_body = r.json()
    #         except ValueError:
    #             err_body = {"error": r.text}
    #         return err_body, r.status_code

    #     except requests.RequestException as e:
    #         # 純粹網路／timeout／連線失敗
    #         return {
    #             "error": "Forwarding to the CDU control service failed",
    #             "details": str(e)
    #         }, 502

    #     # 更新內存資料
    #     scp["SetPoint"] = new_sp
    #     # pump_switch 控制 State
    #     cdus_pumps_1["Status"]["State"] = "Enabled" if new_sw else "Disabled"
    #     # 取得轉速
    #     pump_speed = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/pump_speed")["pump1_speed"]
    #     cdus_pumps_1["PumpSpeedPercent"]["Reading"] = pump_speed
    #     cdus_pumps_1["PumpSpeedPercent"]["SpeedRPM"] = pump_speed * pump_max_speed / 100

    #     # 回傳整個 Pump 資源
    #     return cdus_pumps_1, 200

    
    
@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/1/Filters")
class ThermalEquipmentCdus1Filters(Resource):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_filters")
    def get(self):
        
        return cdus_filters
    
@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<cdu_id>/Filters/<filter_id>")
class ThermalEquipmentCdus1Filters1(Resource):
    # # @requires_auth
    '''
    p3, p4其中一個broken他就broken
    warning, alert抓p4
    '''
    @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_filters_1")
    def get(self, cdu_id, filter_id):
        rep = RfThermalEquipmentService().fetch_CDUs_Filters_id(cdu_id, filter_id)

        # return cdus_filters_1
        return rep
    
@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<cdu_id>/EnvironmentMetrics")
class ThermalEquipmentCdus1EnvironmentMetrics(MyBaseThermalEquipment):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_environment_metrics")
    def get(self, cdu_id):
        thermal_equipment_service = RfThermalEquipmentService()
        return thermal_equipment_service.fetch_CDUs_EnvironmentMetrics(cdu_id)
        # return "environment_metrics"
    
# @ThermalEquipment_ns.route("/ThermalEquipment/CDUs/1/Reservoirs")
# class ThermalEquipmentCdus1Reservoirs(Resource):
#     # # @requires_auth
#     @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_reservoirs")
#     def get(self):
        
#         return reservoirs
    
    
# @ThermalEquipment_ns.route("/ThermalEquipment/CDUs/1/Reservoirs/1")
# class ThermalEquipmentCdus1Reservoirs1(Resource):
#     # # @requires_auth
#     @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_reservoirs_1")
#     def get(self):
        
#         return reservoirs_1

@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<cdu_id>/LeakDetection")
class LeakDetection(MyBaseThermalEquipment):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_LeakDetection")
    def get(self, cdu_id):
        rep = RfThermalEquipmentService().fetch_CDUs_LeakDetection(cdu_id)
        
        # return LeakDetection_data    
        return rep

# test = [
#     "/ThermalEquipment/CDUs/<cdu_id>/test",
#     "/ThermalEquipment/CDUs/<cdu_id>/test2"
# ]


@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<cdu_id>/LeakDetection/LeakDetectors",) #*test)
class LeakDetectionLeakDetectors(MyBaseThermalEquipment):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_LeakDetection_LeakDetectors")
    def get(self, cdu_id):
        rf_ThermalEquipment_service = RfThermalEquipmentService()
        resp_json = rf_ThermalEquipment_service.fetch_CDUs_LeakDetection_LeakDetectors(cdu_id)
        return resp_json

@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<cdu_id>/LeakDetection/LeakDetectors/<string:leak_detector_id>")
class LeakDetectionLeakDetectors1(Resource):
    # # @requires_auth
    @ThermalEquipment_ns.doc("thermal_equipment_cdus_1_LeakDetection_LeakDetectors_1")
    def get(self, cdu_id, leak_detector_id):
        # 驗證 cdu_id 和 leak_detector_id
        if leak_detector_id not in hardware_info["leak_detectors"].keys():
            abort(HTTPStatus.NOT_FOUND, description=f"leak_detector_id, {leak_detector_id}, not found")
            
        rep = RfThermalEquipmentService().fetch_CDUs_LeakDetection_LeakDetectors_id(cdu_id, leak_detector_id)
        return rep

Mode_common = ThermalEquipment_ns.model('CoolingUnitPatch', {
    'Mode': fields.String(
        required=True,
        description='Automatic Switch',
        default=True,
        example="Enabled",
        enum = ['Enabled', 'Disabled']
    ),
})

@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<string:cdu_id>/Actions/CoolingUnit.SetMode")
class CoolingUnitSetMode(Resource):
    # # @requires_auth
    @ThermalEquipment_ns.expect(Mode_common, validate=True)
    def post(self, cdu_id):
        data = request.get_json(force=True)
        return RfThermalEquipmentService().fetch_CDUs_SetMode(cdu_id, data)




@ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<string:cdu_id>/Pumps/<string:pump_id>/Actions/Pump.SetMode")
class PumpSetMode(Resource):
    # # @requires_auth
    @ThermalEquipment_ns.expect(Mode_common, validate=True)
    def post(self, cdu_id, pump_id):
        data = request.get_json(force=True)
        return RfThermalEquipmentService().fetch_CDUs_Pumps_SetMode(cdu_id, pump_id, data)

# 0513新增 /redfish/v1/ThermalEquipment/CDUs/{CoolingUnitId}/Oem
# @ThermalEquipment_ns.route('/ThermalEquipment/CDUs/<string:id>/Oem')
# class CduOem(Resource):
#     def get(self, id):
#         return {
#             "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem",
#             "@odata.type": "#Oem.Supermicro.Oem",
#             "Supermicro": {
#                 "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro"
#             }
#         }, 200

# @ThermalEquipment_ns.route('/ThermalEquipment/CDUs/<string:id>/Oem/Supermicro')
# class CduOemSupermicro(Resource):
#     def get(self, id):
#         return {
#             "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro",
#             "@odata.type": "#Supermicro.Supermicro",
#             "DateTime":     { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/DateTime" },
#             "LedLight":     { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/LedLight" },
#             "Network":      { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/Network" },
#             "Device":       { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/Device" },
#             "Unit":         { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/Unit" },
#             "Operation":    { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/Operation" },
#             "Actions":      { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/Actions" },
#             "SensorModule": { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/SensorModule" },
#             "ControlUnit":  { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/ControlUnit" },
#             "ControlSetting":  { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/ControlSetting" },
#             "CloseValveStop":  { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/CloseValveStop" },
#             "ContinueModeSwitch":  { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/ContinueModeSwitch" },
#             "DebugSwitch":  { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/DebugSwitch" },
            
#             # "FactorySettingActionInfo":  { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/FactorySettingActionInfo" },
#             # "PumpOperationTimeResetActionInfo":  { "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/PumpOperationTimeResetActionInfo" },
#         }, 200        

# subnodes = ["DateTime","LedLight","Network","Device","Unit","Operation","Actions","SensorModule","ControlUnit", "ControlSetting", "CloseValveStop", "ContinueModeSwitch", "DebugSwitch"]
# for node in subnodes:
#     @ThermalEquipment_ns.route(f'/ThermalEquipment/CDUs/<string:id>/Oem/Supermicro/{node}')
#     class CduOemNode(Resource):
#         def get(self, id, node=node):
#             return {
#                 "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{id}/Oem/Supermicro/{node}",
#                 "@odata.type": f"#Supermicro.{node}",
#             }, 200        

# @ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<string:cdu_id>/SecondaryCoolantConnectors")
# class SecondaryCoolantConnectorsCollection(MyBaseThermalEquipment):
#     def get(self, cdu_id):
#         SecondaryCoolantConnectors_data = {
#             "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{cdu_id}/SecondaryCoolantConnectors",
#             "@odata.type": "#CoolantConnectorCollection.CoolantConnectorCollection",
#             "@odata.context": "/redfish/v1/$metadata#CoolantConnectorCollection.CoolantConnectorCollection",
#             "Name": "Secondary (supply side) Cooling Loop Connection Collection",
#             "Members": [
#                 {
#                 "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{cdu_id}/SecondaryCoolantConnectors/1"
#                 }
#             ],
#             "Members@odata.count": 1
#         }
#         return SecondaryCoolantConnectors_data

# @ThermalEquipment_ns.route("/ThermalEquipment/CDUs/<string:cdu_id>/SecondaryCoolantConnectors/<string:connector_id>")
# class SecondaryCoolantConnector(MyBaseThermalEquipment):
#     def get(self, cdu_id, connector_id):
#         SecondaryCoolantConnectors_1_data = {
#             "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{cdu_id}/SecondaryCoolantConnectors/{connector_id}",
#             "@odata.type": "#CoolantConnector.v1_1_0.CoolantConnector",
#             "@odata.context": "/redfish/v1/$metadata#CoolantConnector.v1_1_0.CoolantConnector",
            
#             "Id": cdu_id,
#             "Name": f"Secondary Connector {cdu_id}",
            
#             # 額定流量
#             "RatedFlowLitersPerMinute": 1000,
#             "Status": {
#                 "Health": "OK",
#                 "State": "Enabled"
#             },
#             "Coolant": {
#                 "CoolantType": "PropyleneGlycolAq",
#                 "AdditiveName": "Propylene Glycol",
#                 "AdditivePercent": 25,
#                 "DensityKgPerCubicMeter": 1030,
#                 "SpecificHeatkJoulesPerKgK": 3900,
#                 # "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/Coolant"
#             },
#             "CoolantConnectorType": "Pair",
#             "FlowLitersPerMinute": {
#                 "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryFlowLitersPerMinute",
#                 "Reading": "Out of range"
#             },
#             "HeatRemovedkW": {
#                 "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryHeatRemovedkW",
#                 "Reading": 0.2
#             },
#             "SupplyTemperatureCelsius": {
#                 "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimarySupplyTemperatureCelsius",
#                 "Reading": 23.32
#             },
#             "ReturnTemperatureCelsius": {
#                 "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryReturnTemperatureCelsius",
#                 "Reading": 23.45
#             },
#             "DeltaTemperatureCelsius": {
#                 "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryDeltaTemperatureCelsius",
#                 "Reading": 0.13
#             },
#             "SupplyPressurekPa": {
#                 "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimarySupplyPressurekPa",
#                 "Reading": 220.0
#             },
#             "ReturnPressurekPa": {
#                 "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryReturnPressurekPa",
#                 "Reading": 85.0
#             },
#             "DeltaPressurekPa": {
#                 "DataSourceUri": "/redfish/v1/Chassis/1/Sensors/PrimaryDeltaPressurekPa",
#                 "Reading": 135.0
#             },
#             "Oem": {
#                 "supermicro": {  
#                     "PumpSwapTime": {
#                         "@odata.type": "#supermicro.PumpSwapTime.v1_0_0.PumpSwapTime", # 一定要放
#                         "SetPoint": {
#                             "Value": 50,
#                             "Units": "Hours"
#                         }
#                     }   
#                 }

#             },
#         }
#         value_all = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/status/sensor_value")
#         pump_swap_time = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/control/pump_swap_time")
        
#         SecondaryCoolantConnectors_1_data["FlowLitersPerMinute"]["Reading"] = value_all["coolant_flow_rate"]
#         SecondaryCoolantConnectors_1_data["HeatRemovedkW"]["Reading"] = value_all["heat_capacity"]
        
#         SupplyTemperatureCelsius = SecondaryCoolantConnectors_1_data["SupplyTemperatureCelsius"]["Reading"] = value_all["temp_coolant_supply"]
#         ReturnTemperatureCelsius = SecondaryCoolantConnectors_1_data["ReturnTemperatureCelsius"]["Reading"] = value_all["temp_coolant_return"]
#         SecondaryCoolantConnectors_1_data["DeltaTemperatureCelsius"]["Reading"] = round(SupplyTemperatureCelsius - ReturnTemperatureCelsius, 2)
       
#         SupplyPressurekPa = SecondaryCoolantConnectors_1_data["SupplyPressurekPa"]["Reading"] = value_all["pressure_coolant_supply"]
#         ReturnPressurekPa = SecondaryCoolantConnectors_1_data["ReturnPressurekPa"]["Reading"] = value_all["pressure_coolant_return"]
#         SecondaryCoolantConnectors_1_data["DeltaPressurekPa"]["Reading"] = round(SupplyPressurekPa - ReturnPressurekPa, 2)
        
#         SecondaryCoolantConnectors_1_data["Oem"]["supermicro"]["PumpSwapTime"]["SetPoint"]["Value"] = pump_swap_time
#         return SecondaryCoolantConnectors_1_data
