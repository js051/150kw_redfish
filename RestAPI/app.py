# 標準函式庫
import json
import logging
import os
import struct
import time
import zipfile
from collections import OrderedDict

# 第三方套件
from flask import Flask, request
from flask_restx import Api, Resource, fields, Namespace, reqparse
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder, BinaryPayloadBuilder
from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
import requests
import pyzipper
from dotenv import load_dotenv, set_key

# from flask_limiter import Limiter
# from flask_limiter.util import get_remote_address
load_dotenv()

log_path = os.path.dirname(os.getcwd())
json_path = f"{log_path}/webUI/web/json"
web_path = f"{log_path}/webUI/web"

app = Flask(__name__)
api = Api(app, version="0.6.6", title="CDU API", description="API for CDU system")


# limiter = Limiter(
#     key_func=get_remote_address,
#     default_limits=["10 per second"],
#     app=app,
# )

default_ns = Namespace("api/v1", description="api for CDU system")

log_dir = f"{log_path}/RestAPI/logs/operation"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)


file_name = "oplog_api.log"
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
op_logger = logging.getLogger("custom_restapi")
op_logger.setLevel(logging.INFO)
op_logger.addHandler(oplog_handler)

modbus_host = "192.168.3.250"
# modbus_host = "127.0.0.1"
modbus_port = 502
modbus_slave_id = 1

op_mode = {"mode": "stop"}
pump_speed_set = {"pump_speed": 0, "pump1_speed": 0, "pump2_speed": 0, "pump3_speed": 0}
fan_speed_set = {
    "fan1_speed": 0,
    "fan2_speed": 0,
    "fan3_speed": 0,
    "fan4_speed": 0,
    "fan5_speed": 0,
    "fan6_speed": 0,
    "fan7_speed": 0,
    "fan8_speed": 0,
}
temp_set = {"temp_set": 0}
pressure_set = {"pressure_set": 0}
fan_set = {"fan_set": 0}
pump_swap_time = {"pump_swap_time": 0}
unit_set = {"unit": "Metric"}
thrshd = {}
ctr_data = {}
measure_data = {}

data = {
    "sensor_value": {
        "temp_clntSply": 0,
        "temp_clntSplySpare": 0,
        "temp_clntRtn": 0,
        "temp_clntRtnSpare": 0,
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
    "unit": {
        "temperature": "celcius",
        "pressure": "bar",
        "flow": "LPM",
        "power": "kW",
        "heat_capacity": "kW",
    },
    "fan_speed": {
        "fan1_speed": 0,
        "fan2_speed": 0,
        "fan3_speed": 0,
        "fan4_speed": 0,
        "fan5_speed": 0,
        "fan6_speed": 0,
        "fan7_speed": 0,
        "fan8_speed": 0,
    },
    "pump_speed": {
        "pump1_speed": 0, 
        "pump2_speed": 0, 
        "pump3_speed": 0,
    },
    "pump_service_hours": {
        "pump1_service_hours": 0,
        "pump2_service_hours": 0,
        "pump3_service_hours": 0,
    },
    "pump_state": {
        "pump1_state": "Enable",
        "pump2_state": "Disable",
        "pump3_state": "Disable",
    },
    "pump_health": {
        "pump1_health": "OK",
        "pump2_health": "Critical",
        "pump3_health": "Critical",
    },
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
        "M319": ["ATS 1 Communication Error", False],
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

system_data = {
    "value": {
        "unit": "metric",
        "last_unit": "metric",
    }
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


physical_asset = {
    "Name": "cdu",
    "FirmwareVersion": "0100",
    "Version": "N/A",
    # "ProductionDate": "20250430",
    "Manufacturer": "KAORI",
    "Model": "150kw",
    "SerialNumber": "N/A",
    "PartNumber": "N/A",
    # "AssetTag": "N/A",
    # "CDUStatus": "Good",
    "OperationMode": "Auto flow control",
    # "LEDLight": "ON",
    "CDUStatus": "OK",
}

fan_speed_model = default_ns.model(
    "FanSpeed",
    {
        "fan_speed": fields.Integer(
            description="Fan speed", example=50, min=0, max=100
        ),
    },
)

pressure_set_model = default_ns.model(
    "PressureSet",
    {
        "pressure_set": fields.Float(
            required=True, description="The pressure setting", example=1.2
        )
    },
)

pump1_speed_model = default_ns.model(
    "PumpSpeed",
    {
        "pump_speed": fields.Integer(
            description="Pump speed", example=50, min=0, max=100
        ),
        "pump_switch": fields.Boolean(description="Pump switch", example=True),
    },
)

pump2_speed_model = default_ns.model(
    "PumpSpeed",
    {
        "pump_speed": fields.Integer(
            description="Pump speed", example=50, min=0, max=100
        ),
        "pump_switch": fields.Boolean(description="Pump switch", example=True),
    },
)

pump3_speed_model = default_ns.model(
    "PumpSpeed",
    {
        "pump_speed": fields.Integer(
            description="Pump speed", example=50, min=0, max=100
        ),
        "pump_switch": fields.Boolean(description="Pump switch", example=True),
    },
)

pump_swap_time_model = default_ns.model(
    "PumpSwapTime",
    {
        "pump_swap_time": fields.Integer(
            description="Time interval for pump swapping in minutes",
            example=60,
            min=0,
            max=30000,
        )
    },
)

temp_set_model = default_ns.model(
    "TempSet",
    {
        "temp_set": fields.Integer(
            required=True,
            description="The temperature setting 35-55 deg celcius",
            example=40,
        )
    },
)

op_mode_model = default_ns.model(
    "OpMode",
    {
        # auto
        "mode": fields.String(required=True, description="The operational mode", example="stop", enum=["stop", "manual", "auto"]),
        "temp_set": fields.Float(required=False, description="set temperature (manual only)", example="50"),
        "pressure_set": fields.Float(required=False, description="set pressure (manual only)", example="10"),
        "pump_swap_time": fields.Integer(required=False, description="set pump_swap_time (manual only)", example="100"),
        # manual
        "pump_speed": fields.Integer(required=False, description="set pump speed (manual only)", example="50"),
        "pump1_switch": fields.Boolean(required=False, description="set pump1 switch (manual only)", example="true"),
        "pump2_switch": fields.Boolean(required=False, description="set pump2 switch (manual only)", example="true"),
        "pump3_switch": fields.Boolean(required=False, description="set pump3 switch (manual only)", example="true"),
        "fan_speed": fields.Integer(required=False, description="set fan speed (manual only)", example="30"),
        "fan1_switch": fields.Boolean(required=False, description="set fan1 switch (manual only)", example="true"),
        "fan2_switch": fields.Boolean(required=False, description="set fan2 switch (manual only)", example="true"),
        "fan3_switch": fields.Boolean(required=False, description="set fan3 switch (manual only)", example="true"),
        "fan4_switch": fields.Boolean(required=False, description="set fan4 switch (manual only)", example="true"),
        "fan5_switch": fields.Boolean(required=False, description="set fan5 switch (manual only)", example="true"),
        "fan6_switch": fields.Boolean(required=False, description="set fan6 switch (manual only)", example="true"),
        "fan7_switch": fields.Boolean(required=False, description="set fan7 switch (manual only)", example="true"),
        "fan8_switch": fields.Boolean(required=False, description="set fan8 switch (manual only)", example="true"),
    },
)

unit_set_model = default_ns.model(
    "UnitSet",
    {
        "unit_set": fields.String(
            required=True,
            description="The unit setting",
            example="metric",
            enum=["metric", "imperial"],
        )
    },
)

# set temp
def set_temperature():
    temp_set = api.payload.get("temp_set")
    # 檢查輸入
    if not isinstance(temp_set, (int, float, type(None))):
        return False, invalid_type()
    unit = read_unit()
    upLmt = 131 if unit == "imperial" else 55
    lowLmt = 77 if unit == "imperial" else 25
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port, unit=modbus_slave_id) as client:

            if temp_set is None:
                read_data = client.read_holding_registers(226, 2)
                temp_set = cvt_registers_to_float(read_data.registers[0], read_data.registers[1])
                return True, temp_set

            if lowLmt <= temp_set <= upLmt:
                word1, word2 = cvt_float_byte(float(temp_set))
                client.write_registers(993, [word2, word1])
                client.write_registers(226, [word2, word1])
                op_logger.info(f"Temperature updated successfully.{temp_set}")
                return True, temp_set
            else:
                return False, f"Invalid temperature range: {lowLmt}~{upLmt}"
            
        
    except Exception as e:
        print(f"[Modbus Error] {e}")
        return False, "Modbus write failed"
                


# set prsr
def set_pressure_value():
    pressure_set = api.payload.get("pressure_set")
    # 檢查輸入
    if not isinstance(pressure_set, (int, float, type(None))):
        return False, invalid_type()
    unit = read_unit()
    if unit == "imperial":
        upLmt = 108.75
        lowLmt = 0
    else:
        upLmt = 750
        lowLmt = 0
        
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port, unit=modbus_slave_id) as client:
            if pressure_set is None:
                read_data = client.read_holding_registers(224, 2)
                pressure_set = cvt_registers_to_float(read_data.registers[0], read_data.registers[1])
                return True, pressure_set
            
            if not (lowLmt <= pressure_set <= upLmt):
                if unit == "imperial":
                    return False, ("Invalid pressure. Pressure must be between 0 and 108.")
                else:
                    return False, ("Invalid pressure. Pressure must be between 0 and 750.")
            else:
                word1, word2 = cvt_float_byte(float(pressure_set))
                client.write_registers(991, [word2, word1])
                client.write_registers(224, [word2, word1])
                op_logger.info(f"Pressure update successfully. {pressure_set}")
                return True, round(pressure_set, 2)

    except Exception as e:
        print(f"write pressure_set: {e}")
        return False, plc_error()

# set pump swap time
def set_pump_swap_time():
    pump_swap_time = api.payload.get("pump_swap_time")
    if not isinstance(pump_swap_time, (int, float, type(None))):
        return False, invalid_type()
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port, unit=modbus_slave_id) as client:
            if pump_swap_time is None:
                read_data = client.read_holding_registers(303, 2)
                pump_swap_time = cvt_registers_to_float(read_data.registers[0], read_data.registers[1])
                return True, pump_swap_time
            if 0 < pump_swap_time <= 30000:
                word1, word2 = cvt_float_byte(pump_swap_time)
                client.write_registers(303, [word2, word1])
                op_logger.info(f"Pump swap time updated successfully. {pump_swap_time}")
                return True, pump_swap_time
            else:
                return False, ("Invalid value. Time interval must be between 0 and 30000.")
    except Exception as e:
        print(f"write pump swap: {e}")
        return False, plc_error()    
   
# set pump speed & switch
def set_pump_speed():
    data = api.payload
    pump_speed = data.get("pump_speed")
    pump1_switch = data.get("pump1_switch")
    pump2_switch = data.get("pump2_switch")
    pump3_switch = data.get("pump3_switch")

    try:
        # 檢查輸入
        if not isinstance(pump_speed, (int, type(None))):
            return False, invalid_type()
        
        if not all(isinstance(x, (bool, type(None))) for x in [pump1_switch, pump2_switch, pump3_switch]):
            return False, invalid_type()

        sensor = read_sensor_data()
        ctr = read_ctr_data()
        with ModbusTcpClient(host=modbus_host, port=modbus_port, unit=modbus_slave_id) as client:
            # 判斷是否有更改(無的話讀原本的值)
            if pump_speed is None:
                read_data = client.read_holding_registers(246, 2)
                if read_data.isError():
                    return False, {"message": "Failed to read pump speed from Modbus."}
                pump_speed = cvt_registers_to_float(read_data.registers[0], read_data.registers[1])
            # 區域判斷
            if (0 < pump_speed < 25) or (pump_speed > 100):
                op_logger.info(f"Invalid pump speed input. Accepted values are 25-100 or 0.")
                return False, ({
                    "message": "Invalid pump speed input. Accepted values are 25-100 or 0."
                }, 400)
            result = {
                "pump_speed": pump_speed,
                "pump1_switch": pump1_switch,
                "pump2_switch": pump2_switch,
                "pump3_switch": pump3_switch,
            }
            # 輪流檢查
            for pump_id, switch in zip([1, 2, 3], [pump1_switch, pump2_switch, pump3_switch]):
                error = sensor["error"].get(f"Inv{pump_id}_Error", False)
                overload = sensor["error"].get(f"Inv{pump_id}_OverLoad", False)
                mc = ctr["mc"].get(f"resultMC{pump_id}", False)
                # local test
                # error = True
                # overload = False
                # mc = True
                
                if switch: # 檢查(inv, overload)
                    if error: # fail
                        op_logger.info(f"Failed to activate due to Inverter{pump_id} error.")
                        return False,{
                            "message": f"Failed to activate due to Inverter{pump_id} error.",
                        } 
                    elif overload:
                        op_logger.info(f"Failed to activate due to Inverter{pump_id} overload.")
                        return False,{
                            "message": f"Failed to activate due to Inverter{pump_id} overload.",
                        } 
                    elif not mc:
                        op_logger.info(f"Failed to activate due to Inverter MC{pump_id}.")
                        return False,{
                            "message": f"Failed to activate due to Inverter MC{pump_id}.",
                        } 
                    else: # success
                        set_p_check(pump_id - 1, [switch])
                        op_logger.info(f"switch{pump_id} updated successfully. switch{pump_id}{switch}")
                elif switch is None:
                        read_data = client.read_coils((8192 + 820 + pump_id - 1), 1, unit=modbus_slave_id)
                        switch = read_data.bits[0]
                        result[f"pump{pump_id}_switch"] = switch
                else: # 0
                    set_p_check(pump_id- 1, [switch])    
                    op_logger.info(f"switch{pump_id} updated successfully. switch{pump_id}{switch}") 
            
                # pump_speed存入
                if pump_speed > 0:
                        set_ps(pump_speed)
                        op_logger.info(f"pump{pump_id} speed updated successfully. pump speed {pump_speed}")
                else:
                    set_ps(0)
                    op_logger.info(f"pump{pump_id} speed updated successfully. pump speed {pump_speed}")
            return True, result

    except Exception as e:
        print(f"write pump speed error: {e}")
        return False, plc_error()
   
# set fan speed & switch
def set_fan_speed():
    data = api.payload
    fan_speed = data.get("fan_speed")
    fan1_switch = data.get("fan1_switch")
    fan2_switch = data.get("fan2_switch")
    fan3_switch = data.get("fan3_switch")
    fan4_switch = data.get("fan4_switch")
    fan5_switch = data.get("fan5_switch")
    fan6_switch = data.get("fan6_switch")
    fan7_switch = data.get("fan7_switch")
    fan8_switch = data.get("fan8_switch")

    # 初始化回傳資料
    fan_switch_result = {
        "fan_speed": fan_speed,
        "fan1_switch": fan1_switch,
        "fan2_switch": fan2_switch,
        "fan3_switch": fan3_switch,
        "fan4_switch": fan4_switch,
        "fan5_switch": fan5_switch,
        "fan6_switch": fan6_switch,
        "fan7_switch": fan7_switch,
        "fan8_switch": fan8_switch
    }
    # 檢查輸入
    if not isinstance(fan_speed, (int, type(None))):
        return False, invalid_type()

    if not all(isinstance(x, (bool, type(None))) for x in [fan1_switch, fan2_switch, fan3_switch, fan4_switch, fan5_switch, fan6_switch, fan7_switch, fan8_switch]):
        return False, invalid_type()
    
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port, unit=modbus_slave_id) as client:

            # fan_error1 = True
            # fan_error2 = False
            sensor = read_sensor_data()
            fan_error1 = sensor["error"].get("Fan_OverLoad1", False)
            fan_error2 = sensor["error"].get("Fan_OverLoad2", False)


            # 關閉錯誤範圍內的 switch
            if fan_error1:
                # fan1_switch = fan2_switch = fan3_switch = fan4_switch = False
                fan_switch_result["fan1_switch"] = False
                fan_switch_result["fan2_switch"] = False
                fan_switch_result["fan3_switch"] = False
                fan_switch_result["fan4_switch"] = False
            if fan_error2:
                # fan5_switch = fan6_switch = fan7_switch = fan8_switch = False
                fan_switch_result["fan5_switch"] = False
                fan_switch_result["fan6_switch"] = False
                fan_switch_result["fan7_switch"] = False
                fan_switch_result["fan8_switch"] = False    
                
            # 設定 switch
            for num in range(8):
                key = f"fan{num + 1}_switch"
                switch = fan_switch_result.get(key)
                # 判斷switch有無更改
                if switch is None:
                    read_data = client.read_coils((8192 + 850 + num), 1, unit=modbus_slave_id)
                    switch = read_data.bits[0]
                    fan_switch_result[f"fan{num + 1}_switch"] = switch
                else:    
                    num_test = num + 1 if num >= 3 else num
                    set_fan_switch(num_test, [switch])
                    op_logger.info(f"Fan switch{num + 1} updated successfully: {switch}")
            # 判斷fan_speed有無更改
            if fan_speed is None:
                read_data = client.read_holding_registers(470, 2)
                fan_speed = cvt_registers_to_float(read_data.registers[0], read_data.registers[1])
                fan_switch_result["fan_speed"] = fan_speed
            else: 
                if not (15 <= fan_speed <= 100 or fan_speed == 0):
                    return False, {
                        "message": "Invalid fan speed. Accepted values are 15-100 or 0."
                    }  
                   
                set_fan(fan_speed)
                # fan_set["fan_set"] = fan_speed
                op_logger.info(f"Fan speed updated successfully: {fan_speed}")

            
            return True, fan_switch_result

    except Exception as e:
        print(f"write fan_set: {e}")
        return False, plc_error()

   

def set_p_check(num, p_check):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 820 + num), p_check)
    except Exception as e:
        print(f"Pump speed setting error:{e}")


def set_ps(speed):
    speed1, speed2 = cvt_float_byte(speed)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(246, [speed2, speed1])
    except Exception as e:
        print(f"pump speed setting error:{e}")


def set_fan(speed):
    speed1, speed2 = cvt_float_byte(speed)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(470, [speed2, speed1])
    except Exception as e:
        print(f"pump speed setting error:{e}")

def set_fan_switch(num, fan_switch):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 850 + num), fan_switch)
    except Exception as e:
        print(f"Pump speed setting error:{e}")            


def set_swap(swap):
    swap1, swap2 = cvt_float_byte(swap)
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(303, [swap2, swap1])
    except Exception as e:
        print(f"pump swap setting error:{e}")


def combine_bits(lower, upper):
    value = (upper << 16) | lower
    return value


def read_split_register(r, i):
    lower_16 = r[i]
    upper_16 = r[i + 1]
    value = combine_bits(lower_16, upper_16)
    return value


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


def read_data_from_json():
    global thrshd, ctr_data, measure_data, fw_info, sensor_data

    with open(f"{json_path}/thrshd.json", "r") as file:
        thrshd = json.load(file)

    with open(f"{json_path}/ctr_data.json", "r") as file:
        ctr_data = json.load(file)

    with open(f"{json_path}/measure_data.json", "r") as file:
        measure_data = json.load(file)

    with open(f"{web_path}/fw_info.json", "r") as file:
        fw_info = json.load(file)
        
    with open(f"{json_path}/sensor_data.json", "r") as file:
        sensor_data = json.load(file)

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
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            last_unit = client.read_coils((8192 + 501), 1, unit=modbus_slave_id)
            current_unit = client.read_coils((8192 + 500), 1, unit=modbus_slave_id)
            client.close()

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

            if current_unit and current_unit != last_unit:
                change_to_imperial()
            elif not current_unit and current_unit != last_unit:
                change_to_metric()

            client.write_coils((8192 + 501), [current_unit])

            client.close()

    except Exception as e:
        print(f"unit set error:{e}")


def read_ctr_data():
    try:
        with open(f"{json_path}/ctr_data.json", "r") as json_file:
            data = json.load(json_file)
            return data

    except Exception as e:
        print(f"read ctr_data error: {e}")
        return plc_error()


def read_sensor_data():
    try:
        with open(f"{json_path}/sensor_data.json", "r") as json_file:
            data = json.load(json_file)
            return data

    except Exception as e:
        print(f"read sensor_data error: {e}")
        return plc_error()


def read_unit():
    try:
        with open(f"{json_path}/system_data.json", "r") as json_file:
            data = json.load(json_file)
            unit = data["value"]["unit"]
            return unit
    except Exception as e:
        print(f"read unit error: {e}")
        return plc_error()


def plc_error():
    return {"message": "PLC Communication Error"}, 500


def invalid_type():
    return {"message": "Invalid input type"}, 400

@default_ns.route("/cdu")
class CDU(Resource):
    @default_ns.doc("get_cdu_information")
    def get(self):
        """Get the cdu information"""
        read_data_from_json()
        physical_asset["Model"] = fw_info["Model"]
        physical_asset["Version"] = fw_info["Version"]
        physical_asset["SerialNumber"] = fw_info["SN"]
        physical_asset["PartNumber"] = fw_info["PartNumber"]
        physical_asset["OperationMode"] = ctr_data["value"]["opMod"]
        physical_asset["CDUStatus"] = sensor_data["cdu_status"]

        return physical_asset
# set fan speed
@default_ns.route("/cdu/control/fan_speed")
class FanSpeed(Resource):
    @default_ns.doc("get_fan_speed")
    def get(self):
        """Get fan setting"""
        try:
            ctr = read_ctr_data()
            fan_set["fan_set"] = round(ctr["value"]["resultFan"])
        except Exception as e:
            print(f"read pressure_set: {e}")
            return plc_error()

        return fan_set

    @default_ns.expect(fan_speed_model)
    @default_ns.doc("patch_fan_set")
    def patch(self):
        """Update fan setting"""
        try:
            fan = api.payload["fan_speed"]
            if not isinstance(fan, int):
                return invalid_type()

            sensor = read_sensor_data()
            ctr = read_ctr_data()
            fan_error1 = sensor["error"]["Fan_OverLoad1"]
            fan_error2 = sensor["error"]["Fan_OverLoad2"]
            current_mode = ctr["value"]["resultMode"]

            if current_mode in ["Stop", "Auto"]:
                return (
                    {"message": "Fan speed can only be adjusted in manual mode."},
                ), 400

            if not (15 <= fan <= 100 or fan == 0):
                return {
                    "message": "Invalid fan speed. Accepted values are 15-100 or 0."
                }, 400
            elif fan_error1 or fan_error2:
                word = ""
                if fan_error1 and fan_error2:
                    word = "fan1 and fan2"
                elif fan_error1:
                    word = "fan1"
                elif fan_error2:
                    word = "fan2"

                return {
                    "message": f"Unable to set the malfunctioning {word} due to overload error."
                }, 400
            else:
                set_fan(fan)
                fan_set["fan_set"] = fan

        except Exception as e:
            print(f"write fan_set: {e}")
            return plc_error()

        op_logger.info(f"Fan update successfully. {fan_set}")
        return {
            "message": "Fan updated successfully",
            "new_fan_set": fan_set["fan_set"],
        }, 200


# set prsr
@default_ns.route("/cdu/control/pressure_set")
class PressureSet(Resource):
    @default_ns.expect(pressure_set_model)
    @default_ns.doc("patch_pressure_set")
    def patch(self):
        """Update pressure setting: 0-750 kpa (0-108.75 psi)"""
        prsr = api.payload.get("pressure_set")
        try:
            ctr = read_ctr_data()
            current_mode = ctr["value"]["resultMode"]

            if not isinstance(prsr, (int, float)):
                return False, invalid_type()

            if current_mode in ["Stop", "Manual"]:
                return False, ("Pressure can only be adjusted in auto mode.", 400)
            else:
                success, result = set_pressure_value()

            if success:                
                op_logger.info(f"Pressure update successfully. {result}")
                return {
                    "message": "Pressure updated successfully",
                    "new_pressure_set": result
                }, 200
                
            else:
                return {"message": result}, 400
        

                
        except Exception as e:
            print(f"temp_set_limit: {e}")
            return plc_error()


@default_ns.route("/cdu/control/pump_speed")
class PumpSpeed(Resource):
    @default_ns.doc("get_pump_speed")
    def get(self):
        """Get the current pump speeds"""

        try:
            data = read_ctr_data()
            pump_speed_set["pump_speed"] =  data["value"]["pump_speed"]
            pump_speed_set["pump1_speed"] = (
                data["value"]["resultPS"] if data["value"]["resultP1"] else 0
            )
            pump_speed_set["pump2_speed"] = (
                data["value"]["resultPS"] if data["value"]["resultP2"] else 0
            )
            pump_speed_set["pump3_speed"] = (
                data["value"]["resultPS"] if data["value"]["resultP3"] else 0
            )
        except Exception as e:
            print(f"get pump speed error:{e}")
            return plc_error()

        return pump_speed_set


@default_ns.route("/cdu/control/pump1_speed")
class Pump1Speed(Resource):
    @default_ns.expect(pump1_speed_model)
    @default_ns.doc("update_pump_speed")
    def patch(self):
        """Update the pump speeds in percentage(0-100) in manual mode"""

        try:
            ps = api.payload["pump_speed"]
            p1 = api.payload["pump_switch"]

            if not isinstance(ps, (int)):
                return invalid_type()

            if not isinstance(p1, (bool)):
                return invalid_type()

            sensor = read_sensor_data()
            ctr = read_ctr_data()

            current_mode = ctr["value"]["resultMode"]
            error1 = sensor["error"]["Inv1_Error"]
            ol1 = sensor["error"]["Inv1_OverLoad"]
            mc1 = ctr["mc"]["resultMC1"]
            # current_mode = "manual"
            # error1 = False
            # ol1 = False
            # mc1 = True
            if current_mode in ["Stop", "Auto"]:
                return (
                    {"message": "Pump speed can only be adjusted in manual mode."},
                ), 400

            if 0 < ps < 25 or ps > 100:
                return (
                    {
                        "message": "Invalid pump speed input. Accepted values are 25-100 or 0."
                    },
                ), 400

            if ps == 0:
                pump_speed_set["pump1_speed"] = 0
            elif ps > 0:
                if p1:
                    if error1 or ol1 or not mc1:
                        pump_speed_set["pump1_speed"] = 0
                        filter_data = {}
                        filter_data = pump_speed_set.copy()
                        exclude_key = ["pump2_speed", "pump3_speed"]
                        for key in exclude_key:
                            filter_data.pop(key, None)
                        op_logger.info(
                            f"Failed to activate pump1 due to error, overload or closed MC. {filter_data}"
                        )
                        return {
                            "message": "Failed to activate pump1 due to error, overload or closed MC.",
                            "pump_speed": filter_data,
                        }, 400
                    else:
                        pump_speed_set["pump1_speed"] = ps
                else:
                    pump_speed_set["pump1_speed"] = 0
        except Exception as e:
            print(f"write pump speed: {e}")
            return plc_error()

        set_ps(ps)
        set_p_check(0, [p1])


        filter_data = {}
        filter_data = pump_speed_set.copy()
        exclude_key = ["pump2_speed", "pump3_speed"]
        for key in exclude_key:
            filter_data.pop(key, None)

        op_logger.info(f"Pump1 speed updated successfully. pump speed {filter_data}")
        return {
            "message": "Pump1 speed updated successfully",
            "pump_speed": filter_data,
        }, 200


@default_ns.route("/cdu/control/pump2_speed")
class Pump2Speed(Resource):
    @default_ns.expect(pump2_speed_model)
    @default_ns.doc("update_pump_speed")
    def patch(self):
        """Update the pump speeds in percentage(0-100) in manual mode"""

        try:
            ps = api.payload["pump_speed"]
            p2 = api.payload["pump_switch"]

            if not isinstance(ps, (int)):
                return invalid_type()

            if not isinstance(p2, (bool)):
                return invalid_type()

            sensor = read_sensor_data()
            ctr = read_ctr_data()

            current_mode = ctr["value"]["resultMode"]
            error2 = sensor["error"]["Inv2_Error"]
            ol2 = sensor["error"]["Inv2_OverLoad"]
            mc2 = ctr["mc"]["resultMC2"]

            if current_mode in ["Stop", "Auto"]:
                return "Pump speed can only be adjusted in manual mode.", 400

            if 0 < ps < 25 or ps > 100:
                return (
                    {
                        "message": "Invalid pump speed input. Accepted values are 25-100 or 0."
                    },
                ), 400

            if ps == 0:
                pump_speed_set["pump2_speed"] = 0
            elif ps > 0:
                if p2:
                    if error2 or ol2 or not mc2:
                        pump_speed_set["pump2_speed"] = 0

                        filter_data = {}
                        filter_data = pump_speed_set.copy()
                        exclude_key = ["pump1_speed", "pump3_speed"]
                        for key in exclude_key:
                            filter_data.pop(key, None)

                        op_logger.info(
                            f"Failed to activate pump2 due to error, overload or closed MC. {filter_data}"
                        )
                        return {
                            "message": "Failed to activate pump2 due to error, overload or closed MC.",
                            "pump_speed": filter_data,
                        }, 400
                    else:
                        pump_speed_set["pump2_speed"] = ps
                else:
                    pump_speed_set["pump2_speed"] = 0

        except Exception as e:
            print(f"write pump speed: {e}")
            return plc_error()

        set_ps(ps)
        set_p_check(1, [p2])

        filter_data = {}
        filter_data = pump_speed_set.copy()
        exclude_key = ["pump1_speed", "pump3_speed"]
        for key in exclude_key:
            filter_data.pop(key, None)

        op_logger.info(f"Pump2 speed updated successfully. pump speed {filter_data}")
        return {
            "message": "Pump2 speed updated successfully",
            "pump_speed": filter_data,
        }, 200


@default_ns.route("/cdu/control/pump3_speed")
class Pump3Speed(Resource):
    @default_ns.expect(pump3_speed_model)
    @default_ns.doc("update_pump_speed")
    def patch(self):
        """Update the pump speeds in percentage(0-100) in manual mode"""

        try:
            ps = api.payload["pump_speed"]
            p3 = api.payload["pump_switch"]

            if not isinstance(ps, (int)):
                return invalid_type()

            if not isinstance(p3, (bool)):
                return invalid_type()

            sensor = read_sensor_data()
            ctr = read_ctr_data()

            current_mode = ctr["value"]["resultMode"]
            error3 = sensor["error"]["Inv3_Error"]
            ol3 = sensor["error"]["Inv3_OverLoad"]
            mc3 = ctr["mc"]["resultMC3"]

            if current_mode in ["Stop", "Auto"]:
                return "Pump speed can only be adjusted in manual mode.", 400

            if 0 < ps < 25 or ps > 100:
                return (
                    {
                        "message": "Invalid pump speed input. Accepted values are 25-100 or 0."
                    },
                ), 400

            if ps == 0:
                pump_speed_set["pump3_speed"] = 0
            elif ps > 0:
                if p3:
                    if error3 or ol3 or not mc3:
                        pump_speed_set["pump3_speed"] = 0
                        filter_data = {}
                        filter_data = pump_speed_set.copy()
                        exclude_key = ["pump1_speed", "pump2_speed"]
                        for key in exclude_key:
                            filter_data.pop(key, None)
                        op_logger.info(
                            f"Failed to activate pump3 due to error, overload or closed MC. {filter_data}"
                        )
                        return {
                            "message": "Failed to activate pump3 due to error, overload or closed MC.",
                            "pump_speed": filter_data,
                        }, 400
                    else:
                        pump_speed_set["pump3_speed"] = ps
                else:
                    pump_speed_set["pump3_speed"] = 0
        except Exception as e:
            print(f"write pump speed: {e}")
            return plc_error()

        set_ps(ps)
        set_p_check(2, [p3])

        filter_data = {}
        filter_data = pump_speed_set.copy()
        exclude_key = ["pump1_speed", "pump2_speed"]
        for key in exclude_key:
            filter_data.pop(key, None)

        op_logger.info(f"Pump3 speed updated successfully. pump speed {filter_data}")
        return {
            "message": "Pump3 speed updated successfully",
            "pump_speed": filter_data,
        }, 200

# set pump swap time
@default_ns.route("/cdu/control/pump_swap_time")
class PumpSwapTime(Resource):
    @default_ns.doc("get_pump_swap_time")
    def get(self):
        """Get the time interval for pump swapping in minutes"""
        try:
            data = read_ctr_data()
            pump_swap_time = {"pump_swap_time": data["value"]["resultSwap"]}
        except Exception as e:
            print(f"pump swap time error:{e}")
            return plc_error()

        return pump_swap_time

    @default_ns.expect(pump_swap_time_model)
    @default_ns.doc("update_pump_swap_time")
    def patch(self):
        """Update the time interval for pump swapping in minutes"""
        new_time = api.payload.get("pump_swap_time")
        
        ctr = read_ctr_data()
        current_mode = ctr["value"]["resultMode"]

        if not isinstance(new_time, int):
            return False, invalid_type()

        if current_mode in ["Stop", "Manual"]:
            return False, ("Pump swap time can only be adjusted in auto mode.", 400)
        else:
            success, result = set_pump_swap_time()

        if  success:
            op_logger.info(f"Pump swap time updated successfully. {result}")
            return {
                "message": "Pump swap time updated successfully",
                "new_pump_swap_time": result
            }, 200
        else:
            return {"message": result}, 400


# set temp
@default_ns.route("/cdu/control/temp_set")
class TempSet(Resource):

    @default_ns.expect(temp_set_model)
    @default_ns.doc("patch_temp_set")
    def patch(self):
        try:
            ctr = read_ctr_data()
            current_mode = ctr["value"]["resultMode"]
            temp = api.payload["temp_set"]
            # current_mode = "auto"
            if not isinstance(temp, int):
                return False, "Invalid type. Temperature must be integer."

            if current_mode in ["Stop", "Manual"]:
                return False, "Temperature can only be adjusted in auto mode."
            
            else:
                success, result = set_temperature()
                temp_set["temp_set"] = temp

            if success:
                op_logger.info(f"Temperature updated successfully.{temp_set}")
                return {
                    "message": "Temperature updated successfully",
                    "new_temp_set": temp_set["temp_set"],
                }, 200
            else:
                return {"message": result}, 400

        except Exception as e:
            print(f"temp_set_limit: {e}")
            return plc_error()


@default_ns.route("/cdu/status/fan_speed")
class fan_speed(Resource):
    @default_ns.doc("get_fan_speed")
    def get(self):
        """Get speed of fans"""
        try:
            sensor = read_sensor_data()

            for k, v in sensor["value"].items():
                if k.startswith("fan_freq"):
                    i = k[-1]
                    fan_key = f"fan{i}_speed"
                    data["fan_speed"][fan_key] = round(v)
        except Exception as e:
            print(f"fan speed error:{e}")
            return plc_error()

        return data["fan_speed"]


@default_ns.route("/cdu/status/op_mode")
class CduOpMode(Resource): 
    @default_ns.doc("get_op_mode")
    def get(self):
        """Get the current operational mode stop, auto, or manual"""
        try:
            data = read_ctr_data()
            op_mode["mode"] = data["value"]["opMod"]    
            mode = data["value"]["resultMode"].lower()
            temp_set=data["value"]["oil_temp_set"]
            pressure_set=data["value"]["oil_pressure_set"]
            pump_swap_time=data["value"]["resultSwap"]
            if mode == "stop":
                return {"mode": mode} 
            elif mode == "auto":
                return {"mode": mode,"temp_set": temp_set,
                        "pressure_set": pressure_set,
                        "pump_swap_time": pump_swap_time }
                
            elif mode == "manual":
                pump_speed = data["value"]["pump_speed"]
                pump1_switch = data["value"]["resultP1"]
                pump2_switch = data["value"]["resultP2"]
                pump3_switch = data["value"]["resultP3"]
                fan_speed = data["value"]["fan_speed"]
                fan1_switch= data["value"]["resultFan1"]
                fan2_switch= data["value"]["resultFan2"]
                fan3_switch= data["value"]["resultFan3"]
                fan4_switch= data["value"]["resultFan4"]
                fan5_switch= data["value"]["resultFan5"]
                fan6_switch= data["value"]["resultFan6"]
                fan7_switch= data["value"]["resultFan7"]
                fan8_switch= data["value"]["resultFan8"]
                return {"mode": mode ,"pump_speed":pump_speed,
                        "pump1_switch":pump1_switch,
                        "pump2_switch": pump2_switch,
                        "pump3_switch": pump3_switch,
                        "fan_speed": fan_speed,
                        "fan1_switch": fan1_switch,
                        "fan2_switch": fan2_switch,
                        "fan3_switch": fan3_switch,
                        "fan4_switch": fan4_switch,
                        "fan5_switch": fan5_switch,
                        "fan6_switch": fan6_switch,
                        "fan7_switch": fan7_switch,
                        "fan8_switch": fan8_switch, }
            else:
                return plc_error()
                
                
        except Exception as e:
            print(f"get mode error: {e}")
            return plc_error()


    @default_ns.expect(op_mode_model)
    @default_ns.doc("set_op_mode")
    def patch(self):
        """Set the operational mode auto, stop, or manual"""

        try:
            # 引入資料
            mode = api.payload["mode"]

            if mode not in ["auto", "stop", "manual"]:
                return {
                    "message": "Invalid operational mode. The allowed values are ‘auto’, ‘stop’, and ‘manual’."
                }, 400

            with ModbusTcpClient(port=modbus_port, host=modbus_host) as client:
                if mode == "stop":
                    client.write_coils((8192 + 514), [False])
                    op_logger.info(f"mode updated successfully {mode}")
                    return {
                        "message": "mode updated successfully",
                        "new_mode": mode
                    }, 200
                elif mode == "manual":
                    client.write_coils((8192 + 505), [True])
                    client.write_coils((8192 + 514), [True])
                    client.write_coils((8192 + 516), [False])
                    # pump & fan設定
                    pump_success, pump_result = set_pump_speed()
                    fan_success, fan_result = set_fan_speed()
                    # pump & fan錯誤判斷
                    if not pump_success:
                        return {
                            "message": pump_result
                        }, 400
                    if not fan_success:   
                        return {
                            "message": fan_result
                        }, 400                    
                        
                    op_logger.info(f"mode updated successfully {mode}")
                    return {
                        "message": "mode updated successfully",
                        "new_mode": mode,
                        "pump_speed": pump_result["pump_speed"],
                        "pump1_switch": pump_result["pump1_switch"],
                        "pump2_switch": pump_result["pump2_switch"],
                        "pump3_switch": pump_result["pump3_switch"],
                        "fan_speed": fan_result["fan_speed"],
                        "fan1_switch": fan_result["fan1_switch"],
                        "fan2_switch": fan_result["fan2_switch"],
                        "fan3_switch": fan_result["fan3_switch"],
                        "fan4_switch": fan_result["fan4_switch"],
                        "fan5_switch": fan_result["fan5_switch"],
                        "fan6_switch": fan_result["fan6_switch"],
                        "fan7_switch": fan_result["fan7_switch"],
                        "fan8_switch": fan_result["fan8_switch"],
                    }, 200
                else:
                    client.write_coils((8192 + 505), [False])
                    client.write_coils((8192 + 514), [True])
                    client.write_coils((8192 + 516), [False])
                    # temp, prsr, swap設定
                    temp_success, temp_set = set_temperature() 
                    prsr_success, pressure_set = set_pressure_value()
                    swap_success, pump_swap_time = set_pump_swap_time()
                    # temp, prsr, swap錯誤判斷 
                    if not(temp_success): 
                        return {
                            "message": temp_set
                        }, 400
                    if not(prsr_success): 
                        return {
                            "message": pressure_set
                        }, 400
                    if not(swap_success): 
                        return {
                            "message": pump_swap_time
                        }, 400
                    
                    
                    op_logger.info(f"mode updated successfully {mode}")
                    return {
                        "message": "mode updated successfully",
                        "new_mode": mode,
                        "temp_set": temp_set,
                        "pressure_set": pressure_set,
                        "pump_swap_time": pump_swap_time
                    }, 200
                    
                    
                
        except Exception as e:
            print(f"write mode error:{e}")
            return plc_error()


@default_ns.route("/cdu/status/pump_health")
class pump_health(Resource):
    @default_ns.doc("get_pump_health")
    def get(self):
        """Get health of pumps"""
        try:
            sensor = read_sensor_data()

            data["pump_health"]["pump1_health"] = (
                "Overload"
                if sensor["error"]["Inv1_OverLoad"]
                else "Error"
                if sensor["error"]["Inv1_Error"]
                else "OK"
            )
            data["pump_health"]["pump2_health"] = (
                "Overload"
                if sensor["error"]["Inv2_OverLoad"]
                else "Error"
                if sensor["error"]["Inv2_Error"]
                else "OK"
            )
            data["pump_health"]["pump3_health"] = (
                "Overload"
                if sensor["error"]["Inv3_OverLoad"]
                else "Error"
                if sensor["error"]["Inv3_Error"]
                else "OK"
            )

        except Exception as e:
            print(f"pump health error:{e}")
            return plc_error()

        return data["pump_health"]


@default_ns.route("/cdu/status/pump_service_hours")
class pump_Service_hours(Resource):
    @default_ns.doc("get_pump_service_hours")
    def get(self):
        """Get service hours of pumps"""
        try:
            ctr = read_ctr_data()

            data["pump_service_hours"]["pump1_service_hours"] = ctr["text"][
                "Pump1_run_time"
            ]
            data["pump_service_hours"]["pump2_service_hours"] = ctr["text"][
                "Pump2_run_time"
            ]
            data["pump_service_hours"]["pump3_service_hours"] = ctr["text"][
                "Pump3_run_time"
            ]
        except Exception as e:
            print(f"pump speed time error:{e}")
            return plc_error()

        return data["pump_service_hours"]


@default_ns.route("/cdu/status/pump_speed")
class pump_speed(Resource):
    @default_ns.doc("get_pump_status")
    def get(self):
        """Get speed of pumps"""
        try:
            sensor = read_sensor_data()
            data["pump_speed"]["pump1_speed"] = round(sensor["value"]["inv1_freq"])
            data["pump_speed"]["pump2_speed"] = round(sensor["value"]["inv2_freq"])
            data["pump_speed"]["pump3_speed"] = round(sensor["value"]["inv3_freq"])
        except Exception as e:
            print(f"pump speed error:{e}")
            return plc_error()

        return data["pump_speed"]


@default_ns.route("/cdu/status/pump_state")
class pump_state(Resource):
    @default_ns.doc("get_pump_state")
    def get(self):
        """Get state of pumps"""
        try:
            sensor = read_sensor_data()
            data["pump_state"]["pump1_state"] = (
                "Enable" if round(sensor["value"]["inv1_freq"]) >= 25 else "Disable"
            )
            data["pump_state"]["pump2_state"] = (
                "Enable" if round(sensor["value"]["inv2_freq"]) >= 25 else "Disable"
            )
            data["pump_state"]["pump3_state"] = (
                "Enable" if round(sensor["value"]["inv3_freq"]) >= 25 else "Disable"
            )
        except Exception as e:
            print(f"pump speed error:{e}")
            return plc_error()

        return data["pump_state"]


sensor_mapping = {
    "temp_clntSply": "temp_coolant_supply",
    "temp_clntSplySpare": " temp_coolant_supply_spare",
    "temp_clntRtn": "temp_coolant_return",
    "temp_clntRtnSpare": "temp_coolant_return_spare",
    "prsr_clntSply": "pressure_coolant_supply",
    "prsr_clntSplySpare": "pressure_coolant_supply_spare",
    "prsr_clntRtn": "pressure_coolant_return",
    "prsr_clntRtnSpare": "pressure_coolant_return_spare",
    "prsr_fltIn": "pressure_filter_in",
    "prsr_fltOut": "pressure_filter_out",
    "clnt_flow": "coolant_flow_rate",
    "ambient_temp": "temperature_ambient",
    "relative_humid": "humidity_relative",
    "dew_point": "temperature_dew_point",
    "pH": "ph_level",
    "cdct": "conductivity",
    "tbd": "turbidity",
    "power": "power_total",
    "AC": "cooling_capacity",
    "inv1_freq": "pump1_speed",
    "inv2_freq": "pump2_speed",
    "inv3_freq": "pump3_speed",
    "heat_capacity": "heat_capacity",
    "fan_freq1": "fan1_speed",
    "fan_freq2": "fan2_speed",
    "fan_freq3": "fan3_speed",
    "fan_freq4": "fan4_speed",
    "fan_freq5": "fan5_speed",
    "fan_freq6": "fan6_speed",
    "fan_freq7": "fan7_speed",
    "fan_freq8": "fan8_speed",  
}

@default_ns.route("/cdu/status/sensor_value")
class CduSensorValue(Resource):
    @default_ns.doc("get_sensor_value")
    def get(self):
        """Get the current sensor values of CDU"""
        try:
            sensor = read_sensor_data()
            for key in data["sensor_value"]:
                if key != "clnt_flow":
                    data["sensor_value"][key] = round(sensor["value"][key], 2)
                else:
                    data["sensor_value"][key] = round(sensor["value"][key])
        except Exception as e:
            print(f"get mode error: {e}")
            return plc_error()

        exclude_keys = ["inv1_freq", "inv2_freq", "inv3_freq", "fan_freq"]
        filter_data = {}
        filter_data = data["sensor_value"].copy()

        for key in exclude_keys:
            filter_data.pop(key, None)
        result = {sensor_mapping[key]: value for key, value in filter_data.items()}
        return result
@default_ns.route("/cdu/status/device")
class CduDevice(Resource):
    @default_ns.doc("get_device")
    def get(self):
        """Get the current device values of CDU"""
        try:
            with open(f"{json_path}/scc_device.json", "r") as file:
                device = json.load(file)
        except Exception as e:
            return plc_error()
           
        return device


@default_ns.route("/error_messages")
class ErrorMessages(Resource):
    @default_ns.doc("get_error_messages")
    def get(self):
        """Get the list of error messages happening in the system"""

        try:
            sensor = read_sensor_data()
            error_messages = []
            for category in ["warning", "alert", "error", "rack"]:
                for key, status in sensor[category].items():
                    if status:
                        msg = sensor["err_log"][category][key].split(" ", 1)
                        code = msg[0]
                        messages = msg[1]
                        error_messages.append({"error_code": code, "message": messages})
        # error_messages = []
        # for category in ["warning", "alert", "error", "rack"]:
        #     for code, message in messages[category].items():
        #         if message[1]:
        #             error_messages.append({"error_code": code, "message": message[0]})
        except Exception as e:
            return plc_error()
        return error_messages


@default_ns.route("/unit_set")
class Unit(Resource):
    @default_ns.doc("get_unit_set")
    def get(self):
        """Get the current unit setting"""
        try:
            unit = read_unit()
            unit_set["unit"] = unit
        except Exception as e:
            print(f"unit set error:{e}")
            return plc_error()

        return unit_set

    @default_ns.expect(unit_set_model)
    @default_ns.doc("update_unit_set")
    def patch(self):
        """Update the unit setting to metric or imperial"""

        try:
            unit = api.payload["unit_set"].lower()
            if unit not in ["metric", "imperial"]:
                return {
                    "message": "Invalid unit. The unit must be either 'metric' or 'imperial'."
                }, 400
            else:
                unit_set["unit"] = unit
                coil_value = True if unit == "imperial" else False

                with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                    client.write_coil(address=(8192 + 500), value=coil_value)
                change_data_by_unit()
        except Exception as e:
            print(f"write unit: {e}")
            return plc_error()

        op_logger.info(f"Unit updated successfully {unit_set}")
        return {
            "message": "Unit updated successfully",
            "new_unit": unit_set["unit"],
        }, 200

# 設定 reqparse 處理檔案上傳
upload_parser = reqparse.RequestParser()
upload_parser.add_argument("file", location="files", required=True, help="請上傳 ZIP 檔案")

# 目標 API 端點
TARGET_SERVERS = {
    "upload/main/service.zip": "http://192.168.3.100:5501/api/v1/upload_zip",
    "upload/spare/service.zip": "http://192.168.3.101:5501/api/v1/upload_zip",
}

# 定義上傳 API
@default_ns.route("/update_firmware")
#curl -X POST "http://127.0.0.1:5001/api/v1/update_firmware" -F "file=@/path/to/upload.zip"
class UploadZipFile(Resource):
    @default_ns.expect(upload_parser)
    def post(self):
        """上傳 ZIP 並分發到目標伺服器"""
        args = upload_parser.parse_args()
        file = request.files.get("file")    
        superuser_password =  os.getenv("SUPERUSER")

        # 驗證檔案是否存在
        if not file:
            op_logger.info("No file part in the request")
            return {"message": "No File Part"}, 400
        if file.filename == "":
            op_logger.info("No file selected for upload")
            return {"message": "No File Selected"}, 400
        # if file.filename != "upload.zip":
        #     return {"message": "Please upload correct file name"}, 400
        # if not file.filename.endswith(".zip"):
        if not file.filename.endswith(".gpg"):  
            op_logger.info("Wrong file type uploaded")
            return {"message": "Wrong File Type"}, 400

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
        #     return {"message": "Invalid ZIP file"}, 400
        
        
        zip_password = "Itgs50848614"
        try:
            with pyzipper.AESZipFile(local_zip_path, "r", encryption=pyzipper.WZ_AES) as zip_ref:

                # 檢查每個檔案是否加密
                if not any(info.flag_bits & 0x1 for info in zip_ref.infolist()):
                    os.remove(local_zip_path)  # 清理未通過檢查的 zip
                    op_logger.info("ZIP file is not password-protected")
                    return {"message": "ZIP file must be password-protected"}, 400

                zip_ref.setpassword(zip_password.encode())

                try:
                    namelist = zip_ref.namelist()
                    if not namelist:
                        os.remove(local_zip_path)
                        op_logger.info("ZIP file is empty")
                        return {"status": "error", "message": "ZIP file is empty"}, 400

                    # 嘗試讀取第一個檔案驗證密碼
                    zip_ref.read(namelist[0])
                except RuntimeError:
                    os.remove(local_zip_path)
                    op_logger.info("Invalid password for ZIP file")
                    return {"status": "error", "message": "Invalid password"}, 400
                    
                zip_ref.extractall(temp_dir)

        except RuntimeError:
            os.remove(local_zip_path)
            op_logger.info("Wrong password or corrupt zip")
            return {"message": "Wrong password or corrupt zip"}, 400

        except pyzipper.BadZipFile:
            os.remove(local_zip_path)
            op_logger.info("Invalid ZIP file")
            return {"message": "Invalid ZIP file"}, 400


        upload_results = {}

        # 上傳解壓縮的 ZIP 檔案到不同伺服器
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

        try:
            # 發送 GET 請求到該 API
            response = requests.get("http://192.168.3.101/api/v1/reboot", auth=("superuser", superuser_password), verify=False)

            # 檢查回應狀態
            if response.status_code == 200:
                print("System reboot initiated successfully.")
            else:
                print(f"Failed to initiate reboot. Status code: {response.status_code}")

        except requests.RequestException as e:
            print(f"An error occurred: {e}")
        time.sleep(3)
        try:
            # 發送 GET 請求到該 API
            response = requests.get("http://192.168.3.100/api/v1/reboot", auth=("superuser", superuser_password), verify=False)

            # 檢查回應狀態
            if response.status_code == 200:
                print("System reboot initiated successfully.")
            else:
                print(f"Failed to initiate reboot. Status code: {response.status_code}")

        except requests.RequestException as e:
            op_logger.info(f"An error occurred: {e}")
            print(f"An error occurred: {e}")  
             
        op_logger.info(f"Firmware upload completed.")      
        return {"message": "Upload Completed, Please Restart PC", "results": upload_results}, 200

# 0507新增
sensor_mapping_output = {
    "temp_clntSply": "temp_coolant_supply",
    "temp_clntSplySpare": "temp_coolant_supply_spare",
    "temp_clntRtn": "temp_coolant_return",
    "temp_clntRtnSpare": "temp_coolant_return_spare",
    "prsr_clntSply": "pressure_coolant_supply",
    "prsr_clntSplySpare": "pressure_coolant_supply_spare",
    "prsr_clntRtn": "pressure_coolant_return",
    "prsr_clntRtnSpare": "pressure_coolant_return_spare",
    "prsr_fltIn": "pressure_filter_in",
    "prsr_fltOut": "pressure_filter_out",
    "clnt_flow": "coolant_flow_rate",
    "ambient_temp": "temperature_ambient",
    "relative_humid": "humidity_relative",
    "dew_point": "temperature_dew_point",
    "pH": "ph_level",
    "cdct": "conductivity",
    "tbd": "turbidity",
    "power": "power_total",
    "AC": "cooling_capacity",
    "heat_capacity": "heat_capacity",
    "power24v1": "power24v1",
    "power24v2": "power24v2",
    "power12v1": "power12v1",
    "power12v2": "power12v2"
}
def fan_health_judge(i, sensor):
    # fan health
    health = "OK"
    if sensor["error"][f"Fan{i}_Com"]:
        health = "Warning"
    if sensor["error"][f"fan{i}_error"]:
        health = "Critical"
    return health    

def fan_state_judge(i, sensor):
    # fan state
    if sensor["error"][f"fan{i}_error"] or sensor["error"][f"Fan{i}_Com"]:
        state = "Absent"
    elif sensor["value"][f"fan_freq{i}"]:
        state = "Enabled"
    else:
        state = "Disabled"    
    return state  

sensor_mapping_broken = {
    "temp_clntSply": "TempClntSply_broken",
    "temp_clntSplySpare": "TempClntSplySpare_broken",
    "temp_clntRtn": "TempClntRtn_broken",
    "temp_clntRtnSpare": "TempClntRtnSpare_broken",
    "prsr_clntSply": "PrsrClntSply_broken",
    "prsr_clntSplySpare": "PrsrClntSplySpare_broken",
    "prsr_clntRtn": "PrsrClntRtn_broken",
    "prsr_clntRtnSpare": "PrsrClntRtnSpare_broken",
    "prsr_fltIn": "PrsrFltIn_broken",
    "prsr_fltOut": "PrsrFltOut_broken",
    "clnt_flow": "Clnt_Flow_broken",
    "power24v1": "power24v1",
    "power24v2": "power24v2",
    "power12v1": "power12v1",
    "power12v2": "power12v2"
    # "AC": "cooling_capacity", # 沒有error
    # "heat_capacity": "heat_capacity", # 沒有error
}
sensor_mapping_com = {
    "ambient_temp": "Ambient_Temp_Com",
    "relative_humid": "Relative_Humid_Com",
    "dew_point": "Dew_Point_Com",
    "pH": "pH_Com",
    "cdct": "Cdct_Sensor_Com",
    "tbd": "Tbd_Com",
    "power": "Power_Meter_Com",
}
dis_reading = {
    "power24v1",
    "power24v2",
    "power12v1",
    "power12v2"
}
def state_judge(key, sensor, value):
    # all sensor state
    com_key   = sensor_mapping_com.get(key)
    broken_key = sensor_mapping_broken.get(key)
    
    if sensor["error"].get(com_key) or sensor["error"].get(broken_key):
        state = "Absent"
    elif value:
        state = "Enabled"
    else:
        state = "Disabled"    
    return state

def health_judge(key, sensor):
    # all sensor health
    com_key   = sensor_mapping_com.get(key)
    broken_key = sensor_mapping_broken.get(key)

    health = "OK"
    if com_key and sensor["error"].get(com_key):
        health = "Critical"
    if broken_key and sensor["error"].get(broken_key):
        health = "Critical"  
    return health

@default_ns.route("/cdu/components/chassis/summary")
class SensorsSummary(Resource):
    '''
    fan_count_switch true是6個風扇 false是8個風扇
    state: Enabled(啟用) Disabled(未啟用) Absent(斷線、壞掉)
    health: OK(正常) Warning(斷線) Critical(壞掉)
    reading: 風扇轉速
    '''
    @default_ns.doc("get_sensor_summary")
    def get(self):
        with open(f"{json_path}/version.json", "r") as file:
            version_josn = json.load(file)
        # 判斷幾顆風扇
        fan_count_switch = version_josn["fan_count_switch"]
        rep = {}
        try:
            sensor_data = read_sensor_data()
            sensor_value = sensor_data["value"]
            FAN_COUNT = 6 if version_josn["fan_count_switch"] else 8

            # 動態寫入 fan 數量
            for i in range(1, FAN_COUNT + 1):
                fan_key = f"fan{i}"
                # fan 數量判斷取值
                # if fan_count_switch == True and i >= 4:
                #     s = i + 1
                # else:
                #     s = i    
                fan_speed = round(sensor_value[f"fan_freq{i}"], 2)  
                rep[fan_key] = {
                    "status": {
                        "state":  fan_state_judge(i, sensor_data) ,
                        "health": fan_health_judge(i, sensor_data),
                    }, 
                    # hardware{}
                    "reading": fan_speed, 
                    "ServiceHours": -1,
                    "ServiceDate": -1,
                    "HardWareInfo":{}
                }
            # 加入其他sensor
            for key, value in sensor_mapping_output.items():
                sensor_value_get = sensor_value.get(key)
                if sensor_value_get != None:
                    # sensor_reading = round(sensor_value_get, 2) if key != "clnt_flow" else round(sensor_value_get)
                    sensor_reading = round(sensor_value_get, 2)
                # if key in dis_reading: sensor_reading = None
                if key not in rep:
                    rep[value] = {
                        "status": {
                            "state": state_judge(key, sensor_data, sensor_reading),
                            "health": health_judge(key, sensor_data),
                        },
                        "reading": sensor_reading,
                        "ServiceHours": -1,
                        "ServiceDate": -1,
                        "HardWareInfo":{}
                    }
            
        except Exception as e:
            print(f"get sensors data error:{e}")
            return plc_error()

        return  rep, 200
        
thermal_equipment = {
    "ambient_temp": "temperature_ambient",
    "relative_humid": "humidity_relative",
    "dew_point": "temperature_dew_point",    
    # "leakage1": "leak_deteceor"
}

def leak_judge(leak_broken, leak_leak):
    if leak_broken:
        health = "Critical"
        state = "Disabled"
    elif leak_leak:
        health = "Critical"    
        state = "Enabled"
    else:
        health = "OK"    
        state = "Enabled"  
          
    return  {
            "status": {
                "state": state,
                "health": health
            },
            "reading": None,
            "ServiceHours": -1,
            "ServiceDate": -1,
            "HardWareInfo":{}
        }    
    
    
'''
leak broken -> health:Critical state:Disable
leak leak -> health:warning state:Enable
'''
@default_ns.route("/cdu/components/thermal_equipment/summary")
class SensorsSummary(Resource):
    @default_ns.doc("get_thermal_equipment_summary")
    def get(self):
        rep = {}
        try:
            sensor_data = read_sensor_data()
            sensor_value = sensor_data["value"]
            leak_broken = sensor_data["error"]["leakage1_broken"]
            leak_leak = sensor_data["error"]["leakage1_leak"]

            sensor_rack = sensor_data["rack"]
            rack_leakage1_broken = sensor_rack["rack_leakage1_broken"]
            rack_leakage1_leak = sensor_rack["rack_leakage1_leak"]
            rack_leakage2_broken = sensor_rack["rack_leakage2_broken"]
            rack_leakage2_leak = sensor_rack["rack_leakage2_leak"]
                        
            for key, value in thermal_equipment.items():
                raw = sensor_value.get(key, 0)
                # sensor_reading = round(raw, 2) if key != "clnt_flow" else round(raw)
                sensor_reading = round(raw, 2)
                if key not in rep:
                    rep[value] = {
                        "status": {
                            "state": state_judge(key, sensor_data, sensor_reading),
                            "health": health_judge(key, sensor_data),
                        },
                        "reading": sensor_reading,
                        "ServiceHours": 100,
                        "ServiceDate": 100,
                        "HardWareInfo":{}
                    }
                    
            rep["leak_detector"] = leak_judge(leak_broken, leak_leak)
            rep["rack_leak_detector_1"] = leak_judge(rack_leakage1_broken, rack_leakage1_leak)
            rep["rack_leak_detector_2"] = leak_judge(rack_leakage2_broken, rack_leakage2_leak)
            rep["Filter_run_time"] = read_ctr_data()["text"]["Filter_run_time"]
                            
        except Exception as e:
            print(f"get sensors data error:{e}")
            return plc_error()        
        
        return rep    
# 0512新增
def get_version_json():
    try:
        with open(f"{web_path}/fw_info_version.json", "r") as json_file:
            data = json.load(json_file)
            return data
    except Exception as e:
        print(f"read fw_info_version error: {e}")
        return e

def get_fw_info():
    try:
        with open(f"{web_path}/fw_info.json", "r") as json_file:
            data = json.load(json_file)
            return data
    except Exception as e:
        print(f"read fw_info error: {e}")
        return e

@default_ns.route("/cdu/components/display/version")
class DisplayVersion(Resource): 
    def get(self):
        rep = {}  
        rep["version"] = get_version_json()
        rep["fw_info"] = get_fw_info()
        return rep, 200
'''
測試使用
        data_to_write = sensor_data  
        data_to_write["error"]["Inv1_OverLoad"] = True
        data_to_write["error"]["Inv1_Error"] = True
        data_to_write["value"]["inv1_freq"] = 25

        with open(f"{json_path}/sensor_data.json", "w", encoding="utf-8") as file:
            json.dump(data_to_write, file, ensure_ascii=False, indent=2)
'''
@default_ns.route("/cdu/components/mc")
class mc(Resource): 
    def get(self):
        rep = {}
        mc_mapping = {}
        sensor_data = read_sensor_data()
        
        # data_to_write = sensor_data  
        # data_to_write["mc"]["fan_mc1"] = True
        # with open(f"{json_path}/sensor_data.json", "w", encoding="utf-8") as file:
        #     json.dump(data_to_write, file, ensure_ascii=False, indent=2)

        main_mc = {"main_mc": sensor_data["error"]["main_mc_error"]}
        mc_mapping = {**sensor_data["mc"], **main_mc}
        for key, val in mc_mapping.items():
            if key == "main_mc":
                state = "OFF" if val else "ON"
            else:
                state = "ON" if val else "OFF"
            rep[key] = state
        cdu_status = sensor_data["cdu_status"]
        if cdu_status == "alert":
            cdu_status_result = "Critical"
        elif cdu_status == "warning":
            cdu_status_result = "Warning"
        else:
            cdu_status_result = "OK"    
        rep["cdu_status"] = cdu_status_result            
        return rep, 200
    
    
def read_network():
    try:
        with open(f"{json_path}/network.json", "r") as json_file:
            data = json.load(json_file)
            return data

    except Exception as e:
        print(f"read read_network error: {e}")
        return plc_error()    
    
@default_ns.route("/cdu/components/network")
class network(Resource): 
    def get(self):
        raw_list = read_network()

        parsed_list = []
        for item in raw_list:
            if isinstance(item, str): # JSON
                parsed_list.append(json.loads(item))
            elif isinstance(item, dict): # dict
                parsed_list.append(item)
            else: # bytes/bytearray
                try:
                    parsed_list.append(json.loads(item.decode()))
                except Exception:
                    # fallback：直接丢原始值
                    parsed_list.append(item)
        rep = {}
        for idx, entry in enumerate(parsed_list):
            if idx == 0:
                rep["Main"] = entry
            else:
                rep[str(idx + 1)] = entry
                
        return rep, 200
    
@default_ns.route("/cdu/components/Oem")  
class Oem(Resource):
    def get(self):
        data = read_ctr_data()
        rep = {}
        rep["ControlMode"] = data["value"]["opMod"]
        rep["TargetTemperature"] = data["value"]["resultTemp"]
        rep["TargetPressure"] = data["value"]["resultPressure"]
        rep["PumpSwapTime"] = data["value"]["resultSwap"]
        rep["FanSetPoint"] = 0 if data["value"]["fan_speed"] < 15 else data["value"]["fan_speed"]
        rep["PumpSetPoint"] = data["value"]["pump_speed"]
        rep["Pump1Switch"] = data["value"]["pump1_check"]
        rep["Pump2Switch"] = data["value"]["pump2_check"]
        rep["Pump3Switch"] = data["value"]["pump3_check"]
        
        return rep

def read_snmp():
    try:
        with open(f"{log_path}/snmp/snmp.json", "r") as json_file:
            data = json.load(json_file)
            return data

    except Exception as e:
        print(f"read ctr_data error: {e}")
        return plc_error()
    
Snmp_patch = default_ns.model('SnmpPatch', {
    'trap_ip_address': fields.String(
        required=True,
        description='snmp trap ip',
        default=True,
        example="127.0.0.1",
    ),
    'read_community': fields.String(
        required=True,
        description='snmp community',
        default=True,   # 是否設定預設值
        example="public",   # 讓 UI 顯示範例
    ),
    'v3_switch': fields.Boolean(
        required=True,
        description='Switch_Mode',
        default=True,   # 是否設定預設值
        example=False,   # 讓 UI 顯示範例
    ),
})  

@default_ns.route("/cdu/components/Snmp")  
class Snmp(Resource):
    def get(self):
        data = read_snmp()
        return data
    
    @default_ns.expect(Snmp_patch, validate=True)
    def patch(self):
        # data = read_snmp()
        body = request.get_json(force=True)
        data_to_write = {
            "trap_ip_address": body["trap_ip_address"],
            "read_community": body["read_community"],
            "v3_switch": False
        }
        with open(f"{log_path}/snmp/snmp.json", "w", encoding="utf-8") as file:
            json.dump(data_to_write, file, ensure_ascii=False, indent=2)

        return data_to_write
    
    
    
api.add_namespace(default_ns)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
