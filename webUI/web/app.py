# 標準函式庫
import csv
import datetime as dt
from datetime import datetime
import glob
import ipaddress
import json
import logging
import math
import os
import platform
import shutil
import struct
import subprocess
import threading
import time
import zipfile
from collections import OrderedDict
from io import BytesIO

# 第三方套件
import requests
import pyzipper
from dotenv import load_dotenv, set_key
from cryptography.fernet import Fernet, InvalidToken
from flask import (
    Flask, g, jsonify, redirect, render_template, request, 
    send_from_directory, send_file, session
)
from flask_login import (
    LoginManager, current_user, login_required, logout_user
)
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from logging.handlers import RotatingFileHandler
from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
# from mylib.services.debug_service import DebugService



load_dotenv()
app = Flask(__name__)

log_path = os.getcwd()
web_path = f"{log_path}/web"
snmp_path = os.path.dirname(log_path)

upload_path = "/home/user/"
app.config["UPLOAD_FOLDER"] = upload_path

key = os.environ.get("SECRET_KEY")
app.secret_key = key
cipher_suite = Fernet(key.encode())

if platform.system() == "Linux":
    onLinux = True
else:
    onLinux = False

if onLinux:
    modbus_host = os.environ.get("MODBUS_IP")
else:
    # modbus_host = "192.168.3.250"
    modbus_host = "127.0.0.1"

modbus_port = 502
modbus_slave_id = 1
modbus_address = 0

warning_toggle = os.environ.get("WARNING_TOGGLE") == "True"
alert_toggle = os.environ.get("ALERT_TOGGLE") == "True"
error_toggle = os.environ.get("ERROR_TOGGLE") == "True"
repeat = os.environ.get("NOLOGREPEAT") == "False"
debug = os.environ.get("NODEBUG") == "False"

previous_warning_states = {}
previous_alert_states = {}
previous_error_states = {}
previous_rack_states = {}
prev_plc_error = False

if onLinux:
    from web.mylib.services.debug_service import DebugService
else:
    from mylib.services.debug_service import DebugService

if onLinux:
    from web.auth import (
        USER_DATA,
        User,
        auth_bp,
        user_login_info,
    )
else:
    from auth import (
        USER_DATA,
        User,
        auth_bp,
        user_login_info,
    )
# print(f"admin_password =  {os.getenv("ADMIN")}")
app.register_blueprint(auth_bp)

if onLinux:
    from web.scc_app import scc_bp
else:
    from scc_app import scc_bp

app.register_blueprint(scc_bp)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/"

journal_dir = f"{log_path}/logs/journal"
if not os.path.exists(journal_dir):
    os.makedirs(journal_dir)

max_bytes = 4 * 1024 * 1024 * 1024
backup_count = 1

file_name = "journal.log"
log_file = os.path.join(journal_dir, file_name)
journal_handler = RotatingFileHandler(
    log_file,
    maxBytes=max_bytes,
    backupCount=backup_count,
    encoding="UTF-8",
    delay=False,
)

formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
journal_handler.setFormatter(formatter)

journal_logger = logging.getLogger("journal_logger")
journal_logger.setLevel(logging.INFO)
journal_logger.addHandler(journal_handler)

log_dir = f"{log_path}/logs/error"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

file_name = "errorlog.log"
log_file = os.path.join(log_dir, file_name)
errlog_handler = ConcurrentTimedRotatingFileHandler(
    log_file,
    when="midnight",
    backupCount=1100,
    encoding="UTF-8",
)
errlog_handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
errlog_handler.setFormatter(formatter)
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(errlog_handler)

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


@login_manager.user_loader
def load_user(user_id):
    users = USER_DATA
    if user_id in users:
        user_identity["ID"] = user_id
        return User(user_id)
    return None



pc2_active = False
get_data_timeout = 5
tcount_log = 0
error_data = []
signal_records = []
downtime_signal_records = []
imperial_thrshd_factory = {}
imperial_valve_factory = {}
mode_input = {}
export_data = {}


sensorData = {
    "value": {
        "temp_clntSply": 0,
        "temp_clntSplySpare": 0,
        "temp_clntRtn": 0,
        "temp_clntRtnSpare": 0,
        "space": 0,
        "prsr_clntSply": 0,
        "prsr_clntSplySpare": 0,
        "prsr_clntRtn": 0,
        "prsr_clntRtnSpare": 0,
        "prsr_fltIn": 0,
        "prsr_fltOut": 0,
        "clnt_flow": 0,
        "ambient_temp": 0,
        "relative_humid": 0,
        "dew_point": 0,
        "pH": 0,
        "cdct": 0,
        "tbd": 0,
        "power": 0,
        "AC": 0,
        "inv1_freq": 0,
        "inv2_freq": 0,
        "inv3_freq": 0,
        "heat_capacity": 0,
        "fan_freq1": 0,
        "fan_freq2": 0,
        "fan_freq3": 0,
        "fan_freq4": 0,
        "fan_freq5": 0,
        "fan_freq6": 0,
        "fan_freq7": 0,
        "fan_freq8": 0,
    },
    "warning_notice": {
        "temp_clntSply": False,
        "temp_clntSplySpare": False,
        "temp_clntRtn": False,
        "temp_clntRtnSpare": False,
        "prsr_clntSply": False,
        "prsr_clntSplySpare": False,
        "prsr_clntRtn": False,
        "prsr_clntRtnSpare": False,
        "prsr_fltIn": False,
        "prsr_fltOut": False,
        "clnt_flow": False,
        "ambient_temp": False,
        "relative_humid": False,
        "dew_point": False,
        "pH": False,
        "cdct": False,
        "tbd": False,
        "AC": False,
    },
    "alert_notice": {
        "temp_clntSply": False,
        "temp_clntSplySpare": False,
        "temp_clntRtn": False,
        "temp_clntRtnSpare": False,
        "prsr_clntSply": False,
        "prsr_clntSplySpare": False,
        "prsr_clntRtn": False,
        "prsr_clntRtnSpare": False,
        "prsr_fltIn": False,
        "prsr_fltOut": False,
        "clnt_flow": False,
        "ambient_temp": False,
        "relative_humid": False,
        "dew_point": False,
        "pH": False,
        "cdct": False,
        "tbd": False,
        "AC": False,
    },
    "warning": {
        "temp_clntSply_high": False,
        "temp_clntSplySpare_high": False,
        "temp_clntRtn_high": False,
        "temp_clntRtnSpare_high": False,
        "prsr_clntSply_high": False,
        "prsr_clntSplySpare_high": False,
        "prsr_clntRtn_high": False,
        "prsr_clntRtnSpare_high": False,
        "prsr_fltIn_low": False,
        "prsr_fltIn_high": False,
        "prsr_fltOut_high": False,
        "clnt_flow_low": False,
        "ambient_temp_low": False,
        "ambient_temp_high": False,
        "relative_humid_low": False,
        "relative_humid_high": False,
        "dew_point_low": False,
        "pH_low": False,
        "pH_high": False,
        "cdct_low": False,
        "cdct_high": False,
        "tbd_low": False,
        "tbd_high": False,
        "AC_high": False,
    },
    "alert": {
        "temp_clntSply_high": False,
        "temp_clntSplySpare_high": False,
        "temp_clntRtn_high": False,
        "temp_clntRtnSpare_high": False,
        "prsr_clntSply_high": False,
        "prsr_clntSplySpare_high": False,
        "prsr_clntRtn_high": False,
        "prsr_clntRtnSpare_high": False,
        "prsr_fltIn_low": False,
        "prsr_fltIn_high": False,
        "prsr_fltOut_high": False,
        "clnt_flow_low": False,
        "ambient_temp_low": False,
        "ambient_temp_high": False,
        "relative_humid_low": False,
        "relative_humid_high": False,
        "dew_point_low": False,
        "pH_low": False,
        "pH_high": False,
        "cdct_low": False,
        "cdct_high": False,
        "tbd_low": False,
        "tbd_high": False,
        "AC_high": False,
    },
    "error": {
        "Inv1_OverLoad": False,
        "Inv2_OverLoad": False,
        "Inv3_OverLoad": False,
        "Fan_OverLoad1": False,
        "Fan_OverLoad2": False,
        "Inv1_Error": False,
        "Inv2_Error": False,
        "Inv3_Error": False,
        "ATS1": False,
        "Inv1_Com": False,
        "Inv2_Com": False,
        "Inv3_Com": False,
        # "Clnt_Flow_Com": False,
        "Ambient_Temp_Com": False,
        "Relative_Humid_Com": False,
        "Dew_Point_Com": False,
        "pH_Com": False,
        "Cdct_Sensor_Com": False,
        "Tbd_Com": False,
        "ATS1_Com": False,
        "ATS2_Com": False,
        "Power_Meter_Com": False,
        "Average_Current_Com": False,
        "Fan1_Com": False,
        "Fan2_Com": False,
        "Fan3_Com": False,
        "Fan4_Com": False,
        "Fan5_Com": False,
        "Fan6_Com": False,
        "Fan7_Com": False,
        "Fan8_Com": False,
        "TempClntSply_broken": False,
        "TempClntSplySpare_broken": False,
        "TempClntRtn_broken": False,
        "TempClntRtnSpare_broken": False,
        "PrsrClntSply_broken": False,
        "PrsrClntSplySpare_broken": False,
        "PrsrClntRtn_broken": False,
        "PrsrClntRtnSpare_broken": False,
        "PrsrFltIn_broken": False,
        "PrsrFltOut_broken": False,
        "Clnt_Flow_broken": False,
        "pc1_error": False,
        "pc2_error": False,
        "leakage1_leak": False,
        "leakage1_broken": False,
        "level1": False,
        "level2": False,
        "level3": False,
        "power24v1": False,
        "power24v2": False,
        "power12v1": False,
        "power12v2": False,
        "main_mc_error": False,
        "fan1_error": False,
        "fan2_error": False,
        "fan3_error": False,
        "fan4_error": False,
        "fan5_error": False,
        "fan6_error": False,
        "fan7_error": False,
        "fan8_error": False,
        "Low_Coolant_Level_Warning": False,
        "PLC": False,
    },
    "rack": {
        "rack1_broken": False,
        "rack2_broken": False,
        "rack3_broken": False,
        "rack4_broken": False,
        "rack5_broken": False,
        "rack1_leak_com": False,
        "rack2_leak_com": False,
        "rack3_leak_com": False,
        "rack4_leak_com": False,
        "rack5_leak_com": False,
        "rack1_leak": False,
        "rack2_leak": False,
        "rack3_leak": False,
        "rack4_leak": False,
        "rack5_leak": False,
        "rack1_status_com": False,
        "rack2_status_com": False,
        "rack3_status_com": False,
        "rack4_status_com": False,
        "rack5_status_com": False,
        "rack1_error": False,
        "rack2_error": False,
        "rack3_error": False,
        "rack4_error": False,
        "rack5_error": False,
        "rack6_error": False,
        "rack7_error": False,
        "rack8_error": False,
        "rack9_error": False,
        "rack10_error": False,
        "rack_leakage1_leak": False,
        "rack_leakage1_broken": False,
        "rack_leakage2_leak": False,
        "rack_leakage2_broken": False,
        "rack_leakage3_leak": False,
        "rack_leakage3_broken": False,
        "rack_leakage4_leak": False,
        "rack_leakage4_broken": False,
        "rack_leakage5_leak": False,
        "rack_leakage5_broken": False,
    },
    "err_log": {
        "warning": {
            "temp_clntSply_high": "M100 Coolant Supply Temperature Over Range (High) Warning (T1)",
            "temp_clntSplySpare_high": "M101 Coolant Supply Temperature Spare Over Range (High) Warning (T1sp)",
            "temp_clntRtn_high": "M102 Coolant Return Temperature Over Range (High) Warning (T2)",
            "temp_clntRtnSpare_high": "M103 Coolant Return Temperature Over Range Spare (High) Warning (T2sp)",
            "prsr_clntSply_high": "M104 Coolant Supply Pressure Over Range (High) Warning (P1)",
            "prsr_clntSplySpare_high": "M105 Coolant Supply Pressure Spare Over Range (High) Warning (P1sp)",
            "prsr_clntRtn_high": "M106 Coolant Return Pressure Over Range (High) Warning (P2)",
            "prsr_clntRtnSpare_high": "M107 Coolant Return Pressure Spare Over Range (High) Warning (P2sp)",
            "prsr_fltIn_low": "M108 Filter Inlet Pressure Over Range (Low) Warning (P3)",
            "prsr_fltIn_high": "M109 Filter Inlet Pressure Over Range (High) Warning (P3)",
            "prsr_fltOut_high": "M110 Filter Delta P Over Range (High) Warning (P3 - P4)",
            "clnt_flow_low": "M111 Coolant Flow Rate (Low) Warning (F1)",
            "ambient_temp_low": "M112 Ambient Temperature Over Range (Low) Warning (T a)",
            "ambient_temp_high": "M113 Ambient Temperature Over Range (High) Warning (T a)",
            "relative_humid_low": "M114 Relative Humidity Over Range (Low) Warning (RH)",
            "relative_humid_high": "M115 Relative Humidity Over Range (High) Warning (RH)",
            "dew_point_low": "M116 Condensation Warning (T Dp)",
            "pH_low": "M117 pH Over Range (Low) Warning (PH)",
            "pH_high": "M118 pH Over Range (High) Warning (PH)",
            "cdct_low": "M119 Conductivity Over Range (Low) Warning (CON)",
            "cdct_high": "M120 Conductivity Over Range (High) Warning (CON)",
            "tbd_low": "M121 Turbidity Over Range (Low) Warning (Tur)",
            "tbd_high": "M122 Turbidity Over Range (High) Warning (Tur)",
            "AC_high": "M123 Average Current Over Range (High) Warning",
        },
        "alert": {
            "temp_clntSply_high": "M200 Coolant Supply Temperature Over Range (High) Alert (T1)",
            "temp_clntSplySpare_high": "M201 Coolant Supply Temperature Spare Over Range (High) Alert (T1sp)",
            "temp_clntRtn_high": "M202 Coolant Return Temperature Over Range (High) Alert (T2)",
            "temp_clntRtnSpare_high": "M203 Coolant Return Temperature Over Range Spare (High) Alert (T2sp)",
            "prsr_clntSply_high": "M204 Coolant Supply Pressure Over Range (High) Alert (P1)",
            "prsr_clntSplySpare_high": "M205 Coolant Supply Pressure Spare Over Range (High) Alert (P1sp)",
            "prsr_clntRtn_high": "M206 Coolant Return Pressure Over Range (High) Alert (P2)",
            "prsr_clntRtnSpare_high": "M207 Coolant Return Pressure Spare Over Range (High) Alert (P2sp)",
            "prsr_fltIn_low": "M208 Filter Inlet Pressure Over Range (Low) Alert (P3)",
            "prsr_fltIn_high": "M209 Filter Inlet Pressure Over Range (High) Alert (P3)",
            "prsr_fltOut_high": "M210 Filter Delta P Over Range (High) Alert (P3 - P4)",
            "clnt_flow_low": "M211 Coolant Flow Rate (Low) Alert (F1)",
            "ambient_temp_low": "M212 Ambient Temperature Over Range (Low) Alert (T a)",
            "ambient_temp_high": "M213 Ambient Temperature Over Range (High) Alert (T a)",
            "relative_humid_low": "M214 Relative Humidity Over Range (Low) Alert (RH)",
            "relative_humid_high": "M215 Relative Humidity Over Range (High) Alert (RH)",
            "dew_point_low": "M216 Condensation Alert (T Dp)",
            "pH_low": "M217 pH Over Range (Low) Alert (PH)",
            "pH_high": "M218 pH Over Range (High) Alert (PH)",
            "cdct_low": "M219 Conductivity Over Range (Low) Alert (CON)",
            "cdct_high": "M220 Conductivity Over Range (High) Alert (CON)",
            "tbd_low": "M221 Turbidity Over Range (Low) Alert (Tur)",
            "tbd_high": "M222 Turbidity Over Range (High) Alert (Tur)",
            "AC_high": "M223 Average Current Over Range (High) Alert",
        },
        "error": {
            "Inv1_OverLoad": "M300 Coolant Pump1 Inverter Overload",
            "Inv2_OverLoad": "M301 Coolant Pump2 Inverter Overload",
            "Inv3_OverLoad": "M302 Coolant Pump3 Inverter Overload",
            "Fan_OverLoad1": "M303 Fan Group1 Overload",
            "Fan_OverLoad2": "M304 Fan Group2 Overload",
            "Inv1_Error": "M305 Coolant Pump1 Inverter Error",
            "Inv2_Error": "M306 Coolant Pump2 Inverter Error",
            "Inv3_Error": "M307 Coolant Pump3 Inverter Error",
            "ATS1": "M308 Primary Power Broken",
            "Inv1_Com": "M309 Inverter1 Communication Error",
            "Inv2_Com": "M310 Inverter2 Communication Error",
            "Inv3_Com": "M311 Inverter3 Communication Error",
            # "Clnt_Flow_Com": "M312 Coolant Flow (F1) Meter Communication Error",
            "Ambient_Temp_Com": "M313 Ambient Sensor (Ta, RH, TDp) Communication Error",
            "Relative_Humid_Com": "M314 Relative Humidity (RH) Communication Error",
            "Dew_Point_Com": "M315 Dew Point Temperature (TDp) Communication Error",
            "pH_Com": "M316 pH (PH) Sensor Communication Error",
            "Cdct_Sensor_Com": "M317 Conductivity (CON) Sensor Communication Error",
            "Tbd_Com": "M318 Turbidity (Tur) Sensor Communication Error",
            "ATS1_Com": "M319 ATS Communication Error",
            "ATS2_Com": "M320 ATS 2 Communication Error",
            "Power_Meter_Com": "M321 Power Meter Communication Error",
            "Average_Current_Com": "M322 Average Current Communication Error",
            "Fan1_Com": "M323 Fan 1 Communication Error",
            "Fan2_Com": "M324 Fan 2 Communication Error",
            "Fan3_Com": "M325 Fan 3 Communication Error",
            "Fan4_Com": "M326 Fan 4 Communication Error",
            "Fan5_Com": "M327 Fan 5 Communication Error",
            "Fan6_Com": "M328 Fan 6 Communication Error",
            "Fan7_Com": "M329 Fan 7 Communication Error",
            "Fan8_Com": "M330 Fan 8 Communication Error",
            "TempClntSply_broken": "M331 Coolant Supply Temperature (T1) Broken Error",
            "TempClntSplySpare_broken": "M332 Coolant Supply Temperature Spare (T1sp) Broken Error",
            "TempClntRtn_broken": "M333 Coolant Return Temperature (T2) Broken Error",
            "TempClntRtnSpare_broken": "M334 Coolant Return Temperature Spare (T2sp) Broken Error",
            "PrsrClntSply_broken": "M335 Coolant Supply Pressure (P1) Broken Error",
            "PrsrClntSplySpare_broken": "M336 Coolant Supply Pressure Spare (P1sp) Broken Error",
            "PrsrClntRtn_broken": "M337 Coolant Return Pressure (P2) Broken Error",
            "PrsrClntRtnSpare_broken": "M338 Coolant Return Pressure Spare (P2sp) Broken Error",
            "PrsrFltIn_broken": "M339 Filter Inlet Pressure (P3) Broken Error",
            "PrsrFltOut_broken": "M340 Filter Outlet Pressure (P4) Broken Error",
            "Clnt_Flow_broken": "M341 Coolant Flow Rate (F1) Broken Error",
            "pc1_error": "M342 PC1 Error",
            "pc2_error": "M343 PC2 Error",
            "leakage1_leak": "M344 Leakage 1 Leak Error",
            "leakage1_broken": "M345 Leakage 1 Broken Error",
            "level1": "M346 Coolant Level 1 Error",
            "level2": "M347 Coolant Level 2 Error",
            "level3": "M348 Coolant Level 3 Error",
            "power24v1": "M349 24V Power Supply 1 Error",
            "power24v2": "M350 24V Power Supply 2 Error",
            "power12v1": "M351 12V Power Supply 1 Error",
            "power12v2": "M352 12V Power Supply 2 Error",
            "main_mc_error": "M353 Main MC Status Error",
            "fan1_error": "M354 FAN 1 Alarm Status Error",
            "fan2_error": "M355 FAN 2 Alarm Status Error",
            "fan3_error": "M356 FAN 3 Alarm Status Error",
            "fan4_error": "M357 FAN 4 Alarm Status Error",
            "fan5_error": "M358 FAN 5 Alarm Status Error",
            "fan6_error": "M359 FAN 6 Alarm Status Error",
            "fan7_error": "M360 FAN 7 Alarm Status Error",
            "fan8_error": "M361 FAN 8 Alarm Status Error",
            "Low_Coolant_Level_Warning": "M362 Stop Due to Low Coolant Level",
            "PLC": "M363 PLC Communication Broken Error",
        },
        "rack": {
            "rack1_broken": "M400 Rack1 broken",
            "rack2_broken": "M401 Rack2 broken",
            "rack3_broken": "M402 Rack3 broken",
            "rack4_broken": "M403 Rack4 broken",
            "rack5_broken": "M404 Rack5 broken",
            "rack1_leak_com": "M405 Rack1 Leakage Communication Error",
            "rack2_leak_com": "M406 Rack2 Leakage Communication Error",
            "rack3_leak_com": "M407 Rack3 Leakage Communication Error",
            "rack4_leak_com": "M408 Rack4 Leakage Communication Error",
            "rack5_leak_com": "M409 Rack5 Leakage Communication Error",
            "rack1_leak": "M410 Rack1 leakage",
            "rack2_leak": "M411 Rack2 leakage",
            "rack3_leak": "M412 Rack3 leakage",
            "rack4_leak": "M413 Rack4 leakage",
            "rack5_leak": "M414 Rack5 leakage",
            "rack1_status_com": "M415 Rack1 Status Communication Error",
            "rack2_status_com": "M416 Rack2 Status Communication Error",
            "rack3_status_com": "M417 Rack3 Status Communication Error",
            "rack4_status_com": "M418 Rack4 Status Communication Error",
            "rack5_status_com": "M419 Rack5 Status Communication Error",
            "rack1_error": "M420 Rack1 error",
            "rack2_error": "M421 Rack2 error",
            "rack3_error": "M422 Rack3 error",
            "rack4_error": "M423 Rack4 error",
            "rack5_error": "M424 Rack5 error",
            "rack6_error": "M425 Rack6 error",
            "rack7_error": "M426 Rack7 error",
            "rack8_error": "M427 Rack8 error",
            "rack9_error": "M428 Rack9 error",
            "rack10_error": "M429 Rack10 error",
            "rack_leakage1_leak": "M430 Rack Leakage Sensor 1 Leak",
            "rack_leakage1_broken": "M431 Rack Leakage Sensor 1 Broken",
            "rack_leakage2_leak": "M432 Rack Leakage Sensor 2 Leak",
            "rack_leakage2_broken": "M433 Rack Leakage Sensor 2 Broken",
            "rack_leakage3_leak": "M434 Rack Leakage Sensor 3 Leak",
            "rack_leakage3_broken": "M435 Rack Leakage Sensor 3 Broken",
            "rack_leakage4_leak": "M436 Rack Leakage Sensor 4 Leak",
            "rack_leakage4_broken": "M437 Rack Leakage Sensor 4 Broken",
            "rack_leakage5_leak": "M438 Rack Leakage Sensor 5 Leak",
            "rack_leakage5_broken": "M439 Rack Leakage Sensor 5 Broken",
        },
    },
    "unit": {
        "unit_temp": "",
        "unit_pressure": "",
        "unit_flow": "",
    },
    "filter": {"all_filter_sw": False},

    "collapse": {
        "t1sp_adjust_zero": False,
        "p1sp_adjust_zero": False,
        "p2sp_adjust_zero": False,
        "t1_broken": False,
        "p1_broken": False,
        "p2_broken": False,
        "t1sp_show_final": False,
        "p1sp_show_final": False,
        "p2sp_show_final": False,
    },

    "rack_status": {
        "rack1_status": 0,
        "rack2_status": 0,
        "rack3_status": 0,
        "rack4_status": 0,
        "rack5_status": 0,
        "rack6_status": 0,
        "rack7_status": 0,
        "rack8_status": 0,
        "rack9_status": 0,
        "rack10_status": 0,
    },
    "rack_no_connection": {
        "rack1_status": False,
        "rack2_status": False,
        "rack3_status": False,
        "rack4_status": False,
        "rack5_status": False,
        "rack6_status": False,
        "rack7_status": False,
        "rack8_status": False,
        "rack9_status": False,
        "rack10_status": False,
        "rack1_leak": False,
        "rack2_leak": False,
        "rack3_leak": False,
        "rack4_leak": False,
        "rack5_leak": False,
        "rack6_leak": False,
        "rack7_leak": False,
        "rack8_leak": False,
        "rack9_leak": False,
        "rack10_leak": False,
    },
    "rack_leak": {
        "rack1_leak": False,
        "rack2_leak": False,
        "rack3_leak": False,
        "rack4_leak": False,
        "rack5_leak": False,
        "rack6_leak": False,
        "rack7_leak": False,
        "rack8_leak": False,
        "rack9_leak": False,
        "rack10_leak": False,
    },
    "rack_broken": {
        "rack1_broken": False,
        "rack2_broken": False,
        "rack3_broken": False,
        "rack4_broken": False,
        "rack5_broken": False,
        "rack6_broken": False,
        "rack7_broken": False,
        "rack8_broken": False,
        "rack9_broken": False,
        "rack10_broken": False,
    },
    "rack_prev": {
        "rack1": False,
        "rack2": False,
        "rack3": False,
        "rack4": False,
        "rack5": False,
        "rack6": False,
        "rack7": False,
        "rack8": False,
        "rack9": False,
        "rack10": False,
    },
    "ats_status": {
        "ATS1": False,
        "ATS2": False,
    },
    "level_sw": {
        "level1": None,
        "level2": None,
        "level3": None,
        "power24v1": None,
        "power24v2": None,
        "power12v1": None,
        "power12v2": None,
    },
    "mc": {
        "mc1_sw": False,
        "mc2_sw": False,
        "mc3_sw": False,
        "fan_mc1": False,
        "fan_mc2": False,
    },
    "cdu_status": False,
    # 測試用
    "eletricity": {
        "average_voltage": 0,
        "apparent_power": 0,
    },
    "opMod": "Auto",
    "plc_version": "",
    "temporary_data": {
        "command_pressure": 0,
        "feedback_pressure": 0,
        "pressure_output": 0,
        "command_temperature": 0,
        "feedback_temperature": 0,
        "temperature_output": 0,
    },
    "fan_power": {
        "Fan1": 0,
        "Fan2": 0,
        "Fan3": 0,
        "Fan4": 0,
        "Fan5": 0,
        "Fan6": 0,
        "Fan7": 0,
        "Fan8": 0,
    },
    "fan_rpm": {
        "Fan1": 0,
        "Fan2": 0,
        "Fan3": 0,
        "Fan4": 0,
        "Fan5": 0,
        "Fan6": 0,
        "Fan7": 0,
        "Fan8": 0,
    },
}

ctr_data = {
    "value": {
        "opMod": "manual",
        "oil_temp_set": 0,
        "oil_pressure_set": 0,
        "pump_speed": 0,
        "pump1_check": 0,
        "pump2_check": 0,
        "pump3_check": 0,
        "fan_speed": 0,
        "p_swap": 0,
        "resultMode": "Auto",
        "resultTemp": 0,
        "resultPressure": 0,
        "resultPS": 0,
        "resultP1": 0,
        "resultP2": 0,
        "resultP3": 0,
        "resultFan": 0,
        "resultSwap": 0,
        "resultFan1": False,
        "resultFan2": False,
        "resultFan3": False,
        "resultFan4": False,
        "resultFan5": False,
        "resultFan6": False,
        "resultFan7": False,
        "resultFan8": False,
        "fan1_check": False,
        "fan2_check": False,
        "fan3_check": False,
        "fan4_check": False,
        "fan5_check": False,
        "fan6_check": False,
        "fan7_check": False,
        "fan8_check": False,
    },
    "text": {
        "Pump1_run_time": 0,
        "Pump2_run_time": 0,
        "Pump3_run_time": 0,
        "Fan1_run_time": 0,
        "Fan2_run_time": 0,
        "Fan3_run_time": 0,
        "Fan4_run_time": 0,
        "Fan5_run_time": 0,
        "Fan6_run_time": 0,
        "Fan7_run_time": 0,
        "Fan8_run_time": 0,
        "Filter_run_time": 0,
    },
    "mc": {
        "mc1_sw": False,
        "mc2_sw": False,
        "mc3_sw": False,
        "resultMC1": False,
        "resultMC2": False,
        "resultMC3": False,
        "fan_mc1": False,
        "fan_mc2": False,
        "fan_mc1_result": False,
        "fan_mc2_result": False,
    },
    "inv": {
        "inv1": False,
        "inv2": False,
        "inv3": False,
        "fan1": False,
        "fan2": False,
        "fan3": False,
        "fan4": False,
        "fan5": False,
        "fan6": False,
        "fan7": False,
        "fan8": False,
    },
    "checkbox": {"filter_unlock_sw": True, "all_filter_sw": False},
    "unit": {"unit_temp": "", "unit_prsr": ""},

    "filter": {
        "f1": 0,
        "f2": 0,
        "f3": 0,
        "f4": 0,
        "f5": 0,
    },
    "downtime_error": {
        "oc_issue": False,
        "f1_issue": False,
    },
    "inspect_action": False,
    "rack_set": {
        "rack1_sw": False,
        "rack2_sw": False,
        "rack3_sw": False,
        "rack4_sw": False,
        "rack5_sw": False,
        "rack6_sw": False,
        "rack7_sw": False,
        "rack8_sw": False,
        "rack9_sw": False,
        "rack10_sw": False,
        "rack1_sw_result": False,
        "rack2_sw_result": False,
        "rack3_sw_result": False,
        "rack4_sw_result": False,
        "rack5_sw_result": False,
        "rack6_sw_result": False,
        "rack7_sw_result": False,
        "rack8_sw_result": False,
        "rack9_sw_result": False,
        "rack10_sw_result": False,
    },
    "rack_visibility": {
        "rack1_enable": False,
        "rack2_enable": False,
        "rack3_enable": False,
        "rack4_enable": False,
        "rack5_enable": False,
        "rack6_enable": False,
        "rack7_enable": False,
        "rack8_enable": False,
        "rack9_enable": False,
        "rack10_enable": False,
    },
    "rack_pass": {
        "rack1_pass": False,
        "rack2_pass": False,
        "rack3_pass": False,
        "rack4_pass": False,
        "rack5_pass": False,
        "rack6_pass": False,
        "rack7_pass": False,
        "rack8_pass": False,
        "rack9_pass": False,
        "rack10_pass": False,
    },
    "stop_valve_close": False,
}

thrshd = OrderedDict(
    {
        "Thr_W_TempClntSply": 0,
        "Thr_W_Rst_TempClntSply": 0,
        "Thr_A_TempClntSply": 0,
        "Thr_A_Rst_TempClntSply": 0,
        "Thr_W_TempClntSplySpare": 0,
        "Thr_W_Rst_TempClntSplySpare": 0,
        "Thr_A_TempClntSplySpare": 0,
        "Thr_A_Rst_TempClntSplySpare": 0,
        "Thr_W_TempClntRtn": 0,
        "Thr_W_Rst_TempClntRtn": 0,
        "Thr_A_TempClntRtn": 0,
        "Thr_A_Rst_TempClntRtn": 0,
        "Thr_W_TempClntRtnSpare": 0,
        "Thr_W_Rst_TempClntRtnSpare": 0,
        "Thr_A_TempClntRtnSpare": 0,
        "Thr_A_Rst_TempClntRtnSpare": 0,
        "Thr_W_PrsrClntSply": 0,
        "Thr_W_Rst_PrsrClntSply": 0,
        "Thr_A_PrsrClntSply": 0,
        "Thr_A_Rst_PrsrClntSply": 0,
        "Thr_W_PrsrClntSplySpare": 0,
        "Thr_W_Rst_PrsrClntSplySpare": 0,
        "Thr_A_PrsrClntSplySpare": 0,
        "Thr_A_Rst_PrsrClntSplySpare": 0,
        "Thr_W_PrsrClntRtn": 0,
        "Thr_W_Rst_PrsrClntRtn": 0,
        "Thr_A_PrsrClntRtn": 0,
        "Thr_A_Rst_PrsrClntRtn": 0,
        "Thr_W_PrsrClntRtnSpare": 0,
        "Thr_W_Rst_PrsrClntRtnSpare": 0,
        "Thr_A_PrsrClntRtnSpare": 0,
        "Thr_A_Rst_PrsrClntRtnSpare": 0,
        "Thr_W_PrsrFltIn_L": 0,
        "Thr_W_Rst_PrsrFltIn_L": 0,
        "Thr_A_PrsrFltIn_L": 0,
        "Thr_A_Rst_PrsrFltIn_L": 0,
        "Thr_W_PrsrFltIn_H": 0,
        "Thr_W_Rst_PrsrFltIn_H": 0,
        "Thr_A_PrsrFltIn_H": 0,
        "Thr_A_Rst_PrsrFltIn_H": 0,
        "Thr_W_PrsrFltOut_H": 0,
        "Thr_W_Rst_PrsrFltOut_H": 0,
        "Thr_A_PrsrFltOut_H": 0,
        "Thr_A_Rst_PrsrFltOut_H": 0,
        "Thr_W_ClntFlow": 0,
        "Thr_W_Rst_ClntFlow": 0,
        "Thr_A_ClntFlow": 0,
        "Thr_A_Rst_ClntFlow": 0,
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
        "Thr_W_DewPoint": 0,
        "Thr_W_Rst_DewPoint": 0,
        "Thr_A_DewPoint": 0,
        "Thr_A_Rst_DewPoint": 0,
        "Thr_W_pH_L": 0,
        "Thr_W_Rst_pH_L": 0,
        "Thr_A_pH_L": 0,
        "Thr_A_Rst_pH_L": 0,
        "Thr_W_pH_H": 0,
        "Thr_W_Rst_pH_H": 0,
        "Thr_A_pH_H": 0,
        "Thr_A_Rst_pH_H": 0,
        "Thr_W_Cdct_L": 0,
        "Thr_W_Rst_Cdct_L": 0,
        "Thr_A_Cdct_L": 0,
        "Thr_A_Rst_Cdct_L": 0,
        "Thr_W_Cdct_H": 0,
        "Thr_W_Rst_Cdct_H": 0,
        "Thr_A_Cdct_H": 0,
        "Thr_A_Rst_Cdct_H": 0,
        "Thr_W_Tbt_L": 0,
        "Thr_W_Rst_Tbt_L": 0,
        "Thr_A_Tbt_L": 0,
        "Thr_A_Rst_Tbt_L": 0,
        "Thr_W_Tbt_H": 0,
        "Thr_W_Rst_Tbt_H": 0,
        "Thr_A_Tbt_H": 0,
        "Thr_A_Rst_Tbt_H": 0,
        "Thr_W_AC_H": 0,
        "Thr_W_Rst_AC_H": 0,
        "Thr_A_AC_H": 0,
        "Thr_A_Rst_AC_H": 0,
        "Delay_TempClntSply": 0,
        "Delay_TempClntSplySpare": 0,
        "Delay_TempClntRtn": 0,
        "Delay_TempClntRtnSpare": 0,
        "Delay_PrsrClntSply": 0,
        "Delay_PrsrClntSplySpare": 0,
        "Delay_PrsrClntRtn": 0,
        "Delay_PrsrClntRtnSpare": 0,
        "Delay_PrsrFltIn": 0,
        "Delay_PrsrFltOut": 0,
        "Delay_ClntFlow": 0,
        "Delay_AmbientTemp": 0,
        "Delay_RelativeHumid": 0,
        "Delay_DewPoint": 0,
        "Delay_pH": 0,
        "Delay_Cdct": 0,
        "Delay_Tbt": 0,
        "Delay_AC": 0,
        "Delay_Inv1_OverLoad": 0,
        "Delay_Inv2_OverLoad": 0,
        "Delay_Inv3_OverLoad": 0,
        "Delay_Fan_OverLoad1": 0,
        "Delay_Fan_OverLoad2": 0,
        "Delay_Inv1_Error": 0,
        "Delay_Inv2_Error": 0,
        "Delay_Inv3_Error": 0,
        "Delay_ATS": 0,
        "Delay_Inverter1_Communication": 0,
        "Delay_Inverter2_Communication": 0,
        "Delay_Inverter3_Communication": 0,
        "Delay_Coolant_Flow_Meter_Communication": 0,
        "Delay_AmbientTemp_Communication": 0,
        "Delay_RelativeHumid_Communication": 0,
        "Delay_DewPoint_Communication": 0,
        "Delay_pH_Sensor_Communication": 0,
        "Delay_Conductivity_Sensor_Communication": 0,
        "Delay_Turbidity_Sensor_Communication": 0,
        "Delay_ATS1_Communication": 0,
        "Delay_ATS2_Communication": 0,
        "Delay_Power_Meter_Communication": 0,
        "Delay_average_current_Communication": 0,
        "Delay_Fan1Com_Communication": 0,
        "Delay_Fan2Com_Communication": 0,
        "Delay_Fan3Com_Communication": 0,
        "Delay_Fan4Com_Communication": 0,
        "Delay_Fan5Com_Communication": 0,
        "Delay_Fan6Com_Communication": 0,
        "Delay_Fan7Com_Communication": 0,
        "Delay_Fan8Com_Communication": 0,
        "Delay_TempClntSply_broken": 0,
        "Delay_TempClntSplySpare_broken": 0,
        "Delay_TempClntRtn_broken": 0,
        "Delay_TempClntRtnSpare_broken": 0,
        "Delay_PrsrClntSply_broken": 0,
        "Delay_PrsrClntSplySpare_broken": 0,
        "Delay_PrsrClntRtn_broken": 0,
        "Delay_PrsrClntRtnSpare_broken": 0,
        "Delay_PrsrFltIn_broken": 0,
        "Delay_PrsrFltOut_broken": 0,
        "Delay_Clnt_Flow_broken": 0,
        "Delay_leakage1_leak": 0,
        "Delay_leakage1_broken": 0,
        "Delay_level1": 0,
        "Delay_level2": 0,
        "Delay_level3": 0,
        "Delay_power24v1": 0,
        "Delay_power24v2": 0,
        "Delay_power12v1": 0,
        "Delay_power12v2": 0,
        "Delay_main_mc_error": 0,
        "Delay_fan1_error": 0,
        "Delay_fan2_error": 0,
        "Delay_fan3_error": 0,
        "Delay_fan4_error": 0,
        "Delay_fan5_error": 0,
        "Delay_fan6_error": 0,
        "Delay_fan7_error": 0,
        "Delay_fan8_error": 0,
        "Delay_rack_error": 0,
        "Delay_rack_leakage1_leak": 0,
        "Delay_rack_leakage1_broken": 0,
        "Delay_rack_leakage2_leak": 0,
        "Delay_rack_leakage2_broken": 0,
        "Delay_rack_leakage3_leak": 0,
        "Delay_rack_leakage3_broken": 0,
        "Delay_rack_leakage4_leak": 0,
        "Delay_rack_leakage4_broken": 0,
        "Delay_rack_leakage5_leak": 0,
        "Delay_rack_leakage5_broken": 0,
        "W_TempClntSply_trap": False,
        "A_TempClntSply_trap": False,
        "W_TempClntSplySpare_trap": False,
        "A_TempClntSplySpare_trap": False,
        "W_TempClntRtn_trap": False,
        "A_TempClntRtn_trap": False,
        "W_TempClntRtnSpare_trap": False,
        "A_TempClntRtnSpare_trap": False,
        "W_PrsrClntSply_trap": False,
        "A_PrsrClntSply_trap": False,
        "W_PrsrClntSplySpare_trap": False,
        "A_PrsrClntSplySpare_trap": False,
        "W_PrsrClntRtn_trap": False,
        "A_PrsrClntRtn_trap": False,
        "W_PrsrClntRtnSpare_trap": False,
        "A_PrsrClntRtnSpare_trap": False,
        "W_PrsrFltIn_trap": False,
        "A_PrsrFltIn_trap": False,
        "W_PrsrFltOut_trap": False,
        "A_PrsrFltOut_trap": False,
        "W_ClntFlow_trap": False,
        "A_ClntFlow_trap": False,
        "W_AmbientTemp_trap": False,
        "A_AmbientTemp_trap": False,
        "W_RelativeHumid_trap": False,
        "A_RelativeHumid_trap": False,
        "W_DewPoint_trap": False,
        "A_DewPoint_trap": False,
        "W_pH_trap": False,
        "A_pH_trap": False,
        "W_Cdct_trap": False,
        "A_Cdct_trap": False,
        "W_Tbt_trap": False,
        "A_Tbt_trap": False,
        "W_AC_trap": False,
        "A_AC_trap": False,
        "E_Inv1_OverLoad_trap": False,
        "E_Inv2_OverLoad_trap": False,
        "E_Inv3_OverLoad_trap": False,
        "E_Fan_OverLoad1_trap": False,
        "E_Fan_OverLoad2_trap": False,
        "E_Inv1_Error_trap": False,
        "E_Inv2_Error_trap": False,
        "E_Inv3_Error_trap": False,
        "E_ATS_trap": False,
        "E_Inverter1_Communication_trap": False,
        "E_Inverter2_Communication_trap": False,
        "E_Inverter3_Communication_trap": False,
        "E_Coolant_Flow_Meter_Communication_trap": False,
        "E_AmbientTemp_Communication_trap": False,
        "E_RelativeHumid_Communication_trap": False,
        "E_DewPoint_Communication_trap": False,
        "E_pH_Sensor_Communication_trap": False,
        "E_Conductivity_Sensor_Communication_trap": False,
        "E_Turbidity_Sensor_Communication_trap": False,
        "E_ATS1_Communication_trap": False,
        "E_ATS2_Communication_trap": False,
        "E_Power_Meter_Communication_trap": False,
        "E_Average_Current_Communication_trap": False,
        "E_Fan1Com_Communication_trap": False,
        "E_Fan2Com_Communication_trap": False,
        "E_Fan3Com_Communication_trap": False,
        "E_Fan4Com_Communication_trap": False,
        "E_Fan5Com_Communication_trap": False,
        "E_Fan6Com_Communication_trap": False,
        "E_Fan7Com_Communication_trap": False,
        "E_Fan8Com_Communication_trap": False,
        "E_TempClntSply_broken_trap": False,
        "E_TempClntSplySpare_broken_trap": False,
        "E_TempClntRtn_broken_trap": False,
        "E_TempClntRtnSpare_broken_trap": False,
        "E_PrsrClntSply_broken_trap": False,
        "E_PrsrClntSplySpare_broken_trap": False,
        "E_PrsrClntRtn_broken_trap": False,
        "E_PrsrClntRtnSpare_broken_trap": False,
        "E_PrsrFltIn_broken_trap": False,
        "E_PrsrFltOut_broken_trap": False,
        "E_Clnt_Flow_broken_trap": False,
        "E_leakage1_leak_trap": False,
        "E_leakage1_broken_trap": False,
        "E_level1_trap": False,
        "E_level2_trap": False,
        "E_level3_trap": False,
        "E_power24v1_trap": False,
        "E_power24v2_trap": False,
        "E_power12v1_trap": False,
        "E_power12v2_trap": False,
        "E_main_mc_error_trap": False,
        "E_fan1_error_trap": False,
        "E_fan2_error_trap": False,
        "E_fan3_error_trap": False,
        "E_fan4_error_trap": False,
        "E_fan5_error_trap": False,
        "E_fan6_error_trap": False,
        "E_fan7_error_trap": False,
        "E_fan8_error_trap": False,
        "E_rack_trap": False,
        "E_low_coolant_level_warning_trap": False,
        "E_pc1_error_trap": False,
        "E_pc2_error_trap": False,
        "E_plc_trap": False,
        "E_rack_leakage1_leak_trap": False,
        "E_rack_leakage1_broken_trap": False,
        "E_rack_leakage2_leak_trap": False,
        "E_rack_leakage2_broken_trap": False,
        "E_rack_leakage3_leak_trap": False,
        "E_rack_leakage3_broken_trap": False,
        "E_rack_leakage4_leak_trap": False,
        "E_rack_leakage4_broken_trap": False,
        "E_rack_leakage5_leak_trap": False,
        "E_rack_leakage5_broken_trap": False,
    }
)

sensor_adjust = OrderedDict(
    {
        "Temp_ClntSply_Factor": 1,
        "Temp_ClntSply_Offset": 0,
        "Temp_ClntSplySpare_Factor": 1,
        "Temp_ClntSplySpare_Offset": 0,
        "Temp_ClntRtn_Factor": 1,
        "Temp_ClntRtn_Offset": 0,
        "Temp_ClntRtnSpare_Factor": 1,
        "Temp_ClntRtnSpare_Offset": 0,
        "Prsr_ClntSply_Factor": 1,
        "Prsr_ClntSply_Offset": 0,
        "Prsr_ClntSplySpare_Factor": 1,
        "Prsr_ClntSplySpare_Offset": 0,
        "Prsr_ClntRtn_Factor": 1,
        "Prsr_ClntRtn_Offset": 0,
        "Prsr_ClntRtnSpare_Factor": 1,
        "Prsr_ClntRtnSpare_Offset": 0,
        "Prsr_FltIn_Factor": 1,
        "Prsr_FltIn_Offset": 0,
        "Prsr_FltOut_Factor": 1,
        "Prsr_FltOut_Offset": 0,
        "Clnt_Flow_Factor": 1,
        "Clnt_Flow_Offset": 0,
        "Ambient_Temp_Factor": 1,
        "Ambient_Temp_Offset": 0,
        "Relative_Humid_Factor": 1,
        "Relative_Humid_Offset": 0,
        "Dew_Point_Factor": 1,
        "Dew_Point_Offset": 0,
        "pH_Factor": 1,
        "pH_Offset": 0,
        "Cdct_Factor": 1,
        "Cdct_Offset": 0,
        "Tbd_Factor": 1,
        "Tbd_Offset": 0,
        "Power_Factor": 1,
        "Power_Offset": 0,
        "AC_Factor": 1,
        "AC_Offset": 0,
        "Heat_Capacity_Factor": 1,
        "Heat_Capacity_Offset": 0,
    }
)

time_data = {
    "check": {
        "rack1_broken": 0,
        "rack2_broken": 0,
        "rack3_broken": 0,
        "rack4_broken": 0,
        "rack5_broken": 0,
        "rack6_broken": 0,
        "rack7_broken": 0,
        "rack8_broken": 0,
        "rack9_broken": 0,
        "rack10_broken": 0,
        "rack1_leak": 0,
        "rack2_leak": 0,
        "rack3_leak": 0,
        "rack4_leak": 0,
        "rack5_leak": 0,
        "rack6_leak": 0,
        "rack7_leak": 0,
        "rack8_leak": 0,
        "rack9_leak": 0,
        "rack10_leak": 0,
        "rack1_error": 0,
        "rack2_error": 0,
        "rack3_error": 0,
        "rack4_error": 0,
        "rack5_error": 0,
        "rack6_error": 0,
        "rack7_error": 0,
        "rack8_error": 0,
        "rack9_error": 0,
        "rack10_error": 0,
        "rack_leakage1_leak": 0,
        "rack_leakage1_broken": 0,
        "rack_leakage2_leak": 0,
        "rack_leakage2_broken": 0,
        "rack_leakage3_leak": 0,
        "rack_leakage3_broken": 0,
        "rack_leakage4_leak": 0,
        "rack_leakage4_broken": 0,
        "rack_leakage5_leak": 0,
        "rack_leakage5_broken": 0,
    },
    "start": {
        "rack1_broken": 0,
        "rack2_broken": 0,
        "rack3_broken": 0,
        "rack4_broken": 0,
        "rack5_broken": 0,
        "rack6_broken": 0,
        "rack7_broken": 0,
        "rack8_broken": 0,
        "rack9_broken": 0,
        "rack10_broken": 0,
        "rack1_leak": 0,
        "rack2_leak": 0,
        "rack3_leak": 0,
        "rack4_leak": 0,
        "rack5_leak": 0,
        "rack6_leak": 0,
        "rack7_leak": 0,
        "rack8_leak": 0,
        "rack9_leak": 0,
        "rack10_leak": 0,
        "rack1_error": 0,
        "rack2_error": 0,
        "rack3_error": 0,
        "rack4_error": 0,
        "rack5_error": 0,
        "rack6_error": 0,
        "rack7_error": 0,
        "rack8_error": 0,
        "rack9_error": 0,
        "rack10_error": 0,
        "rack_leakage1_leak": 0,
        "rack_leakage1_broken": 0,
        "rack_leakage2_leak": 0,
        "rack_leakage2_broken": 0,
        "rack_leakage3_leak": 0,
        "rack_leakage3_broken": 0,
        "rack_leakage4_leak": 0,
        "rack_leakage4_broken": 0,
        "rack_leakage5_leak": 0,
        "rack_leakage5_broken": 0,
    },
    "end": {
        "rack1_broken": 0,
        "rack2_broken": 0,
        "rack3_broken": 0,
        "rack4_broken": 0,
        "rack5_broken": 0,
        "rack6_broken": 0,
        "rack7_broken": 0,
        "rack8_broken": 0,
        "rack9_broken": 0,
        "rack10_broken": 0,
        "rack1_leak": 0,
        "rack2_leak": 0,
        "rack3_leak": 0,
        "rack4_leak": 0,
        "rack5_leak": 0,
        "rack6_leak": 0,
        "rack7_leak": 0,
        "rack8_leak": 0,
        "rack9_leak": 0,
        "rack10_leak": 0,
        "rack1_error": 0,
        "rack2_error": 0,
        "rack3_error": 0,
        "rack4_error": 0,
        "rack5_error": 0,
        "rack6_error": 0,
        "rack7_error": 0,
        "rack8_error": 0,
        "rack9_error": 0,
        "rack10_error": 0,
        "rack_leakage1_leak": 0,
        "rack_leakage1_broken": 0,
        "rack_leakage2_leak": 0,
        "rack_leakage2_broken": 0,
        "rack_leakage3_leak": 0,
        "rack_leakage3_broken": 0,
        "rack_leakage4_leak": 0,
        "rack_leakage4_broken": 0,
        "rack_leakage5_leak": 0,
        "rack_leakage5_broken": 0,
    },
    "errorlog_start": {
        "rack1": 0,
        "rack2": 0,
        "rack3": 0,
        "rack4": 0,
        "rack5": 0,
        "rack6": 0,
        "rack7": 0,
        "rack8": 0,
        "rack9": 0,
        "rack10": 0,
    },
}

rack_opening_setting = {
    "setting_value" : 100,
    "factor_value" : 100,
}

valve_factory = {"ambient": 20, "coolant": 20}

auto_factory = {"fan": 100, "pump": 80}

dpt_error_factory = {"fan": 20, "t1": 60}

auto_mode_setting_factory = {
    "fan": 20,
}

ver_switch = {
    "median_switch": False,
    "coolant_quality_meter_switch": False,
    "fan_count_switch": False,
    "liquid_level_1_switch": False,
    "liquid_level_2_switch": False,
    "liquid_level_3_switch": False,
    "leakage_sensor_1_switch": False,
    "leakage_sensor_2_switch": False,
    "leakage_sensor_3_switch": False,
    "leakage_sensor_4_switch": False,
    "leakage_sensor_5_switch": False,
}


adjust_factory = {
    "Temp_ClntSply_Factor": 1,
    "Temp_ClntSply_Offset": 0,
    "Temp_ClntSplySpare_Factor": 1,
    "Temp_ClntSplySpare_Offset": 0,
    "Temp_ClntRtn_Factor": 1,
    "Temp_ClntRtn_Offset": 0,
    "Temp_ClntRtnSpare_Factor": 1,
    "Temp_ClntRtnSpare_Offset": 0,
    "Prsr_ClntSply_Factor": 500,
    "Prsr_ClntSply_Offset": 0,
    "Prsr_ClntSplySpare_Factor": 500,
    "Prsr_ClntSplySpare_Offset": 0,
    "Prsr_ClntRtn_Factor": 500,
    "Prsr_ClntRtn_Offset": 0,
    "Prsr_ClntRtnSpare_Factor": 500,
    "Prsr_ClntRtnSpare_Offset": 0,
    "Prsr_FltIn_Factor": 500,
    "Prsr_FltIn_Offset": 0,
    "Prsr_FltOut_Factor": 500,
    "Prsr_FltOut_Offset": 0,
    "Clnt_Flow_Factor": 1,
    "Clnt_Flow_Offset": 0,
    "Ambient_Temp_Factor": 1,
    "Ambient_Temp_Offset": 0,
    "Relative_Humid_Factor": 1,
    "Relative_Humid_Offset": 0,
    "Dew_Point_Factor": 1,
    "Dew_Point_Offset": 0,
    "pH_Factor": 1,
    "pH_Offset": 0,
    "Cdct_Factor": 1,
    "Cdct_Offset": 0,
    "Tbd_Factor": 1,
    "Tbd_Offset": 0,
    "Power_Factor": 1,
    "Power_Offset": 0,
    "AC_Factor": 1,
    "AC_Offset": 0,
    "Heat_Capacity_Factor": 1,
    "Heat_Capacity_Offset": 0,
}

thrshd_factory = {
    "A_AC_trap": False,
    "A_AmbientTemp_trap": False,
    "A_Cdct_trap": False,
    "A_ClntFlow_trap": False,
    "A_DewPoint_trap": False,
    "A_PrsrClntRtnSpare_trap": False,
    "A_PrsrClntRtn_trap": False,
    "A_PrsrClntSplySpare_trap": False,
    "A_PrsrClntSply_trap": False,
    "A_PrsrFltIn_trap": False,
    "A_PrsrFltOut_trap": False,
    "A_RelativeHumid_trap": False,
    "A_Tbt_trap": False,
    "A_TempClntRtnSpare_trap": False,
    "A_TempClntRtn_trap": False,
    "A_TempClntSplySpare_trap": False,
    "A_TempClntSply_trap": False,
    "A_pH_trap": False,
    "Delay_AC": 10,
    "Delay_ATS": 60,
    "Delay_ATS1_Communication": 10,
    "Delay_ATS2_Communication": 10,
    "Delay_AmbientTemp": 0,
    "Delay_AmbientTemp_Communication": 10,
    "Delay_Cdct": 0,
    "Delay_ClntFlow": 40,
    "Delay_Clnt_Flow_broken": 15,
    "Delay_Conductivity_Sensor_Communication": 10,
    "Delay_Coolant_Flow_Meter_Communication": 10,
    "Delay_DewPoint": 0,
    "Delay_DewPoint_Communication": 10,
    "Delay_Fan1Com_Communication": 10,
    "Delay_Fan2Com_Communication": 10,
    "Delay_Fan3Com_Communication": 10,
    "Delay_Fan4Com_Communication": 10,
    "Delay_Fan5Com_Communication": 10,
    "Delay_Fan6Com_Communication": 10,
    "Delay_Fan7Com_Communication": 10,
    "Delay_Fan8Com_Communication": 10,
    "Delay_Fan_OverLoad1": 0,
    "Delay_Fan_OverLoad2": 0,
    "Delay_Inv1_Error": 0,
    "Delay_Inv1_OverLoad": 0,
    "Delay_Inv2_Error": 0,
    "Delay_Inv2_OverLoad": 0,
    "Delay_Inv3_Error": 0,
    "Delay_Inv3_OverLoad": 0,
    "Delay_Inverter1_Communication": 10,
    "Delay_Inverter2_Communication": 10,
    "Delay_Inverter3_Communication": 10,
    "Delay_Power_Meter_Communication": 10,
    "Delay_PrsrClntRtn": 0,
    "Delay_PrsrClntRtnSpare": 0,
    "Delay_PrsrClntRtnSpare_broken": 15,
    "Delay_PrsrClntRtn_broken": 15,
    "Delay_PrsrClntSply": 0,
    "Delay_PrsrClntSplySpare": 0,
    "Delay_PrsrClntSplySpare_broken": 15,
    "Delay_PrsrClntSply_broken": 15,
    "Delay_PrsrFltIn": 0,
    "Delay_PrsrFltIn_broken": 15,
    "Delay_PrsrFltOut": 0,
    "Delay_PrsrFltOut_broken": 15,
    "Delay_RelativeHumid": 0,
    "Delay_RelativeHumid_Communication": 10,
    "Delay_Tbt": 0,
    "Delay_TempClntRtn": 0,
    "Delay_TempClntRtnSpare": 0,
    "Delay_TempClntRtnSpare_broken": 15,
    "Delay_TempClntRtn_broken": 15,
    "Delay_TempClntSply": 0,
    "Delay_TempClntSplySpare": 0,
    "Delay_TempClntSplySpare_broken": 15,
    "Delay_TempClntSply_broken": 15,
    "Delay_Turbidity_Sensor_Communication": 10,
    "Delay_average_current_Communication": 10,
    "Delay_fan1_error": 0,
    "Delay_fan2_error": 0,
    "Delay_fan3_error": 0,
    "Delay_fan4_error": 0,
    "Delay_fan5_error": 0,
    "Delay_fan6_error": 0,
    "Delay_fan7_error": 0,
    "Delay_fan8_error": 0,
    "Delay_leakage1_broken": 0,
    "Delay_leakage1_leak": 0,
    "Delay_level1": 0,
    "Delay_level2": 0,
    "Delay_level3": 0,
    "Delay_main_mc_error": 0,
    "Delay_pH": 0,
    "Delay_pH_Sensor_Communication": 10,
    "Delay_power12v1": 0,
    "Delay_power12v2": 0,
    "Delay_power24v1": 0,
    "Delay_power24v2": 0,
    "Delay_rack_error": 0,
    "Delay_rack_leakage1_broken": 0,
    "Delay_rack_leakage1_leak": 0,
    "Delay_rack_leakage2_broken": 0,
    "Delay_rack_leakage2_leak": 0,
    "Delay_rack_leakage3_broken": 0,
    "Delay_rack_leakage3_leak": 0,
    "Delay_rack_leakage4_broken": 0,
    "Delay_rack_leakage4_leak": 0,
    "Delay_rack_leakage5_broken": 0,
    "Delay_rack_leakage5_leak": 0,
    "E_ATS1_Communication_trap": False,
    "E_ATS2_Communication_trap": False,
    "E_ATS_trap": False,
    "E_AmbientTemp_Communication_trap": False,
    "E_Average_Current_Communication_trap": False,
    "E_Clnt_Flow_broken_trap": False,
    "E_Conductivity_Sensor_Communication_trap": False,
    "E_Coolant_Flow_Meter_Communication_trap": False,
    "E_DewPoint_Communication_trap": False,
    "E_Fan1Com_Communication_trap": False,
    "E_Fan2Com_Communication_trap": False,
    "E_Fan3Com_Communication_trap": False,
    "E_Fan4Com_Communication_trap": False,
    "E_Fan5Com_Communication_trap": False,
    "E_Fan6Com_Communication_trap": False,
    "E_Fan7Com_Communication_trap": False,
    "E_Fan8Com_Communication_trap": False,
    "E_Fan_OverLoad1_trap": False,
    "E_Fan_OverLoad2_trap": False,
    "E_Inv1_Error_trap": False,
    "E_Inv1_OverLoad_trap": False,
    "E_Inv2_Error_trap": False,
    "E_Inv2_OverLoad_trap": False,
    "E_Inv3_Error_trap": False,
    "E_Inv3_OverLoad_trap": False,
    "E_Inverter1_Communication_trap": False,
    "E_Inverter2_Communication_trap": False,
    "E_Inverter3_Communication_trap": False,
    "E_Power_Meter_Communication_trap": False,
    "E_PrsrClntRtnSpare_broken_trap": False,
    "E_PrsrClntRtn_broken_trap": False,
    "E_PrsrClntSplySpare_broken_trap": False,
    "E_PrsrClntSply_broken_trap": False,
    "E_PrsrFltIn_broken_trap": False,
    "E_PrsrFltOut_broken_trap": False,
    "E_RelativeHumid_Communication_trap": False,
    "E_TempClntRtnSpare_broken_trap": False,
    "E_TempClntRtn_broken_trap": False,
    "E_TempClntSplySpare_broken_trap": False,
    "E_TempClntSply_broken_trap": False,
    "E_Turbidity_Sensor_Communication_trap": False,
    "E_fan1_error_trap": False,
    "E_fan2_error_trap": False,
    "E_fan3_error_trap": False,
    "E_fan4_error_trap": False,
    "E_fan5_error_trap": False,
    "E_fan6_error_trap": False,
    "E_fan7_error_trap": False,
    "E_fan8_error_trap": False,
    "E_low_coolant_level_warning_trap": False,
    "E_leakage1_broken_trap": False,
    "E_leakage1_leak_trap": False,
    "E_level1_trap": False,
    "E_level2_trap": False,
    "E_level3_trap": False,
    "E_main_mc_error_trap": False,
    "E_pH_Sensor_Communication_trap": False,
    "E_pc1_error_trap": False,
    "E_pc2_error_trap": False,
    "E_plc_trap": False,
    "E_power12v1_trap": False,
    "E_power12v2_trap": False,
    "E_power24v1_trap": False,
    "E_power24v2_trap": False,
    "E_rack_trap": False,
    "E_rack_leakage1_broken_trap": False,
    "E_rack_leakage1_leak_trap": False,
    "E_rack_leakage2_broken_trap": False,
    "E_rack_leakage2_leak_trap": False,
    "E_rack_leakage3_broken_trap": False,
    "E_rack_leakage3_leak_trap": False,
    "E_rack_leakage4_broken_trap": False,
    "E_rack_leakage4_leak_trap": False,
    "E_rack_leakage5_broken_trap": False,
    "E_rack_leakage5_leak_trap": False,
    "Thr_A_AC_H": 45,
    "Thr_A_AmbientTemp_H": 45,
    "Thr_A_AmbientTemp_L": 18,
    "Thr_A_Cdct_H": 4700,
    "Thr_A_Cdct_L": 4000,
    "Thr_A_ClntFlow": 20,
    "Thr_A_DewPoint": 2,
    "Thr_A_PrsrClntRtn": 200,
    "Thr_A_PrsrClntRtnSpare": 200,
    "Thr_A_PrsrClntSply": 400,
    "Thr_A_PrsrClntSplySpare": 400,
    "Thr_A_PrsrFltIn_H": 550,
    "Thr_A_PrsrFltIn_L": 23,
    "Thr_A_PrsrFltOut_H": 200,
    "Thr_A_RelativeHumid_H": 80,
    "Thr_A_RelativeHumid_L": 8,
    "Thr_A_Rst_AC_H": 40,
    "Thr_A_Rst_AmbientTemp_H": 40,
    "Thr_A_Rst_AmbientTemp_L": 23,
    "Thr_A_Rst_Cdct_H": 4650,
    "Thr_A_Rst_Cdct_L": 4100,
    "Thr_A_Rst_ClntFlow": 25,
    "Thr_A_Rst_DewPoint": 2.5,
    "Thr_A_Rst_PrsrClntRtn": 150,
    "Thr_A_Rst_PrsrClntRtnSpare": 150,
    "Thr_A_Rst_PrsrClntSply": 350,
    "Thr_A_Rst_PrsrClntSplySpare": 350,
    "Thr_A_Rst_PrsrFltIn_H": 500,
    "Thr_A_Rst_PrsrFltIn_L": 25,
    "Thr_A_Rst_PrsrFltOut_H": 150,
    "Thr_A_Rst_RelativeHumid_H": 75,
    "Thr_A_Rst_RelativeHumid_L": 8.5,
    "Thr_A_Rst_Tbt_H": 11,
    "Thr_A_Rst_Tbt_L": 2,
    "Thr_A_Rst_TempClntRtn": 60,
    "Thr_A_Rst_TempClntRtnSpare": 60,
    "Thr_A_Rst_TempClntSply": 60,
    "Thr_A_Rst_TempClntSplySpare": 60,
    "Thr_A_Rst_pH_H": 7.9,
    "Thr_A_Rst_pH_L": 7.2,
    "Thr_A_Tbt_H": 15,
    "Thr_A_Tbt_L": 1,
    "Thr_A_TempClntRtn": 65,
    "Thr_A_TempClntRtnSpare": 65,
    "Thr_A_TempClntSply": 65,
    "Thr_A_TempClntSplySpare": 65,
    "Thr_A_pH_H": 8,
    "Thr_A_pH_L": 7,
    "Thr_W_AC_H": 40,
    "Thr_W_AmbientTemp_H": 40,
    "Thr_W_AmbientTemp_L": 23,
    "Thr_W_Cdct_H": 4600,
    "Thr_W_Cdct_L": 4200,
    "Thr_W_ClntFlow": 30,
    "Thr_W_DewPoint": 5,
    "Thr_W_PrsrClntRtn": 150,
    "Thr_W_PrsrClntRtnSpare": 150,
    "Thr_W_PrsrClntSply": 350,
    "Thr_W_PrsrClntSplySpare": 350,
    "Thr_W_PrsrFltIn_H": 500,
    "Thr_W_PrsrFltIn_L": 30,
    "Thr_W_PrsrFltOut_H": 150,
    "Thr_W_RelativeHumid_H": 75,
    "Thr_W_RelativeHumid_L": 8.5,
    "Thr_W_Rst_AC_H": 35,
    "Thr_W_Rst_AmbientTemp_H": 35,
    "Thr_W_Rst_AmbientTemp_L": 25,
    "Thr_W_Rst_Cdct_H": 4500,
    "Thr_W_Rst_Cdct_L": 4300,
    "Thr_W_Rst_ClntFlow": 35,
    "Thr_W_Rst_DewPoint": 5.5,
    "Thr_W_Rst_PrsrClntRtn": 100,
    "Thr_W_Rst_PrsrClntRtnSpare": 100,
    "Thr_W_Rst_PrsrClntSply": 300,
    "Thr_W_Rst_PrsrClntSplySpare": 300,
    "Thr_W_Rst_PrsrFltIn_H": 450,
    "Thr_W_Rst_PrsrFltIn_L": 35,
    "Thr_W_Rst_PrsrFltOut_H": 100,
    "Thr_W_Rst_RelativeHumid_H": 70,
    "Thr_W_Rst_RelativeHumid_L": 9,
    "Thr_W_Rst_Tbt_H": 8,
    "Thr_W_Rst_Tbt_L": 3,
    "Thr_W_Rst_TempClntRtn": 55,
    "Thr_W_Rst_TempClntRtnSpare": 55,
    "Thr_W_Rst_TempClntSply": 55,
    "Thr_W_Rst_TempClntSplySpare": 55,
    "Thr_W_Rst_pH_H": 7.8,
    "Thr_W_Rst_pH_L": 7.3,
    "Thr_W_Tbt_H": 10,
    "Thr_W_Tbt_L": 2,
    "Thr_W_TempClntRtn": 60,
    "Thr_W_TempClntRtnSpare": 60,
    "Thr_W_TempClntSply": 60,
    "Thr_W_TempClntSplySpare": 60,
    "Thr_W_pH_H": 7.9,
    "Thr_W_pH_L": 7.2,
    "W_AC_trap": False,
    "W_AmbientTemp_trap": False,
    "W_Cdct_trap": False,
    "W_ClntFlow_trap": False,
    "W_DewPoint_trap": False,
    "W_PrsrClntRtnSpare_trap": False,
    "W_PrsrClntRtn_trap": False,
    "W_PrsrClntSplySpare_trap": False,
    "W_PrsrClntSply_trap": False,
    "W_PrsrFltIn_trap": False,
    "W_PrsrFltOut_trap": False,
    "W_RelativeHumid_trap": False,
    "W_Tbt_trap": False,
    "W_TempClntRtnSpare_trap": False,
    "W_TempClntRtn_trap": False,
    "W_TempClntSplySpare_trap": False,
    "W_TempClntSply_trap": False,
    "W_pH_trap": False,
}


pid_factory = {
    "temperature": {
        "sample_time_temp": 100,
        "kp_temp": 500,
        "ki_time_temp": 10,
        "kd_temp": 0,
        "kd_time_temp": 0,
    },
    "pressure": {
        "sample_time_pressure": 20,
        "kp_pressure": 800,
        "ki_time_pressure": 10,
        "kd_pressure": 0,
        "kd_time_pressure": 0,
    },
}

key_mapping = {
    "Temp_ClntSply_broken": "temp_clntSply",
    "Temp_ClntSplySpare_broken": "temp_clntSplySpare",
    "Temp_ClntRtn_broken": "temp_clntRtn",
    "Temp_ClntRtnSpare_broken": "temp_clntRtnSpare",
    "Prsr_ClntSply_broken": "prsr_clntSply",
    "Prsr_ClntSplySpare_broken": "prsr_clntSplySpare",
    "Prsr_ClntRtn_broken": "prsr_clntRtn",
    "Prsr_ClntRtnSpare_broken": "prsr_clntRtnSpare",
    "Prsr_FltIn_broken": "prsr_fltIn",
    "Prsr_FltOut_broken": "prsr_fltOut",
    "f1": "clnt_flow",
    "pH": "pH",
    "cdct": "cdct",
    "tbd": "tbd",
    "power": "power",
    "p1_speed": "inv1_freq",
    "p2_speed": "inv2_freq",
    "p3_speed": "inv3_freq",
    "AC": "AC",
    "heat_capacity": "heat_capacity",
    "fan1_speed": "fan_freq1",
    "fan2_speed": "fan_freq2",
    "fan3_speed": "fan_freq3",
    "fan4_speed": "fan_freq4",
    "fan5_speed": "fan_freq5",
    "fan6_speed": "fan_freq6",
    "fan7_speed": "fan_freq7",
    "fan8_speed": "fan_freq8",
}

inspection_value = {
    "Temp_ClntSply_broken": 0,
    "Temp_ClntSplySpare_broken": 0,
    "Temp_ClntRtn_broken": 0,
    "Temp_ClntRtnSpare_broken": 0,
    "Prsr_ClntSply_broken": 0,
    "Prsr_ClntSplySpare_broken": 0,
    "Prsr_ClntRtn_broken": 0,
    "Prsr_ClntRtnSpare_broken": 0,
    "Clnt_Flow_broken": 0,
    "f1": 0,
    "pH": 0,
    "cdct": 0,
    "tbd": 0,
    "power": 0,
    "p1_speed": 0,
    "p2_speed": 0,
    "p3_speed": 0,
    "AC": 0,
    "heat_capacity": 0,
    "fan1_speed": 0,
    "fan2_speed": 0,
    "fan3_speed": 0,
    "fan4_speed": 0,
    "fan5_speed": 0,
    "fan6_speed": 0,
    "fan7_speed": 0,
    "fan8_speed": 0,
}

measure_data = {
    "p1_speed": 1,
    "p2_speed": 1,
    "p3_speed": 1,
    "f1": 1,
    "Temp_ClntSply_broken": 1,
    "Temp_ClntSplySpare_broken": 1,
    "Temp_ClntRtn_broken": 1,
    "Temp_ClntRtnSpare_broken": 1,
    "Prsr_ClntSply_broken": 1,
    "Prsr_ClntSplySpare_broken": 1,
    "Prsr_ClntRtn_broken": 1,
    "Prsr_ClntRtnSpare_broken": 1,
    "Prsr_FltIn_broken": 1,
    "Prsr_FltOut_broken": 1,
    "Clnt_Flow_broken": 1,
    "fan1_speed": 1,
    "fan2_speed": 1,
    "fan3_speed": 1,
    "fan4_speed": 1,
    "fan5_speed": 1,
    "fan6_speed": 1,
    "fan7_speed": 1,
    "fan8_speed": 1,
}

result_data = {
    "p1_speed": False,
    "p2_speed": False,
    "p3_speed": False,
    "f1": [],
    "Temp_ClntSply_broken": False,
    "Temp_ClntSplySpare_broken": False,
    "Temp_ClntRtn_broken": False,
    "Temp_ClntRtnSpare_broken": False,
    "Prsr_ClntSply_broken": False,
    "Prsr_ClntSplySpare_broken": False,
    "Prsr_ClntRtn_broken": False,
    "Prsr_ClntRtnSpare_broken": False,
    "Prsr_FltIn_broken": False,
    "Prsr_FltOut_broken": False,
    "Clnt_Flow_broken": False,
    "Inv1_Freq_com": [],
    "Inv2_Freq_com": [],
    "Inv3_Freq_com": [],
    # "coolant_flow_rate_com": [],
    "AmbientTemp_com": [],
    "RelativeHumid_com": [],
    "DewPoint_com": [],
    "pH_com": [],
    "conductivity_com": [],
    "turbidity_com": [],
    "ATS1_com": [],
    "ATS2_com": [],
    "inst_power_com": [],
    "average_current_com": [],
    "Fan1Com_com": [],
    "Fan2Com_com": [],
    "Fan3Com_com": [],
    "Fan4Com_com": [],
    "Fan5Com_com": [],
    "Fan6Com_com": [],
    "Fan7Com_com": [],
    "Fan8Com_com": [],
    "level1": False,
    "level2": False,
    "level3": False,
    "power24v1": False,
    "power24v2": False,
    "power12v1": False,
    "power12v2": False,
    "fan1_speed": False,
    "fan2_speed": False,
    "fan3_speed": False,
    "fan4_speed": False,
    "fan5_speed": False,
    "fan6_speed": False,
    "fan7_speed": False,
    "fan8_speed": False,
    "Inv1_OverLoad": [],
    "Inv2_OverLoad": [],
    "Inv3_OverLoad": [],
    "Fan_OverLoad1": [],
    "Fan_OverLoad2": [],
    "Inv1_Error": [],
    "Inv2_Error": [],
    "Inv3_Error": [],
    "fan1_error": [],
    "fan2_error": [],
    "fan3_error": [],
    "fan4_error": [],
    "fan5_error": [],
    "fan6_error": [],
    "fan7_error": [],
    "fan8_error": [],
    "force_change_mode": False,
    "inspect_finish": 3,
    "inspect_time": "",
}

progress_data = {
    "p1_speed": 1,
    "p2_speed": 1,
    "p3_speed": 1,
    "f1": 1,
    "Temp_ClntSply_broken": 1,
    "Temp_ClntSplySpare_broken": 1,
    "Temp_ClntRtn_broken": 1,
    "Temp_ClntRtnSpare_broken": 1,
    "Prsr_ClntSply_broken": 1,
    "Prsr_ClntSplySpare_broken": 1,
    "Prsr_ClntRtn_broken": 1,
    "Prsr_ClntRtnSpare_broken": 1,
    "Prsr_FltIn_broken": 1,
    "Prsr_FltOut_broken": 1,
    "Clnt_Flow_broken": 1,
    "Inv1_Freq_com": 1,
    "Inv2_Freq_com": 1,
    "Inv3_Freq_com": 1,
    # "coolant_flow_rate_com": 1,
    "AmbientTemp_com": 1,
    "RelativeHumid_com": 1,
    "DewPoint_com": 1,
    "pH_com": 1,
    "conductivity_com": 1,
    "turbidity_com": 1,
    "ATS1_com": 1,
    "ATS2_com": 1,
    "inst_power_com": 1,
    "average_current_com": 1,
    "Fan1Com_com": 1,
    "Fan2Com_com": 1,
    "Fan3Com_com": 1,
    "Fan4Com_com": 1,
    "Fan5Com_com": 1,
    "Fan6Com_com": 1,
    "Fan7Com_com": 1,
    "Fan8Com_com": 1,
    "level1": 1,
    "level2": 1,
    "level3": 1,
    "power24v1": 1,
    "power24v2": 1,
    "power12v1": 1,
    "power12v2": 1,
    "fan1_speed": 1,
    "fan2_speed": 1,
    "fan3_speed": 1,
    "fan4_speed": 1,
    "fan5_speed": 1,
    "fan6_speed": 1,
    "fan7_speed": 1,
    "fan8_speed": 1,
    "Inv1_OverLoad": 1,
    "Inv2_OverLoad": 1,
    "Inv3_OverLoad": 1,
    "Fan_OverLoad1": 1,
    "Fan_OverLoad2": 1,
    "Inv1_Error": 1,
    "Inv2_Error": 1,
    "Inv3_Error": 1,
    "fan1_error": 1,
    "fan2_error": 1,
    "fan3_error": 1,
    "fan4_error": 1,
    "fan5_error": 1,
    "fan6_error": 1,
    "fan7_error": 1,
    "fan8_error": 1,
}

inspection_time = {
    "pump_open_time": 0,
}

inspection_time_last_check = {"current_time": ""}

light_mark = {
    "warning": False,
    "alert": False,
    "error": False,
}

pid_setting = {
    "temperature": {
        "sample_time_temp": 0,
        "kp_temp": 0,
        "ki_time_temp": 0,
        "kd_temp": 0,
        "kd_time_temp": 0,
    },
    "pressure": {
        "sample_time_pressure": 0,
        "kp_pressure": 0,
        "ki_time_pressure": 0,
        "kd_pressure": 0,
        "kd_time_pressure": 0,
    },
}

pid_order = {
    "pressure": [
        "sample_time_pressure",
        "kp_pressure",
        "ki_time_pressure",
        "kd_pressure",
        "kd_time_pressure",
    ],
    "temperature": [
        "sample_time_temp",
        "kp_temp",
        "ki_time_temp",
        "kd_temp",
        "kd_time_temp",
    ],
}
auto_setting = {"auto_broken_temperature": 0, "auto_broken_pressure": 0}

dpt_error_setting = {
    "dpt_error_fan": 0,
    "dpt_error_t1": 0,
}

auto_mode_setting = {
    "auto_mode_fan": 0,
}

system_data = {
    "value": {
        "unit": "metric",
        "last_unit": "metric",
    }
}

FW_Info = {
    "SN": "ABC-1234",
    "Model": "800KW",
    "Version": "1",
    "UI": "240229-1",
    "PC": "240229-2",
    "PLC": "240229-3",
}

TIMEOUT_Info = {"timeoutLight": 60}
all_network_set = [
    {
        "v4dhcp_en": "",
        "IPv4Address": "",
        "v4Subnet": "",
        "v4DefaultGateway": "",
        "v4AutoDNS": "",
        "v4DNSPrimary": "",
        "v4DNSOther": "",
        "v6dhcp_en": "",
        "IPv6Address": "",
        "v6Subnet": "",
        "v6DefaultGateway": "",
        "v6AutoDNS": "",
        "v6DNSPrimary": "",
        "v6DNSOther": "",
    },
    {
        "v4dhcp_en": "",
        "IPv4Address": "",
        "v4Subnet": "",
        "v4DefaultGateway": "",
        "v4AutoDNS": "",
        "v4DNSPrimary": "",
        "v4DNSOther": "",
        "v6dhcp_en": "",
        "IPv6Address": "",
        "v6Subnet": "",
        "v6DefaultGateway": "",
        "v6AutoDNS": "",
        "v6DNSPrimary": "",
        "v6DNSOther": "",
    },
    {
        "v4dhcp_en": "",
        "IPv4Address": "",
        "v4Subnet": "",
        "v4DefaultGateway": "",
        "v4AutoDNS": "",
        "v4DNSPrimary": "",
        "v4DNSOther": "",
        "v6dhcp_en": "",
        "IPv6Address": "",
        "v6Subnet": "",
        "v6DefaultGateway": "",
        "v6AutoDNS": "",
        "v6DNSPrimary": "",
        "v6DNSOther": "",
    },
    {
        "v4dhcp_en": "",
        "IPv4Address": "",
        "v4Subnet": "",
        "v4DefaultGateway": "",
        "v4AutoDNS": "",
        "v4DNSPrimary": "",
        "v4DNSOther": "",
        "v6dhcp_en": "",
        "IPv6Address": "",
        "v6Subnet": "",
        "v6DefaultGateway": "",
        "v6AutoDNS": "",
        "v6DNSPrimary": "",
        "v6DNSOther": "",
    },
]

read_data = {
    "status": False,
    "systemset": False,
    "control": False,
    "engineerMode": False,
}


sensor_map = {
    "temp_clntSply": "Coolant Supply Temperature (T1)",
    "temp_clntSplySpare": "Coolant Supply Temperature Spare (T1sp)",
    "temp_clntRtn": "Coolant Return Temperature (T2)",
    "temp_clntRtnSpare": "Coolant Return Temperature Spare (T2sp)",
    "prsr_clntSply": "Coolant Supply Pressure (P1)",
    "prsr_clntSplySpare": "Coolant Supply Pressure Spare (P1sp)",
    "prsr_clntRtn": "Coolant Return Pressure (P2)",
    "prsr_clntRtnSpare": "Coolant Return Pressure Spare (P2sp)",
    "prsr_diff": "Differential Pressure (Pd=P1-P2)",
    "prsr_fltIn": "Filter Inlet Pressure (P3)",
    "prsr_fltOut": "Filter Outlet Pressure (P4)",
    "clnt_flow": "Coolant Flow Rate (F1)",
    "ambient_temp": "Ambient Temperature (Ta)",
    "relative_humid": "Relative Humidity (RH)",
    "dew_point": "Dew Point (TDp)",
    "pH": "pH (PH)",
    "cdct": "Conductivity (CON)",
    "tbd": "Turbidity (Tur)",
    "power": "Instant Power Consumption",
    "AC": "Average Current",
    "heat_capacity": "Heat Capacity",
    "inv1_freq": "Coolant Pump1[%]",
    "inv2_freq": "Coolant Pump2[%]",
    "inv3_freq": "Coolant Pump3[%]",
    "fan_freq1": "Fan Speed1[%]",
    "fan_freq2": "Fan Speed2[%]",
    "fan_freq3": "Fan Speed3[%]",
    "fan_freq4": "Fan Speed4[%]",
    "fan_freq5": "Fan Speed5[%]",
    "fan_freq6": "Fan Speed6[%]",
    "fan_freq7": "Fan Speed7[%]",
    "fan_freq8": "Fan Speed8[%]",
}

ctrl_map = {
    "resultMode": "Mode Selection",
    "resultTemp": "Target Coolant Temperature Setting",
    "resultPressure": "Target Coolant Pressure Setting",
    "resultSwap": "Pump Swap Time Setting",
    "resultP1": "Pump1 Speed Setting",
    "resultP2": "Pump2 Speed Setting",
    "resultP3": "Pump3 Speed Setting",
    "resultFan1": "Fan 1 Speed Setting",
    "resultFan2": "Fan 2 Speed Setting",
    "resultFan3": "Fan 3 Speed Setting",
    "resultFan4": "Fan 4 Speed Setting",
    "resultFan5": "Fan 5 Speed Setting",
    "resultFan6": "Fan 6 Speed Setting",
    "resultFan7": "Fan 7 Speed Setting",
    "resultFan8": "Fan 8 Speed Setting",
}

temporary_map = {
    "command_pressure": "Command Pressure",
    "feedback_pressure": "Feedback Pressure",
    "pressure_output":  "Pressure Output",
    "command_temperature":  "Command Temperature",
    "feedback_temperature":  "Feedback Temperature",
    "temperature_output":   "Temperature Output",
}

fan_status_map = {
    "fan_power": {
        "Fan1": "Fan1 Current Power(W)",
        "Fan2": "Fan2 Current Power(W)",
        "Fan3": "Fan3 Current Power(W)",
        "Fan4": "Fan4 Current Power(W)",
        "Fan5": "Fan5 Current Power(W)",
        "Fan6": "Fan6 Current Power(W)",
        "Fan7": "Fan7 Current Power(W)",
        "Fan8": "Fan8 Current Power(W)",
    },
    "fan_rpm": {
        "Fan1": "Fan1 Speed(RPM)",
        "Fan2": "Fan2 Speed(RPM)",
        "Fan3": "Fan3 Speed(RPM)",
        "Fan4": "Fan4 Speed(RPM)",
        "Fan5": "Fan5 Speed(RPM)",
        "Fan6": "Fan6 Speed(RPM)",
        "Fan7": "Fan7 Speed(RPM)",
        "Fan8": "Fan8 Speed(RPM)",
    },
}

logData = {
    "value": {
        "temp_clntSply": 0,
        "temp_clntSplySpare": 0,
        "temp_clntRtn": 0,
        "temp_clntRtnSpare": 0,
        "prsr_clntSply": 0,
        "prsr_clntSplySpare": 0,
        "prsr_clntRtn": 0,
        "prsr_clntRtnSpare": 0,
        "prsr_diff": 0,
        "prsr_fltIn": 0,
        "prsr_fltOut": 0,
        "clnt_flow": 0,
        "ambient_temp": 0,
        "relative_humid": 0,
        "dew_point": 0,
        "pH": 0,
        "cdct": 0,
        "tbd": 0,
        "power": 0,
        "AC": 0,
        "heat_capacity": 0,
        "inv1_freq": 0,
        "inv2_freq": 0,
        "inv3_freq": 0,
        "fan_freq1": 0,
        "fan_freq2": 0,
        "fan_freq3": 0,
        "fan_freq4": 0,
        "fan_freq5": 0,
        "fan_freq6": 0,
        "fan_freq7": 0,
        "fan_freq8": 0,
    },
    "setting": {
        "resultMode": "Manual",
        "resultTemp": 0,
        "resultPressure": 0,
        "resultSwap": 0,
        "resultP1": 0,
        "resultP2": 0,
        "resultP3": 0,
        "resultFan1": False,
        "resultFan2": False,
        "resultFan3": False,
        "resultFan4": False,
        "resultFan5": False,
        "resultFan6": False,
        "resultFan7": False,
        "resultFan8": False,
    },
    "temporary_data": {
        "command_pressure": 0,
        "feedback_pressure": 0,
        "pressure_output": 0,
        "command_temperature": 0,
        "feedback_temperature": 0,
        "temperature_output": 0,
    },
    "fan_power": {
        "Fan1": 0,
        "Fan2": 0,
        "Fan3": 0,
        "Fan4": 0,
        "Fan5": 0,
        "Fan6": 0,
        "Fan7": 0,
        "Fan8": 0,
    },
    "fan_rpm": {
        "Fan1": 0,
        "Fan2": 0,
        "Fan3": 0,
        "Fan4": 0,
        "Fan5": 0,
        "Fan6": 0,
        "Fan7": 0,
        "Fan8": 0,
    },
}

setting_limit = {
    "control": {
        "oil_temp_set_up": 0,
        "oil_temp_set_low": 0,
        "oil_pressure_set_up": 0,
        "oil_pressure_set_low": 0,
    }
}

sampling_rate = {"number": 15}
user_identity = {"ID": "user"}
collapse_state = {"status": False}

snmp_setting = {
    "trap_ip_address": "",
    "read_community": "",
    "write_community": "",
    "v3_switch": False,
}

FAN_ERROR_KEYS = [
    "space1",
    "space2",
    "space3",
    "UzLow",
    "space4",
    "RL_Cal",
    "space5",
    "n_Limit",
    "BLK",
    "HLL",
    "TFM",
    "FB",
    "SKF",
    "TFE",
    "space6",
    "PHA",
]

FAN_WANINIG_KEYS = [
    "LRF",
    "UeHigh",
    "space1",
    "UzHigh",
    "space2",
    "OpenCir",
    "n_Low",
    "RL_Cal",
    "Braking",
    "UzLow",
    "TEI_high",
    "TM_high",
    "TE_high",
    "P_Limit",
    "L_high",
    "I_Limit",
]

fan_status_message = {
    "error":{
        "UzLow": "DC-link undervoltage",
        "RL_Cal": "Rotor position sensor calibration error",
        "n_Limit": "Speed limit exceeded",
        "BLK": "Motor blocked",
        "HLL": "Hall sensor error",
        "TFM": "Motor overheated",
        "FB": "Fan Bad",
        "SKF": "Internal communication error",
        "TFE": "Output stage overheated",
        "PHA": "Phase failure or line undervoltage",
    },
    "warning":{
        "LRF": "Shedding function active",
        "UeHigh": "Line voltage high",
        "UzHigh": "DC-link voltage high",
        "OpenCir": "No signal detected at analog or PWM input",
        "n_Low": "Actual speed is lower than speed limit or running monitoring",
        "RL_Cal": "Calibration of rotor position sensor in progress",
        "Braking": "Braking mode",
        "UzLow": "DC-link voltage low",
        "TEI_high": "Temperature inside electronics high",
        "TM_high": "Motor temperature high",
        "TE_high": "Outout stage temerature high",
        "P_Limit": "Power limiter in action",
        "L_high": "Line impedance too high",
        "I_Limit": "Current limitation in action",
    }
}

fan_error_status = {
    f"Fan{i + 1}": {key: False for key in FAN_ERROR_KEYS} for i in range(8)
}

fan_warning_status = {
    f"Fan{i + 1}": {key: False for key in FAN_WANINIG_KEYS} for i in range(8)
}

def check_fans_status():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            err_key_len = len(FAN_ERROR_KEYS)
            warning_key_len = len(FAN_WANINIG_KEYS)
            err_keys_list = list(FAN_ERROR_KEYS)
            warning_keys_list = list(FAN_WANINIG_KEYS)
            start_address = 2500
            warning_start_address = 2508
            for i in range(8):
                err_result = client.read_holding_registers(start_address + i, 1)
                warning_reslut = client.read_holding_registers(warning_start_address + i , 1)
                
                if not err_result.isError():
                    err_value = err_result.registers[0]
                    err_binary_string = bin(err_value)[2:].zfill(err_key_len)
                    for index, key in enumerate(err_keys_list):
                        fan_error_status[f"Fan{i+1}"][key] = bool(int(err_binary_string[index]))
                        
                if not warning_reslut.isError():
                    warning_value = warning_reslut.registers[0]
                    warning_binary_string = bin(warning_value)[2:].zfill(warning_key_len)
                    for index, key in enumerate(warning_keys_list):
                        fan_warning_status[f"Fan{i+1}"][key] = bool(int(warning_binary_string[index]))
    except Exception as e:
        print(f"Fan status error:{e}")        

def read_net_name():
    net_data = {
        "netname1": "ethernet1",
        "netname2": "ethernet2",
        "netname3": "Wired connection 1",
        "netname4": "Wired connection 2",
    }

    interface_name = [
        value for key, value in net_data.items() if key.startswith("netname")
    ]

    return interface_name


def check_warning_status():
    for base_key in sensorData["warning_notice"].keys():
        high_key = base_key + "_high"
        low_key = base_key + "_low"

        if sensorData["warning"].get(high_key, False) or sensorData["warning"].get(
            low_key, False
        ):
            sensorData["warning_notice"][base_key] = True
        else:
            sensorData["warning_notice"][base_key] = False

    for base_key in sensorData["alert_notice"].keys():
        high_key = base_key + "_high"
        low_key = base_key + "_low"

        if sensorData["alert"].get(high_key, False) or sensorData["alert"].get(
            low_key, False
        ):
            sensorData["alert_notice"][base_key] = True
        else:
            sensorData["alert_notice"][base_key] = False

def check_cdu_status():
    cdu_status = "ok"

    # 優先處理 alert 和 error（最高優先權）
    for key in sensorData["error"]:
        if sensorData["error"][key]:
            cdu_status = "alert"
            break  # 已達最高優先，直接跳出

    if cdu_status != "alert":
        for key in sensorData["alert_notice"]:
            if sensorData["alert_notice"][key]:
                cdu_status = "alert"
                break

    # 再處理 warning（中優先權）
    if cdu_status != "alert":
        for key in sensorData["warning_notice"]:
            if sensorData["warning_notice"][key]:
                cdu_status = "warning"
                break

    sensorData["cdu_status"] = cdu_status

def parse_nmcli_output(outputs, network_set, is_ipv6=False):
    for output in outputs:
        if output.strip():
            key, value = map(str.strip, output.split(":", 1))

            if is_ipv6:
                if "ipv6.method" in key:
                    network_set["v6dhcp_en"] = value

                elif key.startswith("IP6.ADDRESS"):
                    ip_net = ipaddress.ip_interface(value)
                    network_set["IPv6Address"] = str(ip_net.ip)
                    network_set["v6Subnet"] = str(ip_net.network.prefixlen)

                elif "IP6.GATEWAY" in key:
                    if value == "--":
                        network_set["v6DefaultGateway"] = ""
                    else:
                        network_set["v6DefaultGateway"] = value

                elif "ipv6.ignore-auto-dns" in key:
                    if value == "no":
                        network_set["v6AutoDNS"] = "auto"
                    else:
                        network_set["v6AutoDNS"] = "manual"

                elif "IP6.DNS[1]" in key:
                    network_set["v6DNSPrimary"] = value

                elif "IP6.DNS[2]" in key:
                    network_set["v6DNSOther"] = value

            else:
                if "ipv4.method" in key:
                    network_set["v4dhcp_en"] = value

                elif "IP4.ADDRESS[1]" in key:
                    ip_net = ipaddress.ip_interface(value)
                    network_set["IPv4Address"] = str(ip_net.ip)
                    network_set["v4Subnet"] = str(ip_net.network.netmask)

                elif "IP4.GATEWAY" in key:
                    if value == "--":
                        network_set["v4DefaultGateway"] = ""
                    else:
                        network_set["v4DefaultGateway"] = value

                elif "ipv4.ignore-auto-dns" in key:
                    if value == "no":
                        network_set["v4AutoDNS"] = "auto"
                    else:
                        network_set["v4AutoDNS"] = "manual"

                elif "IP4.DNS[1]" in key:
                    network_set["v4DNSPrimary"] = value

                elif "IP4.DNS[2]" in key:
                    network_set["v4DNSOther"] = value


def get_ethernet_info(interface_name, local_network_set):
    command = f'sudo nmcli -f ipv4.method,ip4.ADDRESS,ip4.gateway,ip4.dns,ipv4.ignore-auto-dns con show "{interface_name}"'
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    parse_nmcli_output(result.stdout.splitlines(), local_network_set, is_ipv6=False)

    command = f'sudo nmcli -f ipv6.method,ip6.address,ip6.gateway,ip6.dns,ipv6.ignore-auto-dns con show "{interface_name}"'
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    parse_nmcli_output(result.stdout.splitlines(), local_network_set, is_ipv6=True)

    return local_network_set


def collect_allnetwork_info():
    interface_names = read_net_name()
    network_info_list = []

    for i, interface_name in enumerate(interface_names):
        ethernet_info = get_ethernet_info(interface_name, all_network_set[i])
        network_info_list.append(ethernet_info)

    return network_info_list


def delete_old_logs(location, days_to_keep=1100):
    current_time = time.time()

    for subdir in ["error", "operation", "sensor", "journal"]:
        subdir_path = os.path.join(location, subdir)
        if os.path.isdir(subdir_path):
            for root, dirs, files in os.walk(subdir_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    if os.path.isfile(file_path):
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > days_to_keep * 86400:
                            os.remove(file_path)
                            print(f"Deleted old log file: {file_path}")


def write_sensor_log():
    try:
        column_names = (
            ["time"]
            + list(sensor_map.values())
            + list(ctrl_map.values())
            + list(temporary_map.values())
            + list(fan_status_map["fan_power"].values())
            + list(fan_status_map["fan_rpm"].values())
        )
        log_dir = f"{log_path}/logs/sensor"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file = f"{log_dir}/sensor.log.{datetime.now().strftime('%Y-%m-%d')}.csv"
    except Exception as e:
        journal_logger.info(f"create sensor log file error: {e}")

    try:
        if not os.path.exists(log_file):
            os.makedirs(log_dir, exist_ok=True)
        with open(log_file, mode="a", newline="") as file:
            writer = csv.writer(file)

            if file.tell() == 0:
                writer.writerow(column_names)
            else:
                with open(log_file, "r") as file:
                    file.seek(0)
                    file.readline()
                    last_log_date = file.readline().split(",")[0]
                    last_log_date = last_log_date.split()[0]

                    current_date = datetime.now().strftime("%Y-%m-%d")

                    if current_date != last_log_date:
                        file.close()

                        log_file = f"{log_dir}/sensor.log.{current_date}.csv"
                        with open(log_file, mode="a", newline="") as new_file:
                            writer = csv.writer(new_file)
                            writer.writerow(column_names)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(
                [timestamp]
                + list(logData["value"].values())
                + list(logData["setting"].values())
                + list(logData["temporary_data"].values())
                + list(logData["fan_power"].values())
                + list(logData["fan_rpm"].values())
            )
    except Exception as e:
        journal_logger.info(f"write sensor log error: {e}")


def load_signal_records():
    try:
        if not os.path.exists(f"{web_path}/json/signal_records.json"):
            with open(f"{web_path}/json/signal_records.json", "w") as file:
                file.write("[]")

        with open(f"{web_path}/json/signal_records.json", "r") as json_file:
            global signal_records
            signal_records = json.load(json_file)
            if len(signal_records) > 500:
                signal_records = signal_records[:500]
                with open(f"{web_path}/json/signal_records.json", "w") as json_file:
                    json.dump(signal_records, json_file, indent=4)
    except FileNotFoundError:
        signal_records = []


def load_downtime_signal_records():
    try:
        if not os.path.exists(f"{web_path}/json/downtime_signal_records.json"):
            with open(f"{web_path}/json/downtime_signal_records.json", "w") as file:
                file.write("[]")

        with open(f"{web_path}/json/downtime_signal_records.json", "r") as json_file:
            global downtime_signal_records
            downtime_signal_records = json.load(json_file)
            if len(downtime_signal_records) > 500:
                downtime_signal_records = downtime_signal_records[:500]
                with open(
                    f"{web_path}/json/downtime_signal_records.json", "w"
                ) as json_file:
                    json.dump(downtime_signal_records, json_file, indent=4)
    except FileNotFoundError:
        downtime_signal_records = []


def save_to_json():
    signal_records.sort(key=lambda x: x["on_time"], reverse=True)
    if not os.path.exists(f"{web_path}/json/signal_records.json"):
        with open(f"{web_path}/json/signal_records.json", "w") as file:
            file.write("[]")

    with open(f"{web_path}/json/signal_records.json", "w") as json_file:
        json.dump(signal_records, json_file, indent=4)


def save_to_downtime_json():
    downtime_signal_records.sort(key=lambda x: x["on_time"], reverse=True)
    if not os.path.exists(f"{web_path}/json/downtime_signal_records.json"):
        with open(f"{web_path}/json/downtime_signal_records.json", "w") as file:
            file.write("[]")

    with open(f"{web_path}/json/downtime_signal_records.json", "w") as json_file:
        json.dump(downtime_signal_records, json_file, indent=4)


def record_signal_on(signal_name, singnal_value):
    load_signal_records()
    max_records_to_check = min(50, len(signal_records))
    for record in signal_records[:max_records_to_check]:
        if (
            record["signal_value"] == singnal_value
            and record["on_time"] is not None
            and record["off_time"] is None
        ):
            return
        # if (
        #     record["signal_name"] == signal_name
        #     and record["on_time"] is not None
        #     and record["off_time"] is None
        # ):
        #     return

    record = {
        "signal_name": signal_name,
        "on_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "off_time": None,
        "signal_value": singnal_value,
    }
    signal_records.append(record)
    save_to_json()


def record_downtime_signal_on(signal_name, singnal_value):
    load_downtime_signal_records()
    max_records_to_check = min(50, len(downtime_signal_records))
    for record in downtime_signal_records[:max_records_to_check]:
        if (
            record["signal_name"] == signal_name
            and record["on_time"] is not None
            and record["off_time"] is None
        ):
            return

    record = {
        "signal_name": signal_name,
        "on_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "off_time": None,
        "signal_value": singnal_value,
    }
    downtime_signal_records.append(record)
    save_to_downtime_json()


def record_signal_off(signal_name, singnal_value):
    load_signal_records()
    max_records_to_check = min(50, len(signal_records))
    for record in signal_records[:max_records_to_check]:
        if (
            record["signal_value"] == singnal_value
            and record["on_time"] is not None
            and record["off_time"] is None
        ):
            record["off_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_to_json()
            break


def record_downtime_signal_off(signal_name, singnal_value):
    load_downtime_signal_records()
    max_records_to_check = min(50, len(downtime_signal_records))
    for record in downtime_signal_records[:max_records_to_check]:
        if (
            record["signal_name"] == signal_name
            and record["on_time"] is not None
            and record["off_time"] is None
        ):
            record["off_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_to_downtime_json()
            break


def delete_old_file():
    log_dir = f"{log_path}/logs"
    current_date = dt.date.today()
    one_year_ago = current_date - dt.timedelta(days=365 * 3)
    for file in glob.glob(os.path.join(log_dir, "*.csv")):
        modified_date = dt.date.fromtimestamp(os.path.getmtime(file))
        if modified_date < one_year_ago:
            os.remove(file)


def change_to_metric():
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
    thr_reg = (sum(1 for key in thrshd if "Thr_" in key)) * 2

    for key in thrshd:
        value = thrshd[key]
        if index < int(thr_reg / 2):
            word1, word2 = cvt_float_byte(value)
            registers.append(word2)
            registers.append(word1)
        index += 1

    grouped_register = [registers[i : i + 64] for i in range(0, len(registers), 64)]

    i = 0
    for group in grouped_register:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(1000 + i * 64, group)
        except Exception as e:
            print(f"write register thrshd issue:{e}")
            return retry_modbus(1000 + i * 64, group, "register")
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
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(993, [temp2, temp1])
            client.write_registers(226, [temp2, temp1])
    except Exception as e:
        print(f"write oil temp error:{e}")
        return retry_modbus_2reg(993, [temp2, temp1], 226, [temp2, temp1])

    prsr1, prsr2 = cvt_float_byte(ctr_data["value"]["oil_pressure_set"])
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(991, [prsr2, prsr1])
            client.write_registers(224, [prsr2, prsr1])
    except Exception as e:
        print(f"write oil pressure error:{e}")
        return retry_modbus_2reg(991, [prsr2, prsr1], 224, [prsr2, prsr1])

    key_list = list(measure_data.keys())
    for key in key_list:
        if "Temp" in key:
            measure_data[key] = (measure_data[key] - 32) * 5.0 / 9.0

        if "Prsr" in key:
            measure_data[key] = measure_data[key] * 6.89476

        if "f1" in key or "f2" in key:
            measure_data[key] = measure_data[key] / 0.2642
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            for i, (key, value) in enumerate(measure_data.items()):
                word1, word2 = cvt_float_byte(value)
                registers = [word2, word1]
                client.write_registers(901 + i * 2, registers)
    except Exception as e:
        print(f"measure data input error:{e}")
        return retry_modbus(901 + i * 2, registers, "register")
    
    t1 = round((float(auto_mode_setting["t1"]) - 32) * 5.0 / 9.0)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(980, [t1])
    except Exception as e:
        print(f"write t1:{e}")
        return retry_modbus(980, [t1], "register")


def change_to_imperial():
    key_list = list(thrshd.keys())
    for key in key_list:
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
    thr_count = sum(1 for key in thrshd if "Thr_" in key) * 2

    for key in thrshd.keys():
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
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(1000 + i * 64, group)
        except Exception as e:
            print(f"write register thrshd issue:{e}")
            return retry_modbus(1000 + i * 64, group, "register")
        i += 1

    try:
        word1, word2 = cvt_float_byte(ctr_data["value"]["oil_pressure_set"])
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(224, [word2, word1])
    except Exception as e:
        print(f"write oil pressure error:{e}")
        return retry_modbus(224, [word2, word1], "register")

    try:
        word1, word2 = cvt_float_byte(ctr_data["value"]["oil_temp_set"])
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(226, [word2, word1])
    except Exception as e:
        print(f"write oil pressure error:{e}")
        return retry_modbus(226, [word2, word1], "register")

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
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(993, [temp2, temp1])
    except Exception as e:
        print(f"write oil temp error:{e}")
        return retry_modbus(993, [temp2, temp1], "register")

    pressure1, pressure2 = cvt_float_byte(ctr_data["value"]["oil_pressure_set"])
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(991, [pressure2, pressure1])
    except Exception as e:
        print(f"write oil pressure error:{e}")
        return retry_modbus(991, [pressure2, pressure1], "register")

    key_list = list(measure_data.keys())
    for key in key_list:
        if "Temp" in key:
            measure_data[key] = measure_data[key] * 9.0 / 5.0 + 32.0

        if "Prsr" in key:
            measure_data[key] = measure_data[key] * 0.145038

        if "f1" in key or "f2" in key:
            measure_data[key] = measure_data[key] * 0.2642

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            for i, (key, value) in enumerate(measure_data.items()):
                word1, word2 = cvt_float_byte(value)
                registers = [word2, word1]
                client.write_registers(901 + i * 2, registers)
    except Exception as e:
        print(f"measure data input error:{e}")
        return retry_modbus(901 + i * 2, registers, "register")
    
    t1 = round((auto_mode_setting["t1"]) * 9.0 / 5.0 + 32.0)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(980, [t1])
    except Exception as e:
        print(f"write t1:{e}")
        return retry_modbus(980, [t1], "register")

def auto_import(data):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(960, int(data["fan"]))
            client.write_register(961, int(data["pump"]))

    except Exception as e:
        print(f"auto setting:{e}")
        return retry_modbus(960, [int(data["fan"]), int(data["pump"])], "register")

    op_logger.info(
        "Auto Mode Redundant Sensor Broken Setting Inputs received successfully"
    )
    return "Inputs received successfully"

def dpt_error_import(data):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(974, int(data["fan"]))
            client.write_register(980, int(data["t1"]))
    except Exception as e:
        print(f"auto setting:{e}")
        return retry_modbus_2reg(974, [int(data["fan"])], 980, int(data["t1"]))

    op_logger.info(
        "Dew Point Error Setting Inputs received successfully"
    )
    return "Inputs received successfully"

def auto_mode_import(data):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            fan_rpm = data["fan"] * 160
            client.write_register(533, int(fan_rpm))

    except Exception as e:
        print(f"auto setting:{e}")
        return retry_modbus(533, [int(fan_rpm)], "register")

    op_logger.info(
        "Fan Speed in Auto Mode Setting successfully"
    )
    return "Inputs received successfully"

def threshold_import(input):
    for key, value in input.items():
        if key in thrshd:
            thrshd[key] = value

    registers = []
    grouped_register = []
    coil_registers = []
    index = 0
    thr_reg = (sum(1 for key in thrshd if "Thr_" in key)) * 2

    for key in thrshd.keys():
        value = thrshd[key]
        if key.endswith("_trap"):
            coil_registers.append(value)
        else:
            if index < int(thr_reg / 2):
                word1, word2 = cvt_float_byte(value)
                registers.append(word2)
                registers.append(word1)
            else:
                registers.append(int(value))
            index += 1

    grouped_register = [registers[i : i + 64] for i in range(0, len(registers), 64)]

    i = 0
    for group in grouped_register:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(1000 + i * 64, group)
        except Exception as e:
            print(f"write register thrshd issue:{e}")
            return retry_modbus(1000 + i * 64, group, "register")
        i += 1

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 2000), coil_registers)
    except Exception as e:
        print(f"write trap error: {e}")
        return retry_modbus((8192 + 2000), coil_registers, "coil")

    for key in thrshd.keys():
        value = thrshd[key]
        op_logger.info("%s: %s", key, value)

    return "Setting Successful"


def adjust_import(input):
    for key, value in input.items():
        if key in sensor_adjust:
            sensor_adjust[key] = value

    registers = []

    for key in sensor_adjust.keys():
        value = sensor_adjust[key]
        word1, word2 = cvt_float_byte(value)
        registers.append(word2)
        registers.append(word1)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(1400, registers)
    except Exception as e:
        print(f"write sensor adjust error:{e}")
        return retry_modbus(1400, registers, "register")

    op_logger.info("Sensor Adjust Inputs received Successfully")

    return "Inputs received successfully"

def rack_opening_import(data):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(370, int(data))
    except Exception as e:
        print(f"rack opening setting:{e}")
        return retry_modbus(370, [int(data)], "register")

    op_logger.info(
        "Rack Opening Setting Inputs received successfully"
    )
    return "Inputs received successfully"

def pid_import(data):
    for key in data.keys():
        if key in pid_order:
            register = []
            sample_time = (
                data[key]["sample_time_temp"]
                if key == "temperature"
                else data[key]["sample_time_pressure"]
            )
            start_address = 550 if key == "temperature" else 510
            sample_time_address = start_address
            data_start_address = start_address + 3

            for pid_key in pid_order[key]:
                if pid_key in data[key]:
                    if (
                        not pid_key == "sample_time_pressure"
                        and not pid_key == "sample_time_temp"
                    ):
                        register.append(int(data[key][pid_key]))
            try:
                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    client.write_register(sample_time_address, int(sample_time))
                    client.write_registers(data_start_address, register)
            except Exception as e:
                print(f"write pid data error:{e}")
                return retry_modbus(data_start_address, register, "register")


def unit_import(data):
    if data == "metric":
        coil_value = False
    elif data == "imperial":
        coil_value = True

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coil(address=(8192 + 500), value=coil_value)
    except Exception as e:
        print(f"write in unit error:{e}")
        return retry_modbus((8192 + 500), coil_value, "coil")

    change_data_by_unit()


def log_interval_import(data):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(3000, data)

        return "Log Interval Updated Successfully"
    except Exception as e:
        print(f"error:{e}")


def snmp_import(data):
    with open(f"{snmp_path}/snmp/snmp.json", "w") as json_file:
        json.dump(data, json_file)


def network_set_import(interface_name, input):
    try:
        if input["v4dhcp_en"] == "auto":
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "modify",
                    interface_name,
                    "ipv4.method",
                    "auto",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv4.addresses",
                    "",
                    "ipv4.gateway",
                    "",
                ],
                check=True,
            )
        elif input["v4dhcp_en"] == "manual":
            mask = input["v4Subnet"]
            network = ipaddress.IPv4Network("0.0.0.0/" + mask, strict=False)

            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "modify",
                    interface_name,
                    "ipv4.method",
                    "manual",
                    "ipv4.address",
                    f"{input['IPv4Address']}/{network.prefixlen}",
                    "ipv4.gateway",
                    input["v4DefaultGateway"],
                ],
                check=True,
            )

        if input["v4AutoDNS"] == "auto":
            subprocess.run(
                ["sudo", "nmcli", "con", "mod", interface_name, "ipv4.dns", ""],
                check=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv4.ignore-auto-dns",
                    "no",
                ],
                check=True,
            )
        elif input["v4AutoDNS"] == "manual":
            dns_servers = []
            if input["v4DNSPrimary"]:
                dns_servers.append(input["v4DNSPrimary"])
            if input["v4DNSOther"]:
                dns_servers.append(input["v4DNSOther"])

            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv4.ignore-auto-dns",
                    "yes",
                ],
                check=True,
            )
            subprocess.run(
                ["sudo", "nmcli", "con", "mod", interface_name, "ipv4.dns", ""],
                check=True,
            )
            if dns_servers:
                dns_servers_str = " ".join(dns_servers)
                print("Setting DNS servers to:", dns_servers_str)
                subprocess.run(
                    [
                        "sudo",
                        "nmcli",
                        "con",
                        "mod",
                        interface_name,
                        "ipv4.dns",
                        dns_servers_str,
                    ],
                    check=True,
                )

        if input["v6dhcp_en"] == "auto":
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "modify",
                    interface_name,
                    "ipv6.method",
                    "auto",
                ],
                check=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv6.addresses",
                    "",
                    "ipv6.gateway",
                    "",
                ],
                check=True,
            )
        elif input["v6dhcp_en"] == "manual":
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "modify",
                    interface_name,
                    "ipv6.method",
                    "manual",
                    "ipv6.address",
                    f"{input['IPv6Address']}/{input['v6Subnet']}",
                    "ipv6.gateway",
                    input["v6DefaultGateway"],
                ],
                check=True,
            )

        if input["v6AutoDNS"] == "auto":
            subprocess.run(
                ["sudo", "nmcli", "con", "mod", interface_name, "ipv6.dns", ""],
                check=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv6.ignore-auto-dns",
                    "no",
                ],
                check=True,
            )
        elif input["v6AutoDNS"] == "manual":
            dns_servers = []
            if input["v6DNSPrimary"]:
                dns_servers.append(input["v6DNSPrimary"])
            if input["v6DNSOther"]:
                dns_servers.append(input["v6DNSOther"])

            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv6.ignore-auto-dns",
                    "yes",
                ],
                check=True,
            )
            subprocess.run(
                ["sudo", "nmcli", "con", "mod", interface_name, "ipv6.dns", ""],
                check=True,
            )
            if dns_servers:
                dns_servers_str = " ".join(dns_servers)
                print("Setting DNS servers to:", dns_servers_str)
                subprocess.run(
                    [
                        "sudo",
                        "nmcli",
                        "con",
                        "mod",
                        interface_name,
                        "ipv6.dns",
                        dns_servers_str,
                    ],
                    check=True,
                )

        subprocess.run(
            ["sudo", "systemctl", "restart", "NetworkManager"],
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def read_unit():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            r = client.read_coils(address=(8192 + 500), count=1)

            if r.bits[0]:
                system_data["value"]["unit"] = "imperial"
                ctr_data["unit"]["unit_temp"] = "°F"
                ctr_data["unit"]["unit_prsr"] = "psi"
            else:
                system_data["value"]["unit"] = "metric"
                ctr_data["unit"]["unit_temp"] = "°C"
                ctr_data["unit"]["unit_prsr"] = "kPa"

            if r.bits[0]:
                setting_limit["control"]["oil_temp_set_up"] = 55.0 * 9.0 / 5.0 + 32.0
                setting_limit["control"]["oil_temp_set_low"] = 25.0 * 9.0 / 5.0 + 32.0
                setting_limit["control"]["oil_pressure_set_up"] = 750 * 0.145038
                setting_limit["control"]["oil_pressure_set_low"] = 0
            else:
                setting_limit["control"]["oil_temp_set_up"] = 55.0
                setting_limit["control"]["oil_temp_set_low"] = 25.0
                setting_limit["control"]["oil_pressure_set_up"] = 750
                setting_limit["control"]["oil_pressure_set_low"] = 0
    except Exception as e:
        print(f"unit error:{e}")


def change_to_adjust(key):
    except_key = [
        "pH_low",
        "pH_high",
    ]
    try:
        if key in except_key:
            return "pH_Factor"

        if key.endswith("_high"):
            new_key = key.replace("_high", "_Factor")
        elif key.endswith("_low"):
            new_key = key.replace("_low", "_Factor")

        parts = new_key.split("_")
        new_key = "_".join(part[0].upper() + part[1:] for part in parts)
    except Exception as e:
        print(f"{key} error:{e}")

    return new_key


def retry_modbus(address, value, method, max_retries=3):
    attempt = 0

    while attempt < max_retries:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                if method == "register":
                    client.write_registers(address, value)
                elif method == "coil":
                    client.write_coils(address, value)
                return True
        except Exception as e:
            attempt += 1
            print(f"Write attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("Max retries reached. Write failed.")
                return jsonify(
                    {
                        "status": "error",
                        "title": "Error",
                        "message": "Writing failed",
                    }
                )


def retry_modbus_both(address_reg, value_reg, address_coil, value_coil, max_retries=3):
    attempt = 0

    while attempt < max_retries:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(address_reg, value_reg)
                client.write_coils(address_coil, value_coil)
                return True
        except Exception as e:
            attempt += 1
            print(f"Write attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("Max retries reached. Write failed.")
                return jsonify(
                    {
                        "status": "error",
                        "title": "Error",
                        "message": "Writing failed",
                    }
                )


def retry_modbus_2reg(
    address_reg1, value_reg1, address_reg2, value_reg2, max_retries=3
):
    attempt = 0

    while attempt < max_retries:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(address_reg1, value_reg1)
                client.write_registers(address_reg2, value_reg2)
                return True
        except Exception as e:
            attempt += 1
            print(f"Write attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("Max retries reached. Write failed.")
                return jsonify(
                    {
                        "status": "error",
                        "title": "Error",
                        "message": "Writing failed",
                    }
                )


def retry_modbus_2coil(
    address_coil1, value_coil1, address_coil2, value_coil2, max_retries=3
):
    attempt = 0

    while attempt < max_retries:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils(address_coil1, value_coil1)
                client.write_coils(address_coil2, value_coil2)
                return True
        except Exception as e:
            attempt += 1
            print(f"Write attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("Max retries reached. Write failed.")
                return jsonify(
                    {
                        "status": "error",
                        "title": "Error",
                        "message": "Writing failed",
                    }
                )

def retry_modbus_3coil(
    address_coil1, value_coil1, address_coil2, value_coil2, address_coil3, value_coil3,max_retries=3
):
    attempt = 0

    while attempt < max_retries:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils(address_coil1, value_coil1)
                client.write_coils(address_coil2, value_coil2)
                client.write_coils(address_coil3, value_coil3)
                return True
        except Exception as e:
            attempt += 1
            print(f"Write attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("Max retries reached. Write failed.")
                return jsonify(
                    {
                        "status": "error",
                        "title": "Error",
                        "message": "Writing failed",
                    }
                )

def retry_modbus_setmode_singlecoil(address_coil, value_coil, max_retries=3):
    attempt = 0

    while attempt < max_retries:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils(address_coil, value_coil)
                return True
        except Exception as e:
            attempt += 1
            print(f"Write attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("Max retries reached. Write failed.")
                return False


def retry_modbus_setmode(
    address_coil1, value_coil1, address_coil2, value_coil2, max_retries=3
):
    attempt = 0

    while attempt < max_retries:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils(address_coil1, value_coil1)
                client.write_coils(address_coil2, value_coil2)
                return True
        except Exception as e:
            attempt += 1
            print(f"Write attempt {attempt} failed: {e}")
            if attempt == max_retries:
                print("Max retries reached. Write failed.")
                return False


def update_json_restore_times():
    try:
        if not os.path.exists(f"{web_path}/json/signal_records.json"):
            with open(f"{web_path}/json/signal_records.json", "w") as file:
                file.write("[]")
        with open(f"{web_path}/json/signal_records.json", "r") as file:
            data = json.load(file)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for entry in data:
            if entry["off_time"] is None:
                entry["off_time"] = current_time

        with open(f"{web_path}/json/signal_records.json", "w") as file:
            json.dump(data, file, indent=4)

    except Exception as e:
        print(f"更新 JSON 文件時發生錯誤: {e}")
    try:
        if not os.path.exists(f"{web_path}/json/downtime_signal_records.json"):
            with open(f"{web_path}/json/downtime_signal_records.json", "w") as file:
                file.write("[]")
        with open(f"{web_path}/json/downtime_signal_records.json", "r") as file:
            data = json.load(file)

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for entry in data:
            if entry["off_time"] is None:
                entry["off_time"] = current_time

        with open(f"{web_path}/json/downtime_signal_records.json", "w") as file:
            json.dump(data, file, indent=4)

    except Exception as e:
        print(f"更新 JSON 文件時發生錯誤: {e}")


def change_data_by_unit():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            last_unit = client.read_coils((8192 + 501), 1, unit=modbus_slave_id)
            current_unit = client.read_coils((8192 + 500), 1, unit=modbus_slave_id)

            last_unit = last_unit.bits[0]
            current_unit = current_unit.bits[0]

            if current_unit:
                system_data["value"]["unit"] = "imperial"
            else:
                system_data["value"]["unit"] = "metric"

            if last_unit:
                system_data["value"]["last_unit"] = "imperial"
            else:
                system_data["value"]["last_unit"] = "metric"

            print(f"{last_unit} -> {current_unit}")

            if current_unit and current_unit != last_unit:
                change_to_imperial()
            elif not current_unit and current_unit != last_unit:
                change_to_metric()

            client.write_coils((8192 + 501), [current_unit])

    except Exception as e:
        print(f"unit set error:{e}")
        return retry_modbus((8192 + 501), [current_unit], "coil")


def return_to_manual_when_logout():
    try:
        with ModbusTcpClient(port=modbus_port, host=modbus_host) as client:
            r = client.read_coils((8192 + 516), 1)
            if r.bits[0]:
                client.write_coils((8192 + 516), [False])
                client.write_coils((8192 + 505), [True])
    except Exception as e:
        print(f"return to manual error:{e}")
        retry_modbus_2coil((8192 + 516), [False], (8192 + 505), [True])


def cvt_registers_to_float(reg1, reg2):
    temp1 = [reg1, reg2]
    decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
        temp1, byteorder=Endian.Big, wordorder=Endian.Little
    )
    decoded_value_big_endian = decoder_big_endian.decode_32bit_float()
    return decoded_value_big_endian


def read_split_register(r, i):
    return (r[i + 1] << 16) | r[i]


def cvt_float_byte(value):
    float_as_bytes = struct.pack(">f", float(value))
    word1, word2 = struct.unpack(">HH", float_as_bytes)
    return word1, word2


def set_mode(value_to_write):
    coil_value = False

    if value_to_write == "auto":
        coil_value = False
    else:
        coil_value = True

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coil((8192 + 505), coil_value)
    except Exception as e:
        print(f"set op mode:{e}")
        return retry_modbus_setmode_singlecoil((8192 + 505), coil_value)

    if value_to_write == "engineer":
        coil_value = True
    else:
        coil_value = False
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coil((8192 + 516), coil_value)
    except Exception as e:
        print(f"set engineer mode:{e}")
        return retry_modbus_setmode_singlecoil((8192 + 516), coil_value)

    if value_to_write == "inspection":
        coil_value = True
    else:
        coil_value = False
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coil((8192 + 517), coil_value)
    except Exception as e:
        print(f"set inspection mode:{e}")
        return retry_modbus_setmode_singlecoil((8192 + 517), coil_value)

    if value_to_write == "auto":
        coil_value = True
    elif value_to_write == "manual":
        coil_value = True
    elif value_to_write == "stop":
        coil_value = False
    elif value_to_write == "engineer":
        coil_value = True
    elif value_to_write == "inspection":
        coil_value = True
    else:
        coil_value = False

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coil(address=(8192 + 514), value=coil_value)
            client.write_coil((8192 + 600), result_data["force_change_mode"])
    except Exception as e:
        print(f"setting force change mode and set mode error:{e}")
        return retry_modbus_setmode(
            (8192 + 514), coil_value, (8192 + 600), result_data["force_change_mode"]
        )

    op_logger.info("Mode Updated Successfully. Mode: %s", value_to_write)
    return True

### 轉換 freq
def translate_pump_speed(speed):
    ps = (float(speed)) / 100 * 16000.0
    ps = int(ps)
    return ps


def translate_fan_speed(speed):
    fan = (float(speed)) / 100 * 16000.0
    fan = int(fan)
    return fan


def set_p1_reg(speed):
    speed1, speed2 = cvt_float_byte(speed)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(246, [speed2, speed1])
        op_logger.info("Pump Speed Updated Successfully. Pump1 Speed: %s", speed)
    except Exception as e:
        print(f"pump speed reg setting error:{e}")
        return retry_modbus(246, speed, "register")


def set_p1(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 6660), speed)
    except Exception as e:
        print(f"pump speed 1 setting error:{e}")
        return retry_modbus((20480 + 6660), speed, "register")


def set_p2(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers((20480 + 6700), speed)
    except Exception as e:
        print(f"pump speed 2 setting error:{e}")
        return retry_modbus((20480 + 6700), speed, "register")


def set_p3(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers((20480 + 6740), speed)
    except Exception as e:
        print(f"pump speed setting error:{e}")
        return retry_modbus((20480 + 6740), speed, "register")


def set_fan_reg(speed):
    fan1, fan2 = cvt_float_byte(speed)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(470, [fan2, fan1])
        op_logger.info("Pump Speed Updated Successfully. Pump1 Speed: %s", speed)
    except Exception as e:
        print(f"fan speed setting error:{e}")
        return retry_modbus(470, speed, "register")


def set_fan1(speed):
    base_addr = 20480
    offsets = [7020, 7060, 7100, 7140]
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            for offset in offsets:
                client.write_register(base_addr + offset, speed)
    except Exception as e:
        print(f"Fan speed1 setting error:{e}")
        for offset in offsets:
            result = retry_modbus(20480 + offset, [speed], "register")
            if isinstance(result, dict) and result.get("status") == "error":
                return result
        return any(result)


def set_fan2(speed):
    base_addr = 20480
    offsets = [7380, 7420, 7460, 7500]
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            for offset in offsets:
                client.write_register(base_addr + offset, speed)
    except Exception as e:
        print(f"Fan speed2 setting error:{e}")
        for offset in offsets:
            result = retry_modbus(20480 + offset, [speed], "register")
            if isinstance(result, dict) and result.get("status") == "error":
                return result
        return any(result)


def set_p_check(p_check):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 820), p_check)
    except Exception as e:
        print(f"Pump speed setting error:{e}")
        return retry_modbus((8192 + 820), p_check, "coil")


def set_f_check(f_check):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 850), f_check)
    except Exception as e:
        print(f"Pump speed setting error:{e}")
        return retry_modbus((8192 + 850), f_check, "coil")


def read_modbus_data():
    global \
        prev_plc_error, \
        light_mark, \
        tcount_log, \
        error_data, \
        pc2_active, \
        previous_alert_states, \
        previous_error_states, \
        previous_rack_states, \
        previous_warning_states
    current_date = datetime.now().strftime("%Y-%m-%d")
    last_date = datetime.now().strftime("%Y-%m-%d")
    flag = False
    sensorData["error"]["PLC"] = False
    start_time = time.time()
    check_file_age = 0
    plc_status_cnt = 0
    plc_status_cnt = 0
    error_count = 0
    warning_count = 0
    alert_count = 0
    rack_count = 0

    while True:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                r = client.read_holding_registers(0, 10)
                if r.isError():
                    journal_logger.info(f"connect error: {r}")
                    raise Exception("error occured")
                sensorData["error"]["PLC"] = False
                record_signal_off(
                    sensorData["err_log"]["error"]["PLC"].split()[0],
                    sensorData["err_log"]["error"]["PLC"],
                )
                plc_status_cnt = 0
                prev_plc_error = False  # 連接恢復正常時，重置 prev_plc_error
        except Exception as e:
            if plc_status_cnt < 3:
                plc_status_cnt += 1
            else:
                sensorData["error"]["PLC"] = True
                if not prev_plc_error:  # 避免重複記錄
                    if sensorData["err_log"]["error"]["PLC"] not in error_data:
                        error_data.append(sensorData["err_log"]["error"]["PLC"])
                    app.logger.warning(sensorData["err_log"]["error"]["PLC"])
                    record_signal_on(
                        sensorData["err_log"]["error"]["PLC"].split()[0],
                        sensorData["err_log"]["error"]["PLC"],
                    )
                    prev_plc_error = True  # 記錄錯誤狀態
                    print(f"plc connection error: {e}")

            time.sleep(1)
            continue

        ### 從modbus讀取PLC的版號
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                r = client.read_holding_registers(990, 1)
                sensorData["plc_version"] = r.registers[0]
        except Exception as e:
            print(f"plc version error: {e}")
    
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                read_oc = client.read_coils((8192 + 700), 1)
                ctr_data["downtime_error"]["oc_issue"] = read_oc.bits[0]

                read_ats = client.read_coils((8192 + 10), 2, unit=modbus_slave_id)
                sensorData["ats_status"]["ATS1"] = read_ats.bits[0]
                sensorData["ats_status"]["ATS2"] = read_ats.bits[1]

                read_mc1 = client.read_coils(2, 2, unit=modbus_slave_id)
                read_mc2 = client.read_coils(5, 1, unit=modbus_slave_id)
                read_mc3 = client.read_coils(10, 2, unit=modbus_slave_id)

                ctr_data["mc"]["mc1_sw"] = read_mc1.bits[0]
                ctr_data["mc"]["mc2_sw"] = read_mc1.bits[1]
                ctr_data["mc"]["resultMC1"] = read_mc1.bits[0]
                ctr_data["mc"]["resultMC2"] = read_mc1.bits[1]

                ctr_data["mc"]["mc3_sw"] = read_mc2.bits[0]
                ctr_data["mc"]["resultMC3"] = read_mc2.bits[0]

                ctr_data["mc"]["fan_mc1"] = read_mc3.bits[0]
                ctr_data["mc"]["fan_mc1_result"] = read_mc3.bits[0]
                ctr_data["mc"]["fan_mc2"] = read_mc3.bits[1]
                ctr_data["mc"]["fan_mc2_result"] = read_mc3.bits[1]

                read_ver = client.read_coils((8192 + 803), 11)
                ver_switch["median_switch"] = read_ver.bits[0]
                ver_switch["coolant_quality_meter_switch"] = read_ver.bits[1]
                ver_switch["fan_count_switch"] = read_ver.bits[2]
                ver_switch["liquid_level_1_switch"] = read_ver.bits[3]
                ver_switch["liquid_level_2_switch"] = read_ver.bits[4]
                ver_switch["liquid_level_3_switch"] = read_ver.bits[5]
                ver_switch["leakage_sensor_1_switch"] = read_ver.bits[6]
                ver_switch["leakage_sensor_2_switch"] = read_ver.bits[7]
                ver_switch["leakage_sensor_3_switch"] = read_ver.bits[8]
                ver_switch["leakage_sensor_4_switch"] = read_ver.bits[9]
                ver_switch["leakage_sensor_5_switch"] = read_ver.bits[10]
                
                if not os.path.exists(f"{web_path}/json/version.json"):
                    with open(f"{web_path}/json/version.json", "w") as file:
                        file.write("")
                with open(f"{web_path}/json/version.json", "w") as json_file:
                    json.dump(ver_switch, json_file, indent=4)
                    
        except Exception as e:
            print(f"read oc issue error: {e}")

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                read_sec = client.read_holding_registers(3000, 1, unit=modbus_slave_id)
                sampling_rate["number"] = read_sec.registers[0]

                read_temp = client.read_holding_registers(address=993, count=2)
                oil_temp_set = cvt_registers_to_float(
                    read_temp.registers[0], read_temp.registers[1]
                )
                ctr_data["value"]["resultTemp"] = oil_temp_set
                ctr_data["value"]["oil_temp_set"] = oil_temp_set

                read_prsr = client.read_holding_registers(address=991, count=2)
                oil_pressure_set = cvt_registers_to_float(
                    read_prsr.registers[0], read_prsr.registers[1]
                )
                ctr_data["value"]["resultPressure"] = oil_pressure_set
                ctr_data["value"]["oil_pressure_set"] = oil_pressure_set

                read_swap = client.read_holding_registers(303, 2, unit=modbus_slave_id)
                swap = cvt_registers_to_float(
                    read_swap.registers[0], read_swap.registers[1]
                )
                ctr_data["value"]["p_swap"] = swap
                ctr_data["value"]["resultSwap"] = swap

                read_inspect = client.read_holding_registers(973, 1)
                ctr_data["inspect_action"] = read_inspect.registers[0]

                read_pump_sec = client.read_holding_registers(
                    740, 1, unit=modbus_slave_id
                )
                inspection_time["pump_open_time"] = read_pump_sec.registers[0]

        except Exception as e:
            print(f"read sampling rate error:{e}")

        try:
            with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                r = client.read_discrete_inputs(27, 5, unit=modbus_slave_id)
                sensorData["mc"]["mc1_sw"] = r.bits[0]
                sensorData["mc"]["mc2_sw"] = r.bits[1]
                sensorData["mc"]["mc3_sw"] = r.bits[2]
                sensorData["mc"]["fan_mc1"] = r.bits[3]
                sensorData["mc"]["fan_mc2"] = r.bits[4]
        except Exception as e:
            print(f"read mc error: {e}")

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                value_reg = (len(sensorData["value"].keys())) * 2
                r = client.read_holding_registers(5000, value_reg, unit=modbus_slave_id)

                keys_list = list(sensorData["value"].keys())

                for j, i in enumerate(range(0, value_reg, 2)):
                    temp1 = [r.registers[i], r.registers[i + 1]]
                    decoder = BinaryPayloadDecoder.fromRegisters(
                        temp1, byteorder=Endian.Big, wordorder=Endian.Little
                    )
                    sensorData["value"][keys_list[j]] = decoder.decode_32bit_float()
        except Exception as e:
            print(f"read status data error:{e}")

        # sensorData["value"]['fan_freq1']=5
        # 測試用開始
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                value_reg = (len(sensorData["eletricity"].keys())) * 2
                r = client.read_holding_registers(7000, 4, unit=modbus_slave_id)
                keys_list = list(sensorData["eletricity"].keys())
                
                for j, i in enumerate(range(0, value_reg, 2)):
                    temp1 = [r.registers[i], r.registers[i + 1]]
                    decoder = BinaryPayloadDecoder.fromRegisters(
                        temp1, byteorder=Endian.Big, wordorder=Endian.Little
                    )
                    sensorData["eletricity"][keys_list[j]] = decoder.decode_32bit_float()
        except Exception as e:
            print(f"read eletricity data error:{e}")
        # 測試用結束
        # 臨時log開始
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                value_reg = (len(sensorData["temporary_data"].keys())) * 2
                r = client.read_holding_registers(7004, value_reg, unit=modbus_slave_id)
                keys_list = list(sensorData["temporary_data"].keys())
                for j, i in enumerate(range(0, value_reg, 2)):
                    temp1 = [r.registers[i], r.registers[i + 1]]
                    decoder = BinaryPayloadDecoder.fromRegisters(
                        temp1, byteorder=Endian.Big, wordorder=Endian.Little
                    )
                    sensorData["temporary_data"][keys_list[j]] = decoder.decode_32bit_float()
        except Exception as e:
            print(f"read temporary data error:{e}")
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                value_reg = (len(sensorData["fan_power"].keys())) * 2
                r = client.read_holding_registers(7016, value_reg, unit=modbus_slave_id)
                keys_list = list(sensorData["fan_power"].keys())
                for j, i in enumerate(range(0, value_reg, 2)):
                    temp1 = [r.registers[i], r.registers[i + 1]]
                    decoder = BinaryPayloadDecoder.fromRegisters(
                        temp1, byteorder=Endian.Big, wordorder=Endian.Little
                    )
                    sensorData["fan_power"][keys_list[j]] = (
                        decoder.decode_32bit_float()
                    )
        except Exception as e:
            print(f"read fan power data error:{e}")
            
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                value_reg = (len(sensorData["fan_rpm"].keys())) * 2
                r = client.read_holding_registers(7032, value_reg, unit=modbus_slave_id)
                keys_list = list(sensorData["fan_rpm"].keys())
                for j, i in enumerate(range(0, value_reg, 2)):
                    temp1 = [r.registers[i], r.registers[i + 1]]
                    decoder = BinaryPayloadDecoder.fromRegisters(
                        temp1, byteorder=Endian.Big, wordorder=Endian.Little
                    )
                    sensorData["fan_rpm"][keys_list[j]] = decoder.decode_32bit_float()
        except Exception as e:
            print(f"read fan rpm data error:{e}")
        
        # 臨時log結束
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                r = client.read_coils(address=(8192 + 500), count=1)

                if not r.isError():
                    sensorData["unit"]["unit_temp"] = "°F" if r.bits[0] else "°C"
                    sensorData["unit"]["unit_pressure"] = "psi" if r.bits[0] else "kPa"
                    sensorData["unit"]["unit_flow"] = "GPM" if r.bits[0] else "LPM"

                    if r.bits[0]:
                        setting_limit["control"]["oil_temp_set_up"] = (
                            55.0 * 9.0 / 5.0 + 32.0
                        )
                        setting_limit["control"]["oil_temp_set_low"] = (
                            25.0 * 9.0 / 5.0 + 32.0
                        )
                        setting_limit["control"]["oil_pressure_set_up"] = 750 * 0.145038
                        setting_limit["control"]["oil_pressure_set_low"] = 0
                    else:
                        setting_limit["control"]["oil_temp_set_up"] = 55.0
                        setting_limit["control"]["oil_temp_set_low"] = 25.0
                        setting_limit["control"]["oil_pressure_set_up"] = 750.0
                        setting_limit["control"]["oil_pressure_set_low"] = 0
                else:
                    print(f"read error: {r}")

        except Exception as e:
            print(f"read unit/oil temp/oil pressure error:{e}")

        tcount_log = time.time() - start_time

        if tcount_log >= sampling_rate["number"]:
            try:
                for key in sensorData["value"]:
                    if key in logData["value"]:
                        new_data_value = round(sensorData["value"][key], 1)
                        logData["value"][key] = new_data_value

                p1_num = (
                    sensorData["value"]["prsr_clntSply"]
                    if not sensorData["error"]["PrsrClntSply_broken"]
                    else sensorData["value"]["prsr_clntSplySpare"]
                    if sensorData["error"]["PrsrClntSplySpare_broken"]
                    else "-"
                )

                p2_num = (
                    sensorData["value"]["prsr_clntRtn"]
                    if not sensorData["error"]["PrsrClntRtn_broken"]
                    else sensorData["value"]["prsr_clntRtnSpare"]
                    if sensorData["error"]["PrsrClntRtnSpare_broken"]
                    else "-"
                )

                if p1_num == "-" or p2_num == "-":
                    logData["value"]["prsr_diff"] = "-"
                else:
                    logData["value"]["prsr_diff"] = round((p1_num - p2_num), 1)

                for key in ctr_data["value"]:
                    if key in logData["setting"]:
                        if key == "resultMode":
                            logData["setting"][key] = ctr_data["value"][key]
                        elif "resultP" in key and key != "resultPressure":
                            pump_key = f"pump{key[-1]}_check"
                            logData["setting"][key] = (
                                ctr_data["value"]["resultPS"]
                                if ctr_data["value"][pump_key]
                                else 0
                            )
                            logData["setting"][key] = round(logData["setting"][key])
                        elif "resultF" in key:
                            fan_key = f"fan{key[-1]}_check"
                            logData["setting"][key] = (
                                ctr_data["value"]["resultFan"]
                                if ctr_data["value"][fan_key]
                                else 0
                            )
                            logData["setting"][key] = round(logData["setting"][key])
                        else:
                            new_data_setting = round(ctr_data["value"][key], 1)
                            logData["setting"][key] = new_data_setting
                for key in sensorData["temporary_data"]:
                    if key in logData["temporary_data"]:
                        logData["temporary_data"][key] = round(sensorData["temporary_data"][key], 1)
                        
                for key in sensorData["fan_power"]:
                    if key in logData["fan_power"]:
                        logData["fan_power"][key] = round(
                            sensorData["fan_power"][key], 1
                        )
                        
                for key in sensorData["fan_rpm"]:
                    if key in logData["fan_rpm"]:
                        logData["fan_rpm"][key] = round(
                            sensorData["fan_rpm"][key], 1
                        )
            except Exception as e:
                print(f"write log error: {e}")

            write_sensor_log()
            tcount_log = 0
            start_time = time.time()

        current_date = datetime.now().strftime("%Y-%m-%d")
        if current_date != last_date:
            delete_old_file()
        last_date = datetime.now().strftime("%Y-%m-%d")

        if check_file_age > 60:
            delete_old_logs(f"{log_path}/logs")
            check_file_age = 0
        check_file_age += 1

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                r = client.read_holding_registers(1404, 2, unit=modbus_slave_id)
                r2 = client.read_holding_registers(1416, 2, unit=modbus_slave_id)
                r3 = client.read_holding_registers(1424, 2, unit=modbus_slave_id)

                t1sp = cvt_registers_to_float(r.registers[0], r.registers[1])
                p1sp = cvt_registers_to_float(r2.registers[0], r2.registers[1])
                p2sp = cvt_registers_to_float(r3.registers[0], r3.registers[1])

                sensorData["collapse"]["t1sp_adjust_zero"] = (
                    True if t1sp == 0 else False
                )
                sensorData["collapse"]["t1_broken"] = (
                    True if sensorData["error"]["TempClntSply_broken"] else False
                )

                sensorData["collapse"]["p1sp_adjust_zero"] = (
                    True if p1sp == 0 else False
                )
                sensorData["collapse"]["p1_broken"] = (
                    True if sensorData["error"]["PrsrClntSply_broken"] else False
                )

                sensorData["collapse"]["p2sp_adjust_zero"] = (
                    True if p2sp == 0 else False
                )
                sensorData["collapse"]["p2_broken"] = (
                    True if sensorData["error"]["PrsrClntRtn_broken"] else False
                )

                if (
                    not sensorData["collapse"]["t1sp_adjust_zero"]
                    and not sensorData["collapse"]["t1_broken"]
                ):
                    sensorData["collapse"]["t1sp_show_final"] = True
                else:
                    sensorData["collapse"]["t1sp_show_final"] = False

                if (
                    not sensorData["collapse"]["p1sp_adjust_zero"]
                    and not sensorData["collapse"]["p1_broken"]
                ):
                    sensorData["collapse"]["p1sp_show_final"] = True
                else:
                    sensorData["collapse"]["p1sp_show_final"] = False

                if (
                    not sensorData["collapse"]["p2sp_adjust_zero"]
                    and not sensorData["collapse"]["p2_broken"]
                ):
                    sensorData["collapse"]["p2sp_show_final"] = True
                else:
                    sensorData["collapse"]["p2sp_show_final"] = False

        except Exception as e:
            print(f"read temp spare adjust error:{e}")

        read_unit()
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                r = client.read_coils(address=(8192 + 514), count=1)

                if r.isError():
                    print(f"Modbus Error: {r}")
                else:
                    if not r.bits[0]:
                        ctr_data["value"]["resultMode"] = "Stop"
                        ctr_data["value"]["opMod"] = "stop"
                        sensorData["opMod"] = "Stop"
                    else:
                        r2 = client.read_coils(address=(8192 + 516), count=1)

                        if r2.bits[0]:
                            ctr_data["value"]["resultMode"] = "Engineer"
                            ctr_data["value"]["opMod"] = "engineer"
                            sensorData["opMod"] = "Engineer"
                        else:
                            r3 = client.read_coils(address=(8192 + 517), count=1)

                            if r3.bits[0]:
                                ctr_data["value"]["resultMode"] = "Inspection"
                                ctr_data["value"]["opMod"] = "inspection"
                                sensorData["opMod"] = "Inspection"
                            else:
                                r4 = client.read_coils(address=(8192 + 505), count=1)

                                if r4.isError():
                                    print(f"Modbus Error: {r4}")
                                else:
                                    if not r4.bits[0]:
                                        ctr_data["value"]["resultMode"] = "Auto"
                                        ctr_data["value"]["opMod"] = "auto"
                                        sensorData["opMod"] = "Auto"
                                    else:
                                        ctr_data["value"]["resultMode"] = "Manual"
                                        ctr_data["value"]["opMod"] = "manual"
                                        sensorData["opMod"] = "Manual"
        except Exception as e:
            print(f"set mode error:{e}")

        try:
            ### 轉換 freq
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                inv1 = client.read_holding_registers(address=(20480 + 6660), count=1)
                inv2 = client.read_holding_registers(address=(20480 + 6700), count=1)
                inv3 = client.read_holding_registers(address=(20480 + 6740), count=1)
                fan1 = client.read_holding_registers(address=(20480 + 7020), count=1)
                fan2 = client.read_holding_registers(address=(20480 + 7060), count=1)
                fan3 = client.read_holding_registers(address=(20480 + 7100), count=1)
                fan4 = client.read_holding_registers(address=(20480 + 7140), count=1)
                fan5 = client.read_holding_registers(address=(20480 + 7380), count=1)
                fan6 = client.read_holding_registers(address=(20480 + 7420), count=1)
                fan7 = client.read_holding_registers(address=(20480 + 7460), count=1)
                fan8 = client.read_holding_registers(address=(20480 + 7500), count=1)
                
                inv1_v = inv1.registers[0] / 16000 * 100
                inv2_v = inv2.registers[0] / 16000 * 100
                inv3_v = inv3.registers[0] / 16000 * 100
                
                ### 依照風扇數量轉換要讀取的寄存器
                if ver_switch["fan_count_switch"]:
                    fan1_v = fan1.registers[0] / 16000 * 100
                    fan2_v = fan2.registers[0] / 16000 * 100
                    fan3_v = fan3.registers[0] / 16000 * 100
                    fan4_v = fan5.registers[0] / 16000 * 100
                    fan5_v = fan6.registers[0] / 16000 * 100
                    fan6_v = fan7.registers[0] / 16000 * 100
                else:
                    fan1_v = fan1.registers[0] / 16000 * 100
                    fan2_v = fan2.registers[0] / 16000 * 100
                    fan3_v = fan3.registers[0] / 16000 * 100
                    fan4_v = fan4.registers[0] / 16000 * 100
                    fan5_v = fan5.registers[0] / 16000 * 100
                    fan6_v = fan6.registers[0] / 16000 * 100
                    fan7_v = fan7.registers[0] / 16000 * 100
                    fan8_v = fan8.registers[0] / 16000 * 100
                # journal_logger.info(fan1_v)
                # journal_logger.info(fan2_v)
                # journal_logger.info(fan3_v)
                # journal_logger.info(fan4_v)
                # journal_logger.info(fan5_v)
                # journal_logger.info(fan6_v)
                # journal_logger.info(fan7_v)
                # journal_logger.info(fan8_v)
                if not ctr_data["mc"]["resultMC1"] or not ctr_data["value"]["resultP1"]:
                    inv1_v = 0

                if not ctr_data["mc"]["resultMC2"] or not ctr_data["value"]["resultP2"]:
                    inv2_v = 0

                if not ctr_data["mc"]["resultMC3"] or not ctr_data["value"]["resultP3"]:
                    inv3_v = 0
                    
                if ver_switch["fan_count_switch"]:
                    if (
                        not ctr_data["mc"]["fan_mc1_result"]
                        or not ctr_data["value"]["resultFan1"]
                    ):
                        fan1_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc1_result"]
                        or not ctr_data["value"]["resultFan2"]
                    ):
                        fan2_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc1_result"]
                        or not ctr_data["value"]["resultFan3"]
                    ):
                        fan3_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc2_result"]
                        or not ctr_data["value"]["resultFan4"]
                    ):
                        fan4_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc2_result"]
                        or not ctr_data["value"]["resultFan5"]
                    ):
                        fan5_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc2_result"]
                        or not ctr_data["value"]["resultFan6"]
                    ):
                        fan6_v = 0
                else:
                    if (
                        not ctr_data["mc"]["fan_mc1_result"]
                        or not ctr_data["value"]["resultFan1"]
                    ):
                        fan1_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc1_result"]
                        or not ctr_data["value"]["resultFan2"]
                    ):
                        fan2_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc1_result"]
                        or not ctr_data["value"]["resultFan3"]
                    ):
                        fan3_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc1_result"]
                        or not ctr_data["value"]["resultFan4"]
                    ):
                        fan4_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc2_result"]
                        or not ctr_data["value"]["resultFan5"]
                    ):
                        fan5_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc2_result"]
                        or not ctr_data["value"]["resultFan6"]
                    ):
                        fan6_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc2_result"]
                        or not ctr_data["value"]["resultFan7"]
                    ):
                        fan7_v = 0

                    if (
                        not ctr_data["mc"]["fan_mc2_result"]
                        or not ctr_data["value"]["resultFan8"]
                    ):
                        fan8_v = 0
                
                ctr_data["inv"]["inv1"] = inv1_v >= 25
                ctr_data["inv"]["inv2"] = inv2_v >= 25
                ctr_data["inv"]["inv3"] = inv3_v >= 25
                # ctr_data["inv"]["fan1"] = fan1_v >= 2
                # ctr_data["inv"]["fan2"] = fan2_v >= 2
                # ctr_data["inv"]["fan3"] = fan3_v >= 2
                # ctr_data["inv"]["fan4"] = fan4_v >= 2
                # ctr_data["inv"]["fan5"] = fan5_v >= 2
                # ctr_data["inv"]["fan6"] = fan6_v >= 2
                # ctr_data["inv"]["fan7"] = fan7_v >= 2
                # ctr_data["inv"]["fan8"] = fan8_v >= 2
                if ver_switch["fan_count_switch"]:
                    ctr_data["inv"]["fan1"] = fan1_v >= 6
                    ctr_data["inv"]["fan2"] = fan2_v >= 6
                    ctr_data["inv"]["fan3"] = fan3_v >= 6
                    ctr_data["inv"]["fan4"] = fan4_v >= 6
                    ctr_data["inv"]["fan5"] = fan5_v >= 6
                    ctr_data["inv"]["fan6"] = fan6_v >= 6
                else:
                    ctr_data["inv"]["fan1"] = fan1_v >= 6
                    ctr_data["inv"]["fan2"] = fan2_v >= 6
                    ctr_data["inv"]["fan3"] = fan3_v >= 6
                    ctr_data["inv"]["fan4"] = fan4_v >= 6
                    ctr_data["inv"]["fan5"] = fan5_v >= 6
                    ctr_data["inv"]["fan6"] = fan6_v >= 6
                    ctr_data["inv"]["fan7"] = fan7_v >= 6
                    ctr_data["inv"]["fan8"] = fan8_v >= 6
                    
        except Exception as e:
            print(f"read inv_en error:{e}")

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                r = client.read_holding_registers(address=246, count=2)
                ps = cvt_registers_to_float(r.registers[0], r.registers[1])

                r2 = client.read_coils(address=(8192 + 820), count=3)
                p1 = r2.bits[0]
                p2 = r2.bits[1]
                p3 = r2.bits[2]

                r3 = client.read_holding_registers(address=470, count=2)
                fan = cvt_registers_to_float(r3.registers[0], r3.registers[1])

                r4 = client.read_coils(address=(8192 + 850), count=8)
                
                ### 將打勾選項換至4 5 6
                
                if ver_switch["fan_count_switch"]:
                    f1 = r4.bits[0]
                    f2 = r4.bits[1]
                    f3 = r4.bits[2]
                    f4 = r4.bits[4]
                    f5 = r4.bits[5]
                    f6 = r4.bits[6]

                else:
                    f1 = r4.bits[0]
                    f2 = r4.bits[1]
                    f3 = r4.bits[2]
                    f4 = r4.bits[3]
                    f5 = r4.bits[4]
                    f6 = r4.bits[5]
                    f7 = r4.bits[6]
                    f8 = r4.bits[7]

                ctr_data["value"]["pump_speed"] = ps
                ctr_data["value"]["pump1_check"] = p1
                ctr_data["value"]["pump2_check"] = p2
                ctr_data["value"]["pump3_check"] = p3
                ctr_data["value"]["resultP1"] = p1
                ctr_data["value"]["resultP2"] = p2
                ctr_data["value"]["resultP3"] = p3

                ctr_data["value"]["fan_speed"] = fan
                ctr_data["value"]["resultFan"] = fan
                # sensorData["value"]["fan_freq"] = fan

                ctr_data["value"]["fan1_check"] = f1
                ctr_data["value"]["resultFan1"] = f1

                ctr_data["value"]["fan2_check"] = f2
                ctr_data["value"]["resultFan2"] = f2

                ctr_data["value"]["fan3_check"] = f3
                ctr_data["value"]["resultFan3"] = f3

                ctr_data["value"]["fan4_check"] = f4
                ctr_data["value"]["resultFan4"] = f4

                ctr_data["value"]["fan5_check"] = f5
                ctr_data["value"]["resultFan5"] = f5

                ctr_data["value"]["fan6_check"] = f6
                ctr_data["value"]["resultFan6"] = f6
                
                if not ver_switch["fan_count_switch"]:
                    
                    ctr_data["value"]["fan7_check"] = f7
                    ctr_data["value"]["resultFan7"] = f7

                    ctr_data["value"]["fan8_check"] = f8
                    ctr_data["value"]["resultFan8"] = f8

        except Exception as e:
            print(f"pump speed error:{e}")

        inv_addresses = {"inv1": 6660, "inv2": 6700, "inv3": 6740}

        for k, v in ctr_data["inv"].items():
            if k.startswith("inv"):
                if v:
                    address = inv_addresses.get(k)
                    try:
                        with ModbusTcpClient(
                            host=modbus_host, port=modbus_port, unit=modbus_slave_id
                        ) as client:
                            r = client.read_holding_registers(
                                address=(20480 + address), count=1
                            )
                            ### 轉換 freq
                            ps = r.registers[0]
                            ps = ps / 16000 * 100
                            ctr_data["value"]["resultPS"] = round(ps)
                            break
                    except Exception as e:
                        print(f"pump or speed check error: {e}")
                    break

        if not any(v for k, v in ctr_data["inv"].items() if k.startswith("inv")):
            ctr_data["value"]["resultPS"] = 0
            
        ### 寫入resultFan 
        
        if ver_switch["fan_count_switch"]:
            fan_inv_addresses = {
                "fan1": 7020,
                "fan2": 7060,
                "fan3": 7100,
                "fan4": 7380,
                "fan5": 7420,
                "fan6": 7460,
            }
        else:
            fan_inv_addresses = {
                "fan1": 7020,
                "fan2": 7060,
                "fan3": 7100,
                "fan4": 7140,
                "fan5": 7380,
                "fan6": 7420,
                "fan7": 7460,
                "fan8": 7500,
            }
          
        for k, v in ctr_data["inv"].items():
            if k.startswith("fan"):
                if v:
                    address = fan_inv_addresses.get(k)
                    try:
                        with ModbusTcpClient(
                            host=modbus_host, port=modbus_port, unit=modbus_slave_id
                        ) as client:
                            r = client.read_holding_registers(
                                address=(20480 + address), count=1
                            ) 
                            
                            ### 轉換 freq
                            
                            fs = r.registers[0]
                            fs = fs / 16000 * 100
                            # print(f'fs:{fs}')
                            
                            ### 如果速度小於7, 速度就為0 
                            
                            if fs < 7:
                                fs = 0
                            ctr_data["value"]["resultFan"] = round(fs)
                            break
                    except Exception as e:
                        print(f"fan speed error: {e}")
                    break

        if not any(v for k, v in ctr_data["inv"].items() if k.startswith("fan")):
            ctr_data["value"]["resultFan"] = 0      
            
        ### 讀取pump runtime
        
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                r = client.read_holding_registers(address=200, count=6)

                p1 = read_split_register(r.registers, 0)
                p2 = read_split_register(r.registers, 2)
                p3 = read_split_register(r.registers, 4)

                ctr_data["text"]["Pump1_run_time"] = p1
                ctr_data["text"]["Pump2_run_time"] = p2
                ctr_data["text"]["Pump3_run_time"] = p3
        except Exception as e:
            print(f"read pump runtime error: {e}")
        ### 讀取 fan runtime

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                r = client.read_holding_registers(address=350, count=18)

                f1 = read_split_register(r.registers, 0)
                f2 = read_split_register(r.registers, 2)
                f3 = read_split_register(r.registers, 4)
                f4 = read_split_register(r.registers, 6)
                f5 = read_split_register(r.registers, 8)
                f6 = read_split_register(r.registers, 10)
                f7 = read_split_register(r.registers, 12)
                f8 = read_split_register(r.registers, 14)
                filter = read_split_register(r.registers, 16)

                ctr_data["text"]["Fan1_run_time"] = f1
                ctr_data["text"]["Fan2_run_time"] = f2
                ctr_data["text"]["Fan3_run_time"] = f3
                ctr_data["text"]["Fan4_run_time"] = f4
                ctr_data["text"]["Fan5_run_time"] = f5
                ctr_data["text"]["Fan6_run_time"] = f6
                ctr_data["text"]["Fan7_run_time"] = f7
                ctr_data["text"]["Fan8_run_time"] = f8
                ctr_data["text"]["Filter_run_time"] = filter
        except Exception as e:
            print(f"read pump runtime error: {e}")

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                read_rack = client.read_coils((8192 + 720), 10)
                for i, (k, v) in enumerate(ctr_data["rack_set"].items()):
                    result_key = k.replace("_sw", "_sw_result")
                    if k.endswith("_sw"):
                        ctr_data["rack_set"][k] = read_rack.bits[i]
                        ctr_data["rack_set"][result_key] = read_rack.bits[i]

                read_rack2 = client.read_coils((8192 + 730), 10, unit=modbus_slave_id)
                for x, key in enumerate(ctr_data["rack_pass"].keys()):
                    ctr_data["rack_pass"][key] = read_rack2.bits[x]

                read_rack3 = client.read_coils((8192 + 710), 10, unit=modbus_slave_id)
                for i, (k, v) in enumerate(ctr_data["rack_visibility"].items()):
                    ctr_data["rack_visibility"][k] = read_rack3.bits[i]
        except Exception as e:
            print(f"read rack control: {e}")

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                adjust_len = len(sensor_adjust.keys()) * 2
                result = client.read_holding_registers(
                    1400, adjust_len, unit=modbus_slave_id
                )

                if result.isError():
                    print(f"Modbus Error: {result}")
                else:
                    keys_list = list(sensor_adjust.keys())
                    j = 0
                    for i in range(0, adjust_len, 2):
                        temp1 = [result.registers[i], result.registers[i + 1]]
                        decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
                            temp1, byteorder=Endian.Big, wordorder=Endian.Little
                        )
                        decoded_value_big_endian = (
                            decoder_big_endian.decode_32bit_float()
                        )
                        sensor_adjust[keys_list[j]] = decoded_value_big_endian
                        j += 1
        except Exception as e:
            print(f"read adjust error:{e}")

        check_fans_status()
        error_data.clear()

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                warning_key_len = len(sensorData["warning"].keys())
                warning_reg = (warning_key_len // 16) + (
                    1 if warning_key_len % 16 != 0 else 0
                )
                result = client.read_holding_registers(
                    1700, warning_reg, unit=modbus_slave_id
                )

                if not result.isError():
                    value = result.registers[0] | result.registers[1] << 16

                    binary_string = bin(value)[2:].zfill(warning_key_len)
                    index = -1

                    for key in sensorData["warning"]:
                        sensorData["warning"][key] = bool(int(binary_string[index]))
                        index -= 1

                    for key in sensorData["warning"]:
                        adjust_key = change_to_adjust(key)
                        if (
                            sensorData["warning"][key]
                            and sensor_adjust[adjust_key] != 0
                        ):
                            if sensorData["err_log"]["warning"][key] not in error_data:
                                error_data.append(sensorData["err_log"]["warning"][key])
                    warning_count += 1

                    if warning_toggle:
                        if warning_count > 10:
                            for key in sensorData["warning"]:
                                current_state = sensorData["warning"][key]
                                adjust_key = change_to_adjust(key)
                                if sensor_adjust[adjust_key] != 0:
                                    if key not in previous_warning_states:
                                        previous_warning_states[key] = False
                                    if (
                                        current_state
                                        and not previous_warning_states[key]
                                    ):
                                        app.logger.warning(
                                            sensorData["err_log"]["warning"][key]
                                        )

                                    elif (
                                        not current_state
                                        and previous_warning_states[key]
                                    ):
                                        app.logger.info(
                                            f"{sensorData['err_log']['warning'][key]} Restore"
                                        )

                                    previous_warning_states[key] = current_state
                            warning_count = 0

                    check_warning_status()

        except Exception as e:
            print(f"read warning error issue:{e}")

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                alert_key_len = len(sensorData["alert"].keys())
                alert_reg = (alert_key_len // 16) + (
                    1 if alert_key_len % 16 != 0 else 0
                )
                result = client.read_holding_registers(
                    1705, alert_reg, unit=modbus_slave_id
                )

                if not result.isError():
                    value = result.registers[0] | result.registers[1] << 16
                    binary_string = bin(value)[2:].zfill(alert_key_len)

                    index = -1

                    for key in sensorData["alert"]:
                        sensorData["alert"][key] = bool(int(binary_string[index]))
                        index -= 1

                    for key in sensorData["alert"]:
                        adjust_key = change_to_adjust(key)
                        if sensorData["alert"][key] and sensor_adjust[adjust_key] != 0:
                            if sensorData["err_log"]["alert"][key] not in error_data:
                                error_data.append(sensorData["err_log"]["alert"][key])

                    alert_count += 1

                    if alert_toggle:
                        if alert_count > 10:
                            for key in sensorData["alert"]:
                                current_state = sensorData["alert"][key]
                                adjust_key = change_to_adjust(key)
                                if sensor_adjust[adjust_key] != 0:
                                    if key not in previous_alert_states:
                                        previous_alert_states[key] = False
                                    if current_state and not previous_alert_states[key]:
                                        app.logger.warning(
                                            sensorData["err_log"]["alert"][key]
                                        )

                                        record_signal_on(
                                            sensorData["err_log"]["alert"][key].split()[
                                                0
                                            ],
                                            sensorData["err_log"]["alert"][key],
                                        )
                                    elif (
                                        not current_state and previous_alert_states[key]
                                    ):
                                        app.logger.info(
                                            f"{sensorData['err_log']['alert'][key]} Restore"
                                        )

                                        record_signal_off(
                                            sensorData["err_log"]["alert"][key].split()[
                                                0
                                            ],
                                            sensorData["err_log"]["alert"][key],
                                        )
                                    previous_alert_states[key] = current_state
                            alert_count = 0

        except Exception as e:
            print(f"read alert error issue:{e}")

        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                err_key_len = len(sensorData["error"].keys()) - 1
                err_reg = (err_key_len // 16) + (1 if err_key_len % 16 != 0 else 0)
                result = client.read_holding_registers(
                    1708, err_reg, unit=modbus_slave_id
                )
                if not result.isError():
                    value = (
                        result.registers[0]
                        | result.registers[1] << 16
                        | result.registers[2] << 32
                        | result.registers[3] << 48
                    )
                    binary_string = bin(value)[2:].zfill(err_key_len)
                    keys_list = list(sensorData["error"].keys())

                    index = -1
                    for key in keys_list:
                        if key != "PLC":
                            sensorData["error"][key] = bool(int(binary_string[index]))
                            index -= 1

                    for key in keys_list:
                        if sensorData["error"][key]:
                            if sensorData["err_log"]["error"][key] not in error_data:
                                if key.startswith("fan") and key.endswith("_error"):
                                    index = key[3]
                                    for err_key in fan_error_status[f"Fan{index}"]:
                                        if fan_error_status[f"Fan{index}"][err_key]:
                                            error_data.append(
                                                f"{sensorData['err_log']['error'][key]} ; {fan_status_message['error'][err_key]}"
                                            )
                                    for warning_key in fan_warning_status[f"Fan{index}"]:
                                        if fan_warning_status[f"Fan{index}"][warning_key]:
                                            error_data.append(
                                                f"{sensorData['err_log']['error'][key]} ; {fan_status_message['warning'][warning_key]}"
                                            )
                                else:
                                    error_data.append(sensorData["err_log"]["error"][key])
                    error_count += 1

                    if error_toggle:
                        if error_count > 10:
                            fan_status_list = []
                            fan_warning_list = []
                            for key in keys_list:
                                current_state = sensorData["error"][key]

                                if key not in previous_error_states:
                                    previous_error_states[key] = False

                                if current_state and not previous_error_states[key]:
                                    if key.startswith("fan") and key.endswith("_error"):
                                        index = key[3]
                                        for err_key in fan_error_status[f"Fan{index}"]:
                                            if fan_error_status[f"Fan{index}"][err_key]:
                                                fan_status_list.append(err_key)
                                                app.logger.warning(
                                                    f'{sensorData["err_log"]["error"][key]} ; {fan_status_message["error"][err_key]}'
                                                )

                                                record_signal_on(
                                                    sensorData["err_log"]["error"][
                                                        key
                                                    ].split()[0],
                                                    f"{sensorData['err_log']['error'][key]};\n{fan_status_message['error'][err_key]}",
                                                )
                                        for warning_key in fan_warning_status[f"Fan{index}"]:
                                            if fan_warning_status[f"Fan{index}"][warning_key]:
                                                fan_warning_list.append(warning_key)
                                                app.logger.warning(
                                                    f"{sensorData['err_log']['error'][key]} ; {fan_status_message['warning'][warning_key]}"
                                                )

                                                record_signal_on(
                                                    sensorData["err_log"]["error"][
                                                        key
                                                    ].split()[0],
                                                    f"{sensorData['err_log']['error'][key]};\n{fan_status_message['warning'][warning_key]}",
                                                )        
                                    else:
                                        app.logger.warning(
                                            sensorData["err_log"]["error"][key]
                                        )

                                        record_signal_on(
                                            sensorData["err_log"]["error"][key].split()[0],
                                            sensorData["err_log"]["error"][key],
                                        )
                                        if (
                                            sensorData["err_log"]["error"][key].split()[0]
                                            == "M300"
                                            or sensorData["err_log"]["error"][key].split()[
                                                0
                                            ]
                                            == "M301"
                                            or sensorData["err_log"]["error"][key].split()[
                                                0
                                            ]
                                            == "M302"
                                        ):
                                            record_downtime_signal_on(
                                                sensorData["err_log"]["error"][key].split()[
                                                    0
                                                ],
                                                sensorData["err_log"]["error"][key],
                                            )

                                elif not current_state and previous_error_states[key]:
                                    if key.startswith("fan") and key.endswith("_error"):
                                        index = key[3]
                                        for err_key in fan_error_status[f"Fan{index}"]:
                                            if err_key in fan_status_list:
                                                app.logger.info(
                                                    f"{sensorData['err_log']['error'][key]} ; {fan_status_message['error'][err_key]} Restore"
                                                )
                                                record_signal_off(
                                                    sensorData["err_log"]["error"][
                                                        key
                                                    ].split()[0],
                                                    f"{sensorData['err_log']['error'][key]};\n{fan_status_message['error'][err_key]}",
                                                )
                                        for warning_key in fan_warning_status[f"Fan{index}"]:
                                            if warning_key in fan_warning_list:
                                                app.logger.info(
                                                    f"{sensorData['err_log']['error'][key]} ; {fan_status_message['warning'][warning_key]} Restore"
                                                )
                                                record_signal_off(
                                                    sensorData["err_log"]["error"][
                                                        key
                                                    ].split()[0],
                                                    f"{sensorData['err_log']['error'][key]};\n{fan_status_message['warning'][warning_key]}",
                                                )
                                    else:
                                        app.logger.info(
                                            f"{sensorData['err_log']['error'][key]} Restore"
                                        )

                                        record_signal_off(
                                            sensorData["err_log"]["error"][key].split()[0],
                                            sensorData["err_log"]["error"][key],
                                        )
                                        if (
                                            sensorData["err_log"]["error"][key].split()[0]
                                            == "M300"
                                            or sensorData["err_log"]["error"][key].split()[
                                                0
                                            ]
                                            == "M301"
                                            or sensorData["err_log"]["error"][key].split()[
                                                0
                                            ]
                                            == "M302"
                                        ):
                                            record_downtime_signal_off(
                                                sensorData["err_log"]["error"][key].split()[
                                                    0
                                                ],
                                                sensorData["err_log"]["error"][key],
                                            )
                                previous_error_states[key] = current_state
                            error_count = 0
            ###檢查全部status是否有任何warning, alert, error
            check_cdu_status()  
        except Exception as e:
            print(f"read error issue:{e}")
            
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                rack_key_len = len(sensorData["rack"].keys())
                rack_reg = (rack_key_len // 16) + (1 if rack_key_len % 16 != 0 else 0)
                result = client.read_holding_registers(
                    1715, rack_reg, unit=modbus_slave_id
                )

                if not result.isError():
                    value = (
                        result.registers[0]
                        | result.registers[1] << 16
                        | result.registers[2] << 32
                    )
                    binary_string = bin(value)[2:].zfill(rack_key_len)
                    keys_list = list(sensorData["rack"].keys())
                    index = -1

                    for key in keys_list:
                        sensorData["rack"][key] = bool(int(binary_string[index]))
                        index -= 1

                    for key in keys_list:
                        if sensorData["rack"][key]:
                            if sensorData["err_log"]["rack"][key] not in error_data:
                                error_data.append(sensorData["err_log"]["rack"][key])
                    rack_count += 1

                    if error_toggle:
                        if rack_count > 10:
                            for key in keys_list:
                                # sensorData["rack"]["rack1_leak"] = False
                                current_state = sensorData["rack"][key]

                                if key not in previous_rack_states:
                                    previous_rack_states[key] = False

                                if current_state and not previous_rack_states[key]:
                                    app.logger.warning(
                                        sensorData["err_log"]["rack"][key]
                                    )

                                    record_signal_on(
                                        sensorData["err_log"]["rack"][key].split()[0],
                                        sensorData["err_log"]["rack"][key],
                                    )

                                elif not current_state and previous_rack_states[key]:
                                    app.logger.info(
                                        f"{sensorData['err_log']['rack'][key]} Restore"
                                    )

                                    record_signal_off(
                                        sensorData["err_log"]["rack"][key].split()[0],
                                        sensorData["err_log"]["rack"][key],
                                    )
                                previous_rack_states[key] = current_state
                            rack_count = 0

        except Exception as e:
            print(f"read rack error issue:{e}")

        # sensorData["error"] = False
        read_data["control"] = False

        if read_data["engineerMode"]:
            read_unit()
            try:
                thr_reg = (sum(1 for key in thrshd if "Thr_" in key)) * 2
                delay_reg = sum(1 for key in thrshd if "Delay_" in key)
                trap_reg = sum(1 for key in thrshd if "_trap" in key)
                start_address = 1000
                total_registers = thr_reg
                read_num = 120

                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    for counted_num in range(0, total_registers, read_num):
                        count = min(read_num, total_registers - counted_num)
                        result = client.read_holding_registers(
                            start_address + counted_num, count, unit=modbus_slave_id
                        )

                        if result.isError():
                            print(f"Modbus Errorxxx: {result}")
                            continue
                        else:
                            keys_list = list(thrshd.keys())
                            j = counted_num // 2
                            for i in range(0, count, 2):
                                if i + 1 < len(result.registers) and j < len(keys_list):
                                    temp1 = [
                                        result.registers[i],
                                        result.registers[i + 1],
                                    ]
                                    decoder_big_endian = (
                                        BinaryPayloadDecoder.fromRegisters(
                                            temp1,
                                            byteorder=Endian.Big,
                                            wordorder=Endian.Little,
                                        )
                                    )
                                    decoded_value_big_endian = (
                                        decoder_big_endian.decode_32bit_float()
                                    )
                                    thrshd[keys_list[j]] = decoded_value_big_endian
                                    j += 1

                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    result = client.read_holding_registers(
                        1000 + thr_reg, delay_reg, unit=modbus_slave_id
                    )

                    if result.isError():
                        print(f"Modbus Error: {result}")
                    else:
                        keys_list = list(thrshd.keys())
                        j = int(thr_reg / 2)
                        for i in range(0, delay_reg):
                            thrshd[keys_list[j]] = result.registers[i]
                            j += 1

                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    r = client.read_coils((8192 + 2000), trap_reg)

                    if r.isError():
                        print(f"Modbus Error: {r}")
                    else:
                        keys_list = list(thrshd.keys())
                        j = int(thr_reg / 2 + delay_reg)
                        for i in range(0, trap_reg):
                            thrshd[keys_list[j]] = r.bits[i]
                            j += 1

                    with open(f"{web_path}/json/thrshd.json", "w") as json_file:
                        json.dump(thrshd, json_file)
            except Exception as e:
                print(f"read thrshd error:{e}")
                flag = True

            try:
                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    r = client.read_holding_registers(510, 1, unit=modbus_slave_id)

                    pid_setting["pressure"]["sample_time_pressure"] = r.registers[0]
                    result = client.read_holding_registers(513, 4, unit=modbus_slave_id)

                    key_list = list(pid_setting["pressure"].keys())
                    y = 0
                    for i in range(1, 5):
                        pid_setting["pressure"][key_list[i]] = result.registers[y]
                        y += 1
            except Exception as e:
                print(f"read pid pressure error:{e}")
                flag = True
            try:
                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    r = client.read_holding_registers(960, 2, unit=modbus_slave_id)

                    auto_setting["auto_broken_temperature"] = r.registers[0]
                    auto_setting["auto_broken_pressure"] = r.registers[1]
            except Exception as e:
                print(f"read auto setting error:{e}")
                flag = True
                
            try:
                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    r = client.read_holding_registers(974, 1, unit=modbus_slave_id)
                    r2 = client.read_holding_registers(980, 1, unit=modbus_slave_id)
                    dpt_error_setting["dpt_error_fan"] = r.registers[0]
                    dpt_error_setting["dpt_error_t1"] = r2.registers[0]
            except Exception as e:
                print(f"read auto setting error:{e}")
                flag = True
                
            try:
                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    r = client.read_holding_registers(533, 1, unit=modbus_slave_id)
                    fan_speed = r.registers[0] / 160
                    auto_mode_setting["auto_mode_fan"] = fan_speed
            except Exception as e:
                print(f"read auto setting error:{e}")
                flag = True
                
            try:
                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    r = client.read_holding_registers(370, 1, unit=modbus_slave_id)

                    rack_opening_setting["setting_value"] = r.registers[0]
            except Exception as e:
                print(f"read rack opening setting error:{e}")
                flag = True

            try:
                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    r = client.read_holding_registers(550, 1, unit=modbus_slave_id)

                    pid_setting["temperature"]["sample_time_temp"] = r.registers[0]
                    result = client.read_holding_registers(553, 4, unit=modbus_slave_id)

                    key_list = list(pid_setting["temperature"].keys())
                    y = 0
                    for i in range(1, 5):
                        pid_setting["temperature"][key_list[i]] = result.registers[y]
                        y += 1
            except Exception as e:
                print(f"read pid temp error:{e}")
                flag = True

            with open(f"{web_path}/json/pid_setting.json", "w") as json_file:
                json.dump(pid_setting, json_file)

        if read_data["systemset"]:
            try:
                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    r = client.read_coils(address=(8192 + 500), count=1)
                    system_data["value"]["unit"] = "imperial" if r.bits[0] else "metric"

            except Exception as e:
                print(f"unit error:{e}")

            read_data["systemset"] = False

        read_data["engineerMode"] = flag

        flag = False

        try:
            if not os.path.exists(f"{web_path}/json/sensor_data.json"):
                with open(f"{web_path}/json/sensor_data.json", "w") as file:
                    file.write("")
            with open(f"{web_path}/json/sensor_data.json", "w") as json_file:
                json.dump(sensorData, json_file, indent=4)
        except Exception as e:
            print(f"sensor_data.json:{e}")

        try:
            if not os.path.exists(f"{web_path}/json/ctr_data.json"):
                with open(f"{web_path}/json/ctr_data.json", "w") as file:
                    file.write("")
            with open(f"{web_path}/json/ctr_data.json", "w") as json_file2:
                json.dump(ctr_data, json_file2, indent=4)
        except Exception as e:
            print(f"ctr_data.json:{e}")

        try:
            if not os.path.exists(f"{web_path}/json/system_data.json"):
                with open(f"{web_path}/json/system_data.json", "w") as file:
                    file.write("")

            with open(f"{web_path}/json/system_data.json", "w") as json_file3:
                json.dump(system_data, json_file3, indent=4)
        except Exception as e:
            print(f"system_data.json:{e}")

        try:
            if not os.path.exists(f"{web_path}/json/measure_data.json"):
                with open(f"{web_path}/json/measure_data.json", "w") as file:
                    file.write("")
            with open(f"{web_path}/json/measure_data.json", "w") as json_file3:
                json.dump(measure_data, json_file3, indent=4)
        except Exception as e:
            print(f"measure_data.json:{e}")

        time.sleep(0.9)


@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/debug")
def debug():
    # check port of web services
    debug_service = DebugService()
    t1 = time.time()
    report = debug_service.load_report()
    t2 = time.time()
    report["time_elapsed"] = t2 - t1
    return jsonify(report)

@app.route("/status")
@login_required
def statusEngineer():
    return render_template(
        "status_Engineer.html",
        user=current_user.id,
    )


@app.route("/download_logs")
@login_required
def download_logs():
    files = os.listdir(f"{log_path}/logs")
    print(files)
    return render_template("download.html", files=files, user=current_user.id)


@app.route("/download_logs/<path:filename>")
@login_required
def download(filename):
    return send_from_directory(f"{log_path}/logs", filename, as_attachment=True)


class LogManager:
    def __init__(self, log_type, base_dir, filename_current, template_name):
        self.log_type = log_type
        self.base_dir = base_dir
        self.filename_current = filename_current
        self.template_name = template_name
        self.old_dir = os.path.join(base_dir, f"old_{log_type}")
        self.current_dir = os.path.join(base_dir, log_type)

    def ensure_dirs(self):
        os.makedirs(self.current_dir, exist_ok=True)
        if current_user.id == "superuser":
            os.makedirs(self.old_dir, exist_ok=True)

    def list_logs(self):
        self.ensure_dirs()
        current_files = self._filter_files(os.listdir(self.current_dir))
        old_files = []

        current_sorted = sorted(
            current_files,
            key=lambda x: (x != self.filename_current, x.split(".")[2] if x != self.filename_current else ""),
            reverse=True
        )
        if self.filename_current in current_sorted:
            current_sorted.insert(0, current_sorted.pop(current_sorted.index(self.filename_current)))

        if current_user.id == "superuser":
            old_files = self._filter_files(os.listdir(self.old_dir))
            old_files = sorted(
                old_files,
                key=lambda x: os.path.getmtime(os.path.join(self.old_dir, x)),
                reverse=True
            )

        return render_template(self.template_name, files=current_sorted, old_files=old_files, user=current_user.id)

    def download_file(self, filename):
        archive = request.args.get("archive")
        if archive and current_user.id != "superuser":
            print(403)

        base_dir = self.old_dir if archive else self.current_dir
        return send_from_directory(base_dir, filename, as_attachment=True)

    def download_by_range(self, date_range):
        start_date_str, end_date_str = date_range.split("~")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        today = datetime.now().date()

        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, "w") as zip_file:
            for directory, is_old in [(self.current_dir, False), (self.old_dir, True)]:
                if not os.path.exists(directory):
                    continue
                if is_old and current_user.id != "superuser":
                    continue
                for file in os.listdir(directory):
                    try:
                        file_path = os.path.join(directory, file)
                        if file == self.filename_current:
                            file_date = today
                        else:
                            file_date_str = file.rsplit(".", 1)[-1]
                            file_date = datetime.strptime(file_date_str, "%Y-%m-%d").date()

                        if start_date <= file_date <= end_date:
                            arcname = f"old_{self.log_type}/{file}" if is_old else file
                            zip_file.write(file_path, arcname=arcname)
                    except (IndexError, ValueError):
                        continue

        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{self.log_type}logs_{start_date_str}_to_{end_date_str}.zip",
        )

    @staticmethod
    def _filter_files(files):
        return [f for f in files if not (f.startswith(".__") or f == ".DS_Store")]
    
@app.route("/sensor_logs")
@login_required
def sensor_logs():
    sensor_dir = os.path.join(log_path, "logs", "sensor")
    old_sensor_dir = os.path.join(log_path, "logs", "old_sensor")

    if not os.path.exists(sensor_dir):
        os.makedirs(sensor_dir)

    sensor_files = os.listdir(sensor_dir)
    sensor_files = [f for f in sensor_files if not (f.startswith(".__") or f == ".DS_Store")]

    sorted_sensor_files = sorted(
        sensor_files, key=lambda x: x.split(".")[2].split(".")[0], reverse=True
    )

    # 如果是 superuser，才傳回 old_sensor 檔案
    old_sensor_files = []
    if current_user.id == "superuser":
        if not os.path.exists(old_sensor_dir):
            os.makedirs(old_sensor_dir)

        old_sensor_files = os.listdir(old_sensor_dir)
        old_sensor_files = [f for f in old_sensor_files if not (f.startswith(".__") or f == ".DS_Store")]
        old_sensor_files = sorted(
            old_sensor_files, key=lambda x: os.path.getmtime(os.path.join(old_sensor_dir, x)), reverse=True
        )

    return render_template(
        "sensorLog.html",
        files=sorted_sensor_files,
        old_files=old_sensor_files,
        user=current_user.id
    )


@app.route("/download_sensor_logs/<filename>")
@login_required
def download_sensor_logs(filename):
    archive = request.args.get("archive")
    if archive and current_user.id != "superuser":
        print(f'403')

    base_dir = os.path.join(log_path, "logs", "old_sensor") if archive else os.path.join(log_path, "logs", "sensor")
    return send_from_directory(base_dir, filename, as_attachment=True)

@app.route("/download_logs/sensor/<date_range>")
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
                file_date_str = file.rsplit(".")[2]
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d")

                if start_date <= file_date <= end_date:
                    zip_file.write(f"{log_path}/logs/sensor/{file}", arcname=file)
            except (IndexError, ValueError):
                continue
        # ✅ Superuser 的額外處理：logs/old_sensor/
        if current_user.id == "superuser":
            old_sensor_dir = os.path.join(log_path, "logs", "old_sensor")
            if os.path.exists(old_sensor_dir):
                old_files = os.listdir(old_sensor_dir)
                for file in old_files:
                    try:
                        file_date_str = file.rsplit(".")[2]
                        file_date = datetime.strptime(file_date_str, "%Y-%m-%d")

                        if start_date <= file_date <= end_date:
                            # arcname 放在子資料夾中，讓 zip 結構清晰
                            arcname = f"old_sensor/{file}"
                            zip_file.write(os.path.join(old_sensor_dir, file), arcname=arcname)
                    except (IndexError, ValueError):
                        continue
    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"sensorlogs_{start_date_str}_to_{end_date_str}.zip",
    )


@app.route("/operation_logs")
@login_required
def operation_logs():
    return LogManager("operation", os.path.join(log_path, "logs"), "oplog.log", "operationLog.html").list_logs()


@app.route("/download_operation_logs/<filename>")
@login_required
def download_operation_logs(filename):
    return LogManager("operation", os.path.join(log_path, "logs"), "oplog.log", "operationLog.html").download_file(filename)


@app.route("/download_logs/operation/<date_range>")
@login_required
def download_oplogs_by_range(date_range):
    return LogManager("operation", os.path.join(log_path, "logs"), "oplog.log", "operationLog.html").download_by_range(date_range)



@app.route("/operation_logs_restapi")
@login_required
def operation_logs_restapi():
    return LogManager("operation", os.path.join(snmp_path, "RestAPI", "logs"), "oplog_api.log", "operationLogRestAPI.html").list_logs()

@app.route("/download_operation_logs_restapi/<path:filename>")
@login_required
def download_operation_logs_restapi(filename):
    return LogManager("operation", os.path.join(snmp_path, "RestAPI", "logs"), "oplog_api.log", "operationLogRestAPI.html").download_file(filename)

@app.route("/download_logs/operation_restapi/<date_range>")
@login_required
def download_oplogs_restapi_by_range(date_range):
    return LogManager("operation", os.path.join(snmp_path, "RestAPI", "logs"), "oplog_api.log", "operationLogRestAPI.html").download_by_range(date_range)

@app.route("/error_logs")
@login_required
def error_logs():
    return LogManager("error", os.path.join(log_path, "logs"), "errorlog.log", "errorLog.html").list_logs()

@app.route("/download_error_logs/<filename>")
@login_required
def download_error_logs(filename):
    return LogManager("error", os.path.join(log_path, "logs"), "errorlog.log", "errorLog.html").download_file(filename)

@app.route("/download_logs/error/<date_range>")
@login_required
def download_errorlogs_by_range(date_range):
    return LogManager("error", os.path.join(log_path, "logs"), "errorlog.log", "errorLog.html").download_by_range(date_range)


@app.route("/logout")
@login_required
def logout():
    return_to_manual_when_logout()

    logout_user()
    session.pop("username", None)
    return redirect("/")


@app.route("/network")
@login_required
def network():
    return render_template("network.html", user=current_user.id)


@app.route("/error_logs_table")
@login_required
def error_logs_table():
    return render_template("errorLogTable.html", user=current_user.id)


@app.route("/systemset")
@login_required
def systemset():
    return render_template("systemSetting.html", user=current_user.id)


@app.route("/fwStatus")
@login_required
def fwStatus():
    return render_template("fwStatus.html", user=current_user.id)


@app.route("/inspection")
@login_required
def inspection():
    return render_template("inspection.html", user=current_user.id)


@app.route("/modbus")
@login_required
def Page():
    return render_template("modbus.html")


@app.route("/engineerMode")
@login_required
def engineerMode():
    return render_template("engineerMode.html", user=current_user.id)


@app.route("/get_data")
@login_required
def get_data():
    keys_list = list(sensorData["value"].keys())

    for key in keys_list:
        if isinstance(sensorData["value"][key], float) and math.isnan(
            sensorData["value"][key]
        ):
            sensorData["value"][key] = 0

    return jsonify(sensorData)


@app.route("/get_data_engineerMode")
@login_required
def get_data_engineerMode():
    read_data["engineerMode"] = True
    timeout = get_data_timeout
    start_time = time.time()
    while read_data["engineerMode"]:
        if time.time() - start_time > timeout:
            read_data["engineerMode"] = False
            return jsonify({"error": "Request timeout"}), 504
        time.sleep(0.5)

    return jsonify(
        {
            "sensor_adjust": sensor_adjust,
            "thrshd": thrshd,
            "pid_pressure": pid_setting["pressure"],
            "pid_temp": pid_setting["temperature"],
            "inspection_time": inspection_time,
            "visibility": ctr_data["rack_visibility"],
            "auto_setting": auto_setting,
            "dpt_error_setting": dpt_error_setting,
            "auto_mode_setting": auto_mode_setting,
            "ver_switch": ver_switch,
            "rack_opening_setting": rack_opening_setting["setting_value"],
        }
    )


@app.route("/get_data_control")
@login_required
def get_data_control():
    read_data["control"] = True
    timeout = get_data_timeout
    start_time = time.time()
    while read_data["control"]:
        if time.time() - start_time > timeout:
            read_data["control"] = False
            return jsonify({"error": "Request timeout"}), 504
        time.sleep(0.5)

    return jsonify(ctr_data)


@app.route("/get_data_systemset")
@login_required
def get_data_systemset():
    read_data["systemset"] = True
    timeout = get_data_timeout
    start_time = time.time()
    while read_data["systemset"]:
        if time.time() - start_time > timeout:
            read_data["systemset"] = False
            return jsonify({"error": "Request timeout"}), 504
        time.sleep(0.5)

    return jsonify(
        {
            "system_data": system_data,
            "sampling_rate": sampling_rate,
        }
    )


@app.route("/get_data_version")
@login_required
def get_data_version():
    return jsonify(ver_switch)


@app.route("/control")
@login_required
def controlPage():
    return render_template("control.html", user=current_user.id)


@app.route("/reset_pump_swap", methods=["POST"])
@login_required
def reset_pump_swap():
    word1, word2 = cvt_float_byte(24)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(303, [word2, word1])
        return jsonify(
                {
                    "status": "success",
                    "title": "Success",
                    "message": "Success",
                }
            )
    except Exception as e:
        print(f"set pump swap time error:{e}")
        return retry_modbus(303, [word2, word1], "register")
    
    
@app.route("/set_operation_mode", methods=["POST"])
@login_required
def set_operation_mode():
    data = request.json
    value_to_write = data.get("value")
    result_data["force_change_mode"] = data.get("force_change_mode")
    mode_input = data.get("input")

    if mode_input["selectMode"] == "auto":
        temp = mode_input["temp"]
        prsr = mode_input["prsr"]
        swap = mode_input["swap"]
        
        ### D224 跟D226 是油壓跟溫度在plc的設定

        try:
            if system_data["value"]["unit"] == "imperial":
                temp_change = (float(temp) - 32) * 5.0 / 9.0
                prsr_change = float(prsr) * 6.89476
                
                if (temp_change > 55) or (
                    temp_change < 25
                ):
                    return jsonify(
                        {
                            "status": "warning",
                            "title": "Out of Range",
                            "message": "Temperature setting must be between\n25°C and 55°C (77°F to 131°F).",
                        }
                    )
                elif (prsr_change > 750
                    or prsr_change < 0
                ):
                    return jsonify(
                        {
                            "status": "warning",
                            "title": "Out of Range",
                            "message": "Pressure setting must be between\n0 kPa and 750 kPa (0 Psi to 108.75 Psi).",
                        }
                    )
                temp1, temp2 = cvt_float_byte(temp_change)
                prsr1, prsr2 = cvt_float_byte(prsr_change)

                try:
                    with ModbusTcpClient(
                        host=modbus_host, port=modbus_port, unit=modbus_slave_id
                    ) as client:
                        client.write_registers(226, [temp2, temp1])
                        client.write_registers(224, [prsr2, prsr1])
                except Exception as e:
                    print(f"set temp error:{e}")
                    return retry_modbus_2reg(226, [temp2, temp1], 224, [prsr2, prsr1])
            else:
                if (temp > setting_limit["control"]["oil_temp_set_up"]) or (
                    temp < setting_limit["control"]["oil_temp_set_low"]
                ):
                    return jsonify(
                        {
                            "status": "warning",
                            "title": "Out of Range",
                            "message": "Temperature setting must be between\n25°C and 55°C (77°F to 131°F).",
                        }
                    )
                elif (prsr > setting_limit["control"]["oil_pressure_set_up"]
                    or prsr < setting_limit["control"]["oil_pressure_set_low"]
                ):
                    return jsonify(
                        {
                            "status": "warning",
                            "title": "Out of Range",
                            "message": "Pressure setting must be between\n0 kPa and 750 kPa (0 Psi to 108.75 Psi).",
                        }
                    )
                temp1, temp2 = cvt_float_byte(temp)
                prsr1, prsr2 = cvt_float_byte(prsr)

                try:
                    with ModbusTcpClient(
                        host=modbus_host, port=modbus_port, unit=modbus_slave_id
                    ) as client:
                        client.write_registers(226, [temp2, temp1])
                        client.write_registers(224, [prsr2, prsr1])
                except Exception as e:
                    print(f"set temp error:{e}")
                    return retry_modbus_2reg(226, [temp2, temp1], 224, [prsr2, prsr1])

        except Exception as e:
            print(f"change temp pressure error: {e}")

        if (temp > setting_limit["control"]["oil_temp_set_up"]) or (
            temp < setting_limit["control"]["oil_temp_set_low"]
        ):
            return jsonify(
                {
                    "status": "warning",
                    "title": "Out of Range",
                    "message": "Temperature setting must be between\n25°C and 55°C (77°F to 131°F).",
                }
            )
        word1, word2 = cvt_float_byte(temp)
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(993, [word2, word1])
        except Exception as e:
            print(f"set temp error:{e}")
            return retry_modbus(993, [word2, word1], "register")

        if (
            prsr > setting_limit["control"]["oil_pressure_set_up"]
            or prsr < setting_limit["control"]["oil_pressure_set_low"]
        ):
            return jsonify(
                {
                    "status": "warning",
                    "title": "Out of Range",
                    "message": "Pressure setting must be between\n0 kPa and 750 kPa (0 Psi to 108.75 Psi).",
                }
            )
        word1, word2 = cvt_float_byte(prsr)
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(991, [word2, word1])
        except Exception as e:
            print(f"set pressure error:{e}")
            return retry_modbus(991, [word2, word1], "register")

        word1, word2 = cvt_float_byte(swap)
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(303, [word2, word1])
        except Exception as e:
            print(f"set pump swap time error:{e}")
            return retry_modbus(303, [word2, word1], "register")

        if (
            sensorData["error"]["Inv1_Error"]
            or sensorData["error"]["Inv2_Error"]
            or sensorData["error"]["Inv3_Error"]
        ):
            if set_mode(value_to_write):
                return jsonify(
                    {
                        "status": "info",
                        "title": "Inverter Notice",
                        "message": "Error inverter unable to power on",
                    }
                )
        op_logger.info("Temperature: %s, Pressure: %s", temp, prsr)

        if set_mode(value_to_write):
            return jsonify(
                {
                    "status": "success",
                    "title": "Success",
                    "message": "Auto mode is activated successfully",
                }
            )
        else:
            return jsonify(
                {
                    "status": "error",
                    "title": "Error",
                    "message": "Failed to set mode",
                }
            )

    try:
        if (
            mode_input["selectMode"] == "engineer"
            or mode_input["selectMode"] == "manual"
        ):
            ps = mode_input["ps"]
            p1 = mode_input["p1"]
            p2 = mode_input["p2"]
            p3 = mode_input["p3"]
            fan = mode_input["fan"]
            f1 = mode_input["f1"]
            f2 = mode_input["f2"]
            f3 = mode_input["f3"]
            f4 = mode_input["f4"]
            f5 = mode_input["f5"]
            f6 = mode_input["f6"]
            f7 = mode_input["f7"]
            f8 = mode_input["f8"]

            inv1_err = sensorData["error"]["Inv1_Error"]
            inv2_err = sensorData["error"]["Inv2_Error"]
            inv3_err = sensorData["error"]["Inv3_Error"]
            inv1_ol = sensorData["error"]["Inv1_OverLoad"]
            inv2_ol = sensorData["error"]["Inv2_OverLoad"]
            inv3_ol = sensorData["error"]["Inv3_OverLoad"]
            fan_ol1 = sensorData["error"]["Fan_OverLoad1"]
            fan_ol2 = sensorData["error"]["Fan_OverLoad2"]

            flag1 = False
            flag2 = False
            flag3 = False
            flag4 = False
            flag5 = False

            fan_flag = False
            pump_flag = False
            mc_flag = False

            set_p_check([p1, p2, p3])
            
            ### 將打勾選項換至4 5 6
            if ver_switch["fan_count_switch"]:
                set_f_check([f1, f2, f3, 0, f4, f5, f6, 0])
            else:
                set_f_check([f1, f2, f3, f4, f5, f6, f7, f8])
                
            ### 如果設定值為0, 設定2% 320
            if fan == 0:
                ### 將傳給PLC的速度設成2
                # set_fan_reg(2)
                # set_fan1(320)
                # set_fan2(320)
                set_fan_reg(6)
                set_fan1(960)
                set_fan2(960)
            else:
                set_fan_reg(float(fan))

                if fan_ol1:
                    flag4 = True
                    # set_fan1(320)
                    set_fan1(960)
                    

                if fan_ol2:
                    flag5 = True
                    # set_fan2(320)
                    set_fan2(960)

                if not flag4:
                    final_fan = translate_fan_speed(fan)
                    set_fan1(final_fan)

                if not flag5:
                    final_fan = translate_fan_speed(fan)
                    set_fan2(final_fan)

                check_fan_list = [flag4, flag5]
                if any(check_fan_list):
                    fan_flag = True

            if ps == 0:
                set_p1(0)
                set_p2(0)
                set_p3(0)
                set_p1_reg(0)
            else:
                set_p1_reg(float(ps))
                if p1:
                    # print(f'inv1_ol{inv1_ol}')
                    # print(f'inv1_err{inv1_err}')
                    if inv1_ol or inv1_err:
                        flag1 = True
                        set_p1(0)

                if p2:
                    if inv2_ol or inv2_err:
                        flag2 = True
                        set_p2(0)

                if p3:
                    if inv3_ol or inv3_err:
                        flag3 = True
                        set_p3(0)

                if not flag1:
                    ps_set = translate_pump_speed(ps)
                    set_p1(ps_set)

                if not flag2:
                    ps_set = translate_pump_speed(ps)
                    set_p2(ps_set)

                if not flag3:
                    ps_set = translate_pump_speed(ps)
                    set_p3(ps_set)

                check_list = [flag1, flag2, flag3]
                if any(check_list):
                    pump_flag = True

            # if not all(
            #     [
            #         ctr_data["mc"]["mc1_sw"],
            #         ctr_data["mc"]["mc2_sw"],
            #         ctr_data["mc"]["mc3_sw"],
            #     ]
            # ):
            #     mc_flag = True

            if pump_flag or fan_flag :
                # print(f'pump_flag"{pump_flag}')
                # print(f'fan_flag"{fan_flag}')
                # print(f'mc_flag"{mc_flag}')
                pump_line = ""
                fan_line = ""
                mc_line = ""
                middle_line = ""

                if pump_flag:
                    pump_line = "pump"

                if fan_flag:
                    fan_line = "fan"

                # if mc_flag:
                #     mc_line = "or closed MC"

                if pump_flag and fan_flag:
                    middle_line = "/"

                if set_mode(value_to_write):
                    return jsonify(
                        {
                            "status": "warning",
                            "title": "Warning",
                            "message": f"Failed to activate malfunctioning {fan_line} {middle_line} {pump_line} due to error or overload {mc_line}",
                        }
                    )

            if set_mode(value_to_write):
                if mode_input["selectMode"] == "engineer":
                    return jsonify(
                        {
                            "status": "success",
                            "title": "Success",
                            "message": "Engineer mode is activated successfully",
                        }
                    )
                elif mode_input["selectMode"] == "manual":
                    return jsonify(
                        {
                            "status": "success",
                            "title": "Success",
                            "message": "Manual mode is activated successfully",
                        }
                    )
            else:
                return jsonify(
                    {
                        "status": "error",
                        "title": "Error",
                        "message": "Failed to set mode",
                    }
                )

    except Exception as e:
        print(f"mode setting error：{e}")

    if mode_input["selectMode"] == "stop":
        if set_mode(value_to_write):
            return jsonify(
                {
                    "status": "success",
                    "title": "Success",
                    "message": "Stop mode is activated successfully",
                }
            )
        else:
            return jsonify(
                {
                    "status": "error",
                    "title": "Error",
                    "message": "Failed to set mode",
                }
            )

    if mode_input["selectMode"] == "inspection":
        if set_mode(value_to_write):
            return jsonify(
                {
                    "status": "success",
                    "title": "Success",
                    "message": "Inspection mode is activated successfully",
                }
            )
        else:
            return jsonify(
                {
                    "status": "error",
                    "title": "Error",
                    "message": "Failed to set mode",
                }
            )


@app.route("/thrshd_set", methods=["POST"])
@login_required
def thrshd_set():
    data = request.get_json()

    with open(f"{web_path}/json/thrshd.json", "w") as json_file:
        json.dump(data, json_file)

    registers = []
    grouped_register = []
    coil_registers = []
    index = 0
    thr_count = sum(1 for key in thrshd if "Thr_" in key)

    for key in thrshd:
        value = data[key]
        if key.endswith("_trap"):
            coil_registers.append(value)
        else:
            if index < thr_count:
                word1, word2 = cvt_float_byte(value)
                registers.append(word2)
                registers.append(word1)
            else:
                registers.append(int(value))
            index += 1

    grouped_register = [registers[i : i + 64] for i in range(0, len(registers), 64)]

    i = 0
    for group in grouped_register:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(1000 + i * 64, group)
        except Exception as e:
            print(f"set thrshd error:{e}")
            return retry_modbus(1000 + i * 64, group, "register")
        i += 1

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 2000), coil_registers)
    except Exception as e:
        print(f"write trap error: {e}")
        return retry_modbus((8192 + 2000), coil_registers, "coil")

    for key in thrshd.keys():
        value = data[key]
        op_logger.info("%s: %s", key, value)

    return "Threshold Setting Updated Successfully"


@app.route("/writeSensorAdjust", methods=["POST"])
@login_required
def writeSensorAdjust():
    data = request.get_json()

    registers = []

    for key in sensor_adjust.keys():
        value = data[key]
        word1, word2 = cvt_float_byte(value)
        registers.append(word2)
        registers.append(word1)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(1400, registers)

    except Exception as e:
        print(f"write sensor adjust error:{e}")
        return retry_modbus(1400, registers, "register")

    op_logger.info("Sensor Adjust Inputs received Successfully")

    return "Sensor Adjust Setting Updated Successfully"


@app.route("/systemSetting/unit_set", methods=["POST"])
@login_required
def unit_set():
    data = request.json
    value_to_write = data.get("value")

    if value_to_write == "metric":
        coil_value = False
    elif value_to_write == "imperial":
        coil_value = True

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coil(address=(8192 + 500), value=coil_value)
    except Exception as e:
        print(f"write in unit error:{e}")
        return retry_modbus((8192 + 500), coil_value, "coil")

    change_data_by_unit()
    op_logger.info("setting unit_set successfully")
    return f"Unit set to '{value_to_write}' successfully"


@app.route("/systemSetting/unit_cancel", methods=["GET"])
@login_required
def unit_cancel():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            result = client.read_coils(address=(8192 + 500), count=1)

            if result.isError():
                print(f"Modbus Error: {result}")
            else:
                if not result.bits[0]:
                    system_data["value"]["unit"] = "metric"
                else:
                    system_data["value"]["unit"] = "imperial"
    except Exception as e:
        print(f"read unit error:{e}")

    op_logger.info("Unit: %s", system_data["value"]["unit"])
    return jsonify(system_data)


@app.route("/update_password", methods=["POST"])
@login_required
def update_password():
    pwd_package = request.get_json().get("pwd_package")

    password = pwd_package["password"]
    last_pwd = pwd_package["last_pwd"]
    passwordcfm = pwd_package["passwordcfm"]

    if passwordcfm != password:
        return jsonify(
            {"status": "error", "message": "Passwords do not match. Please re-enter."}
        )

    if not all([password, last_pwd, passwordcfm]):
        return jsonify(
            {
                "status": "error",
                "message": "Please fill out all password fields",
            }
        )

    if last_pwd != USER_DATA["admin"]:
        return jsonify(
            {
                "status": "error",
                "message": "Last password is incorrect",
            }
        )

    USER_DATA["admin"] = password

    set_key(f"{web_path}/.env", "ADMIN", USER_DATA["admin"])
    os.chmod(f"{web_path}/.env", 0o666)
    op_logger.info("Admin password updated successfully")
    return jsonify({"status": "success", "message": "Password Updated Successfully"})


@app.route("/reset_password", methods=["POST"])
@login_required
def reset_password():
    USER_DATA["admin"] = "password"

    set_key(f"{web_path}/.env", "ADMIN", USER_DATA["admin"])
    os.chmod(f"{web_path}/.env", 0o666)
    op_logger.info("Admin password updated successfully")
    return jsonify({"status": "success", "message": "Password Updated Successfully"})

@app.route("/get_admin_password", methods=["GET"])
@login_required
def get_admin_password():
               
    return USER_DATA["admin"]


# @app.route("/get_modbus_ip", methods=["GET"])
# def get_modbus_ip():
#     modbus_host = os.environ.get("MODBUS_IP")
#     return jsonify({"modbus_ip": modbus_host})


# @app.route("/update_modbus_ip", methods=["POST"])
# @login_required
# def update_modbus_ip():
#     new_ip = request.json.get("modbus_ip")
#     if not new_ip:
#         return jsonify({"error": "No IP address provided"}), 400

#     set_key(f"{web_path}/.env", "MODBUS_IP", new_ip)

#     global modbus_host
#     modbus_host = new_ip
#     os.environ["MODBUS_IP"] = new_ip

#     op_logger.info(f"MODBUS_IP updated successfully, new_modbus_ip: {modbus_host}")
#     return jsonify(
#         {"message": "MODBUS_IP updated successfully", "new_modbus_ip": modbus_host}
#     )


@app.route("/write_version", methods=["POST"])
@login_required
def write_version():
    data = request.json
    ### 前端在engineer mode可寫入 SN, Model, Version, PartNmuber 

    if os.path.exists(f"{web_path}/fw_info.json"):
        with open(f"{web_path}/fw_info.json", "r") as file:
            FW_Info = json.load(file)

    FW_Info["SN"] = data["SN"]
    FW_Info["Model"] = data["Model"]
    # FW_Info["Version"] = data["Version"]
    FW_Info["PartNumber"] = data["PartNumber"]

    with open(f"{web_path}/fw_info.json", "w") as file:
        json.dump(FW_Info, file)

    op_logger.info(f"FW Setting Updated Successfully. {data}")
    return "FW Setting Updated Successfully"


@app.route("/read_version", methods=["GET"])
@login_required
def read_version():
    ###讀取前端可修改的SN, part number, model及version
    if not os.path.exists(f"{web_path}/fw_info.json"):
        with open(f"{web_path}/fw_info.json", "w") as file:
            file.write("")
    with open(f"{web_path}/fw_info.json", "r") as file:
        FW_Info = json.load(file)

    ###讀取我們自己修改的webui, scc_api, snmp, redfish_api, redfish_server, modbus_server版本號

    if not os.path.exists(f"{web_path}/fw_info_version.json"):
        with open(f"{web_path}/fw_info_version.json", "w") as file2:
            file2.write("")
    with open(f"{web_path}/fw_info_version.json", "r") as file2:
        FW_Info_Version = json.load(file2)

    plc_version = sensorData["plc_version"]
    # 使用字符串格式化將 plc_version 補充為4位數，例如 "0107"
    plc_version_padded = str(plc_version).zfill(4)
    FW_Info_Version["PLC"] = plc_version_padded
    # 寫回 fw_info_version.json
    with open(f"{web_path}/fw_info_version.json", "w") as file2:
        json.dump(FW_Info_Version, file2, indent=4)
    return jsonify(
        {
            "FW_Info": FW_Info,
            "FW_Info_Version": FW_Info_Version,
            "plc_version": plc_version,
        }
    )



@app.route("/set_time", methods=["POST"])
def set_time():
    try:
        data = request.json
        datetime_str = data["value"]
        # 檢查輸入的格式，若缺少秒數則補上 ":00"
        if len(datetime_str) == 16:  # "YYYY-MM-DDTHH:MM"
            datetime_str += ":00"  # 變成 "YYYY-MM-DDTHH:MM:00"
        json_datetime = dt.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")
        formatted_date_time = json_datetime.strftime("%Y-%m-%d %H:%M:%S")

        subprocess.run(["sudo", "timedatectl", "set-ntp", "False"], check=True)

        result = subprocess.run(
            ["sudo", "timedatectl", "set-time", formatted_date_time],
            capture_output=True,
            text=True,
            check=True,
        )

        if result.stderr:
            op_logger.info(f"Failed to set time: {result.stderr}")
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Failed to set time: {result.stderr}",
                    }
                ),
                500,
            )

        # 確保 RTC 時鐘也更新
        subprocess.run(["sudo", "hwclock", "--systohc"], check=True)

        op_logger.info("Date and time set successfully.")
        return jsonify(
            {
                "status": "success",
                "message": "Date and time set successfully. Please log in again.",
            }
        )

    except subprocess.CalledProcessError as e:
        op_logger.info(f"Time Set Unsuccessful. {e}")
        return (
            jsonify({"status": "error", "message": f"Time Set Unsuccessful: {e}"}),
            500,
        )

    except Exception as e:
        op_logger.info(f"General error: {e}")
        return jsonify({"status": "error", "message": f"Unexpected error: {e}"}), 500


@app.route("/sync_time", methods=["POST"])
def sync_time():
    data = request.json
    ntp_server = data.get("ntp_server")
    timezone = data.get("timezone")

    if not ntp_server or not timezone:
        return (
            jsonify(
                {"status": "error", "message": "NTP server and timezone are required."}
            ),
            400,
        )

    try:
        # 設定時區
        subprocess.run(["sudo", "timedatectl", "set-timezone", timezone], check=True)
        op_logger.info(f"Timezone set to {timezone}.")

        # 執行 NTP 同步
        result = subprocess.run(
            ["sudo", "ntpdate", ntp_server], capture_output=True, text=True
        )

        if result.returncode != 0:
            op_logger.info(f"NTP sync failed: {result.stderr}")
            return (
                jsonify(
                    {"status": "error", "message": f"NTP sync failed: {result.stderr}"}
                ),
                500,
            )

        op_logger.info(f"Sync result: {result.stdout}")

        # 同步 RTC 硬體時鐘
        subprocess.run(["sudo", "hwclock", "--systohc"], check=True)
        op_logger.info("RTC clock updated with system time.")

        # 重新載入 systemd（非必要，但可避免 service 問題）
        subprocess.run(
            ["sudo", "systemctl", "daemon-reload"], capture_output=True, text=True
        )

        # 重新啟動 webui.service，確保應用程式正確運行
        # result = subprocess.run(
        #     ["sudo", "systemctl", "restart", "webui.service"],
        #     capture_output=True,
        #     text=True,
        # )
        # if result.returncode != 0:
        #     return (
        #         jsonify(
        #             {
        #                 "status": "error",
        #                 "message": f"Failed to restart webui service: {result.stderr}",
        #             }
        #         ),
        #         500,
        #     )

        op_logger.info(
            f"Time synchronized with {ntp_server} and timezone set to {timezone}."
        )
        return jsonify(
            {
                "status": "success",
                "message": f"Time synchronized with {ntp_server} and timezone set to {timezone}.",
            }
        )

    except subprocess.CalledProcessError as e:
        return jsonify({"status": "error", "message": f"Sync process failed: {e}"}), 500


@app.route("/get_system_time", methods=["GET"])
def get_system_time():
    current_time = dt.datetime.now()

    current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S")

    return jsonify({"system_time": current_time_str})


@app.route("/get_timeout", methods=["GET"])
def get_timeout():
    if not os.path.exists(f"{web_path}/json/timeout_light.json"):
        with open(f"{web_path}/json/timeout_light.json", "w") as file:
            file.write('{"timeoutLight": "30011"}')

    with open(f"{web_path}/json/timeout_light.json", "r") as file:
        TIMEOUT_Info = json.load(file)

    return jsonify(TIMEOUT_Info)


@app.route("/set_timeout", methods=["POST"])
def set_timeout():
    data = request.json
    TIMEOUT_Info = data

    with open(f"{web_path}/json/timeout_light.json", "w") as file:
        json.dump(TIMEOUT_Info, file)
    op_logger.info(
        f"Update indicator delay successfully. Indicator delay:{TIMEOUT_Info}"
    )
    return jsonify({"status": "success"})


@app.route("/get_network_info", methods=["GET"])
@login_required
def get_network_info():
    web_formatted_string = []

    network_info_list = collect_allnetwork_info()

    web_formatted_string = [
        json.dumps(info, indent=4, separators=(",", ": ")) for info in network_info_list
    ]

    with open(f"{web_path}/json/network.json", "w") as jsonFile:
        json.dump(web_formatted_string, jsonFile, indent=4)

    return jsonify(
        {
            "ethernet_info1": web_formatted_string[0],
            "ethernet_info2": web_formatted_string[1],
            "ethernet_info3": web_formatted_string[2],
            "ethernet_info4": web_formatted_string[3],
        }
    )


@app.route("/set_network", methods=["POST"])
@login_required
def set_network():
    data = request.json
    network_set = all_network_set[int(data["networkId"]) - 1]

    response = {
        "status": "success",
        "message": "Network Setting Updated Successfully",
    }

    for key in data.keys():
        if key != "networkId":
            network_set[key] = data[key]

    interface_names = read_net_name()
    networkId = int(data["networkId"])
    interface_name = interface_names[networkId - 1]

    try:
        if network_set["v4dhcp_en"]:
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "modify",
                    interface_name,
                    "ipv4.method",
                    "auto",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv4.addresses",
                    "",
                    "ipv4.gateway",
                    "",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        else:
            mask = network_set["v4Subnet"]
            network = ipaddress.IPv4Network("0.0.0.0/" + mask, strict=False)

            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "modify",
                    interface_name,
                    "ipv4.gateway",
                    "",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "modify",
                    interface_name,
                    "ipv4.method",
                    "manual",
                    "ipv4.address",
                    f"{network_set['IPv4Address']}/{network.prefixlen}",
                    "ipv4.gateway",
                    network_set["v4DefaultGateway"],
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            op_logger.info(
                f"interface name:{interface_name},ipv4 address:{network_set['IPv4Address']}/{network.prefixlen},netmask:{mask},gateway:{network_set['v4DefaultGateway']}"
            )
    except subprocess.CalledProcessError as e:
        response["status"] = "error"
        response["message"] = f"DHCP v4 setting failed: {e.stderr.strip()}"
        op_logger.info(response)

        return jsonify(response), 400
    except Exception as e:
        response["status"] = "error"
        response["message"] = f"Unexpected error in DHCP v4 setting: {e.stderr.strip()}"
        op_logger.info(response)
        return jsonify(response), 400

    try:
        if network_set["v4AutoDNS"]:
            subprocess.run(
                ["sudo", "nmcli", "con", "mod", interface_name, "ipv4.dns", ""],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv4.ignore-auto-dns",
                    "no",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        else:
            dns_servers = []
            if network_set["v4DNSPrimary"]:
                dns_servers.append(network_set["v4DNSPrimary"])
            if network_set["v4DNSOther"]:
                dns_servers.append(network_set["v4DNSOther"])

            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv4.ignore-auto-dns",
                    "yes",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["sudo", "nmcli", "con", "mod", interface_name, "ipv4.dns", ""],
                check=True,
                capture_output=True,
                text=True,
            )

            if dns_servers:
                dns_servers_str = " ".join(dns_servers)
                print("Setting DNS servers to:", dns_servers_str)
                subprocess.run(
                    [
                        "sudo",
                        "nmcli",
                        "con",
                        "mod",
                        interface_name,
                        "ipv4.dns",
                        dns_servers_str,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
    except subprocess.CalledProcessError as e:
        response["status"] = "error"
        response["message"] = f"DNS v4 setting failed: {e.stderr.strip()}"
        op_logger.info(response)

        return jsonify(response), 400
    except Exception as e:
        response["status"] = "error"
        response["message"] = f"Unexpected error in DNS v4 setting: {e.stderr.strip()}"
        op_logger.info(response)

        return jsonify(response), 400

    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", "NetworkManager"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        response["status"] = "error"
        response["message"] = f"Error restarting NetworkManager: {e.stderr.strip()}"
        return jsonify(response), 500
    except Exception as e:
        response["status"] = "error"
        response["message"] = (
            f"Unexpected error restarting NetworkManager: {e.stderr.strip()}"
        )
        return jsonify(response), 500

    try:
        subprocess.run(
            ["sudo", "nmcli", "con", "down", interface_name],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["sudo", "nmcli", "con", "up", interface_name],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        response["status"] = "error"
        response["message"] = f"Error restarting network connection: {e.stderr.strip()}"
        return jsonify(response), 500
    op_logger.info(response)
    return jsonify(response)


@app.route("/v6set_network", methods=["POST"])
@login_required
def v6set_network():
    data = request.json

    network_set = all_network_set[int(data["networkId"]) - 1]
    response = {
        "status": "success",
        "message": "Network Setting Updated Successfully",
    }
    for key in data.keys():
        if key != "networkId":
            network_set[key] = data[key]

    interface_names = read_net_name()
    networkId = int(data["networkId"])
    interface_name = interface_names[networkId - 1]

    try:
        if network_set["v6dhcp_en"]:
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "modify",
                    interface_name,
                    "ipv6.method",
                    "auto",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv6.addresses",
                    "",
                    "ipv6.gateway",
                    "",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "modify",
                    interface_name,
                    "ipv6.method",
                    "manual",
                    "ipv6.address",
                    f"{network_set['IPv6Address']}/{network_set['v6Subnet']}",
                    "ipv6.gateway",
                    network_set["v6DefaultGateway"],
                ],
                check=True,
                capture_output=True,
                text=True,
            )

    except subprocess.CalledProcessError as e:
        print(f"Error executing DHCP v6 command: {e.stderr.strip()}")
    except Exception as e:
        print(f"Unexpected error in DHCP v6 setting: {e.stderr.strip()}")

    try:
        if network_set["v6AutoDNS"]:
            subprocess.run(
                ["sudo", "nmcli", "con", "mod", interface_name, "ipv6.dns", ""],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv6.ignore-auto-dns",
                    "no",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            dns_servers = []
            if network_set["v6DNSPrimary"]:
                dns_servers.append(network_set["v6DNSPrimary"])
            if network_set["v6DNSOther"]:
                dns_servers.append(network_set["v6DNSOther"])

            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "con",
                    "mod",
                    interface_name,
                    "ipv6.ignore-auto-dns",
                    "yes",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["sudo", "nmcli", "con", "mod", interface_name, "ipv6.dns", ""],
                check=True,
                capture_output=True,
                text=True,
            )

            if dns_servers:
                dns_servers_str = " ".join(dns_servers)
                print("Setting DNS servers to:", dns_servers_str)
                subprocess.run(
                    [
                        "sudo",
                        "nmcli",
                        "con",
                        "mod",
                        interface_name,
                        "ipv6.dns",
                        dns_servers_str,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

    except subprocess.CalledProcessError as e:
        print(f"Error executing DNS v6 command: {e.stderr.strip()}")
    except Exception as e:
        print(f"Unexpected error in DNS v6 setting: {e.stderr.strip()}")

    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", "NetworkManager"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        response["status"] = "error"
        response["message"] = f"Error restarting NetworkManager: {e.stderr.strip()}"
        return jsonify(response), 500
    except Exception as e:
        response["status"] = "error"
        response["message"] = (
            f"Unexpected error restarting NetworkManager: {e.stderr.strip()}"
        )
        return jsonify(response), 500

    try:
        subprocess.run(
            ["sudo", "nmcli", "con", "down", interface_name],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["sudo", "nmcli", "con", "up", interface_name],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        response["status"] = "error"
        response["message"] = f"Error restarting network connection: {e.stderr.strip()}"
        return jsonify(response), 500
    op_logger.info(response)
    return jsonify(response)


@app.route("/export_settings", methods=["POST"])
@login_required
def export_settings():
    data = request.json

    export_data.clear()
    ctr_data_temp = ctr_data.copy()
    try:
        if data.get("exp_system_chk", False):
            export_data["unit"] = system_data["value"]["unit"]
            export_data["log_interval"] = sampling_rate["number"]

            with open(f"{snmp_path}/snmp/snmp.json", "r") as file:
                snmp = json.load(file)
            export_data["snmp"] = snmp

            # if "users" not in export_data:
            #     export_data["users"] = {}

            #     encrypted_password_user = cipher_suite.encrypt(
            #         USER_DATA["user"].encode()
            #     ).decode()
            #     export_data["users"]["user"] = encrypted_password_user

            #     encrypted_password_kiosk = cipher_suite.encrypt(
            #         USER_DATA["user"].encode()
            #     ).decode()
            #     export_data["users"]["kiosk"] = encrypted_password_kiosk
        if data.get("exp_mode_chk", False):
            for key, v in ctr_data_temp["value"].items():
                if isinstance(v, float):
                    ctr_data_temp["value"][key] = round(v, 2)
            export_data["mode_set"] = ctr_data_temp["value"]

        if data.get("exp_alt_chk", False):
            for key in thrshd.keys():
                if key.startswith("Thr_"):
                    thrshd[key] = round(thrshd[key], 2)
            export_data["thrshd"] = thrshd

        if data.get("exp_ntw_chk", False):
            export_data["network_set"] = collect_allnetwork_info()

        if data.get("exp_psw_adj", False):
            export_data["sensor_adjust"] = sensor_adjust

        if data.get("exp_pid_set", False):
            with open(f"{web_path}/json/pid_setting.json", "r") as file:
                export_data["pid_setting"] = json.load(file)

    except Exception as e:
        print(f"export: {e}")

    return jsonify(export_data)


@app.route("/import_settings", methods=["POST"])
@login_required
def import_settings():
    uploaded_file = request.files["file"]

    if uploaded_file.filename != "":
        if not os.path.exists(f"{web_path}/json/upload_file.json"):
            with open(f"{web_path}/json/upload_file.json", "w") as file:
                file.write("")

        uploaded_file.save(f"{web_path}/json/upload_file.json")
        with open(f"{web_path}/json/upload_file.json", "r") as file:
            data = json.load(file)
            if "network_set" in data:
                if len(data["network_set"]) != 4:
                    return jsonify(
                        {
                            "status": "error",
                            "message": "Please Provide Exactly Four Network Configurations",
                        }
                    )

                for i, network in enumerate(data["network_set"]):
                    interface_name = read_net_name()
                    print(interface_name[i], network)

                    network_set_import(interface_name[i], network)

            # if "users" in data:
            #     try:
            #         decrypted_password_user = cipher_suite.decrypt(
            #             data["users"]["user"].encode()
            #         ).decode()
            #         USER_DATA["user"] = decrypted_password_user

            #         decrypted_password_kiosk = cipher_suite.decrypt(
            #             data["users"]["kiosk"].encode()
            #         ).decode()
            #         USER_DATA["kiosk"] = decrypted_password_kiosk

            #         set_key(f"{web_path}/.env", "USER", USER_DATA["user"])
            #         set_key(f"{web_path}/.env", "USER", USER_DATA["kiosk"])
            #         os.chmod(f"{web_path}/.env", 0o666)

            #     except InvalidToken:
            #         return jsonify(
            #             {"status": "error", "message": "Invalid Encrypted Password"}
            #         )

            if "sensor_adjust" in data:
                if user_identity["ID"] == "superuser":
                    sensor_adjust = data["sensor_adjust"]
                    adjust_import(sensor_adjust)
                else:
                    return jsonify(
                        {
                            "status": "error",
                            "message": "No access to modify sensor adjustment data",
                        }
                    )

            if "pid_setting" in data:
                pid_setting = data["pid_setting"]
                pid_import(pid_setting)

            if "unit" in data:
                unit_value = data.get("unit")
                unit_import(unit_value)

            if "log_interval" in data:
                log_interval_value = data.get("log_interval")
                log_interval_import(log_interval_value)

            if "snmp" in data:
                snmp_value = data.get("snmp")
                snmp_import(snmp_value)

            if "thrshd" in data:
                read_unit()
                if system_data["value"]["unit"] == "metric":
                    thrshd = data["thrshd"]
                    threshold_import(thrshd)
                else:
                    thrshd = data["thrshd"]
                    key_list = list(thrshd.keys())
                    for key in key_list:
                        if not key.endswith("_trap") and not key.startswith("Delay_"):
                            thrshd[key] = thrshd[key]
                            if "Temp" in key:
                                thrshd[key] = thrshd[key] * 9.0 / 5.0 + 32.0

                            if "DewPoint" in key:
                                thrshd[key] = thrshd[key] * 9.0 / 5.0

                            if "Prsr" in key:
                                thrshd[key] = thrshd[key] * 0.145038

                            if "Flow" in key:
                                thrshd[key] = thrshd[key] * 0.2642

                    threshold_import(thrshd)

        return jsonify({"status": "success", "message": "Data Imported Successfully"})
    else:
        return jsonify({"status": "error", "message": "Invalid File"})


@app.route("/reboot", methods=["GET"])
@login_required
def reboot():
    def delayed_reboot():
        time.sleep(5)  # 延遲 5 秒，讓 response 有時間送出
        subprocess.run(["sudo", "reboot"], check=True)

    threading.Thread(target=delayed_reboot).start()
    return "Restarting System"


@app.route("/shutdown", methods=["GET"])
@login_required
def shutdown():
    def delayed_shutdown():
        time.sleep(5)  # 延遲 5 秒，讓 response 有時間送出
        subprocess.run(["sudo", "shutdown", "now"], check=True)

    threading.Thread(target=delayed_shutdown).start()
    return "System will shut down in 5 seconds"


@app.route("/upload_zip", methods=["GET", "POST"])
@login_required
def upload_zip():
    if request.method == "POST":
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
                journal_logger.info(f"runtime error: {e}")
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
                journal_logger.info(f"Error extracting ZIP: {e}")
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
                journal_logger.info(f"Script output:{result.stdout}")
            except subprocess.CalledProcessError as e:
                journal_logger.info(f"Error executing script: {e}")
                journal_logger.info(f"Script error output:{e.stderr}")

            return (
                jsonify(
                    {"status": "success", "message": "ZIP file uploaded successfully."}
                ),
                200,
            )

        return (
            jsonify(
                {"status": "error", "message": "Wrong file type or missing password"}
            ),
            400,
        )

@app.route("/upload_zip_pc_both", methods=["POST"])
def upload_zip_pc_both():
    superuser_password =  os.getenv("SUPERUSER")
    
    if "file" not in request.files:
        return jsonify({"message": "No File Part"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"message": "No File Selected"}), 400
    ### 取消zip檔名限制
    # if file.filename != "upload.zip":
    #     return jsonify({"message": "Please upload correct file name"}), 400

    # if not file.filename.endswith(".zip"):
    if not file.filename.endswith(".gpg"):
        return jsonify({"message": "Wrong File Type"}), 400

    # 定義暫存解壓縮目錄
    temp_dir = "/tmp/uploaded_zip"
    os.makedirs(temp_dir, exist_ok=True)
    
    # 存到本機暫存區
    local_zip_path = os.path.join(temp_dir, file.filename.replace(".gpg", ".zip"))
    # local_zip_path = os.path.join(temp_dir, file.filename)
    file.save(local_zip_path)

    # 解壓縮 ZIP
    # try:
    #     with zipfile.ZipFile(local_zip_path, "r") as zip_ref:
    #         zip_ref.extractall(temp_dir)
    # except zipfile.BadZipFile:
    #     return jsonify({"message": "Invalid ZIP file"}), 400
    zip_password = "Itgs50848614"
    try:
        with pyzipper.AESZipFile(local_zip_path, "r", encryption=pyzipper.WZ_AES) as zip_ref:

            # 檢查每個檔案是否加密
            if not any(info.flag_bits & 0x1 for info in zip_ref.infolist()):
                os.remove(local_zip_path)  # 清理未通過檢查的 zip
                return jsonify({"message": "ZIP file must be password-protected"}), 400

            zip_ref.setpassword(zip_password.encode())

            try:
                namelist = zip_ref.namelist()
                if not namelist:
                    os.remove(local_zip_path)
                    return jsonify({"status": "error", "message": "ZIP file is empty"}), 400

                # 嘗試讀取第一個檔案驗證密碼
                zip_ref.read(namelist[0])
            except RuntimeError:
                os.remove(local_zip_path)
                return jsonify({"status": "error", "message": "Invalid password"}), 400
                
            zip_ref.extractall(temp_dir)

    except RuntimeError:
        os.remove(local_zip_path)
        return jsonify({"message": "Wrong password or corrupt zip"}), 400

    except pyzipper.BadZipFile:
        os.remove(local_zip_path)
        return jsonify({"message": "Invalid ZIP file"}), 400

    # 定義目標 API 端點
    TARGET_SERVERS = {
        "upload/main/service.zip": "http://192.168.3.100:5501/api/v1/upload_zip",
        "upload/spare/service.zip": "http://192.168.3.101:5501/api/v1/upload_zip",
    }

    upload_results = {}

    for file_path, target_url in TARGET_SERVERS.items():
        full_file_path = os.path.join(temp_dir, file_path)  # 修正檔案路徑
        if os.path.exists(full_file_path):
            try:
                with open(full_file_path, "rb") as f:
                    files = {"file": (os.path.basename(file_path), f, "application/zip")}
                    response = requests.post(target_url, files=files, auth=("superuser", superuser_password), verify=False)

                upload_results[file_path] = {
                    "status": response.status_code,
                    "response": response.text
                }
            except Exception as e:
                upload_results[file_path] = {"status": "error", "error": str(e)}
        else:
            upload_results[file_path] = {"status": "error", "error": "File not found"}

    # 清理暫存檔案
    os.remove(local_zip_path)
    for file_path in TARGET_SERVERS.keys():
        full_file_path = os.path.join(temp_dir, file_path)
        if os.path.exists(full_file_path):
            os.remove(full_file_path)

    return jsonify({"message": "Upload Completed, Please restart PC .", "results": upload_results}), 200


@app.route('/reboot-all', methods=['GET'])
def reboot_all():
    superuser_password =  os.getenv("SUPERUSER")
    
    second_pc = "http://192.168.3.101:5501/api/v1/reboot"
    first_pc = "http://192.168.3.100:5501/api/v1/reboot"

    results = {}

    try:
        response2 = requests.get(second_pc, auth=("superuser", superuser_password), verify=False)
        results["second_pc"] = f"{response2.status_code}: {response2.text}"
    except Exception as e:
        results["second_pc"] = f"Error: {e}"

    # 等待 5 秒再關第一台
    time.sleep(5)

    try:
        response1 = requests.get(first_pc, auth=("superuser", superuser_password), verify=False)
        results["first_pc"] = f"{response1.status_code}: {response1.text}"
    except Exception as e:
        results["first_pc"] = f"Error: {e}"

    return jsonify({
        "message": "Reboot requests sent (second first, first after 5s)",
        "results": results
    }), 200
    
@app.route("/store_sampling_rate", methods=["POST"])
@login_required
def store_sampling_rate():
    try:
        data = request.json
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(3000, data["sampleRate"])

        op_logger.info("Log Interval: %s", data["sampleRate"])
        return "Log Interval Updated Successfully"
    except Exception as e:
        print(f"error:{e}")
        return retry_modbus(3000, data["sampleRate"], "register")


@app.route("/Pump1reset", methods=["POST"])
@login_required
def Pump1reset():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(200, [0, 0])
            client.write_registers(270, [0] * 4)

        op_logger.info("reset Pump1 Running Time successfully!")
        return "Reset Pump1 Running Time Successfully"
    except Exception as e:
        op_logger.info("reset Pump1 Running Time failed!")
        print(f"pump1 reset error:{e}")
        return retry_modbus_2reg(200, [0] * 2, 270, [0] * 4)


@app.route("/Pump2reset", methods=["POST"])
@login_required
def Pump2reset():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(202, [0, 0])
            client.write_registers(274, [0] * 4)
        op_logger.info("reset Pump2 Running Time successfully!")
        return "Reset Pump2 Running Time Successfully"
    except Exception as e:
        op_logger.info("reset Pump2 Running Time failed!")
        print(f"pump2 reset error:{e}")
        return retry_modbus_2reg(202, [0] * 2, 274, [0] * 4)


@app.route("/Pump3reset", methods=["POST"])
@login_required
def Pump3reset():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(204, [0, 0])
            client.write_registers(278, [0] * 4)
        op_logger.info("reset Pump3 Running Time successfully!")
        return "Reset Pump3 Running Time Successfully"
    except Exception as e:
        op_logger.info("reset Pump3 Running Time failed!")
        print(f"pump3 reset error:{e}")
        return retry_modbus_2reg(204, [0] * 2, 278, [0] * 4)

@app.route("/filter_reset", methods=["POST"])
@login_required
def filter_reset():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(366, [0, 0])
            client.write_registers(342, [0] * 4)
        op_logger.info("reset Filter Running Time successfully!")
        return "Reset Filter Running Time Successfully"
    except Exception as e:
        op_logger.info("reset Filter Running Time failed!")
        print(f"Filter reset error:{e}")
        return retry_modbus_2reg(366, [0] * 2, 342, [0] * 4)


FAN_REGISTERS = {
    "Fan1": {"reg1": 350, "reg2": 310},
    "Fan2": {"reg1": 352, "reg2": 314},
    "Fan3": {"reg1": 354, "reg2": 318},
    "Fan4": {"reg1": 356, "reg2": 322},
    "Fan5": {"reg1": 358, "reg2": 326},
    "Fan6": {"reg1": 360, "reg2": 330},
    "Fan7": {"reg1": 362, "reg2": 334},
    "Fan8": {"reg1": 364, "reg2": 338},
}

def reset_fan(fan_id, reg1, reg2):
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port, unit=modbus_slave_id) as client:
            client.write_registers(reg1, [0, 0])
            client.write_registers(reg2, [0] * 4)

        op_logger.info(f"Reset {fan_id} Running Time successfully!")
        return f"Reset {fan_id} Running Time Successfully"
    except Exception as e:
        op_logger.info(f"Reset {fan_id} Running Time failed!")
        print(f"{fan_id} reset error: {e}")
        return retry_modbus_2reg(reg1, [0] * 2, reg2, [0] * 4)

@app.route("/<fan_id>reset", methods=["POST"])
@login_required
def fan_reset(fan_id):
    if fan_id in FAN_REGISTERS:
        reg_info = FAN_REGISTERS[fan_id]
        return reset_fan(fan_id, reg_info["reg1"], reg_info["reg2"])
    return "Invalid Fan ID", 400

class LogMover:
    def __init__(self, src_dir, dst_dir, name="log"):
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.name = name

    def move_logs(self):
        try:
            if not os.path.exists(self.src_dir) or not os.path.isdir(self.src_dir):
                print(f"[{self.name}] Source directory does not exist: {self.src_dir}")
                return

            if not os.path.exists(self.dst_dir):
                os.makedirs(self.dst_dir)

            for filename in os.listdir(self.src_dir):
                src_file = os.path.join(self.src_dir, filename)
                dst_file = os.path.join(self.dst_dir, filename)

                if os.path.isfile(src_file):
                    if os.path.exists(dst_file):
                        name, ext = os.path.splitext(filename)
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        new_filename = f"{name}.{timestamp}{ext}"
                        dst_file = os.path.join(self.dst_dir, new_filename)

                    shutil.move(src_file, dst_file)
                    print(f"[{self.name}] Moved: {filename} → {os.path.basename(dst_file)}")

            print(f"[{self.name}] All files moved from {self.src_dir} to {self.dst_dir}")
        except Exception as e:
            print(f"[{self.name}] Move error: {e}")


@app.route("/restore_factory_setting_all", methods=["POST"])
def restoreFactorySettingAll():
    ###1. SystemSetting: Log Interval(sec) : 2
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(3000, 2)

        op_logger.info("Sampling Rate: %s", 2)
        # return "Log Interval Updated Successfully"
    except Exception as e:
        print(f"error:{e}")
        # return retry_modbus(3000, 2, "register")
    
    ###2.Control: Pump & Filter Running Time: Reset
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(200, [0, 0])
            client.write_registers(270, [0] * 4)

        op_logger.info("reset Pump1 Running Time successfully!")
        # return "Reset Pump1 Running Time Successfully"
    except Exception as e:
        op_logger.info("reset Pump1 Running Time failed!")
        print(f"pump1 reset error:{e}")
        # return retry_modbus_2reg(200, [0] * 2, 270, [0] * 4)

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(202, [0, 0])
            client.write_registers(274, [0] * 4)
        op_logger.info("reset Pump2 Running Time successfully!")
        # return "Reset Pump2 Running Time Successfully"
    except Exception as e:
        op_logger.info("reset Pump2 Running Time failed!")
        print(f"pump2 reset error:{e}")
        # return retry_modbus_2reg(202, [0] * 2, 274, [0] * 4)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(204, [0, 0])
            client.write_registers(278, [0] * 4)
        op_logger.info("reset Pump3 Running Time successfully!")
        # return "Reset Pump3 Running Time Successfully"
    except Exception as e:
        op_logger.info("reset Pump3 Running Time failed!")
        print(f"pump3 reset error:{e}")
        # return retry_modbus_2reg(204, [0] * 2, 278, [0] * 4)

    
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(310, [0, 0, 0, 0])
            client.write_registers(314, [0, 0, 0, 0])
            client.write_registers(318, [0, 0, 0, 0])
            client.write_registers(322, [0, 0, 0, 0])
            client.write_registers(326, [0, 0, 0, 0])
            client.write_registers(330, [0, 0, 0, 0])
            client.write_registers(334, [0, 0, 0, 0])
            client.write_registers(338, [0, 0, 0, 0])
            client.write_registers(342, [0, 0, 0, 0])
            
            client.write_registers(350, [0] * 18)
            
        op_logger.info("reset Filter and Fan Running Time successfully!")
        # return "Reset Filter Running Time Successfully"
    except Exception as e:
        print(f"Filter and Fan reset error:{e}")
        op_logger.info("reset Filter and Fan Running Time failed!")

    ###3. Error Table: 隱藏或刪除所有已經回復的Message(superuser保留)
    try:
        global signal_records
        if signal_records:
            signal_records = []
            save_to_json()
        # return jsonify({"status": "success", "message": "All records deleted successfully."})
        else:
            # return jsonify({"status": "fail", "message": "No records to delete."})
            print("No records to delete.")
    except Exception as e:
        print(f"Error deleting records: {e}")
    
    try:
        global downtime_signal_records
        if downtime_signal_records:
            downtime_signal_records = []
            save_to_downtime_json()
            # return jsonify({"status": "success", "message": "All records deleted successfully."})
        else:
            # return jsonify({"status": "fail", "message": "No records to delete."})
            print("No records to delete.")

    except Exception as e:
        print(f"Error deleting downtime records: {e}")    

    ###4. Logs:軟刪除所有Log檔: 將其轉至old_xxx 資料夾(superuser可見)
    

    LogMover(
        src_dir=os.path.join(log_path, "logs", "error"),
        dst_dir=os.path.join(log_path, "logs", "old_error"),
        name="error"
    ).move_logs()

    LogMover(
        src_dir=os.path.join(log_path, "logs", "operation"),
        dst_dir=os.path.join(log_path, "logs", "old_operation"),
        name="operation"
    ).move_logs()

    LogMover(
        src_dir=os.path.join(log_path, "logs", "sensor"),
        dst_dir=os.path.join(log_path, "logs", "old_sensor"),
        name="sensor"
    ).move_logs()

    LogMover(
        src_dir=os.path.join(snmp_path, "RestAPI", "logs", "operation"),
        dst_dir=os.path.join(snmp_path, "RestAPI", "logs", "old_operation"),
        name="snmp_operation"
    ).move_logs()

    # try:
    #     error_dir = os.path.join(log_path, "logs", "error")
    #     old_error_dir = os.path.join(log_path, "logs", "old_error")

    #     if os.path.exists(error_dir) and os.path.isdir(error_dir):
    #         if not os.path.exists(old_error_dir):
    #             os.makedirs(old_error_dir)

    #         for filename in os.listdir(error_dir):
    #             src_file = os.path.join(error_dir, filename)
    #             dst_file = os.path.join(old_error_dir, filename)
    #             if os.path.isfile(src_file):
    #                 # 如果目的地已存在同名檔案，則改名避免覆蓋
    #                 if os.path.exists(dst_file):
    #                     name, ext = os.path.splitext(filename)
    #                     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #                     new_filename = f"{name}.{timestamp}{ext}"
    #                     dst_file = os.path.join(old_sensor_dir, new_filename)

    #                 shutil.move(src_file, dst_file)
    #         print("All error log files moved to old_error successfully.")
    #     else:
    #         print("Error log directory does not exist.")
    # except Exception as e:
    #     print(f"Move log error: {e}")
        

    # try:
    #     operation_dir = os.path.join(log_path, "logs", "operation")
    #     old_operation_dir = os.path.join(log_path, "logs", "old_operation")

    #     if os.path.exists(operation_dir) and os.path.isdir(operation_dir):
    #         if not os.path.exists(old_operation_dir):
    #             os.makedirs(old_operation_dir)

    #         for filename in os.listdir(operation_dir):
    #             src_file = os.path.join(operation_dir, filename)
    #             dst_file = os.path.join(old_operation_dir, filename)
    #             if os.path.isfile(src_file):
    #                 # 如果目的地已存在同名檔案，則改名避免覆蓋
    #                 if os.path.exists(dst_file):
    #                     name, ext = os.path.splitext(filename)
    #                     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #                     new_filename = f"{name}.{timestamp}{ext}"
    #                     dst_file = os.path.join(old_sensor_dir, new_filename)
    #                 shutil.move(src_file, dst_file)
    #         print("All operation log files moved to old_operation successfully.")
    #     else:
    #         print("operation log directory does not exist.")
    # except Exception as e:
    #     print(f"Move log operation: {e}")
        
        
    # try:
    #     sensor_dir = os.path.join(log_path, "logs", "sensor")
    #     old_sensor_dir = os.path.join(log_path, "logs", "old_sensor")

    #     if os.path.exists(sensor_dir) and os.path.isdir(sensor_dir):
    #         if not os.path.exists(old_sensor_dir):
    #             os.makedirs(old_sensor_dir)

    #         for filename in os.listdir(sensor_dir):
    #             src_file = os.path.join(sensor_dir, filename)
    #             dst_file = os.path.join(old_sensor_dir, filename)
    #             if os.path.isfile(src_file):
    #                 # 如果目的地已存在同名檔案，則改名避免覆蓋
    #                 if os.path.exists(dst_file):
    #                     name, ext = os.path.splitext(filename)
    #                     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #                     new_filename = f"{name}.{timestamp}{ext}"
    #                     dst_file = os.path.join(old_sensor_dir, new_filename)

    #                 shutil.move(src_file, dst_file)
    #         print("All sensor log files moved to old_sensor successfully.")
    #     else:
    #         print("Sensor log directory does not exist.")
    # except Exception as e:
    #     print(f"Move log error: {e}")
        

    # try:
    #     operation_dir = os.path.join(snmp_path, "RestAPI", "logs", "operation")
    #     old_operation_dir = os.path.join(snmp_path, "RestAPI", "logs", "old_operation")

    #     if os.path.exists(operation_dir) and os.path.isdir(operation_dir):
    #         if not os.path.exists(old_operation_dir):
    #             os.makedirs(old_operation_dir)

    #         for filename in os.listdir(operation_dir):
    #             src_file = os.path.join(operation_dir, filename)
    #             dst_file = os.path.join(old_operation_dir, filename)
    #             if os.path.isfile(src_file):
    #                 # 如果目的地已存在同名檔案，則改名避免覆蓋
    #                 if os.path.exists(dst_file):
    #                     name, ext = os.path.splitext(filename)
    #                     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    #                     new_filename = f"{name}.{timestamp}{ext}"
    #                     dst_file = os.path.join(old_sensor_dir, new_filename)

    #                 shutil.move(src_file, dst_file)
    #         print("All operation log files moved to old_operation successfully.")
    #     else:
    #         print("operation log directory does not exist.")
    # except Exception as e:
    #     print(f"Move log operation: {e}")
    
    ###5. Engineer Mode: Sensor Adjustment Setting恢復預設值
    try:
        adjust_import(adjust_factory)
    except Exception as e:
        print(f"sensor adjust import error:{e}")
        
    ###6. Engineer Mode: Alert Threshold Setting恢復預設值
    try:
        if system_data["value"]["unit"] == "metric":
            threshold_import(thrshd_factory)
        else:
            key_list = list(thrshd_factory.keys())
            for key in key_list:
                if not key.endswith("_trap") and not key.startswith("Delay_"):
                    imperial_thrshd_factory[key] = thrshd_factory[key]
                    if "Temp" in key and "TempCds" not in key:
                        imperial_thrshd_factory[key] = (
                            thrshd_factory[key] * 9.0 / 5.0 + 32.0
                        )

                    if "TempCds" in key:
                        imperial_thrshd_factory[key] = thrshd_factory[key] * 9.0 / 5.0

                    if "Prsr" in key:
                        imperial_thrshd_factory[key] = thrshd_factory[key] * 0.145038

                    if "Flow" in key:
                        imperial_thrshd_factory[key] = thrshd_factory[key] * 0.2642
            threshold_import(imperial_thrshd_factory)
        op_logger.info("Reset Threshold to Factory Setting Successfully")
    except Exception as e:  
        print(f"threshold import error:{e}")
    
    ###7. Engineer Mode: PID Setting恢復預設值
    try:
        pid_import(pid_factory)
        op_logger.info("Reset PID to Factory Setting Successfully")
    except Exception as e:  
        print(f"pid import error:{e}")      
        
    ###8. *Ststua Indicator Delay:3000010
    try:
        with open(f"{web_path}/json/timeout_light.json", "w") as file:
            json.dump({"timeoutLight": "30000"}, file)
        op_logger.info(
            "Update indicator delay successfully. Indicator delay:30000"
        )
    except Exception as e:  
        print(f"timeout light error:{e}") 
        
    ###9. Engineer Mode: Auto Mode Redundant Sensor Broken Setting
    try:
        auto_import(auto_factory)
    except Exception as e:
        print(f"Auto Mode Redundant Sensor Broken Setting import error:{e}")
    
    ###10. Engineer Mode: When Dew Point Error in Auto Mode Setting
    try:
        dpt_error_import(dpt_error_factory)
    except Exception as e:
        print(f"Dew Point Error Setting to Factory Setting import error:{e}")
    
    ###11. Engineer Mode: Fan Speed in Auto Mode Setting
    try:
        auto_mode_import(auto_mode_setting_factory)
    except Exception as e:
        print(f"Fan Speed in Auto Mode Setting import error:{e}")
    
    ###12. Engineer Mode: Rack Opening Setting
    try:
        rack_opening_import(rack_opening_setting["factor_value"])
    except Exception as e:
        print(f"Rack Opening Setting import error:{e}")
        
    ###13 Control page : reset pump swap time
    try:
        word1, word2 = cvt_float_byte(24)
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(303, [word2, word1])
    except Exception as e:
        print(f"set pump swap time error:{e}")
        
    ### 14 Control page : reset auto mode temperature and pressure
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            temp1, temp2 = cvt_float_byte(35) ## 預設值35度C
            prsr1, prsr2 = cvt_float_byte(30) ## 預設值30psi
            
            # Reset Auto Mode Temperature
            client.write_registers(226, [temp2, temp1])
            client.write_registers(993, [temp2, temp1])
            
            # Reset Auto Mode Pressure
            client.write_registers(224, [prsr2, prsr1])  
            client.write_registers(991, [prsr2, prsr1])
            
    except Exception as e:
        print(f"reset auto mode temperature and pressure error:{e}")    
    
    ### 15 Control page : reset manual mode pump speed and fan speed
    
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            speed1, speed2 = cvt_float_byte(70)
            client.write_registers(246, [speed2, speed1])  # Reset Manual Mode Pump Speed
            
            fan1, fan2 = cvt_float_byte(70)
            
            client.write_registers(470, [fan2, fan1])  # Reset Manual Mode Fan Speed             
    except Exception as e:
        print(f"reset manual mode pump and fan speed error:{e}")
    
    ##### 最後一步, 重啟電腦
    # subprocess.run(
    #     ["sudo", "reboot"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    # )
    return "Reset all to factory settings Successfully, Please restart PC."



@app.route("/store_pid", methods=["POST"])
@login_required
def store_pid_temp():
    data = request.json
    registers = []

    for key in data["temp"].keys():
        if key in pid_setting["temperature"]:
            pid_setting["temperature"][key] = int(data["temp"][key])
            if not key == "sample_time_temp":
                registers.append(pid_setting["temperature"][key])

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(550, pid_setting["temperature"]["sample_time_temp"])
            client.write_registers(553, registers)

    except Exception as e:
        print(f"error:{e}")
        return retry_modbus_2reg(
            550, pid_setting["temperature"]["sample_time_temp"], 553, registers
        )

    registers = []
    for key in data["pressure"].keys():
        if key in pid_setting["pressure"]:
            pid_setting["pressure"][key] = int(data["pressure"][key])
            if not key == "sample_time_pressure":
                registers.append(pid_setting["pressure"][key])

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(510, pid_setting["pressure"]["sample_time_pressure"])
            client.write_registers(513, registers)

    except Exception as e:
        print(f"error:{e}")
        return retry_modbus_2reg(
            510, pid_setting["pressure"]["sample_time_pressure"], 513, registers
        )

    with open(f"{web_path}/json/pid_setting.json", "w") as json_file:
        json.dump(pid_setting, json_file)

    return "Update PID setting successfully"


@app.route("/collapse_network", methods=["POST"])
@login_required
def collapse_network():
    data = request.get_json()

    if data["collapse"]:
        collapse_state["status"] = True
        return "Collapsed Successfully"
    else:
        collapse_state["status"] = False
        return "Uncollapsed Successfully"


@app.route("/check_network", methods=["GET"])
@login_required
def check_network():
    global collapse_state

    return jsonify({"collapse_state": collapse_state})


@app.route("/store_snmp_setting", methods=["POST"])
@login_required
def store_snmp_setting():
    data = request.get_json()

    with open(f"{snmp_path}/snmp/snmp.json", "w") as json_file:
        json.dump(data, json_file)

    try:
        script_path = f"{snmp_path}/snmp/restart.sh"
        subprocess.run(["/bin/bash", script_path], check=True)
    except subprocess.CalledProcessError as e:
        return f"Error running script: {e}", 500
    op_logger.info(f"SNMP Setting Updated Successfully. {data}")
    return "SNMP Setting Updated Successfully"


@app.route("/get_snmp_setting", methods=["GET"])
@login_required
def get_snmp_setting():
    with open(f"{snmp_path}/snmp/snmp.json", "r") as json_file:
        data = json.load(json_file)
        trap_ip = data.get("trap_ip_address")
        read_community = data.get("read_community")

    snmp_setting["trap_ip_address"] = trap_ip
    snmp_setting["read_community"] = read_community

    return jsonify(snmp_setting)


@app.route("/get_error_data", methods=["GET"])
@login_required
def get_error_data():
    global error_data
    data = list(error_data)
    return jsonify(data)


@app.route("/get_inspection_result")
@login_required
def get_inspection_result():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            inspect_result_len = len(result_data) - 3
            # r = client.read_holding_registers(
            #     750, inspect_result_len, unit=modbus_slave_id
            # )
            r = client.read_holding_registers(
                2000, inspect_result_len, unit=modbus_slave_id
            )
            key_list = list(result_data.keys())

            for i in range(inspect_result_len):
                key = key_list[i]
                if r.registers[i] == 1:
                    result_data[key] = True
                elif r.registers[i] == 0:
                    result_data[key] = False

            prog_len = len(progress_data.keys())

            # r2 = client.read_holding_registers(800, prog_len, unit=modbus_slave_id)
            r2 = client.read_holding_registers(
                2100, prog_len, unit=modbus_slave_id
            )
            key_list = list(progress_data.keys())
            for i in range(prog_len):
                key = key_list[i]
                progress_data[key] = r2.registers[i]
    except Exception as e:
        print(f"get inspection result error:{e}")

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            r = client.read_holding_registers(950, 1)
            result_data["inspect_finish"] = r.registers[0]
    except Exception as e:
        print(f"get inspection finish signal error:{e}")

    if result_data["inspect_finish"] == 1:
        current_time = time.time()
        formatted_time = datetime.fromtimestamp(current_time).strftime(
            "%Y/%m/%d %H:%M:%S"
        )
        result_data["inspect_time"] = formatted_time

        with open(f"{web_path}/json/inspect_time.json", "w") as json_file:
            json.dump({"inspect_time": result_data["inspect_time"]}, json_file)

    with open(f"{web_path}/json/inspect_time.json", "r") as file:
        data = json.load(file)
        inspection_time_last_check["current_time"] = data.get("inspect_time")

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            measure_len = len(measure_data.keys()) * 2
            r = client.read_holding_registers(901, measure_len)
            key_list = list(measure_data.keys())

            j = 0
            for i in range(0, measure_len, 2):
                temp1 = [r.registers[i], r.registers[i + 1]]
                decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
                    temp1, byteorder=Endian.Big, wordorder=Endian.Little
                )
                decoded_value_big_endian = decoder_big_endian.decode_32bit_float()
                format_value = decoded_value_big_endian
                measure_data[key_list[j]] = format_value
                j += 1
    except Exception as e:
        print(f"get measured result error:{e}")

    for inspection_key, sensor_key in key_mapping.items():
        if sensor_key in sensorData["value"]:
            inspection_value[inspection_key] = sensorData["value"][sensor_key]

    with open(f"{web_path}/fw_info.json", "r") as file:
        fw_info_data = json.load(file)
    
    with open(f"{web_path}/fw_info_version.json", "r") as file:
        fw_info_version = json.load(file)
        fw_info_version["PLC"]= sensorData["plc_version"]

    whole_data = {
        "result_data": result_data,
        "inspection_value": inspection_value,
        "progress_data": progress_data,
        "sensor_data": sensorData,
        "measure_data": measure_data,
        "inspection_time_last_check": inspection_time_last_check,
        "fw_info_data": fw_info_data,
        "fw_info_version": fw_info_version,
        "ver_switch": ver_switch,
    }
    return jsonify(whole_data)


@app.route("/inspection_time_apply", methods=["POST"])
def inspection_time_apply():
    data = request.get_json("data")

    pump_open_time = int(data.get("pump_open_time"))

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(740, [pump_open_time])

    except Exception as e:
        print(f"inspection time error:{e}")
        return retry_modbus(740, [pump_open_time], "register")
    op_logger.info("Inspection Time Updated Successfully")
    return "Inspection Time Updated Successfully"


@app.route("/reset_current", methods=["POST"])
def reset_current():
    button_pressed = True

    if any(
        sensorData["error"][key]
        for key in [
            "Inv1_OverLoad",
            "Inv2_OverLoad",
            "Inv3_OverLoad",
            "Fan_OverLoad1",
            "Fan_OverLoad2",
        ]
    ):
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils((8192 + 800), button_pressed)

        except Exception as e:
            print(f"reset_current:{e}")
            return retry_modbus((8192 + 800), [True], "coil")
    else:
        return jsonify(status="error", message="Currently not overload")

    return jsonify(status="success", message="Reset System Failure Successfully")

@app.route("/change_to_stop_mode", methods=["POST"])
def change_to_stop_mode():
    stop_mode = "stop"
    set_mode(stop_mode)
    return jsonify(status="success", message="Stop mode is activated successfully")

@app.route("/start_inspect", methods=["POST"])
def start_inspect():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(900, 1)
            client.write_register(973, 1)
    except Exception as e:
        print(f"start inspect:{e}")
        return retry_modbus_2reg(900, 1, 973, 1)
    op_logger.info("Begin Inspection")
    return jsonify(message="Begin Inspection")


@app.route("/cancel_inspect", methods=["POST"])
def cancel_inspect():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(900, 2)
            client.write_register(973, 2)
    except Exception as e:
        print(f"cancel inspect:{e}")
        return retry_modbus_2reg(900, 2, 973, 2)
    op_logger.info("Cancel Inspection")
    return jsonify(message="Cancel Inspection")

@app.route("/auto_setting_apply", methods=["POST"])
def auto_setting_apply():
    data = request.get_json("data")
    auto_broken_temperature = data["auto_broken_temperature"]
    auto_broken_pressure = data["auto_broken_pressure"]


    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(960, int(auto_broken_temperature))
            client.write_register(961, int(auto_broken_pressure))


    except Exception as e:
        print(f"auto setting:{e}")
 
    op_logger.info(f"Update Auto Setting Successfully. {data}")
    return jsonify(message="Update Auto Setting Successfully")

@app.route("/dpt_error_setting_apply", methods=["POST"])
def dpt_error_setting_apply():
    data = request.get_json("data")
    fan = data["dpt_error_fan"]
    t1 = data["dpt_error_t1"]
    if system_data["value"]["unit"] == "metric":
        if t1 > 100 or t1 < 0:
            return jsonify(
                status="over_range",
                message="Valid Input Range is between 0°C to 100°C",
            )
    else:
        if t1 > 212 or t1 < 32:
            return jsonify(
                status="over_range",
                message="Valid Input Range is between 32°F to 212°F",
            )
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(974, int(fan))
            client.write_register(980, int(t1))
    except Exception as e:
        print(f"dpt error setting:{e}")
        
    op_logger.info(f"Update Dew Point Error Setting Successfully. {data}")
    return jsonify(
        status="success", message="Update Dew Point Error Setting Successfully"
    )


@app.route("/auto_mode_setting_apply", methods=["POST"])
def auto_mode_setting_apply():
    data = request.get_json("data")
    fan = data["auto_mode_fan"]
    fan_rpm = fan * 160
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(533, int(fan_rpm))
    except Exception as e:
        print(f"fan speed in auto mode setting:{e}")

    op_logger.info(f"Update Fan Speed in Auto Mode Setting Successfully. {data}")
    return jsonify(
        status="success", message="Update Fan Speed in Auto Mode Setting Successfully"
    )

@app.route("/rack_opening_setting_apply", methods=["POST"])
def rack_opening_setting_apply():
    data = request.get_json("data")
    value = data["rack_opening_setting"]
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(370, int(value))
    except Exception as e:
        print(f"rack opening setting:{e}")
    op_logger.info(f"Update Rack Opening Setting Successfully. {data}")
    return jsonify(message="Update Rack Opening Setting Successfully")

@app.route("/resetRackOpening", methods=["POST"])
def resetRackOpening():
    rack_opening_import(rack_opening_setting["factor_value"])
    op_logger.info("Reset Rack Opening to Factory Setting Successfully")
    return jsonify(message="Reset Rack Opening to Factory Setting Successfully")


@app.route("/resetAdjust", methods=["POST"])
def resetAdjust():
    adjust_import(adjust_factory)
    op_logger.info("Reset Adjust to Factory Setting Successfully")
    return jsonify(message="Reset Adjust to Factory Setting Successfully")


@app.route("/resetThrshd", methods=["POST"])
def resetThrshd():
    if system_data["value"]["unit"] == "metric":
        threshold_import(thrshd_factory)
    else:
        key_list = list(thrshd_factory.keys())
        for key in key_list:
            if not key.endswith("_trap") and not key.startswith("Delay_"):
                imperial_thrshd_factory[key] = thrshd_factory[key]
                if "Temp" in key:
                    imperial_thrshd_factory[key] = (
                        thrshd_factory[key] * 9.0 / 5.0 + 32.0
                    )

                if "DewPoint" in key:
                    imperial_thrshd_factory[key] = thrshd_factory[key] * 9.0 / 5.0

                if "Prsr" in key:
                    imperial_thrshd_factory[key] = thrshd_factory[key] * 0.145038

                if "Flow" in key:
                    imperial_thrshd_factory[key] = thrshd_factory[key] * 0.2642
        threshold_import(imperial_thrshd_factory)
    op_logger.info("Reset Threshold to Factory Setting Successfully")
    return jsonify(message="Reset Threshold to Factory Setting Successfully")


@app.route("/resetPID", methods=["POST"])
def resetPID():
    pid_import(pid_factory)
    op_logger.info("Reset PID to Factory Setting Successfully")
    return jsonify(message="Reset PID to Factory Setting Successfully")

@app.route("/resetAuto", methods=["POST"])
def resetAuto():
    auto_import(auto_factory)
    op_logger.info("Reset Auto to Factory Setting Successfully")
    return jsonify(message="Reset Auto to Factory Setting Successfully")

@app.route("/resetAutoMode", methods=["POST"])
def resetAutoMode():
    auto_mode_import(auto_mode_setting_factory)
    op_logger.info("Reset Fan Speed in Auto Mode to Factory Setting Successfully")
    return jsonify(
        message="Reset Fan Speed in Auto Mode to Factory Setting Successfully"
    )

@app.route("/resetDptError", methods=["POST"])
def resetDptError():
    dpt_error_import(dpt_error_factory)
    op_logger.info("Reset Dew Point Error Setting to Factory Setting Successfully")
    return jsonify(
        message="Reset Dew Point Error Setting to Factory Setting Successfully"
    )

@app.route("/set_rack_control", methods=["POST"])
def set_rack_control():
    data = request.get_json()

    failed_racks = []

    host = {
        "rack1": "192.168.3.10",
        "rack2": "192.168.3.11",
        "rack3": "192.168.3.12",
        "rack4": "192.168.3.13",
        "rack5": "192.168.3.14",
        "rack6": "192.168.3.15",
        "rack7": "192.168.3.16",
        "rack8": "192.168.3.17",
        "rack9": "192.168.3.18",
        "rack10": "192.168.3.19",
    }

    try:
        for i, coil_val in enumerate(data):
            key = f"rack{i + 1}_sw"
            result_key = f"rack{i + 1}_sw_result"
            rack_key = f"rack{i + 1}"
            rack_ip = host.get(rack_key)
            enable_key = f"rack{i + 1}_enable"
            coil_addr = 8192 + 720 + i
            pass_key = f"rack{i + 1}_pass"

            if not (rack_ip and ctr_data["rack_visibility"].get(enable_key, False)):
                continue

            if not ctr_data["rack_pass"].get(pass_key, False):
                print(f"{pass_key} did not pass")
                failed_racks.append(rack_key)
                continue

            try:
                with ModbusTcpClient(
                    host=modbus_host,
                    port=modbus_port,
                    unit=modbus_slave_id,
                    timeout=0.5,
                ) as client:
                    client.write_coils(coil_addr, [coil_val])
                    ctr_data["rack_set"][key] = bool(coil_val)
                    ctr_data["rack_set"][result_key] = True
            except Exception as e:
                print(f"failed to update rack control: {e}")
                success = retry_modbus_setmode_singlecoil(
                    coil_addr, coil_val if ctr_data["rack_pass"][pass_key] else 0
                )
                if not success:
                    failed_racks.append(rack_key)
                    continue

        if failed_racks:
            failed_racks_list = "".join([f"<li>{rack}</li>" for rack in failed_racks])
            failed_message = f"Failed to update the following racks due to comm error:<br><ul style='margin-left: 67px;margin-top: 10px; text-align: left;'>{failed_racks_list}</ul>"
            return jsonify(status="error", message=failed_message)

        return jsonify(status="success", message="Update rack setting successfully")

    except Exception as e:
        print(f"Error: {e}")

        return jsonify(
            status="error", message="Error occurred while updating rack settings"
        )


@app.route("/set_rack_engineer", methods=["POST"])
def set_rack_engineer():
    data = request.get_json()

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 710), data)
    except Exception as e:
        print(f"rack engineer error: {e}")
        return retry_modbus((8192 + 710), data, "coil")

    try:
        for i, v in enumerate(data):
            key = f"rack{i + 1}_enable"
            ctr_data["rack_visibility"][key] = v

        return jsonify(
            status="success", message="Rack visibility settings updated successfully"
        )
    except Exception as e:
        print(f"Error: {e}")
        return jsonify(
            status="error", message="Error occurred while updating rack settings"
        )

@app.route("/version_switch_admin", methods=["POST"])
def version_switch_admin():
    data = request.get_json()
    leakage_sensor_1_switch = data["leakage_sensor_1_switch"]
    leakage_sensor_2_switch = data["leakage_sensor_2_switch"]
    leakage_sensor_3_switch = data["leakage_sensor_3_switch"]
    leakage_sensor_4_switch = data["leakage_sensor_4_switch"]
    leakage_sensor_5_switch = data["leakage_sensor_5_switch"]
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils(
                (8192 + 809),
                [
                    leakage_sensor_1_switch,
                    leakage_sensor_2_switch,
                    leakage_sensor_3_switch,
                    leakage_sensor_4_switch,
                    leakage_sensor_5_switch,
                ],
            )
        op_logger.info(f"Version setting updated successfully. {data}")
        return jsonify(status="success", message="Version setting updated successfully")
    except Exception as e:
        print(f"Error: {e}")
        return retry_modbus(
            (8092 + 809), 
            [
                leakage_sensor_1_switch,
                leakage_sensor_2_switch,
                leakage_sensor_3_switch,
                leakage_sensor_4_switch,
                leakage_sensor_5_switch,
            ],
            "coil"
        )

@app.route("/version_switch", methods=["POST"])
def version_switch():
    data = request.get_json()

    median_switch = data["median_switch"]
    coolant_quality_meter_switch = data["coolant_quality_meter_switch"]
    fan_count_switch = data["fan_count_switch"]
    liquid_level_1_switch = data["liquid_level_1_switch"]
    liquid_level_2_switch = data["liquid_level_2_switch"]
    liquid_level_3_switch = data["liquid_level_3_switch"]
    leakage_sensor_1_switch = data["leakage_sensor_1_switch"]
    leakage_sensor_2_switch = data["leakage_sensor_2_switch"]
    leakage_sensor_3_switch = data["leakage_sensor_3_switch"]
    leakage_sensor_4_switch = data["leakage_sensor_4_switch"]
    leakage_sensor_5_switch = data["leakage_sensor_5_switch"]
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            # client.write_coils((8192 + 803), [median_switch])
            # client.write_coils((8192 + 804), [coolant_quality_meter_switch])
            # client.write_coils((8192 + 805), [fan_count_switch])
            # client.write_coils((8192 + 806), [liquid_level_1_switch])
            # client.write_coils((8192 + 807), [liquid_level_2_switch])
            # client.write_coils((8192 + 808), [liquid_level_3_switch])
            # client.write_coils((8192 + 809), [leakage_sensor_1_switch])
            # client.write_coils((8192 + 810), [leakage_sensor_2_switch])
            client.write_coils(
                (8192 + 803),
                [
                    median_switch,
                    coolant_quality_meter_switch,
                    fan_count_switch,
                    liquid_level_1_switch,
                    liquid_level_2_switch,
                    liquid_level_3_switch,
                    leakage_sensor_1_switch,
                    leakage_sensor_2_switch,
                    leakage_sensor_3_switch,
                    leakage_sensor_4_switch,
                    leakage_sensor_5_switch
                ],
            )
        op_logger.info(f"Version setting updated successfully. {data}")
        return jsonify(status="success", message="Version setting updated successfully")
    except Exception as e:
        print(f"Error: {e}")
        return retry_modbus(
            (8092 + 803),
            [
                median_switch,
                coolant_quality_meter_switch,
                fan_count_switch,
                liquid_level_1_switch,
                liquid_level_2_switch,
                liquid_level_3_switch,
                leakage_sensor_1_switch,
                leakage_sensor_2_switch,
                leakage_sensor_3_switch,
                leakage_sensor_4_switch,
                leakage_sensor_5_switch,
            ],
            "coil",
        )




@app.before_request
def before_request():
    g.sensorData = sensorData
    g.ctr_data = ctr_data
    g.system_data = system_data
    g.result_data = result_data
    g.user_role = USER_DATA
    g.adjust = sensor_adjust
    g.user_login_info = user_login_info


@app.route("/get_signal_records", methods=["GET"])
def get_signal_records():
    try:
        load_signal_records()

        page = request.args.get("page", default=1, type=int)
        limit = request.args.get("limit", default=20, type=int)

        filter_signal_names = request.args.getlist("signal_name")
        search_keyword = request.args.get("search", default="", type=str).lower()

        filtered_records = signal_records
        if filter_signal_names:
            filtered_records = [
                record
                for record in filtered_records
                if record["signal_name"] in filter_signal_names
            ]

        if search_keyword:
            filtered_records = [
                record
                for record in filtered_records
                if search_keyword in record.get("signal_name", "").lower()
                or search_keyword in record.get("signal_value", "").lower()
            ]

        total_records = len(filtered_records)
        total_pages = (total_records + limit - 1) // limit

        start = (page - 1) * limit
        end = start + limit
        paginated_records = filtered_records[start:end]

        return jsonify(
            {
                "total_records": total_records,
                "total_pages": total_pages,
                "records": paginated_records,
            }
        )
    except FileNotFoundError:
        return jsonify([])


@app.route("/get_downtime_signal_records", methods=["GET"])
def get_downtime_signal_records():
    try:
        load_downtime_signal_records()

        page = request.args.get("page", default=1, type=int)
        limit = request.args.get("limit", default=20, type=int)

        filter_signal_names = request.args.getlist("signal_name")
        search_keyword = request.args.get("search", default="", type=str).lower()

        filtered_records = downtime_signal_records
        if filter_signal_names:
            filtered_records = [
                record
                for record in filtered_records
                if record["signal_name"] in filter_signal_names
            ]

        if search_keyword:
            filtered_records = [
                record
                for record in filtered_records
                if search_keyword in record.get("signal_name", "").lower()
                or search_keyword in record.get("signal_value", "").lower()
            ]

        total_records = len(filtered_records)
        total_pages = (total_records + limit - 1) // limit

        start = (page - 1) * limit
        end = start + limit
        paginated_records = filtered_records[start:end]

        return jsonify(
            {
                "total_records": total_records,
                "total_pages": total_pages,
                "records": paginated_records,
            }
        )
    except FileNotFoundError:
        return jsonify([])


@app.route("/delete_signal_records", methods=["POST"])
def delete_signal_records():
    data = request.get_json()
    signals_to_delete = data.get("signals", [])

    global signal_records
    initial_count = len(signal_records)

    for signal in signals_to_delete:
        signal_name = signal.get("signal_name")
        on_time = signal.get("on_time")

        signal_records = [
            record
            for record in signal_records
            if not (
                record["signal_name"] == signal_name and record["on_time"] == on_time
            )
        ]

    if len(signal_records) < initial_count:
        save_to_json()
        return jsonify(
            {"status": "success", "message": "Records deleted successfully."}
        )
    else:
        return jsonify({"status": "fail", "message": "No records found to delete."})


@app.route("/delete_downtime_signal_records", methods=["POST"])
def delete_downtime_signal_records():
    data = request.get_json()
    signals_to_delete = data.get("signals", [])

    global downtime_signal_records
    initial_count = len(downtime_signal_records)

    for signal in signals_to_delete:
        signal_name = signal.get("signal_name")
        on_time = signal.get("on_time")

        downtime_signal_records = [
            record
            for record in downtime_signal_records
            if not (
                record["signal_name"] == signal_name and record["on_time"] == on_time
            )
        ]

    if len(downtime_signal_records) < initial_count:
        save_to_downtime_json()
        return jsonify(
            {"status": "success", "message": "Records deleted successfully."}
        )
    else:
        return jsonify({"status": "fail", "message": "No records found to delete."})


# @app.route("/mc_power_off", methods=["POST"])
# @login_required
# def mc_power_off():
#     try:
#         with ModbusTcpClient(
#             host=modbus_host, port=modbus_port, unit=modbus_slave_id
#         ) as client:
#             client.write_coils((8192 + 840), [False])
#     except Exception as e:
#         print(f"mc power off error:{e}")
#         return retry_modbus((8192 + 840), [False], "coil")


@app.route("/mc_setting", methods=["POST"])
@login_required
def mc_setting():
    data = request.get_json()

    mc1 = data.get("mc1_sw")
    mc2 = data.get("mc2_sw")
    mc3 = data.get("mc3_sw")
    fan1 = data.get("fan_mc1")
    fan2 = data.get("fan_mc2")

    regs = [mc1, mc2, mc3, fan1, fan2]
    
    
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 840), regs)
    except Exception as e:
        print(f"mc setting error:{e}")
        return retry_modbus((8192 + 840), regs, "coil")

    if not mc1:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils((8192 + 820), [False])
        except Exception as e:
            print(f"setting error:{e}")
            return retry_modbus((8192 + 820), [False], "coil")

    if not mc2:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils((8192 + 821), [False])
        except Exception as e:
            print(f"mc setting error:{e}")
            return retry_modbus((8192 + 821), [False], "coil")

    if not mc3:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils((8192 + 822), [False])
        except Exception as e:
            print(f"mc setting error:{e}")
            return retry_modbus((8192 + 822), [False], "coil")

    if not fan1:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils((8192 + 850), [False] * 4)
        except Exception as e:
            print(f"mc setting error:{e}")
            return retry_modbus((8192 + 850), [False] * 4, "coil")

    if not fan2:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils((8192 + 854), [False] * 4)
        except Exception as e:
            print(f"mc setting error:{e}")
            return retry_modbus((8192 + 824), [False], "coil")

    if ctr_data["downtime_error"]["oc_issue"]:
        return {
            "status": "OC",
            "message": "Overcurrent issue detected\nThe malfunctioning MC cannot be switched on",
        }
    op_logger.info(
        "MC Set Updated Successfully. MC1: %s, MC2: %s, MC3: %s, FanMC1: %s, FanMC2: %s",
        regs[0],
        regs[1],
        regs[2],
        regs[3],
        regs[4],
    )
    return {
        "status": "success",
        "message": "MC Set Updated Successfully",
    }


update_json_restore_times()

def check_rack_leakage_sensor_status(rack_sensor, inputs, delay):
    try:
        if time_data["check"][rack_sensor]:
            if not inputs:
                time_data["check"][rack_sensor] = False
                sensorData["rack"][rack_sensor] = False
            else:
                time_data["end"][rack_sensor] = time.perf_counter()
                passed_time = time_data["end"][rack_sensor] - time_data["start"][rack_sensor]

                if passed_time > thrshd[delay]:
                    sensorData["rack"][rack_sensor] = True
        else:
            if inputs:
                time_data["start"][rack_sensor] = time.perf_counter()
                time_data["check"][rack_sensor] = True
            else:
                sensorData["rack"][rack_sensor] = False
    except Exception as e:
        print(f"check broken error：{e}")


def check_rack_error(rack, delay="Delay_rack_error"):
    broken = rack + "_broken"
    leak = rack + "_leak"
    error = rack + "_error"
    broken_occur = not sensorData["rack_broken"][broken]
    leak_occur = not sensorData["rack_leak"][leak]
    thrsd_low = rack_opening_setting["setting_value"] - 10
    thrsd_high = rack_opening_setting["setting_value"] + 10
    error_occur = (
        ctr_data["rack_set"][f"{rack}_sw"]
        and (sensorData["rack_status"][f"{rack}_status"] < thrsd_low or
        sensorData["rack_status"][f"{rack}_status"] > thrsd_high)
    ) or (
        not ctr_data["rack_set"][f"{rack}_sw"]
        and sensorData["rack_status"][f"{rack}_status"] > 10
    )

    try:
        if time_data["check"][broken]:
            if not broken_occur:
                time_data["check"][broken] = False
                sensorData["rack"][broken] = False

            else:
                time_data["end"][broken] = time.perf_counter()
                passed_time = time_data["end"][broken] - time_data["start"][broken]

                if passed_time > thrshd[delay]:
                    sensorData["rack"][broken] = True

        else:
            if broken_occur:
                time_data["start"][broken] = time.perf_counter()
                time_data["check"][broken] = True
            else:
                time_data["check"][broken] = False
                sensorData["rack"][broken] = False

    except Exception as e:
        print(f"check broken error：{e}")

    try:
        if time_data["check"][leak]:
            if not leak_occur:
                time_data["check"][leak] = False
                sensorData["rack"][leak] = False

            else:
                time_data["end"][leak] = time.perf_counter()
                passed_time = time_data["end"][leak] - time_data["start"][leak]

                if passed_time > thrshd[delay]:
                    sensorData["rack"][leak] = True

        else:
            if leak_occur:
                time_data["start"][leak] = time.perf_counter()
                time_data["check"][leak] = True
            else:
                time_data["check"][leak] = False
                sensorData["rack"][leak] = False

    except Exception as e:
        print(f"check leak error：{e}")

    try:
        if time_data["check"][error]:
            if not error_occur:
                time_data["check"][error] = False
                sensorData["rack"][error] = False

            else:
                time_data["end"][error] = time.perf_counter()
                passed_time = time_data["end"][error] - time_data["start"][error]

                if passed_time > thrshd[delay]:
                    sensorData["rack"][error] = True

        else:
            if error_occur:
                time_data["start"][error] = time.perf_counter()
                time_data["check"][error] = True
            else:
                time_data["check"][error] = False
                sensorData["rack"][error] = False

    except Exception as e:
        print(f"check error：{e}")

def check_rack_com():
    for i in range(5):
        sensorData["rack"][f"rack{i + 1}_status_com"] = True if  sensorData["rack_no_connection"][f"rack{i + 1}_status"] else False
        sensorData["rack"][f"rack{i + 1}_leak_com"] = True if sensorData["rack_no_connection"][f"rack{i + 1}_leak"] else False

def send_error_log():
    for i in range(10):
        num = i + 1
        broken = f"rack{num}_broken"
        leak = f"rack{num}_leak"
        error = f"rack{num}_error"
        key = f"rack{num}"
        visible = f"rack{num}_enable"

        current_time = time.perf_counter()

        # sensorData["rack"][broken] = True
        # sensorData["rack"][leak] = True
        # sensorData["rack"][error] = True

        # sensorData["rack"]["rack4_leak"] = False
        diff = current_time - time_data["errorlog_start"][key]

        if diff >= 10:
            if ctr_data["rack_visibility"][visible]:
                if sensorData["rack"][broken]:
                    app.logger.warning(sensorData["err_log"]["rack"][broken])
                    # print(broken)

                if sensorData["rack"][leak]:
                    app.logger.warning(sensorData["err_log"]["rack"][leak])
                    # print(leak)

                if sensorData["rack"][error]:
                    app.logger.warning(sensorData["err_log"]["rack"][error])
                    # print(error)

            time_data["errorlog_start"][key] = current_time


def read_rack_status():
    global light, warning_light
    host = {
        "rack1_register": "192.168.3.20",
        "rack2_register": "192.168.3.21",
        "rack3_register": "192.168.3.22",
        "rack4_register": "192.168.3.23",
        "rack5_register": "192.168.3.24",
        "rack6_register": "192.168.3.25",
        "rack7_register": "192.168.3.26",
        "rack8_register": "192.168.3.27",
        "rack9_register": "192.168.3.28",
        "rack10_register": "192.168.3.29",
        "rack1_coil": "192.168.3.10",
        "rack2_coil": "192.168.3.11",
        "rack3_coil": "192.168.3.12",
        "rack4_coil": "192.168.3.13",
        "rack5_coil": "192.168.3.14",
        "rack6_coil": "192.168.3.15",
        "rack7_coil": "192.168.3.16",
        "rack8_coil": "192.168.3.17",
        "rack9_coil": "192.168.3.18",
        "rack10_coil": "192.168.3.19",
    }

    for key in time_data["errorlog_start"]:
        time_data["errorlog_start"][key] = time.perf_counter()

    while True:
        if ctr_data["rack_visibility"]["rack1_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack1_register"], port=modbus_port, timeout=0.5
                ) as client_rack1_reg:
                    r = client_rack1_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack1_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    
                    if sensorData["rack_status"]["rack1_status"] <=20:
                        sensorData["rack_status"]["rack1_status"] = 0
                    sensorData["rack_no_connection"]["rack1_status"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack1_status"] = True
                
                print(f"rack1 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack1_coil"], port=modbus_port, timeout=0.5
                ) as client_rack1_coil:
                    r = client_rack1_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack1_leak"] = r.bits[0]
                    sensorData["rack_broken"]["rack1_broken"] = r.bits[1]
                    sensorData["rack_no_connection"]["rack1_leak"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack1_leak"] = True
                
                print(f"rack1 reg error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack1_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 720), [False])
                    if ctr_data["rack_set"]["rack1_sw"]:
                        sensorData["rack_prev"]["rack1"] = True
                else:
                    if sensorData["rack_prev"]["rack1"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 720), [True])
                        sensorData["rack_prev"]["rack1"] = False
            except Exception as e:
                print(f"rack1 set control error: {e}")

            # check_rack_error("rack1")

        if ctr_data["rack_visibility"]["rack2_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack2_register"], port=modbus_port, timeout=0.5
                ) as client_rack2_reg:
                    r = client_rack2_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack2_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    if sensorData["rack_status"]["rack2_status"] <= 20:
                        sensorData["rack_status"]["rack2_status"] = 0
                    sensorData["rack_no_connection"]["rack2_status"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack2_status"] = True
                
                print(f"rack2 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack2_coil"], port=modbus_port, timeout=0.5
                ) as client_rack2_coil:
                    r = client_rack2_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack2_leak"] = r.bits[0]
                    sensorData["rack_broken"]["rack2_broken"] = r.bits[1]
                    sensorData["rack_no_connection"]["rack2_leak"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack2_leak"] = True
                
                print(f"rack2 reg error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack2_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 721), [False])
                    if ctr_data["rack_set"]["rack2_sw"]:
                        sensorData["rack_prev"]["rack2"] = True
                else:
                    if sensorData["rack_prev"]["rack2"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 721), [True])
                        sensorData["rack_prev"]["rack2"] = False
            except Exception as e:
                print(f"rack2 set control error: {e}")

            # check_rack_error("rack2")

        if ctr_data["rack_visibility"]["rack3_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack3_register"], port=modbus_port, timeout=0.5
                ) as client_rack3_reg:
                    r = client_rack3_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack3_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    if sensorData["rack_status"]["rack3_status"] <= 20:
                        sensorData["rack_status"]["rack3_status"] = 0
                    sensorData["rack_no_connection"]["rack3_status"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack3_status"] = True
                
                print(f"rack3 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack3_coil"], port=modbus_port, timeout=0.5
                ) as client_rack3_coil:
                    r = client_rack3_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack3_leak"] =  r.bits[0]
                    sensorData["rack_broken"]["rack3_broken"] =  r.bits[1]
                    sensorData["rack_no_connection"]["rack3_leak"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack3_leak"] = True
                
                print(f"rack3 reg error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack3_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 722), [False])
                    if ctr_data["rack_set"]["rack3_sw"]:
                        sensorData["rack_prev"]["rack3"] = True
                else:
                    if sensorData["rack_prev"]["rack3"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 722), [True])
                        sensorData["rack_prev"]["rack3"] = False
            except Exception as e:
                print(f"rack3 set control error: {e}")

            # check_rack_error("rack3")

        if ctr_data["rack_visibility"]["rack4_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack4_register"], port=modbus_port, timeout=0.5
                ) as client_rack4_reg:
                    r = client_rack4_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack4_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    if sensorData["rack_status"]["rack4_status"] <= 20:
                        sensorData["rack_status"]["rack4_status"] = 0
                    sensorData["rack_no_connection"]["rack4_status"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack4_status"] = True
                
                print(f"rack4 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack4_coil"], port=modbus_port, timeout=0.5
                ) as client_rack4_coil:
                    r = client_rack4_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack4_leak"] = r.bits[0]
                    sensorData["rack_broken"]["rack4_broken"] = r.bits[1]
                    sensorData["rack_no_connection"]["rack4_leak"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack4_leak"] = True
                
                print(f"rack4 coil error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack4_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 723), [False])
                    if ctr_data["rack_set"]["rack4_sw"]:
                        sensorData["rack_prev"]["rack4"] = True
                else:
                    if sensorData["rack_prev"]["rack4"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 723), [True])
                        sensorData["rack_prev"]["rack4"] = False
            except Exception as e:
                print(f"rack4 set control error: {e}")

            # check_rack_error("rack4")

        if ctr_data["rack_visibility"]["rack5_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack5_register"], port=modbus_port, timeout=0.5
                ) as client_rack5_reg:
                    r = client_rack5_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack5_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    if sensorData["rack_status"]["rack5_status"] <= 20:
                        sensorData["rack_status"]["rack5_status"] = 0
                    sensorData["rack_no_connection"]["rack5_status"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack5_status"] = True
                
                print(f"rack5 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack5_coil"], port=modbus_port, timeout=0.5
                ) as client_rack5_coil:
                    r = client_rack5_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack5_leak"] = r.bits[0]
                    sensorData["rack_broken"]["rack5_broken"] = r.bits[1]
                    sensorData["rack_no_connection"]["rack5_leak"] = False
                    
            except Exception as e:
                sensorData["rack_no_connection"]["rack5_leak"] = True
                
                print(f"rack5 coil error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack5_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 724), [False])
                    if ctr_data["rack_set"]["rack5_sw"]:
                        sensorData["rack_prev"]["rack5"] = True
                else:
                    if sensorData["rack_prev"]["rack5"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 724), [True])
                        sensorData["rack_prev"]["rack5"] = False
            except Exception as e:
                print(f"rack5 set control error: {e}")

            # check_rack_error("rack5")

        if ctr_data["rack_visibility"]["rack6_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack6_register"], port=modbus_port, timeout=0.5
                ) as client_rack6_reg:
                    r = client_rack6_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack6_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    if sensorData["rack_status"]["rack6_status"] <= 20:
                        sensorData["rack_status"]["rack6_status"] = 0
                    sensorData["rack_no_connection"]["rack6_status"] = False
            except Exception as e:
                sensorData["rack_no_connection"]["rack6_status"] = True
                print(f"rack6 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack6_coil"], port=modbus_port, timeout=0.5
                ) as client_rack6_coil:
                    r = client_rack6_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack6_leak"] = r.bits[0]
                    sensorData["rack_broken"]["rack6_broken"] = r.bits[1]
                    sensorData["rack_no_connection"]["rack6_leak"] = False
            except Exception as e:
                sensorData["rack_no_connection"]["rack6_leak"] = True
                print(f"rack6 coil error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack6_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 725), [False])
                    if ctr_data["rack_set"]["rack6_sw"]:
                        sensorData["rack_prev"]["rack6"] = True
                else:
                    if sensorData["rack_prev"]["rack6"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 725), [True])
                        sensorData["rack_prev"]["rack6"] = False
            except Exception as e:
                print(f"rack5 set control error: {e}")

            # check_rack_error("rack6")

        if ctr_data["rack_visibility"]["rack7_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack7_register"], port=modbus_port, timeout=0.5
                ) as client_rack7_reg:
                    r = client_rack7_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack7_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    if sensorData["rack_status"]["rack7_status"] <= 20:
                        sensorData["rack_status"]["rack7_status"] = 0
                    sensorData["rack_no_connection"]["rack7_status"] = False
            except Exception as e:
                sensorData["rack_no_connection"]["rack7_status"] = True
                print(f"rack7 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack7_coil"], port=modbus_port, timeout=0.5
                ) as client_rack7_coil:
                    r = client_rack7_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack7_leak"] = r.bits[0]
                    sensorData["rack_broken"]["rack7_broken"] = r.bits[1]
                    sensorData["rack_no_connection"]["rack7_leak"] = False
            except Exception as e:
                sensorData["rack_no_connection"]["rack7_leak"] = True
                print(f"rack7 coil error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack7_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 726), [False])
                    if ctr_data["rack_set"]["rack7_sw"]:
                        sensorData["rack_prev"]["rack7"] = True
                else:
                    if sensorData["rack_prev"]["rack7"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 726), [True])
                        sensorData["rack_prev"]["rack7"] = False
            except Exception as e:
                print(f"rack7 set control error: {e}")

            # check_rack_error("rack7")

        if ctr_data["rack_visibility"]["rack8_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack8_register"], port=modbus_port, timeout=0.5
                ) as client_rack8_reg:
                    r = client_rack8_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack8_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    if sensorData["rack_status"]["rack8_status"] <= 20:
                        sensorData["rack_status"]["rack8_status"] = 0
                    sensorData["rack_no_connection"]["rack8_status"] = False

            except Exception as e:
                sensorData["rack_no_connection"]["rack8_status"] = True
                print(f"rack8 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack8_coil"], port=modbus_port, timeout=0.5
                ) as client_rack8_coil:
                    r = client_rack8_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack8_leak"] = r.bits[0]
                    sensorData["rack_broken"]["rack8_broken"] = r.bits[1]
                    sensorData["rack_no_connection"]["rack8_leak"] = False
            except Exception as e:
                sensorData["rack_no_connection"]["rack8_leak"] = True
                print(f"rack8 coil error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack8_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 727), [False])
                    if ctr_data["rack_set"]["rack8_sw"]:
                        sensorData["rack_prev"]["rack8"] = True
                else:
                    if sensorData["rack_prev"]["rack8"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 727), [True])
                        sensorData["rack_prev"]["rack8"] = False
            except Exception as e:
                print(f"rack8 set control error: {e}")

            # check_rack_error("rack8")

        if ctr_data["rack_visibility"]["rack9_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack9_register"], port=modbus_port, timeout=0.5
                ) as client_rack9_reg:
                    r = client_rack9_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack9_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    if sensorData["rack_status"]["rack9_status"] <= 20:
                        sensorData["rack_status"]["rack9_status"] = 0
                    sensorData["rack_no_connection"]["rack9_status"] = False
            except Exception as e:
                sensorData["rack_no_connection"]["rack9_status"] = True
                print(f"rack9 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack9_coil"], port=modbus_port, timeout=0.5
                ) as client_rack9_coil:
                    r = client_rack9_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack9_leak"] = r.bits[0]
                    sensorData["rack_broken"]["rack9_broken"] = r.bits[1]
                    sensorData["rack_no_connection"]["rack9_leak"] = False
            except Exception as e:
                sensorData["rack_no_connection"]["rack9_leak"] = True
                print(f"rack9 coil error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack9_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 728), [False])
                    if ctr_data["rack_set"]["rack9_sw"]:
                        sensorData["rack_prev"]["rack9"] = True
                else:
                    if sensorData["rack_prev"]["rack9"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 728), [True])
                        sensorData["rack_prev"]["rack9"] = False
            except Exception as e:
                print(f"rack9 set control error: {e}")

            # check_rack_error("rack9")

        if ctr_data["rack_visibility"]["rack10_enable"]:
            try:
                with ModbusTcpClient(
                    host=host["rack10_register"], port=modbus_port, timeout=0.5
                ) as client_rack10_reg:
                    r = client_rack10_reg.read_holding_registers(0, 1)
                    result = r.registers[0]
                    sensorData["rack_status"]["rack10_status"] = (
                        (result - 32767) / 32767 * 100
                    )
                    if sensorData["rack_status"]["rack10_status"] <= 20:
                        sensorData["rack_status"]["rack10_status"] = 0
                    sensorData["rack_no_connection"]["rack10_status"] = False

            except Exception as e:
                sensorData["rack_no_connection"]["rack10_status"] = True
                print(f"rack10 reg error: {e}")
                pass

            try:
                with ModbusTcpClient(
                    host=host["rack10_coil"], port=modbus_port, timeout=0.5
                ) as client_rack10_coil:
                    r = client_rack10_coil.read_coils(0, 2)
                    sensorData["rack_leak"]["rack10_leak"] = r.bits[0]
                    sensorData["rack_broken"]["rack10_broken"] = r.bits[1]
                    sensorData["rack_no_connection"]["rack10_leak"] = False
            except Exception as e:
                sensorData["rack_no_connection"]["rack10_leak"] = True
                print(f"rack10 coil error: {e}")
                pass

            try:
                if not sensorData["rack_leak"]["rack10_leak"]:
                    with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                        client.write_coils((8192 + 729), [False])
                    if ctr_data["rack_set"]["rack10_sw"]:
                        sensorData["rack_prev"]["rack10"] = True
                else:
                    if sensorData["rack_prev"]["rack10"]:
                        with ModbusTcpClient(host="192.168.3.250", port=502) as client:
                            client.write_coils((8192 + 729), [True])
                        sensorData["rack_prev"]["rack10"] = False
            except Exception as e:
                print(f"rack10 set control error: {e}")

            # check_rack_error("rack10")
        check_rack_com()
        for i, (key, enabled) in enumerate(ctr_data["rack_visibility"].items(), start=1):
            rack_name = f"rack{i}"
            if enabled:
                check_rack_error(rack_name)
            else:
                for suffix in ["_broken", "_leak", "_error", "_leak_com", "_status_com"]:
                    sensorData["rack"][f"{rack_name}{suffix}"] = False
                sensorData["rack_no_connection"][f"{rack_name}_status"] = False
                sensorData["rack_no_connection"][f"{rack_name}_leak"] = False
        # index = 1
        # for key in ctr_data["rack_visibility"]:
        #     if ctr_data["rack_visibility"][key]:
        #         check_rack_error(f"rack{index}")
        #     elif not ctr_data["rack_visibility"][key]:
        #         sensorData["rack"][f"rack{index}_broken"] = False
        #         sensorData["rack"][f"rack{index}_leak"] = False
        #         sensorData["rack"][f"rack{index}_error"] = False
        #         sensorData["rack"][f"rack{index}_leak_com"] = False
        #         sensorData["rack"][f"rack{index}_status_com"] = False
        #         sensorData["rack_no_connection"][f"rack{index}_status"] = False
        #         sensorData["rack_no_connection"][f"rack{index}_leak"] = False
        #     index += 1
        # send_error_log()
        
        try:
            rack_key = list(sensorData["rack"].keys())
            rack_key_len = len(sensorData["rack"].keys())
            rack_reg = (rack_key_len // 16) + (1 if rack_key_len % 16 != 0 else 0)
            value_r = [0] * rack_reg
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port) as client:
                r1 = client.read_discrete_inputs(36, 10, unit=modbus_slave_id)
                rack_leakage1_leak = r1.bits[0]
                rack_leakage1_broken = r1.bits[1]
                rack_leakage2_leak = r1.bits[2]
                rack_leakage2_broken = r1.bits[3]
                r2 = client.read_discrete_inputs(4, 6, unit=modbus_slave_id)
                rack_leakage3_leak = r2.bits[0]
                rack_leakage3_broken = r2.bits[1]
                rack_leakage4_leak = r2.bits[2]
                rack_leakage4_broken = r2.bits[3]
                rack_leakage5_leak = r2.bits[4]
                rack_leakage5_broken = r2.bits[5]
                rack_leakage_leak_list = [rack_leakage1_leak, rack_leakage2_leak, rack_leakage3_leak, rack_leakage4_leak, rack_leakage5_leak]
                rack_leakage_broken_list = [rack_leakage1_broken, rack_leakage2_broken, rack_leakage3_broken, rack_leakage4_broken, rack_leakage5_broken]
            for i in range(1, 6):
                if not ver_switch.get(f"leakage_sensor_{i}_switch", False):
                    check_rack_leakage_sensor_status(
                        f"rack_leakage{i}_leak",
                        rack_leakage_leak_list[i - 1],
                        f"Delay_rack_leakage{i}_leak",
                    )
                    check_rack_leakage_sensor_status(
                        f"rack_leakage{i}_broken",
                        rack_leakage_broken_list[i - 1],
                        f"Delay_rack_leakage{i}_broken",
                    )
                else:
                    sensorData["rack"][f"rack_leakage{i}_leak"] = False
                    sensorData["rack"][f"rack_leakage{i}_broken"] = False
            # if not ver_switch["leakage_sensor_1_switch"]:
            #     check_rack_leakage_sensor_status(
            #         "rack_leakage1_leak",
            #         rack_leakage1_leak,
            #         "Delay_rack_leakage1_leak",
            #     )
            #     check_rack_leakage_sensor_status(
            #         "rack_leakage1_broken",
            #         rack_leakage1_broken,
            #         "Delay_rack_leakage1_broken",
            #     )
            # else:
            #     sensorData["rack"]["rack_leakage1_leak"] = False
            #     sensorData["rack"]["rack_leakage1_broken"] = False
                
            # if not ver_switch["leakage_sensor_2_switch"]:
            #     check_rack_leakage_sensor_status(
            #         "rack_leakage2_leak",
            #         rack_leakage2_leak,
            #         "Delay_rack_leakage2_leak",
            #     )
            #     check_rack_leakage_sensor_status(
            #         "rack_leakage2_broken",
            #         rack_leakage2_broken,
            #         "Delay_rack_leakage2_broken",
            #     )
            # else:
            #     sensorData["rack"]["rack_leakage2_leak"] = False
            #     sensorData["rack"]["rack_leakage2_broken"] = False
                
            for i in range(0, rack_key_len):
                key = rack_key[i]
                # 測試用
                # sensorData["rack"][key] = False
                # sensorData["rack"]["rack_leakage1_broken"] = True
                # sensorData["rack"]["rack_leakage1_leak"] = True
                # sensorData["rack"]["rack_leakage2_broken"] = True
                # sensorData["rack"]["rack_leakage2_leak"] = True
                if sensorData["rack"][key]:
                    value_r[i // 16] |= 1 << (i % 16)

            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_registers(1715, value_r)
        except Exception as e:
            print(f"store in 16 bits error: {e}")

        if onLinux:
            try:
                if ctr_data["value"]["resultMode"] == "inspection":
                    light = False
                elif any(value for key, value in sensorData["rack"].items()):
                    light = warning_light
                    warning_light = not warning_light
                else:
                    light = False

                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    client.write_coils(4, light)

            except Exception as e:
                print(f"warning light error:{e}")

        time.sleep(1)


read_rack_status = threading.Thread(target=read_rack_status)
read_rack_status.daemon = True
read_rack_status.start()


modbus_thread = threading.Thread(target=read_modbus_data)
modbus_thread.daemon = True
modbus_thread.start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5501, debug=debug, use_reloader=repeat)
