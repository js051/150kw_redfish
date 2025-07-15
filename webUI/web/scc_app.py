# 標準函式庫
import json
import logging
import os
import platform
import re
import struct
import subprocess
import threading
import time
import zipfile
from datetime import datetime
from functools import wraps
from io import BytesIO

# 第三方套件
import requests
import pyzipper
from dotenv import load_dotenv, set_key
from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
from flask import (
    Flask, Blueprint, Response, g, jsonify, request, send_file
)
from flask_login import LoginManager, UserMixin
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder


load_dotenv()
# USERNAME = "admin"

# PASSWORD = os.getenv("ADMIN")

# 使用者與對應密碼（從環境變數讀取）
USER_CREDENTIALS = {
    "admin": os.getenv("ADMIN"),
    "superuser": os.getenv("SUPERUSER"),
    "root": os.getenv("ROOT"),
}

if platform.system() == "Linux":
    onLinux = True
else:
    onLinux = False


app = Flask(__name__)
log_path = os.getcwd()
web_path = f"{log_path}/web"
snmp_path = os.path.dirname(log_path)

upload_path = "/home/user/"
app.config["UPLOAD_FOLDER"] = upload_path

scc_bp = Blueprint("scc", __name__)


login_manager = LoginManager()
login_manager.init_app(scc_bp)


log_dir = f"{log_path}/logs/operation"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)


file_name = "oplog.log"
log_file = os.path.join(log_dir, file_name)

oplog_handler = ConcurrentTimedRotatingFileHandler(
    log_file,
    when="midnight",
    backupCount=1100,
    encoding="UTF-8",
    delay=False,
)
oplog_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
oplog_handler.setFormatter(formatter)
op_logger = logging.getLogger("custom")
op_logger.setLevel(logging.INFO)
op_logger.addHandler(oplog_handler)
# if onLinux:
#     from web.auth import (
#         USER_DATA,
#         User,
#     )
# else:
#     from auth import (
#         USER_DATA,
#         User,
#     )

class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id


@login_manager.user_loader
def load_user(user_id):
    if user_id in g.user_role:
        return User(user_id)
    return None


modbus_host = "192.168.3.250"
# modbus_host = "127.0.0.1"
modbus_port = 502
modbus_slave_id = 1

thrshd = {}
ctr_data = {}
measure_data = {}
system_data = {}
fw_info = {}

sensor_trap = {
    "CoolantSupplyTemperature": {"Warning": False, "Alert": False},
    "CoolantSupplyTemperatureSpare": {"Warning": False, "Alert": False},
    "CoolantReturnTemperature": {"Warning": False, "Alert": False},
    "CoolantReturnTemperatureSpare": {"Warning": False, "Alert": False},
    "CoolantSupplyPressure": {"Warning": False, "Alert": False},
    "CoolantSupplyPressureSpare": {"Warning": False, "Alert": False},
    "CoolantReturnPressure": {"Warning": False, "Alert": False},
    "CoolantReturnPressureSpare": {"Warning": False, "Alert": False},
    "FilterInletPressure": {"Warning": False, "Alert": False},
    "FilterOutletPressure": {"Warning": False, "Alert": False},
    "CoolantFlowRate": {"Warning": False, "Alert": False},
    "AmbientTemp": {"Warning": False, "Alert": False},
    "RelativeHumid": {"Warning": False, "Alert": False},
    "DewPoint": {"Warning": False, "Alert": False},
    "pH": {"Warning": False, "Alert": False},
    "Conductivity": {"Warning": False, "Alert": False},
    "Turbidity": {"Warning": False, "Alert": False},
    "AverageCurrent": {"Warning": False, "Alert": False},
}

device_trap = {
    "Inv1Overload": False,
    "Inv2Overload": False,
    "Inv3Overload": False,
    "FanOverload1": False,
    "FanOverload2": False,
    "Inv1Error": False,
    "Inv2Error": False,
    "Inv3Error": False,
    "ATS": False,
    "Inv1SpeedComm": False,
    "Inv2SpeedComm": False,
    "Inv3SpeedComm": False,
    "CoolantFlowRateComm": False,
    "AmbientTempComm": False,
    "RelativeHumidComm": False,
    "DewPointComm": False,
    "pHComm": False,
    "ConductivityComm": False,
    "TurbidityComm": False,
    "ATS1Comm": False,
    "ATS2Comm": False,
    "InstantPowerConsumptionComm": False,
    "AverageCurrentComm": False,
    "Fan1Comm": False,
    "Fan2Comm": False,
    "Fan3Comm": False,
    "Fan4Comm": False,
    "Fan5Comm": False,
    "Fan6Comm": False,
    "Fan7Comm": False,
    "Fan8Comm": False,
    "CoolantSupplyTemperatureBroken": False,
    "CoolantSupplyTemperatureSpareBroken": False,
    "CoolantReturnTemperatureBroken": False,
    "CoolantReturnTemperatureBrokenSpare": False,
    "CoolantSupplyPressureBroken": False,
    "CoolantSupplyPressureSpareBroken": False,
    "CoolantReturnPressureBroken": False,
    "CoolantReturnPressureSpareBroken": False,
    "FilterInletPressure": False,
    "FilterOutletPressure": False,
    "CoolantFlowRateBroken": False,
    "Leakage1Leak": False,
    "Leakage1Broken": False,
    "Level1": False,
    "Level2": False,
    "Level3": False,
    "Power24v1": False,
    "Power24v2": False,
    "Power12v1": False,
    "Power12v2": False,
    "MainMcError": False,
    "Fan1Error": False,
    "Fan2Error": False,
    "Fan3Error": False,
    "Fan4Error": False,
    "Fan5Error": False,
    "Fan6Error": False,
    "Fan7Error": False,
    "Fan8Error": False,
    "RackError": False,
    "LowCoolantLevelWarning": False,
    "PC1Error": False,
    "PC2Error": False,
    "ControlUnit": False,
    "RackLeakage1Leak": False,
    "RackLeakage1Broken": False,
    "RackLeakage2Leak": False,
    "RackLeakage2Broken": False,
    "RackLeakage3Leak": False,
    "RackLeakage3Broken": False,
    "RackLeakage4Leak": False,
    "RackLeakage4Broken": False,
    "RackLeakage5Leak": False,
    "RackLeakage5Broken": False,
}


inverter_status = {
    "Inverter1": "",
    "Inverter2": "",
    "Inverter3": "",
}

pump_data = {
    "speed": {
        "Pump1Speed": 0,
        "Pump2Speed": 0,
        "Pump3Speed": 0,
    },
    "runtime": {
        "Pump1ServiceHour": 0,
        "Pump2ServiceHour": 0,
        "Pump3ServiceHour": 0,
    },
    "swap": {
        "PumpSwapTime": 0,
    },
}

fan_data = {
    "speed": {
        "Fan1Speed": 0,
        "Fan2Speed": 0,
        "Fan3Speed": 0,
        "Fan4Speed": 0,
        "Fan5Speed": 0,
        "Fan6Speed": 0,
        "Fan7Speed": 0,
        "Fan8Speed": 0,
    }
}

unit = {
    "temp": {"TemperatureSet": 0},
    "prsr": {"PressureSet": 0.5},
    "unit": {"UnitSet": "Metric", "LastUnit": "Metric"},
}

sensor_value_data = {
    "CoolantSupplyTemperature": {
        "Name": "CoolantSupplyTemperature",
        "DisplayName": "Coolant Supply Temperature (T1)",
        "Status": "Good",
        "Value": "0",
        "Unit": "°C",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "60"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "65"},
        "DelayTime": 0,
    },
    "CoolantSupplyTemperatureSpare": {
        "Name": "CoolantSupplyTemperatureSpare",
        "DisplayName": "Coolant Supply Temperature Spare (T1sp)",
        "Status": "Good",
        "Value": "0",
        "Unit": "°C",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "60"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "65"},
        "DelayTime": 0,
    },
    "CoolantReturnTemperature": {
        "Name": "CoolantReturnTemperature",
        "DisplayName": "Coolant Return Temperature (T2)",
        "Status": "Good",
        "Value": "0",
        "Unit": "°C",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "60"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "65"},
        "DelayTime": 0,
    },
    "CoolantReturnTemperatureSpare": {
        "Name": "CoolantReturnTemperatureSpare",
        "DisplayName": "Coolant Return Temperature Spare (T2sp)",
        "Status": "Good",
        "Value": "0",
        "Unit": "°C",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "60"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "65"},
        "DelayTime": 0,
    },
    "CoolantSupplyPressure": {
        "Name": "CoolantSupplyPressure",
        "DisplayName": "Coolant Supply Pressure (P1)",
        "Status": "Good",
        "Value": "1.23",
        "Unit": "kPa",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "350"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "400"},
        "DelayTime": 0,
    },
    "CoolantSupplyPressureSpare": {
        "Name": "CoolantSupplyPressureSpare",
        "DisplayName": "Coolant Supply Pressure Spare (P1sp)",
        "Status": "Good",
        "Value": "1.23",
        "Unit": "kPa",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "350"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "400"},
        "DelayTime": 0,
    },
    "CoolantReturnPressure": {
        "Name": "CoolantReturnPressure",
        "DisplayName": "Coolant Return Pressure (P2)",
        "Status": "Good",
        "Value": "1.23",
        "Unit": "kPa",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "150"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "200"},
        "DelayTime": 0,
    },
    "CoolantReturnPressureSpare": {
        "Name": "CoolantReturnPressureSpare",
        "DisplayName": "Coolant Return Pressure Spare (P2sp)",
        "Status": "Good",
        "Value": "1.23",
        "Unit": "kPa",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "150"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "200"},
        "DelayTime": 0,
    },
    "FilterInletPressure": {
        "Name": "FilterInletPressure",
        "DisplayName": "Filter Inlet Pressure (P3)",
        "Status": "Good",
        "Value": "1.23",
        "Unit": "kPa",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "150"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "200"},
        "DelayTime": 0,
    },
    "FilterOutletPressure": {
        "Name": "FilterOutletPressure",
        "DisplayName": "Filter Outlet Pressure (P4)",
        "Status": "Good",
        "Value": "1.23",
        "Unit": "kPa",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "150"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "200"},
        "DelayTime": 0,
    },
    "CoolantFlowRate": {
        "Name": "CoolantFlowRate",
        "DisplayName": "Coolant Flow Rate (F1)",
        "Status": "Good",
        "Value": "0",
        "Unit": "LPM",
        "WarningLevel": {"TrapEnabled": True, "MinValue": "30", "MaxValue": None},
        "AlertLevel": {"TrapEnabled": True, "MinValue": "20", "MaxValue": None},
        "DelayTime": 0,
    },
    "AmbientTemp": {
        "Name": "AmbientTemp",
        "DisplayName": "Ambient Temperature (Ta)",
        "Status": "Good",
        "Value": "0",
        "Unit": "°C",
        "WarningLevel": {"TrapEnabled": True, "MinValue": "30", "MaxValue": None},
        "AlertLevel": {"TrapEnabled": True, "MinValue": "20", "MaxValue": None},
        "DelayTime": 0,
    },
    "RelativeHumid": {
        "Name": "RelativeHumid",
        "DisplayName": "Relative Humidity (RH)",
        "Status": "Good",
        "Value": "0",
        "Unit": "%",
        "WarningLevel": {"TrapEnabled": True, "MinValue": "30", "MaxValue": None},
        "AlertLevel": {"TrapEnabled": True, "MinValue": "20", "MaxValue": None},
        "DelayTime": 0,
    },
    "DewPoint": {
        "Name": "DewPoint",
        "DisplayName": "Dew Point Temperature (TDp)",
        "Status": "Good",
        "Value": "0",
        "Unit": "°C",
        "WarningLevel": {"TrapEnabled": True, "MinValue": "30", "MaxValue": None},
        "AlertLevel": {"TrapEnabled": True, "MinValue": "20", "MaxValue": None},
        "DelayTime": 0,
    },
    "pH": {
        "Name": "pH",
        "DisplayName": "pH (PH)",
        "Status": "Good",
        "Value": "0",
        "Unit": "pH",
        "WarningLevel": {"TrapEnabled": True, "MinValue": "7.2", "MaxValue": "7.9"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": "7", "MaxValue": "8"},
        "DelayTime": 0,
    },
    "Conductivity": {
        "Name": "Conductivity",
        "DisplayName": "Conductivity (CON)",
        "Status": "Good",
        "Value": "0",
        "Unit": "µS/cm",
        "WarningLevel": {"TrapEnabled": True, "MinValue": "4200", "MaxValue": "4600"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": "4000", "MaxValue": "4700"},
        "DelayTime": 0,
    },
    "Turbidity": {
        "Name": "Turbidity",
        "DisplayName": "Turbidity (Tur)",
        "Status": "Good",
        "Value": "0",
        "Unit": "NTU",
        "WarningLevel": {"TrapEnabled": True, "MinValue": "2", "MaxValue": "10"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": "1", "MaxValue": "15"},
        "DelayTime": 0,
    },
    "InstantPowerConsumption": {
        "Name": "InstantPowerConsumption",
        "DisplayName": "Instant Power Consumption",
        "Value": "0",
        "Unit": "kW",
    },
    "AverageCurrent": {
        "Name": "AverageCurrent",
        "DisplayName": "Average Current",
        "Status": "Good",
        "Value": "0",
        "Unit": "kW",
        "WarningLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "40"},
        "AlertLevel": {"TrapEnabled": True, "MinValue": None, "MaxValue": "45"},
        "DelayTime": 0,
    },
    "HeatCapacity": {
        "Name": "HeatCapacity",
        "DisplayName": "Heat Capacity",
        "Value": "0",
        "Unit": "kW",
    },
}

sensor_status_data = {
    "CoolantSupplyTemperature": {
        "Name": "CoolantSupplyTemperature",
        # "DisplayName": "Coolant Supply Temperature (T1)",
        "Status": "Good",
    },
    "CoolantSupplyTemperatureSpare": {
        "Name": "CoolantSupplyTemperatureSpare",
        # "DisplayName": "Coolant Supply Temperature Spare (T1sp)",
        "Status": "Good",
    },
    "CoolantReturnTemperature": {
        "Name": "CoolantReturnTemperature",
        # "DisplayName": "Coolant Return Temperature (T2)",
        "Status": "Good",
    },
    "CoolantReturnTemperatureSpare": {
        "Name": "CoolantReturnTemperatureSpare",
        # "DisplayName": "Coolant Return Temperature Spare (T2sp)",
        "Status": "Good",
    },
    "CoolantSupplyPressure": {
        "Name": "CoolantSupplyPressure",
        # "DisplayName": "Coolant Supply Pressure (P1)",
        "Status": "Good",
    },
    "CoolantSupplyPressureSpare": {
        "Name": "CoolantSupplyPressureSpare",
        # "DisplayName": "Coolant Supply Pressure Spare (P1sp)",
        "Status": "Good",
    },
    "CoolantReturnPressure": {
        "Name": "CoolantReturnPressure",
        # "DisplayName": "Coolant Return Pressure (P2)",
        "Status": "Good",
    },
    "CoolantReturnPressureSpare": {
        "Name": "CoolantReturnPressureSpare",
        # "DisplayName": "Coolant Return Pressure Spare (P2sp)",
        "Status": "Good",
    },
    "FilterInletPressure": {
        "Name": "FilterInletPressure",
        # "DisplayName": "Filter Inlet Pressure (P3)",
        "Status": "Good",
    },
    "FilterOutletPressure": {
        "Name": "FilterOutletPressure",
        # "DisplayName": "Filter Outlet Pressure (P4)",
        "Status": "Good",
    },
    "CoolantFlowRate": {
        "Name": "CoolantFlowRate",
        # "DisplayName": "Coolant Flow Rate (F1)",
        "Status": "Good",
    },
    "AmbientTemp": {
        "Name": "AmbientTemp",
        # "DisplayName": "Ambient Temperature (Ta)",
        "Status": "Good",
    },
    "RelativeHumid": {
        "Name": "RelativeHumid",
        # "DisplayName": "Relative Humidity (RH)",
        "Status": "Good",
    },
    "DewPoint": {
        "Name": "DewPoint",
        # "DisplayName": "Dew Point Temperature (TDp)",
        "Status": "Good",
    },
    "pH": {
        "Name": "pH",
        # "DisplayName": "pH (PH)",
        "Status": "Good",
    },
    "Conductivity": {
        "Name": "Conductivity",
        # "DisplayName": "Conductivity (CON)",
        "Status": "Good",
    },
    "Turbidity": {
        "Name": "Turbidity",
        # "DisplayName": "Turbidity (Tur)",
        "Status": "Good",
    },
    "InstantPowerConsumption": {
        "Name": "InstantPowerConsumption",
        # "DisplayName": "Instant Power Consumption",
    },
    "AverageCurrent": {
        "Name": "AverageCurrent",
        # "DisplayName": "Average Current",
        "Status": "Good",
    },
    "HeatCapacity": {
        "Name": "HeatCapacity",
        # "DisplayName": "Heat Capacity",
    },
    "Inv1":{
        "Name": "Inv1",
        # "DisplayName": "Coolant Pump1",
        "Status": "Disable"
    },
    "Inv2":{
        "Name": "Inv2",
        # "DisplayName": "Coolant Pump2",
        "Status": "Disable"
    },
    "Inv3":{
        "Name": "Inv3",
        # "DisplayName": "Coolant Pump3",
        "Status": "Disable"
    },
    "Fan1":{
        "Name": "Fan1",
        # "DisplayName": "Fan Speed 1",
        "Status": "Disable"
    },
    "Fan2":{
        "Name": "Fan2",
        # "DisplayName": "Fan  2",
        "Status": "Disable"
    },
    "Fan3":{
        "Name": "Fan3",
        # "DisplayName": "Fan  3",
        "Status": "Disable"
    },
    "Fan4":{
        "Name": "Fan4",
        # "DisplayName": "Fan  4",
        "Status": "Disable"
    },
    "Fan5":{
        "Name": "Fan5",
        # "DisplayName": "Fan  5",
        "Status": "Disable"
    },
    "Fan6":{
        "Name": "Fan6",
        # "DisplayName": "Fan  6",
        "Status": "Disable"
    },
    "Fan7":{
        "Name": "Fan7",
        # "DisplayName": "Fan  7",
        "Status": "Disable"
    },
    "Fan8":{
        "Name": "Fan8",
        # "DisplayName": "Fan  8",
        "Status": "Disable"
    }
}

trap_enable_key = {
    "W_CoolantSupplyTemperature": False,
    "A_CoolantSupplyTemperature": False,
    "W_CoolantSupplyTemperatureSpare": False,
    "A_CoolantSupplyTemperatureSpare": False,
    "W_CoolantReturnTemperature": False,
    "A_CoolantReturnTemperature": False,
    "W_CoolantReturnTemperatureSpare": False,
    "A_CoolantReturnTemperatureSpare": False,
    "W_CoolantSupplyPressure": False,
    "A_CoolantSupplyPressure": False,
    "W_CoolantSupplyPressureSpare": False,
    "A_CoolantSupplyPressureSpare": False,
    "W_CoolantReturnPressure": False,
    "A_CoolantReturnPressure": False,
    "W_CoolantReturnPressureSpare": False,
    "A_CoolantReturnPressureSpare": False,
    "W_FilterInletPressure": False,
    "A_FilterInletPressure": False,
    "W_FilterOutletPressure": False,
    "A_FilterOutletPressure": False,
    "W_CoolantFlowRate": False,
    "A_CoolantFlowRate": False,
    "W_AmbientTemp": False,
    "A_AmbientTemp": False,
    "W_RelativeHumid": False,
    "A_RelativeHumid": False,
    "W_DewPoint": False,
    "A_DewPoint": False,
    "W_pH": False,
    "A_pH": False,
    "W_Conductivity": False,
    "A_Conductivity": False,
    "W_Turbidity": False,
    "A_Turbidity": False,
    "W_AverageCurrent": False,
    "A_AverageCurrent": False,
}

max_min_value_location = {
    "Thr_W_CoolantSupplyTemperature_H": 1000,
    "Thr_W_Rst_CoolantSupplyTemperature_H": 1002,
    "Thr_A_CoolantSupplyTemperature_H": 1004,
    "Thr_A_Rst_CoolantSupplyTemperature_H": 1006,
    "Thr_W_CoolantSupplyTemperatureSpare_H": 1008,
    "Thr_W_Rst_CoolantSupplyTemperatureSpare_H": 1010,
    "Thr_A_CoolantSupplyTemperatureSpare_H": 1012,
    "Thr_A_Rst_CoolantSupplyTemperatureSpare_H": 1014,
    "Thr_W_CoolantReturnTemperature_H": 1016,
    "Thr_W_Rst_CoolantReturnTemperature_H": 1018,
    "Thr_A_CoolantReturnTemperature_H": 1020,
    "Thr_A_Rst_CoolantReturnTemperature_H": 1022,
    "Thr_W_CoolantReturnTemperatureSpare_H": 1024,
    "Thr_W_Rst_CoolantReturnTemperatureSpare_H": 1026,
    "Thr_A_CoolantReturnTemperatureSpare_H": 1028,
    "Thr_A_Rst_CoolantReturnTemperatureSpare_H": 1030,
    "Thr_W_CoolantSupplyPressure_H": 1032,
    "Thr_W_Rst_CoolantSupplyPressure_H": 1034,
    "Thr_A_CoolantSupplyPressure_H": 1036,
    "Thr_A_Rst_CoolantSupplyPressure_H": 1038,
    "Thr_W_CoolantSupplyPressureSpare_H": 1040,
    "Thr_W_Rst_CoolantSupplyPressureSpare_H": 1042,
    "Thr_A_CoolantSupplyPressureSpare_H": 1044,
    "Thr_A_Rst_CoolantSupplyPressureSpare_H": 1046,
    "Thr_W_CoolantReturnPressure_H": 1048,
    "Thr_W_Rst_CoolantReturnPressure_H": 1050,
    "Thr_A_CoolantReturnPressure_H": 1052,
    "Thr_A_Rst_CoolantReturnPressure_H": 1054,
    "Thr_W_CoolantReturnPressureSpare_H": 1056,
    "Thr_W_Rst_CoolantReturnPressureSpare_H": 1058,
    "Thr_A_CoolantReturnPressureSpare_H": 1060,
    "Thr_A_Rst_CoolantReturnPressureSpare_H": 1062,
    "Thr_W_FilterInletPressure_L": 1064,
    "Thr_W_Rst_FilterInletPressure_L": 1066,
    "Thr_A_FilterInletPressure_L": 1068,
    "Thr_A_Rst_FilterInletPressure_L": 1070,
    "Thr_W_FilterInletPressure_H": 1072,
    "Thr_W_Rst_FilterInletPressure_H": 1074,
    "Thr_A_FilterInletPressure_H": 1076,
    "Thr_A_Rst_FilterInletPressure_H": 1076,
    "Thr_W_FilterOutletPressure_H": 1080,
    "Thr_W_Rst_FilterOutletPressure_H": 1082,
    "Thr_A_FilterOutletPressure_H": 1084,
    "Thr_A_Rst_FilterOutletPressure_H": 1086,
    "Thr_W_CoolantFlowRate_L": 1088,
    "Thr_W_Rst_CoolantFlowRate_L": 1090,
    "Thr_A_CoolantFlowRate_L": 1092,
    "Thr_A_Rst_CoolantFlowRate_L": 1094,
    "Thr_W_AmbientTemp_L": 1096,
    "Thr_W_Rst_AmbientTemp_L": 1098,
    "Thr_A_AmbientTemp_L": 1100,
    "Thr_A_Rst_AmbientTemp_L": 1102,
    "Thr_W_AmbientTemp_H": 1104,
    "Thr_W_Rst_AmbientTemp_H": 1106,
    "Thr_A_AmbientTemp_H": 1108,
    "Thr_A_Rst_AmbientTemp_H": 1110,
    "Thr_W_RelativeHumid_L": 1112,
    "Thr_W_Rst_RelativeHumid_L": 1114,
    "Thr_A_RelativeHumid_L": 1116,
    "Thr_A_Rst_RelativeHumid_L": 1118,
    "Thr_W_RelativeHumid_H": 1120,
    "Thr_W_Rst_RelativeHumid_H": 1122,
    "Thr_A_RelativeHumid_H": 1124,
    "Thr_A_Rst_RelativeHumid_H": 1126,
    "Thr_W_DewPoint_L": 1128,
    "Thr_W_Rst_DewPoint_L": 1130,
    "Thr_A_DewPoint_L": 1132,
    "Thr_A_Rst_DewPoint_L": 1134,
    "Thr_W_pH_L": 1136,
    "Thr_W_Rst_pH_L": 1138,
    "Thr_A_pH_L": 1140,
    "Thr_A_Rst_pH_L": 1142,
    "Thr_W_pH_H": 1144,
    "Thr_W_Rst_pH_H": 1146,
    "Thr_A_pH_H": 1148,
    "Thr_A_Rst_pH_H": 1150,
    "Thr_W_Conductivity_L": 1152,
    "Thr_W_Rst_Conductivity_L": 1154,
    "Thr_A_Conductivity_L": 1156,
    "Thr_A_Rst_Conductivity_L": 1158,
    "Thr_W_Conductivity_H": 1160,
    "Thr_W_Rst_Conductivity_H": 1162,
    "Thr_A_Conductivity_H": 1164,
    "Thr_A_Rst_Conductivity_H": 1166,
    "Thr_W_Turbidity_L": 1168,
    "Thr_W_Rst_Turbidity_L": 1170,
    "Thr_A_Turbidity_L": 1172,
    "Thr_A_Rst_Turbidity_L": 1174,
    "Thr_W_Turbidity_H": 1176,
    "Thr_W_Rst_Turbidity_H": 1178,
    "Thr_A_Turbidity_H": 1180,
    "Thr_A_Rst_Turbidity_H": 1182,
    "Thr_W_AverageCurrent_H": 1184,
    "Thr_W_Rst_AverageCurrent_H": 1186,
    "Thr_A_AverageCurrent_H": 1188,
    "Thr_A_Rst_AverageCurrent_H": 1190,
}

sensor_thrshd = {
    "Thr_W_CoolantSupplyTemperature_H": 0,
    "Thr_W_Rst_CoolantSupplyTemperature_H": 0,
    "Thr_A_CoolantSupplyTemperature_H": 0,
    "Thr_A_Rst_CoolantSupplyTemperature_H": 0,
    "Thr_W_CoolantSupplyTemperatureSpare_H": 0,
    "Thr_W_Rst_CoolantSupplyTemperatureSpare_H": 0,
    "Thr_A_CoolantSupplyTemperatureSpare_H": 0,
    "Thr_A_Rst_CoolantSupplyTemperatureSpare_H": 0,
    "Thr_W_CoolantReturnTemperature_H": 0,
    "Thr_W_Rst_CoolantReturnTemperature_H": 0,
    "Thr_A_CoolantReturnTemperature_H": 0,
    "Thr_A_Rst_CoolantReturnTemperature_H": 0,
    "Thr_W_CoolantReturnTemperatureSpare_H": 0,
    "Thr_W_Rst_CoolantReturnTemperatureSpare_H": 0,
    "Thr_A_CoolantReturnTemperatureSpare_H": 0,
    "Thr_A_Rst_CoolantReturnTemperatureSpare_H": 0,
    "Thr_W_CoolantSupplyPressure_H": 0,
    "Thr_W_Rst_CoolantSupplyPressure_H": 0,
    "Thr_A_CoolantSupplyPressure_H": 0,
    "Thr_A_Rst_CoolantSupplyPressure_H": 0,
    "Thr_W_CoolantSupplyPressureSpare_H": 0,
    "Thr_W_Rst_CoolantSupplyPressureSpare_H": 0,
    "Thr_A_CoolantSupplyPressureSpare_H": 0,
    "Thr_A_Rst_CoolantSupplyPressureSpare_H": 0,
    "Thr_W_CoolantReturnPressure_H": 0,
    "Thr_W_Rst_CoolantReturnPressure_H": 0,
    "Thr_A_CoolantReturnPressure_H": 0,
    "Thr_A_Rst_CoolantReturnPressure_H": 0,
    "Thr_W_CoolantReturnPressureSpare_H": 0,
    "Thr_W_Rst_CoolantReturnPressureSpare_H": 0,
    "Thr_A_CoolantReturnPressureSpare_H": 0,
    "Thr_A_Rst_CoolantReturnPressureSpare_H": 0,
    "Thr_W_FilterInletPressure_L": 0,
    "Thr_W_Rst_FilterInletPressure_L": 0,
    "Thr_A_FilterInletPressure_L": 0,
    "Thr_A_Rst_FilterInletPressure_L": 0,
    "Thr_W_FilterInletPressure_H": 0,
    "Thr_W_Rst_FilterInletPressure_H": 0,
    "Thr_A_FilterInletPressure_H": 0,
    "Thr_A_Rst_FilterInletPressure_H": 0,
    "Thr_W_FilterOutletPressure_H": 0,
    "Thr_W_Rst_FilterOutletPressure_H": 0,
    "Thr_A_FilterOutletPressure_H": 0,
    "Thr_A_Rst_FilterOutletPressure_H": 0,
    "Thr_W_CoolantFlowRate_L": 0,
    "Thr_W_Rst_CoolantFlowRate_L": 0,
    "Thr_A_CoolantFlowRate_L": 0,
    "Thr_A_Rst_CoolantFlowRate_L": 0,
    "Thr_W_AmbientTemp_L": 0,
    "Thr_W_Rst_AmbientTemp_L": 0,
    "Thr_A_AmbientTemp_L": 0,
    "Thr_A_Rst_AmbientTemp_L": 0,
    "Thr_W_AmbientTemp_H": 0,
    "Thr_W_Rst_AmbientTemp_H": 0,
    "Thr_A_AmbientTemp_H": 0,
    "Thr_A_Rst_AmbientTemp_H": 0,
    "Thr_W_RelativeHumid_L": 0,
    "Thr_W_Rst_RelativeHumid_L": 0,
    "Thr_A_RelativeHumid_L": 0,
    "Thr_A_Rst_RelativeHumid_L": 0,
    "Thr_W_RelativeHumid_H": 0,
    "Thr_W_Rst_RelativeHumid_H": 0,
    "Thr_A_RelativeHumid_H": 0,
    "Thr_A_Rst_RelativeHumid_H": 0,
    "Thr_W_DewPoint_L": 0,
    "Thr_W_Rst_DewPoint_L": 0,
    "Thr_A_DewPoint_L": 0,
    "Thr_A_Rst_DewPoint_L": 0,
    "Thr_W_pH_L": 0,
    "Thr_W_Rst_pH_L": 0,
    "Thr_A_pH_L": 0,
    "Thr_A_Rst_pH_L": 0,
    "Thr_W_pH_H": 0,
    "Thr_W_Rst_pH_H": 0,
    "Thr_A_pH_H": 0,
    "Thr_A_Rst_pH_H": 0,
    "Thr_W_Conductivity_L": 0,
    "Thr_W_Rst_Conductivity_L": 0,
    "Thr_A_Conductivity_L": 0,
    "Thr_A_Rst_Conductivity_L": 0,
    "Thr_W_Conductivity_H": 0,
    "Thr_W_Rst_Conductivity_H": 0,
    "Thr_A_Conductivity_H": 0,
    "Thr_A_Rst_Conductivity_H": 0,
    "Thr_W_Turbidity_L": 0,
    "Thr_W_Rst_Turbidity_L": 0,
    "Thr_A_Turbidity_L": 0,
    "Thr_A_Rst_Turbidity_L": 0,
    "Thr_W_Turbidity_H": 0,
    "Thr_W_Rst_Turbidity_H": 0,
    "Thr_A_Turbidity_H": 0,
    "Thr_A_Rst_Turbidity_H": 0,
    "Thr_W_AverageCurrent_H": 0,
    "Thr_W_Rst_AverageCurrent_H": 0,
    "Thr_A_AverageCurrent_H": 0,
    "Thr_A_Rst_AverageCurrent_H": 0,
}

device_delay = {
    "Delay_Inv1Overload": 0,
    "Delay_Inv2Overload": 0,
    "Delay_Inv3Overload": 0,
    "Delay_FanOverload1": 0,
    "Delay_FanOverload2": 0,
    "Delay_Inv1Error": 0,
    "Delay_Inv2Error": 0,
    "Delay_Inv3Error": 0,
    "Delay_ATS": 0,
    "Delay_Inv1SpeedComm": 0,
    "Delay_Inv2SpeedComm": 0,
    "Delay_Inv3SpeedComm": 0,
    "Delay_CoolantFlowRateComm": 0,
    "Delay_AmbientTempComm": 0,
    "Delay_RelativeHumidComm": 0,
    "Delay_DewPointComm": 0,
    "Delay_ConductivityComm": 0,
    "Delay_pHComm": 0,
    "Delay_TurbidityComm": 0,
    "Delay_ATS1Comm": 0,
    "Delay_ATS2Comm": 0,
    "Delay_InstantPowerConsumptionComm": 0,
    "Delay_AverageCurrentComm": 0,
    "Delay_Fan1Comm": False,
    "Delay_Fan2Comm": False,
    "Delay_Fan3Comm": False,
    "Delay_Fan4Comm": False,
    "Delay_Fan5Comm": False,
    "Delay_Fan6Comm": False,
    "Delay_Fan7Comm": False,
    "Delay_Fan8Comm": False,
    "Delay_CoolantSupplyTemperatureBroken": 0,
    "Delay_CoolantSupplyTemperatureSpareBroken": 0,
    "Delay_CoolantReturnTemperatureBroken": 0,
    "Delay_CoolantReturnTemperatureSpareBroken": 0,
    "Delay_CoolantSupplyPressureBroken": 0,
    "Delay_CoolantSupplyPressureSpareBroken": 0,
    "Delay_CoolantReturnPressureBroken": 0,
    "Delay_CoolantReturnPressureSpareBroken": 0,
    "Delay_FilterInletPressureBroken": 0,
    "Delay_FilterOutletPressureBroken": 0,
    "Delay_CoolantFlowRateBroken": 0,
    "Delay_Leakage1Leak": False,
    "Delay_Leakage1Broken": False,
    "Delay_Level1": False,
    "Delay_Level2": False,
    "Delay_Level3": False,
    "Delay_Power24v1": False,
    "Delay_Power24v2": False,
    "Delay_Power12v1": False,
    "Delay_Power12v2": False,
    "Delay_MainMcError": False,
    "Delay_Fan1Error": False,
    "Delay_Fan2Error": False,
    "Delay_Fan3Error": False,
    "Delay_Fan4Error": False,
    "Delay_Fan5Error": False,
    "Delay_Fan6Error": False,
    "Delay_Fan7Error": False,
    "Delay_Fan8Error": False,
    "Delay_RackError": False,
    "Delay_RackLeakageSensor1Leak": False,
    "Delay_RackLeakageSensor1Broken": False,
    "Delay_RackLeakageSensor2Leak": False,
    "Delay_RackLeakageSensor2Broken": False,
}

sensor_delay = {
    "Delay_CoolantSupplyTemperature": 0,
    "Delay_CoolantSupplyTemperatureSpare": 0,
    "Delay_CoolantReturnTemperature": 0,
    "Delay_CoolantReturnTemperatureSpare": 0,
    "Delay_CoolantSupplyPressure": 0,
    "Delay_CoolantSupplyPressureSpare": 0,
    "Delay_CoolantReturnPressure": 0,
    "Delay_CoolantReturnPressureSpare": 0,
    "Delay_FilterInletPressure": 0,
    "Delay_FilterOutletPressure": 0,
    "Delay_CoolantFlowRate": 0,
    "Delay_AmbientTemp": 0,
    "Delay_RelativeHumid": 0,
    "Delay_DewPoint": 0,
    "Delay_pH": 0,
    "Delay_Conductivity": 0,
    "Delay_Turbidity": 0,
    "Delay_AverageCurrent": 0,
}

app_value_mapping = {
    "CoolantSupplyTemperature": "temp_clntSply",
    "CoolantSupplyTemperatureSpare": "temp_clntSplySpare",
    "CoolantReturnTemperature": "temp_clntRtn",
    "CoolantReturnTemperatureSpare": "temp_clntRtnSpare",
    "CoolantSupplyPressure": "prsr_clntSply",
    "CoolantSupplyPressureSpare": "prsr_clntSplySpare",
    "CoolantReturnPressure": "prsr_clntRtn",
    "CoolantReturnPressureSpare": "prsr_clntRtnSpare",
    "FilterInletPressure": "prsr_fltIn",
    "FilterOutletPressure": "prsr_fltOut",
    "CoolantFlowRate": "clnt_flow",
    "AmbientTemp": "ambient_temp",
    "RelativeHumid": "relative_humid",
    "DewPoint": "dew_point",
    "pH": "pH",
    "Conductivity": "cdct",
    "Turbidity": "tbd",
}

app_error_mapping = {
    "CoolantSupplyTemperature": "TempClntSply_broken",
    "CoolantSupplyTemperatureSpare": "TempClntSplySpare_broken",
    "CoolantReturnTemperature": "TempClntRtn_broken",
    "CoolantReturnTemperatureSpare": "TempClntRtnSpare_broken",
    "CoolantSupplyPressure": "PrsrClntSply_broken",
    "CoolantSupplyPressureSpare": "PrsrClntSplySpare_broken",
    "CoolantReturnPressure": "PrsrClntRtn_broken",
    "CoolantReturnPressureSpare": "PrsrClntRtnSpare_broken",
    "FilterInletPressure": "PrsrFltIn_broken",
    "FilterOutletPressure": "PrsrFltOut_broken",
    "CoolantFlowRate": "Clnt_Flow_broken",
    "AmbientTemp": "Ambient_Temp_Com",
    "RelativeHumid": "Relative_Humid_Com",
    "DewPoint": "Dew_Point_Com",
    "pH": "pH_Com",
    "Conductivity": "Cdct_Sensor_Com",
    "Turbidity": "Tbd_Com",
}

app_errorr_mapping_for_status = {
    "CoolantSupplyTemperature": "TempClntSply_broken",
    "CoolantSupplyTemperatureSpare": "TempClntSplySpare_broken",
    "CoolantReturnTemperature": "TempClntRtn_broken",
    "CoolantReturnTemperatureSpare": "TempClntRtnSpare_broken",
    "CoolantSupplyPressure": "PrsrClntSply_broken",
    "CoolantSupplyPressureSpare": "PrsrClntSplySpare_broken",
    "CoolantReturnPressure": "PrsrClntRtn_broken",
    "CoolantReturnPressureSpare": "PrsrClntRtnSpare_broken",
    "FilterInletPressure": "PrsrFltIn_broken",
    "FilterOutletPressure": "PrsrFltOut_broken",
    "CoolantFlowRate": "Clnt_Flow_broken",
    "AmbientTemp": "Ambient_Temp_Com",
    "RelativeHumid": "Relative_Humid_Com",
    "DewPoint": "Dew_Point_Com",
    "pH": "pH_Com",
    "Conductivity": "Cdct_Sensor_Com",
    "Turbidity": "Tbd_Com",
    "Inv1": "Inv1_Com",
    "Inv2": "Inv2_Com",
    "Inv3": "Inv3_Com",
    "Fan1": "Fan1_Com",
    "Fan2": "Fan2_Com",
    "Fan3": "Fan3_Com",
    "Fan4": "Fan4_Com",
    "Fan5": "Fan5_Com",
    "Fan6": "Fan6_Com",
    "Fan7": "Fan7_Com",
    "Fan8": "Fan8_Com"
}


messages = {
    "warning": {
        "M100": ["Coolant Supply Temperature Over Range (High) Warning (T1)", False],
        "M101": [
            "Coolant Supply Temperature Spare Over Range (High) Warning (T1sp)",
            False,
        ],
        "M102": ["Coolant Return Temperature Over Range (High) Warning (T2)", False],
        "M103": [
            "Coolant Return Temperature Over Range Spare (High) Warning (T2sp)",
            False,
        ],
        "M104": ["Coolant Supply Pressure Over Range (High) Warning (P1)", False],
        "M105": [
            "Coolant Supply Pressure Spare Over Range (High) Warning (P1sp)",
            False,
        ],
        "M106": ["Coolant Return Pressure Over Range (High) Warning (P2)", False],
        "M107": [
            "Coolant Return Pressure Spare Over Range (High) Warning (P2sp)",
            False,
        ],
        "M108": ["Filter Inlet Pressure Over Range (Low) Warning (P3)", False],
        "M109": ["Filter Inlet Pressure Over Range (High) Warning (P3)", False],
        "M110": ["Filter Delta P Over Range (High) Warning (P3 - P4)", False],
        "M111": ["Coolant Flow Rate (Low) Warning (F1)", False],
        "M112": ["Ambient Temperature Over Range (Low) Warning (T a)", False],
        "M113": ["Ambient Temperature Over Range (High) Warning (T a)", False],
        "M114": ["Relative Humidity Over Range (Low) Warning (RH)", False],
        "M115": ["Relative Humidity Over Range (High) Warning (RH)", False],
        "M116": ["Condensation Warning (T Dp)", False],
        "M117": ["pH Over Range (Low) Warning (PH)", False],
        "M118": ["pH Over Range (High) Warning (PH)", False],
        "M119": ["Conductivity Over Range (Low) Warning (CON)", False],
        "M120": ["Conductivity Over Range (High) Warning (CON)", False],
        "M121": ["Turbidity Over Range (Low) Warning (Tur)", False],
        "M122": ["Turbidity Over Range (High) Warning (Tur)", False],
        "M123": ["Average Current Over Range (High) Warning", False],
    },
    "alert": {
        "M200": ["Coolant Supply Temperature Over Range (High) Alert (T1)", False],
        "M201": [
            "Coolant Supply Temperature Spare Over Range (High) Alert (T1sp)",
            False,
        ],
        "M202": ["Coolant Return Temperature Over Range (High) Alert (T2)", False],
        "M203": [
            "Coolant Return Temperature Over Range Spare (High) Alert (T2sp)",
            False,
        ],
        "M204": ["Coolant Supply Pressure Over Range (High) Alert (P1)", False],
        "M205": ["Coolant Supply Pressure Spare Over Range (High) Alert (P1sp)", False],
        "M206": ["Coolant Return Pressure Over Range (High) Alert (P2)", False],
        "M207": ["Coolant Return Pressure Spare Over Range (High) Alert (P2sp)", False],
        "M208": ["Filter Inlet Pressure Over Range (Low) Alert (P3)", False],
        "M209": ["Filter Inlet Pressure Over Range (High) Alert (P3)", False],
        "M210": ["Filter Delta P Over Range (High) Alert (P3 - P4)", False],
        "M211": ["Coolant Flow Rate (Low) Alert (F1)", False],
        "M212": ["Ambient Temperature Over Range (Low) Alert (T a)", False],
        "M213": ["Ambient Temperature Over Range (High) Alert (T a)", False],
        "M214": ["Relative Humidity Over Range (Low) Alert (RH)", False],
        "M215": ["Relative Humidity Over Range (High) Alert (RH)", False],
        "M216": ["Condensation Alert (T Dp)", False],
        "M217": ["pH Over Range (Low) Alert (PH)", False],
        "M218": ["pH Over Range (High) Alert (PH)", False],
        "M219": ["Conductivity Over Range (Low) Alert (CON)", False],
        "M220": ["Conductivity Over Range (High) Alert (CON)", False],
        "M221": ["Turbidity Over Range (Low) Alert (Tur)", False],
        "M222": ["Turbidity Over Range (High) Alert (Tur)", False],
        "M223": ["Average Current Over Range (High) Alert", False],
    },
    "error": {
        "M300": ["Coolant Pump1 Inverter Overload", False],
        "M301": ["Coolant Pump2 Inverter Overload", False],
        "M302": ["Coolant Pump3 Inverter Overload", False],
        "M303": ["Fan1 Group1 Overload", False],
        "M304": ["Fan2 Group2 Overload", False],
        "M305": ["Coolant Pump1 Inverter Error", False],
        "M306": ["Coolant Pump2 Inverter Error", False],
        "M307": ["Coolant Pump3 Inverter Error", False],
        "M308": ["Primary Power Broken", False],
        "M309": ["Inverter1 Communication Error", False],
        "M310": ["Inverter2 Communication Error", False],
        "M311": ["Inverter3 Communication Error", False],
        "M312": ["Coolant Flow (F1) Meter Communication Error", False],
        "M313": ["Ambient Sensor (Ta, RH, TDp) Communication Error", False],
        "M314": ["Relative Humidity (RH) Communication Error", False],
        "M315": ["Dew Point Temperature (TDp) Communication Error", False],
        "M316": ["pH (PH) Sensor Communication Error", False],
        "M317": ["Conductivity (CON) Sensor Communication Error", False],
        "M318": ["Turbidity (Tur) Sensor Communication Error", False],
        "M319": ["ATS Communication Error", False],
        "M320": ["ATS 2 Communication Error", False],
        "M321": ["Power Meter Communication Error", False],
        "M322": ["Average Current Communication Error", False],
        "M323": ["Fan 1 Communication Error", False],
        "M324": ["Fan 2 Communication Error", False],
        "M325": ["Fan 3 Communication Error", False],
        "M326": ["Fan 4 Communication Error", False],
        "M327": ["Fan 5 Communication Error", False],
        "M328": ["Fan 6 Communication Error", False],
        "M329": ["Fan 7 Communication Error", False],
        "M330": ["Fan 8 Communication Error", False],
        "M331": ["Coolant Supply Temperature (T1) Broken Error", False],
        "M332": ["Coolant Supply Temperature Spare (T1sp) Broken Error", False],
        "M333": ["Coolant Return Temperature (T2) Broken Error", False],
        "M334": ["Coolant Return Temperature Spare (T2sp) Broken Error", False],
        "M335": ["Coolant Supply Pressure (P1) Broken Error", False],
        "M336": ["Coolant Supply Pressure Spare (P1sp) Broken Error", False],
        "M337": ["Coolant Return Pressure (P2) Broken Error", False],
        "M338": ["Coolant Return Pressure Spare (P2sp) Broken Error", False],
        "M339": ["Filter Inlet Pressure (P3) Broken Error", False],
        "M340": ["Filter Outlet Pressure (P4) Broken Error", False],
        "M341": ["Coolant Flow Rate (F1) Broken Error", False],
        "M342": ["PC1 Error", False],
        "M343": ["PC2 Error", False],
        "M344": ["Leakage 1 Leak Error", False],
        "M345": ["Leakage 1 Broken Error", False],
        "M346": ["Coolant Level 1 Error", False],
        "M347": ["Coolant Level 2 Error", False],
        "M348": ["Coolant Level 3 Error", False],
        "M349": ["24V Power Supply 1 Error", False],
        "M350": ["24V Power Supply 2 Error", False],
        "M351": ["12V Power Supply 1 Error", False],
        "M352": ["12V Power Supply 2 Error", False],
        "M353": ["Main MC Status Error", False],
        "M354": ["FAN 1 Alarm Status Error", False],
        "M355": ["FAN 2 Alarm Status Error", False],
        "M356": ["FAN 3 Alarm Status Error", False],
        "M357": ["FAN 4 Alarm Status Error", False],
        "M358": ["FAN 5 Alarm Status Error", False],
        "M359": ["FAN 6 Alarm Status Error", False],
        "M360": ["FAN 7 Alarm Status Error", False],
        "M361": ["FAN 8 Alarm Status Error", False],
        "M362": ["Stop Due to Low Coolant Level", False],
        "M363": ["PLC Communication Broken Error", False],
    },
    "rack": {
        "M400": ["Rack1 broken", False],
        "M401": ["Rack2 broken", False],
        "M402": ["Rack3 broken", False],
        "M403": ["Rack4 broken", False],
        "M404": ["Rack5 broken", False],
        "M405": ["Rack1 Leakage Communication Error", False],
        "M406": ["Rack2 Leakage Communication Error", False],
        "M407": ["Rack3 Leakage Communication Error", False],
        "M408": ["Rack4 Leakage Communication Error", False],
        "M409": ["Rack5 Leakage Communication Error", False],
        "M410": ["Rack1 leakage", False],
        "M411": ["Rack2 leakage", False],
        "M412": ["Rack3 leakage", False],
        "M413": ["Rack4 leakage", False],
        "M414": ["Rack5 leakage", False],
        "M415": ["Rack1 Status Communication Error", False],
        "M416": ["Rack2 Status Communication Error", False],
        "M417": ["Rack3 Status Communication Error", False],
        "M418": ["Rack4 Status Communication Error", False],
        "M419": ["Rack5 Status Communication Error", False],
        "M420": ["Rack1 error", False],
        "M421": ["Rack2 error", False],
        "M422": ["Rack3 error", False],
        "M423": ["Rack4 error", False],
        "M424": ["Rack5 error", False],
        "M425": ["Rack6 error", False],
        "M426": ["Rack7 error", False],
        "M427": ["Rack8 error", False],
        "M428": ["Rack9 error", False],
        "M429": ["Rack10 error", False],
        "M430": ["Rack Leakage Sensor 1 Leak", False],
        "M431": ["Rack Leakage Sensor 1 Broken", False],
        "M432": ["Rack Leakage Sensor 2 Leak", False],
        "M433": ["Rack Leakage Sensor 2 Broken", False],
    },
}

devices = {
    "Inv1Overload": {
        "Name": "Inv1Overload",
        "DisplayName": "Inverter 1 Overload",
        "Status": "Disable",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Inv2Overload": {
        "Name": "Inv2Overload",
        "DisplayName": "Inverter 2 Overload",
        "Status": "Disable",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Inv3Overload": {
        "Name": "Inv3Overload",
        "DisplayName": "Inverter 3 Overload",
        "Status": "Disable",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "FanOverload1": {
        "Name": "FanOverload1",
        "DisplayName": "Fan 1 Overload",
        "Status": "Disable",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "FanOverload2": {
        "Name": "FanOverload2",
        "DisplayName": "Fan 2 Overload",
        "Status": "Disable",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Inv1Error": {
        "Name": "Inv1Error",
        "DisplayName": "Inverter 1 Error",
        "Status": "Enable",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Inv2Error": {
        "Name": "Inv2Error",
        "DisplayName": "Inverter 2 Error",
        "Status": "Disable",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Inv3Error": {
        "Name": "Inv3Error",
        "DisplayName": "Inverter 3 Error",
        "Status": "Disable",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "ATS": {
        "Name": "ATS",
        "DisplayName": "ATS",
        "Status": "Primary",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Inv1SpeedComm": {
        "Name": "Inv1SpeedCom",
        "DisplayName": "Inverter 1",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Inv2SpeedComm": {
        "Name": "Inv2SpeedComm",
        "DisplayName": "Inverter 2",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Inv3SpeedComm": {
        "Name": "Inv3SpeedComm",
        "DisplayName": "Inverter 3",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantFlowRateComm": {
        "Name": "CoolantFlowRateComm",
        "DisplayName": "Coolant Flow Meter",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "AmbientTempComm": {
        "Name": "AmbientTempComm",
        "DisplayName": "Ambient Temperature (Ta)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "RelativeHumidComm": {
        "Name": "RelativeHumidComm",
        "DisplayName": "Relative Humidity (RH)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "DewPointComm": {
        "Name": "DewPointComm",
        "DisplayName": "Dew Point Temperature (TDp)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "pHComm": {
        "Name": "pHComm",
        "DisplayName": "pH Sensor",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "ConductivityComm": {
        "Name": "ConductivityComm",
        "DisplayName": "Conductivity Sensor",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "TurbidityComm": {
        "Name": "TurbidityComm",
        "DisplayName": "Turbidity Sensor",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "ATS1Comm": {
        "Name": "ATS1Comm",
        "DisplayName": "ATS 1 Communication",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "ATS2Comm": {
        "Name": "ATS2Comm",
        "DisplayName": "ATS 2 Communication",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "InstantPowerConsumptionComm": {
        "Name": "InstantPowerConsumptionComm",
        "DisplayName": "Power Meter",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "AverageCurrentComm": {
        "Name": "AverageCurrentComm",
        "DisplayName": "Average Current",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan1Comm": {
        "Name": "Fan1Comm",
        "DisplayName": "Fan Speed 1",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan2Comm": {
        "Name": "Fan2Comm",
        "DisplayName": "Fan Speed 2",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan3Comm": {
        "Name": "Fan3Comm",
        "DisplayName": "Fan Speed 3",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan4Comm": {
        "Name": "Fan4Comm",
        "DisplayName": "Fan Speed 4",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan5Comm": {
        "Name": "Fan5Comm",
        "DisplayName": "Fan Speed 5",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan6Comm": {
        "Name": "Fan6Comm",
        "DisplayName": "Fan Speed 6",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan7Comm": {
        "Name": "Fan7Comm",
        "DisplayName": "Fan Speed 7",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan8Comm": {
        "Name": "Fan8Comm",
        "DisplayName": "Fan Speed 8",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantSupplyTemperatureBroken": {
        "Name": "CoolantSupplyTemperatureBroken",
        "DisplayName": "Coolant Supply Temperature (T1)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantSupplyTemperatureSpareBroken": {
        "Name": "CoolantSupplyTemperatureSpareBroken",
        "DisplayName": "Coolant Supply Temperature Spare (T1sp)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantReturnTemperatureBroken": {
        "Name": "CoolantReturnTemperatureBroken",
        "DisplayName": "Coolant Return Temperature (T2)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantReturnTemperatureSpareBroken": {
        "Name": "CoolantReturnTemperatureSpareBroken",
        "DisplayName": "Coolant Return Temperature Spare (T2sp)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantSupplyPressureBroken": {
        "Name": "CoolantSupplyPressureBroken",
        "DisplayName": "Coolant Supply Pressure (P1)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantSupplyPressureSpareBroken": {
        "Name": "CoolantSupplyPressureSpareBroken",
        "DisplayName": "Coolant Supply Pressure Spare (P1sp)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantReturnPressureBroken": {
        "Name": "CoolantReturnPressureBroken",
        "DisplayName": "Coolant Return Pressure (P2)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantReturnPressureSpareBroken": {
        "Name": "CoolantReturnPressureSpareBroken",
        "DisplayName": "Coolant Return Pressure Spare (P2sp)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "FilterInletPressureBroken": {
        "Name": "FilterInletPressureBroken",
        "DisplayName": "Filter Inlet Pressure (P3)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "FilterOutletPressureBroken": {
        "Name": "FilterOutletPressureBroken",
        "DisplayName": "Filter Outlet Pressure (P4)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "CoolantFlowRateBroken": {
        "Name": "CoolantFlowRateBroken",
        "DisplayName": "Coolant Flow Rate (F1)",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Leakage1Leak": {
        "Name": "Leakage1Leak",
        "DisplayName": "Leakage 1 Leak",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Leakage1Broken": {
        "Name": "Leakage1Broken",
        "DisplayName": "Leakage 1 Broken",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Level1": {
        "Name": "Level1",
        "DisplayName": "Coolant Level 1",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Level2": {
        "Name": "Level2",
        "DisplayName": "Coolant Level 2",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Level3": {
        "Name": "Level3",
        "DisplayName": "Coolant Level 3",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Power24v1": {
        "Name": "Power24v1",
        "DisplayName": "24V Power Supply 1",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Power24v2": {
        "Name": "Power24v2",
        "DisplayName": "24V Power Supply 2",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Power12v1": {
        "Name": "Power12v1",
        "DisplayName": "12V Power Supply 1",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Power12v2": {
        "Name": "Power12v2",
        "DisplayName": "12V Power Supply 2",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "MainMcError": {
        "Name": "MainMcError",
        "DisplayName": "Main MC Status",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan1Error": {
        "Name": "Fan1Error",
        "DisplayName": "FAN 1 Alarm Status",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan2Error": {
        "Name": "Fan2Error",
        "DisplayName": "FAN 2 Alarm Status",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan3Error": {
        "Name": "Fan3Error",
        "DisplayName": "FAN 3 Alarm Status",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan4Error": {
        "Name": "Fan4Error",
        "DisplayName": "FAN 4 Alarm Status",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan5Error": {
        "Name": "Fan5Error",
        "DisplayName": "FAN 5 Alarm Status",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan6Error": {
        "Name": "Fan6Error",
        "DisplayName": "FAN 6 Alarm Status",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan7Error": {
        "Name": "Fan7Error",
        "DisplayName": "FAN 7 Alarm Status",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "Fan8Error": {
        "Name": "Fan8Error",
        "DisplayName": "FAN 8 Alarm Status",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "RackError": {
        "Name": "RackError",
        "DisplayName": "Rack",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "LowCoolantLevelWarning": {
        "Name": "LowCoolantLevelWarning",
        "DisplayName": "Low Coolant Level Warning",
        "Status": "Good",
        "TrapEnabled": True,
    },
    "PC1Error": {
        "Name": "PC1Error",
        "DisplayName": "PC 1 Error",
        "Status": "Good",
        "TrapEnabled": True,
    },
    "PC2Error": {
        "Name": "PC2Error",
        "DisplayName": "PC 2 Error",
        "Status": "Good",
        "TrapEnabled": True,
    },
    "ControlUnit": {
        "Name": "ControlUnit",
        "DisplayName": "PLC",
        "Status": "Good",
        "TrapEnabled": True,
    },
    "RackLeakageSensor1Leak": {
        "Name": "RackLeakageSensor1Leak",
        "DisplayName": "Rack Leakage Sensor 1 Leak",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "RackLeakageSensor1Broken": {
        "Name": "RackLeakageSensor1Broken",
        "DisplayName": "Rack Leakage Sensor 1 Broken",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "RackLeakageSensor2Leak": {
        "Name": "RackLeakageSensor2Leak",
        "DisplayName": "Rack Leakage Sensor 2 Leak",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
    "RackLeakageSensor2Broken": {
        "Name": "RackLeakageSensor2Broken",
        "DisplayName": "Rack Leakage Sensor 2 Broken",
        "Status": "Good",
        "TrapEnabled": True,
        "DelayTime": 0,
    },
}

physical_asset = {
    "Name":"cdu",
    "FirmwareVersion": "0100",
    "Version": "N/A",
    # "ProductionDate": "20250430",
    "Manufacturer": "Supermicro",
    "Model": "150kw",
    "SerialNumber": "N/A",
    "PartNumber": "N/A",
    # "AssetTag": "N/A",
    # "CDUStatus": "Good",
    "OperationMode": "Auto flow control",
    
    # "LEDLight": "ON",
    "CDUStatus": "OK"

}

snmp_data = {
    "trap_ip_address": "192.168.3.210",
    "v3_switch": False,
    "read_community": "Public",
}

inv = {
    "inv1": False,
    "inv2": False,
    "inv3": False,
}

trap_mapping = {
    "W_CoolantSupplyTemperature": 8192 + 2000,
    "A_CoolantSupplyTemperature": 8192 + 2001,
    "W_CoolantSupplyTemperatureSpare": 8192 + 2002,
    "A_CoolantSupplyTemperatureSpare": 8192 + 2003,
    "W_CoolantReturnTemperature": 8192 + 2004,
    "A_CoolantReturnTemperature": 8192 + 2005,
    "W_CoolantReturnTemperatureSpare": 8192 + 2006,
    "A_CoolantReturnTemperatureSpare": 8192 + 2007,
    "W_CoolantSupplyPressure": 8192 + 2008,
    "A_CoolantSupplyPressure": 8192 + 2009,
    "W_CoolantSupplyPressureSpare": 8192 + 2010,
    "A_CoolantSupplyPressureSpare": 8192 + 2011,
    "W_CoolantReturnPressure": 8192 + 2012,
    "A_CoolantReturnPressure": 8192 + 2013,
    "W_CoolantReturnPressureSpare": 8192 + 2014,
    "A_CoolantReturnPressureSpare": 8192 + 2015,
    "W_FilterInletPressure": 8192 + 2016,
    "A_FilterInletPressure": 8192 + 2017,
    "W_FilterOutletPressure": 8192 + 2018,
    "A_FilterOutletPressure": 8192 + 2019,
    "W_CoolantFlowRate": 8192 + 2020,
    "A_CoolantFlowRate": 8192 + 2021,
    "W_AmbientTemp": 8192 + 2022,
    "A_AmbientTemp": 8192 + 2023,
    "W_RelativeHumid": 8192 + 2024,
    "A_RelativeHumid": 8192 + 2025,
    "W_DewPoint": 8192 + 2026,
    "A_DewPoint": 8192 + 2027,
    "W_pH": 8192 + 2028,
    "A_pH": 8192 + 2029,
    "W_Conductivity": 8192 + 2030,
    "A_Conductivity": 8192 + 2031,
    "W_Turbidity": 8192 + 2032,
    "A_Turbidity": 8192 + 2033,
    "W_AverageCurrent": 8192 + 2034,
    "A_AverageCurrent": 8192 + 2035,
    "E_Inv1Overload": 8192 + 2036,
    "E_Inv2Overload": 8192 + 2037,
    "E_Inv3Overload": 8192 + 2038,
    "E_FanOverload1": 8192 + 2039,
    "E_FanOverload2": 8192 + 2040,
    "E_Inv1Error": 8192 + 2041,
    "E_Inv2Error": 8192 + 2042,
    "E_Inv3Error": 8192 + 2043,
    "E_ATS": 8192 + 2044,
    "E_Inv1SpeedComm": 8192 + 2045,
    "E_Inv2SpeedComm": 8192 + 2046,
    "E_Inv3SpeedComm": 8192 + 2047,
    "E_CoolantFlowRateComm": 8192 + 2048,
    "E_AmbientTempComm": 8192 + 2049,
    "E_RelativeHumidComm": 8192 + 2050,
    "E_DewPointComm": 8192 + 2051,
    "E_pHComm": 8192 + 2052,
    "E_ConductivityComm": 8192 + 2053,
    "E_TurbidityComm": 8192 + 2054,
    "E_ATS1Comm": 8192 + 2055,
    "E_ATS2Comm": 8192 + 2056,
    "E_InstantPowerConsumptionComm": 8192 + 2057,
    "E_AverageCurrentComm": 8192 + 2058,
    "E_Fan1Comm": 8192 + 2059,
    "E_Fan2Comm": 8192 + 2060,
    "E_Fan3Comm": 8192 + 2061,
    "E_Fan4Comm": 8192 + 2062,
    "E_Fan5Comm": 8192 + 2063,
    "E_Fan6Comm": 8192 + 2064,
    "E_Fan7Comm": 8192 + 2065,
    "E_Fan8Comm": 8192 + 2066,
    "E_CoolantSupplyTemperatureBroken": 8192 + 2067,
    "E_CoolantSupplyTemperatureSpareBroken": 8192 + 2068,
    "E_CoolantReturnTemperatureBroken": 8192 + 2069,
    "E_CoolantReturnTemperatureSpareBroken": 8192 + 2070,
    "E_CoolantSupplyPressureBroken": 8192 + 2071,
    "E_CoolantSupplyPressureSpareBroken": 8192 + 2072,
    "E_CoolantReturnPressureBroken": 8192 + 2073,
    "E_CoolantReturnPressureSpareBroken": 8192 + 2074,
    "E_FilterInletPressureBroken": 8192 + 2075,
    "E_FilterOutletPressureBroken": 8192 + 2076,
    "E_CoolantFlowRateBroken": 8192 + 2077,
    "E_Leakage1Leak": 8192 + 2078,
    "E_Leakage1Broken": 8192 + 2079,
    "E_Level1": 8192 + 2080,
    "E_Level2": 8192 + 2081,
    "E_Level3": 8192 + 2082,
    "E_Power24v1": 8192 + 2083,
    "E_Power24v2": 8192 + 2084,
    "E_Power12v1": 8192 + 2085,
    "E_Power12v2": 8192 + 2086,
    "E_MainMcError": 8192 + 2087,
    "E_Fan1Error": 8192 + 2088,
    "E_Fan2Error": 8192 + 2089,
    "E_Fan3Error": 8192 + 2090,
    "E_Fan4Error": 8192 + 2091,
    "E_Fan5Error": 8192 + 2092,
    "E_Fan6Error": 8192 + 2093,
    "E_Fan7Error": 8192 + 2094,
    "E_Fan8Error": 8192 + 2095,
    "E_RackError": 8192 + 2096,
    "E_LowCoolantLevelWarning": 8192 + 2097,
    "E_PC1Error": 8192 + 2098,
    "E_PC2Error": 8192 + 2099,
    "E_ControlUnit": 8192 + 2100,
    "E_RackLeakageSensor1Leak": 8192 + 2101,
    "E_RackLeakageSensor1Broken": 8192 + 2102,
    "E_RackLeakageSensor2Leak": 8192 + 2103,
    "E_RackLeakageSensor2Broken": 8192 + 2104,
}


error_message = {
    400: {"title": "Invalid content-type", "message": "Content type is not correct."},
    401: {"title": "Bad credential", "message": "Invalid username and password."},
    404: {"title": "Not Found", "message": "Specified URL doesn't exist."},
    405: {"title": "Invalid method", "message": "The method is not allowed."},
    503: {
        "title": "Server is busy",
        "message": "The communication between PC and PLC is temporarily broken.",
    },
}


def api_error_response(status_code):
    error_info = error_message.get(
        status_code, {"title": "Unknown Error", "message": "No details available."}
    )
    response = jsonify(
        {
            "error_code": status_code,
            "error_title": error_info["title"],
            "error_message": error_info["message"],
        }
    )
    response.status_code = status_code
    return response


def is_valid_ip(ip):
    """
    驗證是否為合法的 IPv4 地址
    :param ip: IP 地址字串
    :return: True 表示合法, False 表示不合法
    """
    pattern = re.compile(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$")
    if pattern.match(ip):
        parts = ip.split(".")
        return all(0 <= int(part) <= 255 for part in parts)
    return False


def check_auth(username, password):
    """檢查是否為有效的用戶名和密碼"""
    # return username == USERNAME and password == PASSWORD
    return username in USER_CREDENTIALS and password == USER_CREDENTIALS[username]


def authenticate():
    """請求身份驗證"""
    return Response(
        "Authentication required.",
        401,
        {"WWW-Authenticate": "Basic realm='Login Required'"},
    )


def requires_auth(f):
    """裝飾器，要求路由使用基本驗證"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)

    return decorated_function


def check_server_busy():
    """模擬伺服器忙碌的條件"""

    return False


@app.errorhandler(404)
def handle_404_error(e):
    return api_error_response(404)


@app.errorhandler(405)
def handle_405_error(e):
    return api_error_response(405)


def read_split_register(r, i):
    return (r[i + 1] << 16) | r[i]


def cvt_float_byte(value):
    float_as_bytes = struct.pack(">f", float(value))
    word1, word2 = struct.unpack(">HH", float_as_bytes)
    return word1, word2


def cvt_registers_to_float(reg1, reg2):
    temp1 = [reg1, reg2]
    decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
        temp1, byteorder=Endian.Big, wordorder=Endian.Little
    )
    decoded_value_big_endian = decoder_big_endian.decode_32bit_float()
    return decoded_value_big_endian


def input_ps(ps):
    try:
        with ModbusTcpClient(port=modbus_port, host=modbus_host) as client:
            word1, word2 = cvt_float_byte(float(ps))
            client.write_registers(246, [word2, word1])
    except Exception as e:
        print(f"ps error: {e}")


def set_p1(p1):
    try:
        with ModbusTcpClient(port=modbus_port, host=modbus_host) as client:
            client.write_coils((8192 + 820), [p1])
    except Exception as e:
        print(f"p1 error: {e}")


def set_p2(p2):
    try:
        with ModbusTcpClient(port=modbus_port, host=modbus_host) as client:
            client.write_coils((8192 + 821), [p2])
    except Exception as e:
        print(f"p2 error: {e}")


def set_p3(p3):
    try:
        with ModbusTcpClient(port=modbus_port, host=modbus_host) as client:
            client.write_coils((8192 + 822), [p3])
    except Exception as e:
        print(f"p3 error: {e}")


def input_fan(fan):
    try:
        with ModbusTcpClient(port=modbus_port, host=modbus_host) as client:
            word1, word2 = cvt_float_byte(float(fan))
            client.write_registers(470, [word2, word1])
    except Exception as e:
        print(f"fan error: {e}")


def set_fan(fan_list):
    start_reg = 8192 + 850

    for i, fan in enumerate(fan_list):
        if fan is not None:
            try:
                with ModbusTcpClient(port=modbus_port, host=modbus_host) as client:
                    client.write_coils(start_reg + i, [fan])
            except Exception as e:
                print(f"set fan error: {e}")


def read_data_from_json():
    global thrshd, ctr_data, measure_data, fw_info

    with open(f"{web_path}/json/thrshd.json", "r") as file:
        thrshd = json.load(file)

    with open(f"{web_path}/json/ctr_data.json", "r") as file:
        ctr_data = json.load(file)

    with open(f"{web_path}/json/measure_data.json", "r") as file:
        measure_data = json.load(file)
        
    with open(f"{web_path}/fw_info.json", "r") as file:
        fw_info = json.load(file)

def change_to_metric():
    read_data_from_json()

    for key in thrshd:
        if not key.endswith("_trap") and not key.startswith("Delay_"):
            if "Temp" in key:
                thrshd[key] = (thrshd[key] - 32) * 5.0 / 9.0

            if "DewPoint" in key:
                thrshd[key] = (thrshd[key]) * 5.0 / 9.0

            if "Prsr" in key:
                thrshd[key] = thrshd[key] * 6.89476

            if "Flow" in key:
                thrshd[key] = thrshd[key] / 0.2642

    registers = []
    index = 0
    thr_count = len(sensor_thrshd) * 2

    for key in thrshd:
        value = thrshd[key]
        if index < int(thr_count / 2):
            word1, word2 = cvt_float_byte(value)
            registers.append(word2)
            registers.append(word1)
        index += 1

    grouped_register = [registers[i : i + 64] for i in range(0, len(registers), 64)]

    i = 0
    for group in grouped_register:
        try:
            with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                client.write_registers(1000 + i * 64, group)
        except Exception as e:
            print(f"write register thrshd issue:{e}")

        i += 1

    key_list = list(ctr_data["value"].keys())
    for key in key_list:
        if key == "oil_temp_set":
            ctr_data["value"]["oil_temp_set"] = (
                (ctr_data["value"]["oil_temp_set"] - 32) / 9.0 * 5.0
            )

        if key == "oil_pressure_set":
            ctr_data["value"]["oil_pressure_set"] = (
                ctr_data["value"]["oil_pressure_set"] * 6.89476
            )

    temp1, temp2 = cvt_float_byte(ctr_data["value"]["oil_temp_set"])
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            client.write_registers(993, [temp2, temp1])
            client.write_registers(226, [temp2, temp1])
    except Exception as e:
        print(f"write oil temp error:{e}")

    prsr1, prsr2 = cvt_float_byte(ctr_data["value"]["oil_pressure_set"])
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            client.write_registers(991, [prsr2, prsr1])
            client.write_registers(224, [prsr2, prsr1])
    except Exception as e:
        print(f"write oil pressure error:{e}")

    key_list = list(measure_data.keys())
    for key in key_list:
        if "Temp" in key:
            measure_data[key] = (measure_data[key] - 32) * 5.0 / 9.0

        if "Prsr" in key:
            measure_data[key] = measure_data[key] * 6.89476

        if "f1" in key or "f2" in key:
            measure_data[key] = measure_data[key] / 0.2642
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            for i, (key, value) in enumerate(measure_data.items()):
                word1, word2 = cvt_float_byte(value)
                registers = [word2, word1]
                client.write_registers(901 + i * 2, registers)
    except Exception as e:
        print(f"measure data input error:{e}")


def change_to_imperial():
    read_data_from_json()

    for key in thrshd:
        if not key.endswith("_trap") and not key.startswith("Delay_"):
            if "Temp" in key:
                thrshd[key] = thrshd[key] * 9.0 / 5.0 + 32.0

            if "DewPoint" in key:
                thrshd[key] = thrshd[key] * 9.0 / 5.0

            if "Prsr" in key:
                thrshd[key] = thrshd[key] * 0.145038

            if "Flow" in key:
                thrshd[key] = thrshd[key] * 0.2642

    registers = []
    index = 0
    thr_count = len(sensor_thrshd) * 2

    for key in thrshd:
        value = thrshd[key]
        if index < int(thr_count / 2):
            word1, word2 = cvt_float_byte(value)
            registers.append(word2)
            registers.append(word1)
        index += 1

    grouped_register = [registers[i : i + 64] for i in range(0, len(registers), 64)]

    i = 0
    for group in grouped_register:
        try:
            with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                client.write_registers(1000 + i * 64, group)
        except Exception as e:
            print(f"write register thrshd issue:{e}")
        i += 1

    try:
        word1, word2 = cvt_float_byte(ctr_data["value"]["oil_pressure_set"])
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            client.write_registers(224, [word2, word1])
    except Exception as e:
        print(f"write oil pressure error:{e}")

    try:
        word1, word2 = cvt_float_byte(ctr_data["value"]["oil_temp_set"])
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            client.write_registers(226, [word2, word1])
    except Exception as e:
        print(f"write oil pressure error:{e}")

    key_list = list(ctr_data["value"].keys())
    for key in key_list:
        if key == "oil_temp_set":
            ctr_data["value"]["oil_temp_set"] = (
                ctr_data["value"]["oil_temp_set"] * 9.0 / 5.0 + 32.0
            )

        if key == "oil_pressure_set":
            ctr_data["value"]["oil_pressure_set"] = (
                ctr_data["value"]["oil_pressure_set"] * 0.145038
            )

    temp1, temp2 = cvt_float_byte(ctr_data["value"]["oil_temp_set"])
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            client.write_registers(993, [temp2, temp1])
    except Exception as e:
        print(f"write oil temp error:{e}")

    pressure1, pressure2 = cvt_float_byte(ctr_data["value"]["oil_pressure_set"])
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            client.write_registers(991, [pressure2, pressure1])
    except Exception as e:
        print(f"write oil pressure error:{e}")

    key_list = list(measure_data.keys())
    for key in key_list:
        if "Temp" in key:
            measure_data[key] = measure_data[key] * 9.0 / 5.0 + 32.0

        if "Prsr" in key:
            measure_data[key] = measure_data[key] * 0.145038

        if "f1" in key or "f2" in key:
            measure_data[key] = measure_data[key] * 0.2642

    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            for i, (key, value) in enumerate(measure_data.items()):
                word1, word2 = cvt_float_byte(value)
                registers = [word2, word1]
                client.write_registers(901 + i * 2, registers)
    except Exception as e:
        print(f"measure data input error:{e}")


def change_data_by_unit():
    global system_data
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            last_unit = client.read_coils((8192 + 501), 1, unit=modbus_slave_id)
            current_unit = client.read_coils((8192 + 500), 1, unit=modbus_slave_id)

            last_unit = last_unit.bits[0]
            current_unit = current_unit.bits[0]

            if current_unit:
                unit["unit"]["UnitSet"] = "imperial"
            else:
                unit["unit"]["UnitSet"] = "metric"

            if last_unit:
                unit["unit"]["LastUnit"] = "imperial"
            else:
                unit["unit"]["LastUnit"] = "metric"

            if current_unit and current_unit != last_unit:
                change_to_imperial()
            elif not current_unit and current_unit != last_unit:
                change_to_metric()

            client.write_coils((8192 + 501), [current_unit])

    except Exception as e:
        print(f"unit set error:{e}")


def unit_set_scc(unit):
    if unit == "Metric":
        coil_value = False
    elif unit == "Imperial":
        coil_value = True

    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            client.write_coil(address=(8192 + 500), value=coil_value)
            change_data_by_unit()
    except Exception as e:
        print(f"write in unit error:{e}")
        return False

    op_logger.info("setting unit_set successfully")
    return True


@scc_bp.route("/api/v1/cdu/control/op_mode")
@requires_auth
def get_op_mode():
    mode = g.ctr_data["value"]["resultMode"]
    temp = g.ctr_data["value"]["resultTemp"]
    pressure = g.ctr_data["value"]["resultPressure"]
    swap = g.ctr_data["value"]["resultSwap"]
    p1 = g.ctr_data["value"]["resultP1"]
    p2 = g.ctr_data["value"]["resultP2"]
    p3 = g.ctr_data["value"]["resultP3"]
    ps = g.ctr_data["value"]["resultPS"]

    f1 = g.ctr_data["value"]["resultFan1"]
    f2 = g.ctr_data["value"]["resultFan2"]
    f3 = g.ctr_data["value"]["resultFan3"]
    f4 = g.ctr_data["value"]["resultFan4"]
    f5 = g.ctr_data["value"]["resultFan5"]
    f6 = g.ctr_data["value"]["resultFan6"]
    f7 = g.ctr_data["value"]["resultFan7"]
    f8 = g.ctr_data["value"]["resultFan8"]
    fan = g.ctr_data["value"]["resultFan"]

    if mode == "Auto":
        return jsonify(
            {
                "OperationMode": mode,
                "Settings": {
                    "TemperatureSet": round(temp),
                    "PressureSet": round(pressure, 1),
                    "PumpSwapTime": round(swap),
                },
            }
        )
    elif mode == "Manual":
        ps1 = ps if p1 else 0
        ps2 = ps if p2 else 0
        ps3 = ps if p3 else 0

        fan1 = fan if f1 else 0
        fan2 = fan if f2 else 0
        fan3 = fan if f3 else 0
        fan4 = fan if f4 else 0
        fan5 = fan if f5 else 0
        fan6 = fan if f6 else 0
        fan7 = fan if f7 else 0
        fan8 = fan if f8 else 0

        return jsonify(
            {
                "OperationMode": mode,
                "Settings": {
                    "Pump1Speed": round(ps1),
                    "Pump2Speed": round(ps2),
                    "Pump3Speed": round(ps3),
                    "Fan1Speed": round(fan1),
                    "Fan2Speed": round(fan2),
                    "Fan3Speed": round(fan3),
                    "Fan4Speed": round(fan4),
                    "Fan5Speed": round(fan5),
                    "Fan6Speed": round(fan6),
                    "Fan7Speed": round(fan7),
                    "Fan8Speed": round(fan8),
                },
            }
        )
    elif mode == "Inspection" or mode == "Stop":
        return jsonify(
            {
                "Operation Mode": mode,
            }
        )


@scc_bp.route("/api/v1/cdu/control/op_mode", methods=["PATCH"])
@requires_auth
def patch_op_mode():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        print(f"missing error: {e}")
        return api_error_response(400)

    if not data:
        return api_error_response(400)

    settings = data.get("Settings", {})

    if "OperationMode" not in data.keys():
        return api_error_response(400)

    if not data.get("OperationMode"):
        return api_error_response(400)

    if data.get("OperationMode") not in ["Auto", "Stop", "Manual"]:
        return api_error_response(400)

    for key in [
        "PumpSpeed",
        "FanSpeed",
        "TemperatureSet",
        "PumpSwapTime",
    ]:
        if settings.get(key) is not None and not isinstance(settings.get(key), int):
            return api_error_response(400)

    for key in [
        "Pump1",
        "Pump2",
        "Pump3",
        "Fan1",
        "Fan2",
        "Fan3",
        "Fan4",
        "Fan5",
        "Fan6",
        "Fan7",
        "Fan8",
    ]:
        if settings.get(key) is not None and not isinstance(settings.get(key), bool):
            return api_error_response(400)

    if settings.get("PressureSet") is not None and not isinstance(
        settings.get("PressureSet"), (int, float)
    ):
        return api_error_response(400)

    new_mode = data["OperationMode"]
    p1 = settings.get("Pump1")
    p2 = settings.get("Pump2")
    p3 = settings.get("Pump3")
    f1 = settings.get("Fan1")
    f2 = settings.get("Fan2")
    f3 = settings.get("Fan3")
    f4 = settings.get("Fan4")
    f5 = settings.get("Fan5")
    f6 = settings.get("Fan6")
    f7 = settings.get("Fan7")
    f8 = settings.get("Fan8")
    ps = settings.get("PumpSpeed")
    fan = settings.get("FanSpeed")
    swap = settings.get("PumpSwapTime")
    temp = settings.get("TemperatureSet")
    pressure = settings.get("PressureSet")
    temp_upLmt = 0
    temp_lowLmt = 0
    prsr_upLmt = 0
    prsr_lowLmt = 0
    message = "Operation mode updated successfully"
    inv1_error = g.sensorData["error"]["Inv1_Error"]
    inv2_error = g.sensorData["error"]["Inv2_Error"]
    inv3_error = g.sensorData["error"]["Inv3_Error"]
    overload1 = g.sensorData["error"]["Inv1_OverLoad"]
    overload2 = g.sensorData["error"]["Inv2_OverLoad"]
    overload3 = g.sensorData["error"]["Inv3_OverLoad"]
    fanol1 = g.sensorData["error"]["Fan_OverLoad1"]
    fanol2 = g.sensorData["error"]["Fan_OverLoad2"]

    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            result = client.read_coils(address=(8192 + 500), count=1)
        if result.bits[0]:
            temp_upLmt = 131
            temp_lowLmt = 95
            prsr_upLmt = 7.5 * 14.5
            prsr_lowLmt = 0
        else:
            temp_upLmt = 55
            temp_lowLmt = 35
            prsr_upLmt = 750
            prsr_lowLmt = 0
    except Exception as e:
        print(f"temp_set_limit: {e}")
        return api_error_response(503)

    if new_mode == "Auto":
        if temp is not None and pressure is not None:
            if not (temp_lowLmt <= temp <= temp_upLmt):
                return api_error_response(400)

            elif not (prsr_lowLmt <= pressure <= prsr_upLmt):
                return api_error_response(400)
        if swap is not None:
            if swap < 0:
                return api_error_response(400)

    elif new_mode == "Manual":
        if ps is not None:
            if not (ps == 0 or 25 <= ps <= 100):
                return api_error_response(400)

        if fan is not None:
            if fan < 0 or fan > 100:
                return api_error_response(400)

    try:
        with ModbusTcpClient(port=modbus_port, host=modbus_host) as client:
            if new_mode == "Stop":
                client.write_coils((8192 + 514), [False])
                op_logger.info(f"Operation mode updated successfully. {new_mode}")
                return jsonify(
                    {
                        "OperationMode": new_mode,
                    }
                )

            elif new_mode == "Manual":
                if ps is not None:
                    input_ps(ps)

                if p1 is not None:
                    if not inv1_error and not overload1:
                        set_p1(p1)
                    else:
                        message = "Failed to activate malfunctioning inverter or fan due to error or overload"
                if p2 is not None:
                    if not inv2_error and not overload2:
                        set_p2(p2)
                    else:
                        message = "Failed to activate malfunctioning inverter or fan due to error or overload"
                if p3 is not None:
                    if not inv3_error and not overload3:
                        set_p3(p3)
                    else:
                        message = "Failed to activate malfunctioning inverter or fan due to error or overload"
                if fan is not None:
                    if not fanol1 or not fanol2:
                        input_fan(fan)
                    else:
                        message = "Failed to activate malfunctioning inverter or fan due to error or overload"

                ps1 = ps if p1 else None
                ps2 = ps if p2 else None
                ps3 = ps if p3 else None
                fan1 = fan if f1 else None
                fan2 = fan if f2 else None
                fan3 = fan if f3 else None
                fan4 = fan if f4 else None
                fan5 = fan if f5 else None
                fan6 = fan if f6 else None
                fan7 = fan if f7 else None
                fan8 = fan if f8 else None

                if inv1_error or overload1:
                    ps1 = 0

                if inv2_error or overload2:
                    ps2 = 0

                if inv3_error or overload3:
                    ps3 = 0

                if fanol1 or fanol2:
                    fan = 0

                client.write_coils((8192 + 505), [True])
                client.write_coils((8192 + 514), [True])
                client.write_coils((8192 + 516), [False])
                set_fan([f1, f2, f3, f4, f5, f6, f7, f8])

                response_data = {
                    "OperationMode": new_mode,
                }

                settings = {
                    "Pump1Speed": ps1,
                    "Pump2Speed": ps2,
                    "Pump3Speed": ps3,
                    "Fan1Speed": fan1,
                    "Fan2Speed": fan2,
                    "Fan3Speed": fan3,
                    "Fan4Speed": fan4,
                    "Fan5Speed": fan5,
                    "Fan6Speed": fan6,
                    "Fan7Speed": fan7,
                    "Fan8Speed": fan8,
                }

                if message != "Operation mode updated successfully":
                    response_data["Message"] = message

                filtered_settings = {
                    key: value for key, value in settings.items() if value is not None
                }

                if filtered_settings:
                    response_data["Settings"] = filtered_settings

                op_logger.info(f"Operation mode updated successfully. {response_data}")
                return jsonify(response_data)

            elif new_mode == "Auto":
                unit = client.read_coils((8192 + 500), 1)

                if unit.bits[0]:
                    if temp is not None:
                        temp = (float(temp) - 32) / 9.0 * 5.0
                        temp1, temp2 = cvt_float_byte(temp)
                        client.write_registers(224, [temp2, temp1])

                    if pressure is not None:
                        pressure = float(temp) * 6.89476
                        prsr1, prsr2 = cvt_float_byte(pressure)
                        client.write_registers(226, [prsr2, prsr1])

                if temp is not None:
                    word7, word8 = cvt_float_byte(float(temp))
                    client.write_registers(993, [word8, word7])

                if pressure is not None:
                    word9, word10 = cvt_float_byte(float(pressure))
                    client.write_registers(991, [word10, word9])

                if swap is not None:
                    swap1, swap2 = cvt_float_byte(float(swap))
                    client.write_registers(303, [swap2, swap1])

                client.write_coils((8192 + 505), [False])
                client.write_coils((8192 + 514), [True])
                client.write_coils((8192 + 516), [False])

                response_data = {
                    "OperationMode": new_mode,
                }

                settings = {
                    "TemperatureSet": temp,
                    "PressureSet": pressure,
                    "PumpSwapTime": swap,
                }

                filtered_settings = {
                    key: value for key, value in settings.items() if value is not None
                }

                if filtered_settings:
                    response_data["Settings"] = filtered_settings

                op_logger.info(f"Operation mode updated successfully. {response_data}")
                return jsonify(response_data)

    except Exception as e:
        print(f"set mode error: {e}")
        return api_error_response(503)


@scc_bp.route("/api/v1/unit_set")
@requires_auth
def get_unit():
    unit["unit"]["UnitSet"] = g.system_data["value"]["unit"].capitalize()
    return jsonify({"UnitSet": unit["unit"]["UnitSet"]})


@scc_bp.route("/api/v1/unit_set", methods=["PATCH"])
@requires_auth
def patch_unit():
    try:
        data = request.get_json(force=True)
        new_unit = data["UnitSet"]
    except Exception as e:
        print(f"unit set error:{e}")
        return api_error_response(400)

    if new_unit not in ["Metric", "Imperial"]:
        return api_error_response(400)

    unit["unit"]["UnitSet"] = new_unit

    try:
        if unit_set_scc(new_unit):
            return jsonify({"UnitSet": new_unit})
        else:
            return api_error_response(503)

    except Exception as e:
        print(f"unit set error:{e}")
        return api_error_response(503)


@scc_bp.route("/api/v1/cdu/status/pump_service_hours")
@requires_auth
def get_pump_service_hours():
    try:
        pump_data["runtime"]["Pump1ServiceHour"] = g.ctr_data["text"]["Pump1_run_time"]
        pump_data["runtime"]["Pump2ServiceHour"] = g.ctr_data["text"]["Pump2_run_time"]
        pump_data["runtime"]["Pump3ServiceHour"] = g.ctr_data["text"]["Pump3_run_time"]
    except Exception as e:
        print(f"pump speed time error:{e}")
        return api_error_response(503)

    return jsonify(pump_data["runtime"])


@scc_bp.route("/api/v1/cdu/status/pump_speed")
@requires_auth
def get_pump_speed_status():
    try:
        p1 = g.sensorData["value"]["inv1_freq"]
        p2 = g.sensorData["value"]["inv2_freq"]
        p3 = g.sensorData["value"]["inv3_freq"]

        pump_data["speed"]["Pump1Speed"] = round(p1)
        pump_data["speed"]["Pump2Speed"] = round(p2)
        pump_data["speed"]["Pump3Speed"] = round(p3)
    except Exception as e:
        print(f"pump speed error:{e}")
        return api_error_response(503)

    return jsonify(pump_data["speed"])


@scc_bp.route("/api/v1/cdu/status/fan_speed")
@requires_auth
def get_fan_speed_status():
    try:
        f1 = g.sensorData["value"]["fan_freq1"]
        f2 = g.sensorData["value"]["fan_freq2"]
        f3 = g.sensorData["value"]["fan_freq3"]
        f4 = g.sensorData["value"]["fan_freq4"]
        f5 = g.sensorData["value"]["fan_freq5"]
        f6 = g.sensorData["value"]["fan_freq6"]
        f7 = g.sensorData["value"]["fan_freq7"]
        f8 = g.sensorData["value"]["fan_freq8"]

        fan_data["speed"]["Fan1Speed"] = round(f1)
        fan_data["speed"]["Fan2Speed"] = round(f2)
        fan_data["speed"]["Fan3Speed"] = round(f3)
        fan_data["speed"]["Fan4Speed"] = round(f4)
        fan_data["speed"]["Fan5Speed"] = round(f5)
        fan_data["speed"]["Fan6Speed"] = round(f6)
        fan_data["speed"]["Fan7Speed"] = round(f7)
        fan_data["speed"]["Fan8Speed"] = round(f8)
    except Exception as e:
        print(f"fan speed error:{e}")
        return api_error_response(503)

    return jsonify(fan_data["speed"])


@scc_bp.route("/api/v1/cdu/status/sensor_status_beta")
@requires_auth
def get_sensor_status():
    key_list = list(sensor_status_data.keys())
    try:
        for key in key_list:
            if key != "HeatCapacity" and key != "InstantPowerConsumption":
                if "Fan" in key or "Inv" in key:
                    sensor_status_data[key]["Status"] = "Disable"
                else:    
                    sensor_status_data[key]["Status"] = "Good"
                error_keys = app_errorr_mapping_for_status.get(key)
                value_keys = app_value_mapping.get(key)
                if value_keys:
                    if g.sensorData["alert_notice"][value_keys]:
                        sensor_status_data[key]["Status"] = "Alert"
                    elif g.sensorData["warning_notice"][value_keys]:
                        sensor_status_data[key]["Status"] = "Warning"
                if error_keys:
                    if g.sensorData["error"][error_keys]:
                        if "Com" in error_keys:
                            sensor_status_data[key]["Status"] = "Com Error"
                        else:
                            sensor_status_data[key]["Status"] = "Broken Error"
                            
        inv_names = ["1", "2", "3"]
        for inv in inv_names:
            if g.sensorData["error"][f"Inv{inv}_OverLoad"]:
                sensor_status_data[f"Inv{inv}"]["Status"] = "Overload"
            elif g.sensorData["error"][f"Inv{inv}_Error"]:
                sensor_status_data[f"Inv{inv}"]["Status"] = "Error"
            elif g.sensorData["value"][f"inv{inv}_freq"] and (not g.sensorData["error"][f"Inv{inv}_Com"]):
                sensor_status_data[f"Inv{inv}"]["Status"] = "Good"

        
        for i in range(1, 9):
            if g.sensorData["error"][f"fan{i}_error"]:
                sensor_status_data[f"Fan{i}"]["Status"] = "Error"
            elif g.sensorData["value"][f"fan_freq{i}"] and (not g.sensorData["error"][f"Fan{i}_Com"]):
                sensor_status_data[f"Fan{i}"]["Status"] = "Good"
                
        overload_names = ["1", "2"]
        index = 1
        for o in overload_names:
            if g.sensorData["error"][f"Fan_OverLoad{o}"]:
                for i in range(index, index+4):
                    sensor_status_data[f"Fan{i}"]["Status"] = "Overload"
            index = 5

                # if g.sensorData["error"]["Clnt_Flow_Com"]:
                #         sensor_value_data["CoolantFlowRate"]["Status"] = "Error"
        result = []
        for key in key_list:
            if key != "HeatCapacity" and key != "InstantPowerConsumption":
                result.append({
                    "Name": sensor_status_data[key]["Name"],
                    "Status": sensor_status_data[key]["Status"]
                })
    except Exception as e:
        print(f"status plc error: {e}")
        return api_error_response(503)
    return jsonify(result)

@scc_bp.route("/api/v1/cdu/status/sensor_value")
@requires_auth
def get_sensor_value():
    try:
        unit["unit"]["UnitSet"] = g.system_data["value"]["unit"]

        if unit["unit"]["UnitSet"] == "imperial":
            for key in sensor_value_data:
                if "Temp" in key or "Dew" in key:
                    sensor_value_data[key]["Unit"] = "°F"
                if "Pressure" in key:
                    sensor_value_data[key]["Unit"] = "psi"
                if "Flow" in key:
                    sensor_value_data[key]["Unit"] = "GPM"

        elif unit["unit"]["UnitSet"] == "metric":
            for key in sensor_value_data:
                if "Temp" in key or "Dew" in key:
                    sensor_value_data[key]["Unit"] = "°C"
                if "Pressure" in key:
                    sensor_value_data[key]["Unit"] = "kPa"
                if "Flow" in key:
                    sensor_value_data[key]["Unit"] = "LPM"

        sensor_map = {
            "CoolantSupplyTemperature": "temp_clntSply",
            "CoolantSupplyTemperatureSpare": "temp_clntSplySpare",
            "CoolantReturnTemperature": "temp_clntRtn",
            "CoolantReturnTemperatureSpare": "temp_clntRtnSpare",
            "CoolantSupplyPressure": "prsr_clntSply",
            "CoolantSupplyPressureSpare": "prsr_clntSplySpare",
            "CoolantReturnPressure": "prsr_clntRtn",
            "CoolantReturnPressureSpare": "prsr_clntRtnSpare",
            "FilterInletPressure":"prsr_fltIn",
            "FilterOutletPressure":"prsr_fltOut",
            "CoolantFlowRate": "clnt_flow",
            "AmbientTemp": "ambient_temp",
            "RelativeHumid": "relative_humid",
            "DewPoint": "dew_point",
            "pH": "pH",
            "Conductivity": "cdct",
            "Turbidity": "tbd",
            "InstantPowerConsumption": "power",
            "HeatCapacity": "heat_capacity",
            "AverageCurrent": "AC",
        }

        for key, value in sensor_map.items():
            if key == "CoolantFlowRate":
                sensor_value_data[key]["Value"] = int(g.sensorData["value"][value])
            else:
                sensor_value_data[key]["Value"] = round(g.sensorData["value"][value], 1)

    except Exception as e:
        print(f"status value error:{e}")
        return api_error_response(503)

    try:
        key_list = list(sensor_value_data.keys())

        for key in key_list:
            if key != "HeatCapacity" and key != "InstantPowerConsumption":
                sensor_value_data[key]["Status"] = "Good"
                v_key = app_value_mapping.get(key)
                if v_key:
                    if g.sensorData["alert_notice"][v_key]:
                        sensor_value_data[key]["Status"] = "Alert"
                    elif g.sensorData["warning_notice"][v_key]:
                        sensor_value_data[key]["Status"] = "Warning"
    except Exception as e:
        print(f"alert plc error: {e}")
        return api_error_response(503)

    try:
        key_list = list(sensor_value_data.keys())

        for key in key_list:
            if key != "HeatCapacity" and key != "InstantPowerConsumption":
                sensor_value_data[key]["Status"] = "Good"
                e_key = app_error_mapping.get(key)
                if e_key:
                    if g.sensorData["error"][e_key]:
                        sensor_value_data[key]["Status"] = "Error"

                # if g.sensorData["error"]["Clnt_Flow_Com"]:
                #     sensor_value_data["CoolantFlowRate"]["Status"] = "Error"

    except Exception as e:
        print(f"alert plc error: {e}")
        return api_error_response(503)

    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            thr_regs = len(sensor_thrshd.keys()) * 2
            start_address = 1000
            total_registers = thr_regs
            read_num = 120

            for counted_num in range(0, total_registers, read_num):
                count = min(read_num, total_registers - counted_num)
                result = client.read_holding_registers(
                    start_address + counted_num, count
                )

                if not result.isError():
                    keys_list = list(sensor_thrshd.keys())
                    j = counted_num // 2
                    for i in range(0, count, 2):
                        if i + 1 < len(result.registers) and j < len(keys_list):
                            temp1 = [
                                result.registers[i],
                                result.registers[i + 1],
                            ]
                            decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
                                temp1,
                                byteorder=Endian.Big,
                                wordorder=Endian.Little,
                            )
                            decoded_value_big_endian = (
                                decoder_big_endian.decode_32bit_float()
                            )
                            sensor_thrshd[keys_list[j]] = decoded_value_big_endian
                            j += 1

        for key in sensor_thrshd:
            parts = key.split("_")
            short_key = parts[-2]

            if "Rst" not in key:
                if "W_" in key:
                    if "_L" in key:
                        sensor_value_data[short_key]["WarningLevel"]["MinValue"] = (
                            round((sensor_thrshd.get(key, None)), 1)
                        )
                    elif "_H" in key:
                        sensor_value_data[short_key]["WarningLevel"]["MaxValue"] = (
                            round(sensor_thrshd.get(key, None), 1)
                        )
                elif "A_" in key:
                    if "_L" in key:
                        sensor_value_data[short_key]["AlertLevel"]["MinValue"] = round(
                            sensor_thrshd.get(key, None), 1
                        )
                    elif "_H" in key:
                        sensor_value_data[short_key]["AlertLevel"]["MaxValue"] = round(
                            sensor_thrshd.get(key, None), 1
                        )
    except Exception as e:
        print(f"min max plc error: {e}")
        return api_error_response(503)

    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            thr_count = len(trap_enable_key.keys())
            r = client.read_coils((8192 + 2000), thr_count)

            for x, key in enumerate(trap_enable_key.keys()):
                trap_enable_key[key] = r.bits[x]

            for key in sensor_value_data:
                w_key = f"W_{key}"
                a_key = f"A_{key}"

                if key != "HeatCapacity" and key != "InstantPowerConsumption":
                    sensor_value_data[key]["WarningLevel"]["TrapEnabled"] = (
                        trap_enable_key.get(w_key, False)
                    )
                    sensor_value_data[key]["AlertLevel"]["TrapEnabled"] = (
                        trap_enable_key.get(a_key, False)
                    )
    except Exception as e:
        print(f"read trap plc error: {e}")
        return api_error_response(503)

    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            delay_count = len(sensor_delay.keys())
            r = client.read_holding_registers(1000 + thr_regs, delay_count)

            i = 0
            for key, value in sensor_value_data.items():
                if key not in [
                    "InstantPowerConsumption",
                    "HeatCapacity",
                ]:
                    sensor_value_data[key]["DelayTime"] = r.registers[i]
                    i += 1

    except Exception as e:
        print(f"read delay plc error: {e}")
        return api_error_response(503)

    output = [v for v in sensor_value_data.values()]

    try:
        with open("web/json/scc.json", "w") as file:
            json.dump(sensor_value_data, file, indent=4)
    except Exception as e:
        print(f"input error: {e}")
        return api_error_response(503)

    return output


@scc_bp.route("/api/v1/cdu/status/sensor_value", methods=["PATCH"])
@requires_auth
def set_sensor_config():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        print(f"read json issue: {e}")
        return api_error_response(400)

    if data.get("Name") not in sensor_value_data:
        return api_error_response(400)

    AlertLevel = data.get("AlertLevel", {})
    WarningLevel = data.get("WarningLevel", {})

    if not isinstance(AlertLevel.get("TrapEnabled"), bool):
        return api_error_response(400)

    if (
        not isinstance(AlertLevel.get("MaxValue"), (int, float))
        or AlertLevel.get("MaxValue") > 9007199254740991
    ):
        return api_error_response(400)

    if (
        not isinstance(AlertLevel.get("MaxRstValue"), (int, float))
        or AlertLevel.get("MaxRstValue") > 9007199254740991
    ):
        return api_error_response(400)
    
    if (
        not isinstance(AlertLevel.get("MinValue"), (int, float))
        or AlertLevel.get("MinValue") > 9007199254740991
    ):
        return api_error_response(400)

    if (
        not isinstance(AlertLevel.get("MinRstValue"), (int, float))
        or AlertLevel.get("MinRstValue") > 9007199254740991
    ):
        return api_error_response(400)

    if not isinstance(WarningLevel.get("TrapEnabled"), bool):
        return api_error_response(400)

    if (
        not isinstance(WarningLevel.get("MaxValue"), (int, float))
        or WarningLevel.get("MaxValue") > 9007199254740991
    ):
        return api_error_response(400)
    
    if (
        not isinstance(WarningLevel.get("MaxRstValue"), (int, float))
        or WarningLevel.get("MaxRstValue") > 9007199254740991
    ):
        return api_error_response(400)
    
    if (
        not isinstance(WarningLevel.get("MinValue"), (int, float))
        or WarningLevel.get("MinValue") > 9007199254740991
    ):
        return api_error_response(400)

    if (
        not isinstance(WarningLevel.get("MinRstValue"), (int, float))
        or WarningLevel.get("MinRstValue") > 9007199254740991
    ):
        return api_error_response(400)
    
    if not isinstance(data.get("DelayTime"), (int)) or data.get("DelayTime") > 30000:
        return api_error_response(400)

    sensor = data.get("Name")
    w_trap = WarningLevel.get("TrapEnabled")
    w_max = WarningLevel.get("MaxValue")
    w_min = WarningLevel.get("MinValue")
    w_rst_max = WarningLevel.get("MaxRstValue")
    w_rst_min = WarningLevel.get("MinRstValue")
    a_trap = AlertLevel.get("TrapEnabled")
    a_max = AlertLevel.get("MaxValue")
    a_min = AlertLevel.get("MinValue")
    a_rst_max = AlertLevel.get("MaxRstValue")
    a_rst_min = AlertLevel.get("MinRstValue")
    delay = data.get("DelayTime")
    unit["unit"]["UnitSet"] = g.system_data["value"]["unit"]

    try:
        a_key = f"A_{sensor}"
        w_key = f"W_{sensor}"

        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            if w_trap is not None:
                client.write_coils(trap_mapping[w_key], [w_trap])
            if a_trap is not None:
                client.write_coils(trap_mapping[a_key], [a_trap])

        high_W_key = f"Thr_W_{sensor}_H"
        low_W_key = f"Thr_W_{sensor}_L"
        high_W_Rst_key = f"Thr_W_Rst_{sensor}_H"
        low_W_Rst_key = f"Thr_W_Rst_{sensor}_L"
        high_A_key = f"Thr_A_{sensor}_H"
        low_A_key = f"Thr_A_{sensor}_L"
        high_A_Rst_key = f"Thr_A_Rst_{sensor}_H"
        low_A_Rst_key = f"Thr_A_Rst_{sensor}_L"
        
        def convert_imperial(value):
            if value is not None:
                if "Temp" in sensor:
                    value = value * 9.0 / 5.0 + 32.0
                elif "DewPoint" in sensor:
                    value = value * 9.0 / 5.0
                elif "Pressure" in sensor:
                    value = value * 0.145038
                elif "Flow" in sensor:
                    value = value * 0.2642
            return value

        if unit["unit"]["UnitSet"] == "imperial":
            w_max = convert_imperial(w_max)
            w_min = convert_imperial(w_min)
            w_rst_max = convert_imperial(w_rst_max)
            w_rst_min = convert_imperial(w_rst_min)
            a_max = convert_imperial(a_max)
            a_min = convert_imperial(a_min)
            a_rst_max = convert_imperial(a_rst_max)
            a_rst_min = convert_imperial(a_rst_min)

        def update_threshold(key, value):
            if key in sensor_thrshd:
                sensor_thrshd[key] = value
                w1, w2 = cvt_float_byte(value)
                client.write_registers(max_min_value_location[key], [w2, w1])

        try:
            with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                if a_max is not None:
                    update_threshold(high_A_key, a_max)
                if a_min is not None:
                    update_threshold(low_A_key, a_min)
                if a_rst_max is not None:
                    update_threshold(high_A_Rst_key, a_rst_max)
                if a_rst_min is not None:
                    update_threshold(low_A_Rst_key, a_rst_min)
                if w_max is not None:
                    update_threshold(high_W_key, w_max)
                if w_min is not None:
                    update_threshold(low_W_key, w_min)
                if w_rst_max is not None:
                    update_threshold(high_W_Rst_key, w_rst_max)
                if w_rst_min is not None:
                    update_threshold(low_W_Rst_key, w_rst_min)
        except Exception as e:
            print(f"update max/min values: {e}")
            return api_error_response(503)

        if delay is not None:
            try:
                thr_regs = len(sensor_thrshd.keys()) * 2

                for i, key in enumerate(sensor_delay):
                    delay_key = f"Delay_{sensor}"
                    if delay_key == key:
                        with ModbusTcpClient(
                            host=modbus_host, port=modbus_port
                        ) as client:
                            client.write_registers((1000 + thr_regs + i), delay)
            except Exception as e:
                print(f"update delay: {e}")
                return api_error_response(503)

        response_data = {"Name": sensor}

        warning = {
            "TrapEnabled": w_trap,
            "MinValue": w_min,
            "MinRstValue": w_rst_min,
            "MaxValue": w_max,
            "MaxRstValue": w_rst_max,
        }

        alert = {
            "TrapEnabled": a_trap,
            "MinValue": a_min,
            "MinRstValue": a_rst_min,
            "MaxValue": a_max,
            "MaxRstValue": a_rst_max,
        }

        filter_warning = {
            key: value for key, value in warning.items() if value is not None
        }

        filter_alert = {key: value for key, value in alert.items() if value is not None}

        if filter_warning:
            response_data["WarningLevel"] = filter_warning

        if filter_alert:
            response_data["AlertLevel"] = filter_alert

        if delay is not None:
            response_data["DelayTime"] = delay

        op_logger.info(f"Sensor Value updated successfully. {response_data}")
        return jsonify(response_data)

    except Exception as e:
        print(f"set sensor value error: {e}")
        return api_error_response(503)


@scc_bp.route("/api/v1/cdu/status/inverter")
@requires_auth
def get_inverter_status():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            inv1 = client.read_holding_registers(address=(20480 + 6660), count=1)
            inv2 = client.read_holding_registers(address=(20480 + 6700), count=1)
            inv3 = client.read_holding_registers(address=(20480 + 6740), count=1)

            inv1_v = inv1.registers[0] / 16000 * 75 + 25
            inv2_v = inv2.registers[0] / 16000 * 75 + 25
            inv3_v = inv3.registers[0] / 16000 * 75 + 25

            inverter_status["Inverter1"] = inv1_v >= 25
            inverter_status["Inverter2"] = inv2_v >= 25
            inverter_status["Inverter3"] = inv3_v >= 25
    except Exception as e:
        print(f"read inv_en error:{e}")
        return api_error_response(503)

    for i in range(1, 4):
        inverter_status[f"Inverter{i}"] = (
            "On" if inverter_status[f"Inverter{i}"] else "Off"
        )

    return jsonify(inverter_status)


@scc_bp.route("/api/v1/error_messages")
@requires_auth
def get_error_messages():
    # try:
    #     key_mapping = {
    #         "M100": "temp_clntSply_high",
    #         "M101": "temp_clntSplySpare_high",
    #         "M102": "temp_clntRtn_high",
    #         "M103": "temp_clntRtnSpare_high",
    #         "M104": "prsr_clntSply_high",
    #         "M105": "prsr_clntSplySpare_high",
    #         "M106": "prsr_clntRtn_high",
    #         "M107": "prsr_clntRtnSpare_high",
    #         "M108": "prsr_fltIn_low",
    #         "M109": "prsr_fltIn_high",
    #         "M110": "prsr_fltOut_high",
    #         "M111": "clnt_flow_low",
    #         "M112": "ambient_temp_low",
    #         "M113": "ambient_temp_high",
    #         "M114": "relative_humid_low",
    #         "M115": "relative_humid_high",
    #         "M116": "dew_point_low",
    #         "M117": "pH_low",
    #         "M118": "pH_high",
    #         "M119": "cdct_low",
    #         "M120": "cdct_high",
    #         "M121": "tbd_low",
    #         "M122": "tbd_high",
    #         "M123": "AC_high",
    #     }

    #     for msg_key, sensor_key in key_mapping.items():
    #         messages["warning"][msg_key][1] = g.sensorData["warning"][sensor_key]

    #     key_mapping = {
    #         "M200": "temp_clntSply_high",
    #         "M201": "temp_clntSplySpare_high",
    #         "M202": "temp_clntRtn_high",
    #         "M203": "temp_clntRtnSpare_high",
    #         "M204": "prsr_clntSply_high",
    #         "M205": "prsr_clntSplySpare_high",
    #         "M206": "prsr_clntRtn_high",
    #         "M207": "prsr_clntRtnSpare_high",
    #         "M208": "prsr_fltIn_low",
    #         "M209": "prsr_fltIn_high",
    #         "M210": "prsr_fltOut_high",
    #         "M211": "clnt_flow_low",
    #         "M212": "ambient_temp_low",
    #         "M213": "ambient_temp_high",
    #         "M214": "relative_humid_low",
    #         "M215": "relative_humid_high",
    #         "M216": "dew_point_low",
    #         "M217": "pH_low",
    #         "M218": "pH_high",
    #         "M219": "cdct_low",
    #         "M220": "cdct_high",
    #         "M221": "tbd_low",
    #         "M222": "tbd_high",
    #         "M223": "AC_high",
    #     }

    #     for msg_key, sensor_key in key_mapping.items():
    #         messages["alert"][msg_key][1] = g.sensorData["alert"][sensor_key]

    #     key_mapping = {
    #         "M300": "Inv1_OverLoad",
    #         "M301": "Inv2_OverLoad",
    #         "M302": "Inv3_OverLoad",
    #         "M303": "Fan_OverLoad1",
    #         "M304": "Fan_OverLoad2",
    #         "M305": "Inv1_Error",
    #         "M306": "Inv2_Error",
    #         "M307": "Inv3_Error",
    #         "M308": "ATS1",
    #         "M309": "Inv1_Com",
    #         "M310": "Inv2_Com",
    #         "M311": "Inv3_Com",
    #         # "M312": "Clnt_Flow_Com",
    #         "M313": "Ambient_Temp_Com",
    #         "M314": "Relative_Humid_Com",
    #         "M315": "Dew_Point_Com",
    #         "M316": "Cdct_Sensor_Com",
    #         "M317": "pH_Com",
    #         "M318": "Tbd_Com",
    #         "M319": "ATS1_Com",
    #         "M320": "ATS2_Com",
    #         "M321": "Power_Meter_Com",
    #         "M322": "Average_Current_Com",
    #         "M323": "Fan1_Com",
    #         "M324": "Fan2_Com",
    #         "M325": "Fan3_Com",
    #         "M326": "Fan4_Com",
    #         "M327": "Fan5_Com",
    #         "M328": "Fan6_Com",
    #         "M329": "Fan7_Com",
    #         "M330": "Fan8_Com",
    #         "M331": "TempClntSply_broken",
    #         "M332": "TempClntSplySpare_broken",
    #         "M333": "TempClntRtn_broken",
    #         "M334": "TempClntRtnSpare_broken",
    #         "M335": "PrsrClntSply_broken",
    #         "M336": "PrsrClntSplySpare_broken",
    #         "M337": "PrsrClntRtn_broken",
    #         "M338": "PrsrClntRtnSpare_broken",
    #         "M339": "PrsrFltIn_broken",
    #         "M340": "PrsrFltOut_broken",
    #         "M341": "Clnt_Flow_broken",
    #         "M342": "pc1_error",
    #         "M343": "pc2_error",
    #         "M344": "leakage1_leak",
    #         "M345": "leakage1_broken",
    #         "M346": "level1",
    #         "M347": "level2",
    #         "M348": "level3",
    #         "M349": "power24v1",
    #         "M350": "power24v2",
    #         "M351": "power12v1",
    #         "M352": "power12v2",
    #         "M353": "main_mc_error",
    #         "M354": "fan1_error",
    #         "M355": "fan2_error",
    #         "M356": "fan3_error",
    #         "M357": "fan4_error",
    #         "M358": "fan5_error",
    #         "M359": "fan6_error",
    #         "M360": "fan7_error",
    #         "M361": "fan8_error",
    #         "M362": "Low_Coolant_Level_Warning",
    #         "M363": "PLC",
    #     }

    #     for msg_key, sensor_key in key_mapping.items():
    #         messages["error"][msg_key][1] = g.sensorData["error"][sensor_key]

    #     rack_mapping = {
    #         "M400": "rack1_broken",
    #         "M401": "rack2_broken",
    #         "M402": "rack3_broken",
    #         "M403": "rack4_broken",
    #         "M404": "rack5_broken",
    #         "M405": "rack1_leak_com",
    #         "M406": "rack2_leak_com",
    #         "M407": "rack3_leak_com",
    #         "M408": "rack4_leak_com",
    #         "M409": "rack5_leak_com",
    #         "M410": "rack1_leak",
    #         "M411": "rack2_leak",
    #         "M412": "rack3_leak",
    #         "M413": "rack4_leak",
    #         "M414": "rack5_leak",
    #         "M415": "rack1_status_com",
    #         "M416": "rack2_status_com",
    #         "M417": "rack3_status_com",
    #         "M418": "rack4_status_com",
    #         "M419": "rack5_status_com",
    #         "M420": "rack1_error",
    #         "M421": "rack2_error",
    #         "M422": "rack3_error",
    #         "M423": "rack4_error",
    #         "M424": "rack5_error",
    #         "M425": "rack6_error",
    #         "M426": "rack7_error",
    #         "M427": "rack8_error",
    #         "M428": "rack9_error",
    #         "M429": "rack10_error",
    #         "M430": "rack_leakage1_leak",
    #         "M431": "rack_leakage1_broken",
    #         "M432": "rack_leakage2_leak",
    #         "M433": "rack_leakage2_broken",
    #     }

    #     for msg_key, sensor_key in rack_mapping.items():
    #         messages["rack"][msg_key][1] = g.sensorData["rack"][sensor_key]
    # except Exception as e:
    #     print(f"error message issue:{e}")
    #     return api_error_response(503)
    # error_messages = []
    # for category in ["warning", "alert", "error", "rack"]:
    #     for code, message in messages[category].items():
    #         if message[1]:
    #             error_messages.append({"ErrorCode": code, "Message": message[0]})
    try:
        error_messages = []
        for category in ["warning", "alert", "error", "rack"]:
            for key, status in g.sensorData[category].items():
                if status:
                    msg = g.sensorData["err_log"][category][key].split(" ", 1)
                    code = msg[0]
                    messages = msg[1]
                    error_messages.append({"ErrorCode": code, "Message": messages})
    except Exception as e:
        print(f"error message issue:{e}")
        return api_error_response(503)
    
    try:
        with open("web/json/scc_error.json", "w") as file:
            json.dump(error_messages, file, indent=4)
    except Exception as e:
        print(f"input error: {e}")
        return api_error_response(503)

    return error_messages


@scc_bp.route("/api/v1/devices", methods=["GET"])
@requires_auth
def get_devices():
    """GET Device Information"""

    exclude_keys = ["ControlUnit", "PC1Error", "PC2Error", "LowCoolantLevelWarning"]
    rack_leakage_sensor_keys = [
        "RackLeakageSensor1Leak",
        "RackLeakageSensor1Broken",
        "RackLeakageSensor2Leak",
        "RackLeakageSensor2Broken",
    ]
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            start_addr = len(sensor_thrshd.keys()) * 2 + len(sensor_delay.keys())
            device_delay_count = len(device_delay.keys())

            r = client.read_holding_registers(1000 + start_addr, device_delay_count)

            for i, key in enumerate(devices.keys()):
                if key not in exclude_keys:
                    if key not in rack_leakage_sensor_keys:
                        devices[key]["DelayTime"] = r.registers[i]
                    else:
                        devices[key]["DelayTime"] = r.registers[i - 4]

    except Exception as e:
        print(f"read delay plc error: {e}")
        return api_error_response(503)

    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            start_addr = len(sensor_trap.keys()) * 2
            device_trap_count = len(device_trap.keys())
            r = client.read_coils((8192 + 2000 + start_addr), device_trap_count)

            for i, key in enumerate(devices.keys()):
                devices[key]["TrapEnabled"] = r.bits[i]
    except Exception as e:
        print(f"trap enable error: {e}")
        return api_error_response(503)

    try:
        if g.sensorData["error"]["pc1_error"]:
            devices["PC1Error"]["Status"] = "Error"
        else:
            devices["PC1Error"]["Status"] = "Good"

        if g.sensorData["error"]["pc2_error"]:
            devices["PC2Error"]["Status"] = "Error"
        else:
            devices["PC2Error"]["Status"] = "Good"
    except Exception as e:
        print(f"read new devices error: {e}")
        return api_error_response(503)

    try:
        inv_names = ["1", "2", "3"]
        for inv in inv_names:
            if g.sensorData["error"][f"Inv{inv}_Error"]:
                devices[f"Inv{inv}Error"]["Status"] = "Error"
            elif g.sensorData["value"][f"inv{inv}_freq"]:
                devices[f"Inv{inv}Error"]["Status"] = "Enabled"
            else:
                devices[f"Inv{inv}Error"]["Status"] = "Disabled"

        overload_names = ["1", "2", "3"]
        for o in overload_names:
            if g.sensorData["error"][f"Inv{o}_OverLoad"]:
                devices[f"Inv{o}Overload"]["Status"] = "Error"
            else:
                devices[f"Inv{o}Overload"]["Status"] = "Good"

        overload_names = ["1", "2"]
        for o in overload_names:
            if g.sensorData["error"][f"Fan_OverLoad{o}"]:
                devices[f"FanOverload{o}"]["Status"] = "Error"
            else:
                devices[f"FanOverload{o}"]["Status"] = "Good"

        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            if not client.connect():
                devices["ControlUnit"]["Status"] = "Error"
            else:
                devices["ControlUnit"]["Status"] = "Good"

        if g.sensorData["ats_status"]["ATS1"]:
            devices["ATS"]["Status"] = "Primary"
        elif g.sensorData["ats_status"]["ATS2"]:
            devices["ATS"]["Status"] = "Secondary"
        else:
            devices["ATS"]["Status"] = "OFF"
    except Exception as e:
        print(f"read ats plc error: {e}")
        return api_error_response(503)

    try:
        sensor_mapping = {
            "CoolantSupplyTemperatureBroken": "TempClntSply_broken",
            "CoolantSupplyTemperatureSpareBroken": "TempClntSplySpare_broken",
            "CoolantReturnTemperatureBroken": "TempClntRtn_broken",
            "CoolantReturnTemperatureSpareBroken": "TempClntRtnSpare_broken",
            "CoolantSupplyPressureBroken": "PrsrClntSply_broken",
            "CoolantSupplyPressureSpareBroken": "PrsrClntSplySpare_broken",
            "CoolantReturnPressureBroken": "PrsrClntRtn_broken",
            "CoolantReturnPressureSpareBroken": "PrsrClntRtnSpare_broken",
            "FilterInletPressureBroken": "PrsrFltIn_broken",
            "FilterOutletPressureBroken": "PrsrFltOut_broken",
            "CoolantFlowRateBroken": "Clnt_Flow_broken",
        }

        for k, v in sensor_mapping.items():
            devices[k]["Status"] = "Error" if g.sensorData["error"][v] else "Good"

    except Exception as e:
        print(f"read broken plc error: {e}")
        return api_error_response(503)

    try:
        sensor_mapping = {
            "Inv1SpeedComm": "Inv1_Com",
            "Inv2SpeedComm": "Inv2_Com",
            "Inv3SpeedComm": "Inv3_Com",
            # "CoolantFlowRateComm": "Clnt_Flow_Com",
            "AmbientTempComm": "Ambient_Temp_Com",
            "RelativeHumidComm": "Relative_Humid_Com",
            "DewPointComm": "Dew_Point_Com",
            "pHComm": "pH_Com",
            "ConductivityComm": "Cdct_Sensor_Com",
            "TurbidityComm": "Tbd_Com",
            "ATS1Comm": "ATS1_Com",
            "ATS2Comm": "ATS2_Com",
            "InstantPowerConsumptionComm": "Power_Meter_Com",
            "AverageCurrentComm": "Average_Current_Com",
            "Fan1Comm": "Fan1_Com",
            "Fan2Comm": "Fan2_Com",
            "Fan3Comm": "Fan3_Com",
            "Fan4Comm": "Fan4_Com",
            "Fan5Comm": "Fan5_Com",
            "Fan6Comm": "Fan6_Com",
            "Fan7Comm": "Fan7_Com",
            "Fan8Comm": "Fan8_Com",
        }

        for k, v in sensor_mapping.items():
            devices[k]["Status"] = "Error" if g.sensorData["error"][v] else "Good"
    except Exception as e:
        print(f"read comm plc error: {e}")
        return api_error_response(503)

    try:
        mapping = {
            "Leakage1Leak": "leakage1_leak",
            "Leakage1Broken": "leakage1_broken",
            "Level1": "level1",
            "Level2": "level2",
            "Level3": "level3",
            "Power24v1": "power24v1",
            "Power24v2": "power24v2",
            "Power12v1": "power12v1",
            "Power12v2": "power12v2",
            "MainMcError": "main_mc_error",
            "Fan1Error": "fan1_error",
            "Fan2Error": "fan2_error",
            "Fan3Error": "fan3_error",
            "Fan4Error": "fan4_error",
            "Fan5Error": "fan5_error",
            "Fan6Error": "fan6_error",
            "Fan7Error": "fan7_error",
            "Fan8Error": "fan8_error",
            "LowCoolantLevelWarning": "Low_Coolant_Level_Warning",
            "ControlUnit": "PLC",
        }

        for k, v in mapping.items():
            devices[k]["Status"] = "Error" if g.sensorData["error"][v] else "Good"

    except Exception as e:
        print(f"change status: {e}")

    try:
        mapping = {
            "RackLeakageSensor1Leak": "rack_leakage1_leak",
            "RackLeakageSensor1Broken": "rack_leakage1_broken",
            "RackLeakageSensor2Leak": "rack_leakage2_leak",
            "RackLeakageSensor2Broken": "rack_leakage2_broken",
        }
        for k, v in mapping.items():
            devices[k]["Status"] = "Error" if g.sensorData["rack"][v] else "Good"
    except Exception as e:
        print(f"change status: {e}")

    output = [d for d in devices.values()]

    try:
        with open("web/json/scc_device.json", "w") as file:
            json.dump(devices, file, indent=4)
    except Exception as e:
        return {"message": f"File Writing Error: {e}"}

    return output


@scc_bp.route("/api/v1/devices", methods=["PATCH"])
@requires_auth
def devices_set_trap_enable():
    """Set Device Trap Enable"""

    try:
        data = request.get_json(force=True)
    except Exception as e:
        print(f"device read error: {e}")
        return api_error_response(400)

    if not data or not data.get("Name") or data.get("Name") not in devices:
        return api_error_response(400)

    if data.get("TrapEnabled") is not None and not isinstance(
        data.get("TrapEnabled"), (bool)
    ):
        return api_error_response(400)

    if data.get("DelayTime") is not None and not isinstance(
        data.get("DelayTime"), (int)
    ):
        return api_error_response(400)

    name = data.get("Name", None)
    trap = data.get("TrapEnabled")
    delay = data.get("DelayTime")
    key = f"E_{name}"

    if trap is not None:
        try:
            with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                client.write_coils(trap_mapping[key], [trap])
        except Exception as e:
            print(f"change trap plc error: {e}")
            return api_error_response(503)

    if delay is not None:
        if delay > 30000:
            return api_error_response(400)
        else:
            try:
                sensor_delay_count = len(sensor_delay.keys())
                sensor_th_count = len(sensor_thrshd.keys()) * 2
                device_delay_start_addr = sensor_delay_count + sensor_th_count

                for i, key in enumerate(device_delay):
                    delay_key = f"Delay_{name}"
                    if delay_key == key:
                        with ModbusTcpClient(
                            host=modbus_host, port=modbus_port
                        ) as client:
                            client.write_registers(
                                (1000 + device_delay_start_addr + i), delay
                            )
            except Exception as e:
                print(f"update delay: {e}")
                return api_error_response(503)

    response_data = {"Name": name}

    settings = {"TrapEnabled": trap, "DelayTime": delay}

    filter_setting = {
        key: value for key, value in settings.items() if value is not None
    }

    if filter_setting:
        response_data.update(filter_setting)

    op_logger.info(f"Trap Enabled Setting updated successfully. {response_data} ")

    return jsonify(response_data)


@scc_bp.route("/api/v1/physical_asset")
@requires_auth
def get_physical_asset():
    """Get the physical asset information"""
    
    return physical_asset

@scc_bp.route("/api/v1/cdu")
@requires_auth
def get_fw_info():
    """Get the cdu information"""
    read_data_from_json()
    physical_asset["Model"]= fw_info["Model"]
    physical_asset["Version"]= fw_info["Version"]
    physical_asset["SerialNumber"]= fw_info["SN"]
    physical_asset["PartNumber"]= fw_info["PartNumber"]
    physical_asset["OperationMode"]= ctr_data["value"]["opMod"]
    physical_asset["CDUStatus"] = g.sensorData["cdu_status"]
    
    return physical_asset

@scc_bp.route("/api/v1/download_logs/error/<date_range>")
@requires_auth
def download_errorlogs_by_range(date_range):
    """Get Error Logs"""
    try:
        start_date_str, end_date_str = date_range.split("~")

        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

        today = datetime.now().date()

        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            files = os.listdir(f"{log_path}/logs/error")

            for file in files:
                try:
                    if file == "errorlog.log":
                        file_date = today
                    else:
                        file_date_str = file.rsplit(".", 1)[-1]
                        file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()

                    if start_date <= file_date <= end_date:
                        zip_file.write(f"{log_path}/logs/error/{file}", arcname=file)
                except (IndexError, ValueError):
                    continue

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"errorlogs_{start_date_str}_to_{end_date_str}.zip",
        )
    except Exception as e:
        
        return api_error_response()


@scc_bp.route("/api/v1/download_logs/operation/<date_range>")
@requires_auth
def download_oplogs_by_range(date_range):
    """Get Operation Logs"""

    start_date_str, end_date_str = date_range.split("~")

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    today = datetime.now().date()

    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        files = os.listdir(f"{log_path}/logs/operation")

        for file in files:
            try:
                if file == "oplog.log":
                    file_date = today
                    print(f"filedate{file_date}")
                else:
                    file_date_str = file.rsplit(".", 1)[-1]
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()
                    print(f"filedate{file_date}")

                if start_date <= file_date <= end_date:
                    zip_file.write(f"{log_path}/logs/operation/{file}", arcname=file)
            except (IndexError, ValueError):
                continue

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"oplogs_{start_date_str}_to_{end_date_str}.zip",
    )


@scc_bp.route("/api/v1/download_logs/sensor/<date_range>")
@requires_auth
def download_sensorlogs_by_range(date_range):
    """Get Sensor Logs"""

    start_date_str, end_date_str = date_range.split("~")

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    zip_buffer = BytesIO()

    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        files = os.listdir(f"{log_path}/logs/sensor")

        for file in files:
            try:
                file_date_str = file.rsplit(".")[-2]
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d")

                if start_date <= file_date <= end_date:
                    zip_file.write(f"{log_path}/logs/sensor/{file}", arcname=file)
            except (IndexError, ValueError):
                continue

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"sensorlogs_{start_date_str}_to_{end_date_str}.zip",
    )


@scc_bp.route("/api/v1/upload_zip", methods=["POST"])
@requires_auth
def upload_zip_scc():
    """從 URL 中獲取檔案路徑並處理檔案上傳"""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"status": "error", "message": "No file selected"}), 400

    if file.filename != "service.zip":
        return (
            jsonify(
                {"status": "error", "message": "Please upload correct file name"}
            ),
            400,
        )

    if file and file.filename.endswith(".zip"):
        zip_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        file.save(zip_path)

        preset_password = "Itgs50848614"

        try:
            with pyzipper.AESZipFile(
                zip_path, "r", encryption=pyzipper.WZ_AES
            ) as zip_ref:
                if not any([info.flag_bits & 0x1 for info in zip_ref.infolist()]):
                    zip_ref.close()
                    os.remove(zip_path)
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "A password-protected ZIP file is required",
                            }
                        ),
                        400,
                    )

                zip_ref.setpassword(preset_password.encode("utf-8"))

                try:
                    first_file_name = zip_ref.namelist()[0]
                    zip_ref.read(first_file_name)
                    print("ZIP file is password protected and password is correct.")
                except RuntimeError:
                    zip_ref.close()
                    os.remove(zip_path)
                    return (
                        jsonify({"status": "error", "message": "Invalid password"}),
                        400,
                    )

                zip_info = zip_ref.infolist()
                if len(zip_info) > 0:
                    folder_name = os.path.splitext(zip_info[0].filename)[0]
                else:
                    zip_ref.close()
                    os.remove(zip_path)
                    return (
                        jsonify(
                            {"status": "error", "message": "ZIP file is empty"}
                        ),
                        400,
                    )

                os.makedirs(upload_path, exist_ok=True)
                zip_ref.extractall(upload_path)

        except RuntimeError as e:
            print(f"runtime error: {e}")
            os.remove(zip_path)
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid password or invalid ZIP file",
                    }
                ),
                400,
            )
        except Exception as e:
            print(f"Error extracting ZIP: {e}")
            os.remove(zip_path)
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "An error occurred while processing the ZIP file",
                    }
                ),
                500,
            )
        finally:
            if "zip_ref" in locals():
                zip_ref.close()

        os.remove(zip_path)

        try:
            script_path = os.path.join(snmp_path, "restart.sh")
            result = subprocess.run(
                ["sudo", "bash", script_path],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"Script output:{result.stdout}")
        except subprocess.CalledProcessError as e:
            print(f"Error executing script: {e}")
            print(f"Script error output:{e.stderr}")

        return (
            jsonify(
                {"status": "success", "message": "ZIP file uploaded successfully, Please restart PC ."}
            ),
            200,
        )

    return (
        jsonify(
            {"status": "error", "message": "Wrong file type or missing password"}
        ),
        400,
    )

@scc_bp.route("/api/v1/reboot", methods=["GET"])
@requires_auth
def restart():
    def delayed_reboot():
        time.sleep(5)  # 延遲 5 秒，讓 response 有時間送出
        subprocess.run(["sudo", "reboot"], check=True)

    threading.Thread(target=delayed_reboot).start()
    return "Restarting System"

@scc_bp.route("/api/v1/graceful_reboot", methods=["GET"])
@requires_auth
def graceful_reboot():
    def delayed_reboot():
        time.sleep(5)  # 延遲 5 秒，讓 response 有時間送出
        subprocess.run(["sudo", "systemctl","reboot"], check=True)

    threading.Thread(target=delayed_reboot).start()
    return "Restarting System"

@scc_bp.route("/api/v1/snmp_setting", methods=["PATCH"])
@requires_auth
def snmp_setting():
    """Set SNMP Setting"""

    switch = request.json["V3_Switch"]
    name = request.json.get("Community")
    trapIp = request.json.get("Trap_Ip_Address")
    if not isinstance(switch, bool):
        return {"message": "Invalid input. V3 Switch accepts boolean values only."}

    if len(name) > 8:
        return jsonify(
            {"message": "Invalid input. Community name cannot exceed 8 characters."}
        )

    if trapIp and not is_valid_ip(trapIp):
        return jsonify(
            {"message": "Invalid input. Trap IP Address must be a valid IPv4 address."}
        )
    snmp_data["trap_ip_address"] = trapIp
    snmp_data["read_community"] = name
    snmp_data["v3_switch"] = switch
    with open(f"{snmp_path}/snmp/snmp.json", "w") as json_file:
        json.dump(snmp_data, json_file)

    op_logger.info("SNMP Setting updated successfully. ")
    return {
        "message": "SNMP Setting updated successfully",
        "Trap Ip Address": trapIp,
        "Read Community": name,
        "V3 Switch": switch,
    }


@scc_bp.route("/api/v1/get_snmp_setting")

def get_snmp_setting():
    """Get SNMP Setting"""
    with open(f"{snmp_path}/snmp/snmp.json", "r") as file:
        data = json.load(file)
    snmp_data["trap_ip_address"] = data["trap_ip_address"]

    return jsonify(snmp_data)


# @scc_bp.route("/api/v1/update_password", methods=["POST"])
# @requires_auth
# def update_password():

#     password = request.json["password"]
#     last_pwd = request.json["last_pwd"]
#     passwordcfm = request.json["passwordcfm"]

#     if passwordcfm != password:
#         return jsonify(
#             {"status": "error", "message": "Passwords do not match. Please re-enter."}
#         )

#     if not all([password, last_pwd, passwordcfm]):
#         return jsonify(
#             {
#                 "status": "error",
#                 "message": "Please fill out all password fields",
#             }
#         )

#     if last_pwd != USER_DATA["admin"]:
#         return jsonify(
#             {
#                 "status": "error",
#                 "message": "Last password is incorrect",
#             }
#         )

#     USER_DATA["admin"] = password

#     set_key(f"{web_path}/.env", "ADMIN", USER_DATA["admin"])
#     os.chmod(f"{web_path}/.env", 0o666)
#     op_logger.info("User password updated successfully")
#     return jsonify({"status": "success", "message": "Password Updated Successfully"})



class NetworkConfigurator:
    def __init__(self, interface_ip_map):
        self.interface_ip_map = interface_ip_map

    def set_static_ips(self, gateway="192.168.3.1", prefix="24", dns = "8.8.8.8"):
        result = {}
        for name, ip in self.interface_ip_map.items():
            try:
                subprocess.run([
                    "nmcli", "connection", "modify", name,
                    "ipv4.addresses", f"{ip}/{prefix}",
                    "ipv4.gateway", gateway,
                    "ipv4.dns", dns,
                    "ipv4.method", "manual",
                    "connection.autoconnect", "yes"
                ], check=True)

                subprocess.run(["nmcli", "connection", "down", name], check=True)
                subprocess.run(["nmcli", "connection", "up", name], check=True)

                result[name] = "Success"
            except subprocess.CalledProcessError as e:
                result[name] = f"Failed: {e}"
        return result

@scc_bp.route("/api/v1/set_network", methods=["POST"])
@requires_auth

def set_network():
    try:
        data = request.json  # e.g. { "ethernet1": "192.168.3.102", ... }
        configurator = NetworkConfigurator(data)
        result = configurator.set_static_ips()
        return jsonify({"status": "ok", "result": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



def get_scc_data():
    while True:
        try:
            sensor_trap_reg = len(sensor_trap.keys()) * 2
            e_trap_reg = len(device_trap.keys())
            with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                r = client.read_coils((8192 + 2000), sensor_trap_reg)

                for x, key in enumerate(trap_enable_key.keys()):
                    trap_enable_key[key] = r.bits[x]

                for key in sensor_value_data:
                    w_key = f"W_{key}"
                    a_key = f"A_{key}"
                    if key != "HeatCapacity" and key != "InstantPowerConsumption":
                        sensor_trap[key]["Warning"] = trap_enable_key.get(w_key, None)
                        sensor_trap[key]["Alert"] = trap_enable_key.get(a_key, None)
        except Exception as e:
            print(f"[interval] read trap plc error: {e}")

        try:
            with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                r = client.read_coils((8192 + 2000 + sensor_trap_reg), e_trap_reg)

                for i, key in enumerate(device_trap.keys()):
                    device_trap[key] = r.bits[i]
        except Exception as e:
            print(f"[interval] trap enable error: {e}")

        scc_data = {
            "sensor_value_data": sensor_trap,
            "devices": device_trap,
        }

        try:
            with open(f"{web_path}/json/scc_data.json", "w") as file:
                json.dump(scc_data, file, indent=4)
        except Exception as e:
            print(f"input error: {e}")

        time.sleep(2)


scc_thread = threading.Thread(target=get_scc_data)
scc_thread.daemon = True
scc_thread.start()
