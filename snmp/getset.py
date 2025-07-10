import bisect
import json
import logging
from logging.handlers import RotatingFileHandler
import struct
import threading
import time
import os
import sys
from flask import Flask

from pyasn1.codec.ber import decoder, encoder
from pymodbus.client.sync import ModbusTcpClient
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.carrier.asyncore.dispatch import AsyncoreDispatcher
from pysnmp.entity import config, engine
from pysnmp.hlapi import *
from pysnmp.proto import api

app = Flask(__name__)

FORMAT = "%(asctime)s %(levelname)s: %(message)s"

logging.basicConfig(level=logging.INFO, format=FORMAT)
logging.basicConfig(level=logging.ERROR, format=FORMAT)

log_path = os.getcwd()

journal_dir = f"{log_path}/logs/journal"
if not os.path.exists(journal_dir):
    os.makedirs(journal_dir)

max_bytes = 200 * 1024 * 1024

file_name = "journal.log"
log_file = os.path.join(journal_dir, file_name)
journal_handler = RotatingFileHandler(
    log_file,
    maxBytes=max_bytes,
    backupCount=1,
    encoding="UTF-8",
    delay=False,
)

journal_logger = logging.getLogger("journal_logger")
journal_logger.setLevel(logging.INFO)
journal_logger.addHandler(journal_handler)

SNMPV3_USER = "user"
SNMPV3_AUTH_KEY = "Itgs50848614"
SNMPV3_PRIV_KEY = "Itgs50848614"
AUTH_PROTOCOL = usmHMACSHAAuthProtocol
PRIV_PROTOCOL = usmAesCfb128Protocol

ALARM_THRESHOLD = 810
MODBUS_SERVER_IP = "192.168.3.250"
MODBUS_SERVER_PORT = 502
SNMP_TRAP_RECEIVER_IP = ""
SNMP_AGENT_IP = "0.0.0.0"
SNMP_GET_PORT = 9000
SNMP_TRAP_PORT = 9001

data_lock = threading.Lock()
data_details = {}
scc_data = {}
scc_device = {}
snmp_data = {}
float_values = [None] * 32
trap_bool_lists = [None] * 30
alarm_value = [ALARM_THRESHOLD] * 30
ats_list = [None] * 2
cnt = 0
index = 0

check_key_list = [
    [
        "CoolantSupplyTemperature",
        "CoolantSupplyTemperatureSpare",
        "CoolantReturnTemperature",
        "CoolantReturnTemperatureSpare",
        "CoolantSupplyPressure",
        "CoolantSupplyPressureSpare",
        "CoolantReturnPressure",
        "CoolantReturnPressureSpare",
        "FilterInletPressure",
        "FilterInletPressure",
        "FilterOutletPressure",
        "CoolantFlowRate",
        "AmbientTemp",
        "AmbientTemp",
        "RelativeHumid",
        "RelativeHumid",
    ],
    [
        "DewPoint",
        "pH",
        "pH",
        "Conductivity",
        "Conductivity",
        "Turbidity",
        "Turbidity",
        "AverageCurrent",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ],
    [
        "CoolantSupplyTemperature",
        "CoolantSupplyTemperatureSpare",
        "CoolantReturnTemperature",
        "CoolantReturnTemperatureSpare",
        "CoolantSupplyPressure",
        "CoolantSupplyPressureSpare",
        "CoolantReturnPressure",
        "CoolantReturnPressureSpare",
        "FilterInletPressure",
        "FilterInletPressure",
        "FilterOutletPressure",
        "CoolantFlowRate",
        "AmbientTemp",
        "AmbientTemp",
        "RelativeHumid",
        "RelativeHumid",
    ],
    [
        "DewPoint",
        "pH",
        "pH",
        "Conductivity",
        "Conductivity",
        "Turbidity",
        "Turbidity",
        "AverageCurrent",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ],
    [
        "Inv1Overload",
        "Inv2Overload",
        "Inv3Overload",
        "FanOverload1",
        "FanOverload2",
        "Inv1Error",
        "Inv2Error",
        "Inv3Error",
        "ATS",
        "Inv1SpeedComm",
        "Inv2SpeedComm",
        "Inv3SpeedComm",
        # "CoolantFlowRateComm", # 0326刪掉
        "AmbientTempComm",
        "RelativeHumidComm",
        "DewPointComm",
        "pHComm",
    ],
    [
        "ConductivityComm",
        "TurbidityComm",
        "ATS1Comm",
        "ATS2Comm",
        "InstantPowerConsumptionComm",
        "AverageCurrentComm",
        "Fan1Comm",
        "Fan2Comm",
        "Fan3Comm",
        "Fan4Comm",
        "Fan5Comm",
        "Fan6Comm",
        "Fan7Comm",
        "Fan8Comm",
        "CoolantSupplyTemperatureBroken",
        "CoolantSupplyTemperatureSpareBroken",
    ],
    [
        "CoolantReturnTemperatureBroken",
        "CoolantReturnTemperatureBrokenSpare",
        "CoolantSupplyPressureBroken",
        "CoolantSupplyPressureSpareBroken",
        "CoolantReturnPressureBroken",
        "CoolantReturnPressureSpareBroken",
        "FilterInletPressure",
        "FilterOutletPressure",
        "CoolantFlowRateBroken",
        "PC1Error",
        "PC2Error",
        "Leakage1Leak",
        "Leakage1Broken",
        "Level1",
        "Level2",
        "Level3",
    ],
    [
        "Power24v1",
        "Power24v2",
        "Power12v1",
        "Power12v2",
        "MainMcError",
        "Fan1Error",
        "Fan2Error",
        "Fan3Error",
        "Fan4Error",
        "Fan5Error",
        "Fan6Error",
        "Fan7Error",
        "Fan8Error",
        "LowCoolantLevelWarning",
        "ControlUnit",
        "",
    ],
    [
        "Rack1Broken",
        "Rack2Broken",
        "Rack3Broken",
        "Rack4Broken",
        "Rack5Broken",
        "Rack1LeakCom",
        "Rack2LeakCom",
        "Rack3LeakCom",
        "Rack4LeakCom",
        "Rack5LeakCom",
        "Rack1Leak",
        "Rack2Leak",
        "Rack3Leak",
        "Rack4Leak",
        "Rack5Leak",
        "Rack1StatusCom",
    ],
    [
        "Rack2StatusCom",
        "Rack3StatusCom",
        "Rack4StatusCom",
        "Rack5StatusCom",
        "Rack1Error",
        "Rack2Error",
        "Rack3Error",
        "Rack4Error",
        "Rack5Error",
        "Rack6Error",
        "Rack7Error",
        "Rack8Error",
        "Rack9Error",
        "Rack10Error",
        "RackLeakage1Leak",
        "RackLeakage1Broken",
    ],
    [
        "RackLeakage2Leak",
        "RackLeakage2Broken",
        "RackLeakage3Leak",
        "RackLeakage3Broken",
        "RackLeakage4Leak",
        "RackLeakage4Broken",
        "RackLeakage5Leak",
        "RackLeakage5Broken",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ],
]

warning_alert_list = [
    [
        "M100 Coolant Supply Temperature Over Range (High) Warning (T1)",
        "M101 Coolant Supply Temperature Spare Over Range (High) Warning (T1sp)",
        "M102 Coolant Return Temperature Over Range (High) Warning (T2)",
        "M103 Coolant Return Temperature Over Range Spare (High) Warning (T2sp)",
        "M104 Coolant Supply Pressure Over Range (High) Warning (P1)",
        "M105 Coolant Supply Pressure Spare Over Range (High) Warning (P1sp)",
        "M106 Coolant Return Pressure Over Range (High) Warning (P2)",
        "M107 Coolant Return Pressure Spare Over Range (High) Warning (P2sp)",
        "M108 Filter Inlet Pressure Over Range (Low) Warning (P3)",
        "M109 Filter Inlet Pressure Over Range (High) Warning (P3)",
        "M110 Filter Delta P Over Range (High) Warning (P3 - P4)",
        "M111 Coolant Flow Rate (Low) Warning (F1)",
        "M112 Ambient Temperature Over Range (Low) Warning (T a)",
        "M113 Ambient Temperature Over Range (High) Warning (T a)",
        "M114 Relative Humidity Over Range (Low) Warning (RH)",
        "M115 Relative Humidity Over Range (High) Warning (RH)",
    ],
    [
        "M116 Condensation Warning (T Dp)",
        "M117 pH Over Range (Low) Warning (PH)",
        "M118 pH Over Range (High) Warning (PH)",
        "M119 Conductivity Over Range (Low) Warning (CON)",
        "M120 Conductivity Over Range (High) Warning (CON)",
        "M121 Turbidity Over Range (Low) Warning (Tur)",
        "M122 Turbidity Over Range (High) Warning (Tur)",
        "M123 Average Current Over Range (High) Warning",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ],
    [
        "M200 Coolant Supply Temperature Over Range (High) Alert (T1)",
        "M201 Coolant Supply Temperature Spare Over Range (High) Alert (T1sp)",
        "M202 Coolant Return Temperature Over Range (High) Alert (T2)",
        "M203 Coolant Return Temperature Over Range Spare (High) Alert (T2sp)",
        "M204 Coolant Supply Pressure Over Range (High) Alert (P1)",
        "M205 Coolant Supply Pressure Spare Over Range (High) Alert (P1sp)",
        "M206 Coolant Return Pressure Over Range (High) Alert (P2)",
        "M207 Coolant Return Pressure Spare Over Range (High) Alert (P2sp)",
        "M208 Filter Inlet Pressure Over Range (Low) Alert (P3)",
        "M209 Filter Inlet Pressure Over Range (High) Alert (P3)",
        "M210 Filter Delta P Over Range (High) Alert (P3 - P4)",
        "M211 Coolant Flow Rate (Low) Alert (F1)",
        "M212 Ambient Temperature Over Range (Low) Alert (T a)",
        "M213 Ambient Temperature Over Range (High) Alert (T a)",
        "M214 Relative Humidity Over Range (Low) Alert (RH)",
        "M215 Relative Humidity Over Range (High) Alert (RH)",
    ],
    [
        "M216 Condensation Alert (T Dp)",
        "M217 pH Over Range (Low) Alert (PH)",
        "M218 pH Over Range (High) Alert (PH)",
        "M219 Conductivity Over Range (Low) Alert (CON)",
        "M220 Conductivity Over Range (High) Alert (CON)",
        "M221 Turbidity Over Range (Low) Alert (Tur)",
        "M222 Turbidity Over Range (High) Alert (Tur)",
        "M223 Average Current Over Range (High) Alert",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ],
    [
        "M300 Coolant Pump1 Inverter Overload",
        "M301 Coolant Pump2 Inverter Overload",
        "M302 Coolant Pump3 Inverter Overload",
        "M303 Fan1 Group1 Overload",
        "M304 Fan2 Group2 Overload",
        "M305 Coolant Pump1 Inverter Error",
        "M306 Coolant Pump2 Inverter Error",
        "M307 Coolant Pump3 Inverter Error",
        "M308 Primary Power Broken",
        "M309 Inverter1 Communication Error",
        "M310 Inverter2 Communication Error",
        "M311 Inverter3 Communication Error",
        # "M312 Coolant Flow (F1) Meter Communication Error",
        "M313 Ambient Sensor (Ta, RH, TDp) Communication Error",
        "M314 Relative Humidity (RH) Communication Error",
        "M315 Dew Point Temperature (TDp) Communication Error",
        "M316 pH (PH) Sensor Communication Error",
    ],
    [
        "M317 Conductivity (CON) Sensor Communication Error",
        "M318 Turbidity (Tur) Sensor Communication Error",
        "M319 ATS 1 Communication Error",
        "M320 ATS 2 Communication Error",
        "M321 Power Meter Communication Error",
        "M322 Average Current Communication Error",
        "M323 Fan 1 Communication Error",
        "M324 Fan 2 Communication Error",
        "M325 Fan 3 Communication Error",
        "M326 Fan 4 Communication Error",
        "M327 Fan 5 Communication Error",
        "M328 Fan 6 Communication Error",
        "M329 Fan 7 Communication Error",
        "M330 Fan 8 Communication Error",
        "M331 Coolant Supply Temperature (T1) Broken Error",
        "M332 Coolant Supply Temperature Spare (T1sp) Broken Error",
    ],
    [
        "M333 Coolant Return Temperature (T2) Broken Error",
        "M334 Coolant Return Temperature Spare (T2sp) Broken Error",
        "M335 Coolant Supply Pressure (P1) Broken Error",
        "M336 Coolant Supply Pressure Spare (P1sp) Broken Error",
        "M337 Coolant Return Pressure (P2) Broken Error",
        "M338 Coolant Return Pressure Spare (P2sp) Broken Error",
        "M339 Filter Inlet Pressure (P3) Broken Error",
        "M340 Filter Outlet Pressure (P4) Broken Error",
        "M341 Coolant Flow Rate (F1) Broken Error",
        "M342 PC1 Error",
        "M343 PC2 Error",
        "M344 Leakage 1 Leak Error",
        "M345 Leakage 1 Broken Error",
        "M346 Coolant Level 1 Error",
        "M347 Coolant Level 2 Error",
        "M348 Coolant Level 3 Error",
    ],
    [
        "M349 24V Power Supply 1 Error",
        "M350 24V Power Supply 2 Error",
        "M351 12V Power Supply 1 Error",
        "M352 12V Power Supply 2 Error",
        "M353 Main MC Status Error",
        "M354 FAN 1 Alarm Status Error",
        "M355 FAN 2 Alarm Status Error",
        "M356 FAN 3 Alarm Status Error",
        "M357 FAN 4 Alarm Status Error",
        "M358 FAN 5 Alarm Status Error",
        "M359 FAN 6 Alarm Status Error",
        "M360 FAN 7 Alarm Status Error",
        "M361 FAN 8 Alarm Status Error",
        "M362 Stop Due to Low Coolant Level",
        "M363 PLC Communication Broken Error",
        "",
    ],
    [
        "M400 Rack1 broken",
        "M401 Rack2 broken",
        "M402 Rack3 broken",
        "M403 Rack4 broken",
        "M404 Rack5 broken",
        "M405 Rack1 Leakage Communication Error",
        "M406 Rack2 Leakage Communication Error",
        "M407 Rack3 Leakage Communication Error",
        "M408 Rack4 Leakage Communication Error",
        "M409 Rack5 Leakage Communication Error",
        "M410 Rack1 leakage",
        "M411 Rack2 leakage",
        "M412 Rack3 leakage",
        "M413 Rack4 leakage",
        "M414 Rack5 leakage",
        "M415 Rack1 Status Communication Error",
    ],
    [
        "M416 Rack2 Status Communication Error",
        "M417 Rack3 Status Communication Error",
        "M418 Rack4 Status Communication Error",
        "M419 Rack5 Status Communication Error",
        "M420 Rack1 error",
        "M421 Rack2 error",
        "M422 Rack3 error",
        "M423 Rack4 error",
        "M424 Rack5 error",
        "M425 Rack6 error",
        "M426 Rack7 error",
        "M427 Rack8 error",
        "M428 Rack9 error",
        "M429 Rack10 error",
        "M430 Rack Leakage Sensor 1 Leak",
        "M431 Rack Leakage Sensor 1 Broken",
    ],
    [
        "M432 Rack Leakage Sensor 2 Leak",
        "M433 Rack Leakage Sensor 2 Broken",
        "M434 Rack Leakage Sensor 3 Leak",
        "M435 Rack Leakage Sensor 3 Broken",
        "M436 Rack Leakage Sensor 4 Leak",
        "M437 Rack Leakage Sensor 4 Broken",
        "M438 Rack Leakage Sensor 5 Leak",
        "M439 Rack Leakage Sensor 5 Broken",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ],
]

sensor = {
    "CoolantSupplyTemperature": 0,
    "CoolantSupplyTemperatureSpare": 0,
    "CoolantReturnTemperature": 0,
    "CoolantReturnTemperatureSpare": 0,
    "CoolantSupplyPressure": 0,
    "CoolantSupplyPressureSpare": 0,
    "CoolantReturnPressure": 0,
    "CoolantReturnPressureSpare": 0,
    "FilterInletPressure": 0,
    "FilterOutletPressure": 0,
    "CoolantFlowRate": 0,
    "AmbientTemperature": 0,
    "RelativeHumidity": 0,
    "DewPoint": 0,
    "pH": 0,
    "Conductivity": 0,
    "Turbidity": 0,
    "InstantPowerConsumption": 0,
    "AverageCurrent": 0,
    "Inv1Speed": 0,
    "Inv2Speed": 0,
    "Inv3Speed": 0,
    "HeatCapacity": 0,
    "FanSpeed1": 0,
    "FanSpeed2": 0,
    "FanSpeed3": 0,
    "FanSpeed4": 0,
    "FanSpeed5": 0,
    "FanSpeed6": 0,
    "FanSpeed7": 0,
    "FanSpeed8": 0,
}


class SysDescr:
    name = (1, 3, 6, 1, 2, 1, 1, 1, 0)

    def __eq__(self, other):
        return self.name == other

    def __ne__(self, other):
        return self.name != other

    def __lt__(self, other):
        return self.name < other

    def __le__(self, other):
        return self.name <= other

    def __gt__(self, other):
        return self.name > other

    def __ge__(self, other):
        return self.name >= other

    def __call__(self, protoVer):
        return api.protoModules[protoVer].OctetString("version:{}".format(protoVer))


class Uptime:
    name = (1, 3, 6, 1, 2, 1, 1, 3, 0)
    birthday = time.time()

    def __eq__(self, other):
        return self.name == other

    def __ne__(self, other):
        return self.name != other

    def __lt__(self, other):
        return self.name < other

    def __le__(self, other):
        return self.name <= other

    def __gt__(self, other):
        return self.name > other

    def __ge__(self, other):
        return self.name >= other

    def __call__(self, protoVer):
        return api.protoModules[protoVer].TimeTicks((time.time() - self.birthday) * 100)


class Bufferin:
    def __eq__(self, other):
        return self.name == other

    def __ne__(self, other):
        return self.name != other

    def __lt__(self, other):
        return self.name < other

    def __le__(self, other):
        return self.name <= other

    def __gt__(self, other):
        return self.name > other

    def __ge__(self, other):
        return self.name >= other

    def __call__(self, protoVer):
        if self.value is None:
            self.value = ""
        return api.protoModules[protoVer].OctetString(self.value)


def convert_registers_to_str(register_data):
    """
    將寄存器數據轉換為浮點數。

    :param register_data: 寄存器數據列表
    :return: 浮點數數據列表
    """
    float_data = []
    for i in range(0, len(register_data), 2):
        high_word = register_data[i + 1]
        low_word = register_data[i]
        packed_value = struct.pack("<HH", low_word, high_word)
        float_value = struct.unpack("<f", packed_value)[0]
        float_value = round(float_value, 2)
        float_data.append(str(float_value))
    return float_data


def messages(i, c):
    journal_logger.info(f"{i}, {c}")


def convert_float_to_registers(float_data):
    register_data = []
    for value in float_data:
        packed_value = struct.pack("<f", value)
        low_word, high_word = struct.unpack("<HH", packed_value)
        register_data.append(low_word)
        register_data.append(high_word)
    return register_data


def word_to_bool_list(words):
    bit_lengths = [16] * 18
    all_bool_lists = []
    word_index = 0
    for bits in bit_lengths:
        binary_string = bin(words[word_index])[2:].zfill(bits)
        bool_list = [char == "1" for char in binary_string]

        bool_list = bool_list[::-1]

        all_bool_lists.append(bool_list)
        word_index += 1

    return all_bool_lists


def send_snmp_trap(oid, target_ip, severity, port=SNMP_TRAP_PORT, value="0"):
    community = snmp_data.get("read_community", "")
    v3_switch = snmp_data.get("v3_switch")
    oid_severity = (1, 3, 6, 1, 4, 1, 10876, 301, 1, 2, 2, 1)

    if v3_switch:
        errorIndication, errorStatus, errorIndex, varBinds = next(
            sendNotification(
                SnmpEngine(),
                UsmUserData(
                    SNMPV3_USER,
                    SNMPV3_AUTH_KEY,
                    SNMPV3_PRIV_KEY,
                    authProtocol=AUTH_PROTOCOL,
                    privProtocol=PRIV_PROTOCOL,
                ),
                UdpTransportTarget((target_ip, port)),
                ContextData(),
                "trap",
                NotificationType(ObjectIdentity(oid)).addVarBinds(
                    (ObjectIdentity(oid), OctetString(value)),
                    (ObjectIdentity(oid_severity), Integer(severity)),
                ),
            )
        )
    else:
        errorIndication, errorStatus, errorIndex, varBinds = next(
            sendNotification(
                SnmpEngine(),
                CommunityData(community, mpModel=1),
                UdpTransportTarget((target_ip, port)),
                ContextData(),
                "trap",
                NotificationType(ObjectIdentity(oid)).addVarBinds(
                    (oid, OctetString(value)),
                    (ObjectIdentity(oid_severity), Integer(severity)),
                ),
            )
        )

    if errorIndication:
        logging.error(f"Error: {str(errorIndication)}")
    elif errorStatus:
        logging.error(f"Error Status: {str(errorStatus.prettyPrint())}")
    else:
        logging.info(
            f"SNMP Trap successfully sent to {target_ip}:{port} with OID {oid}, severity {severity}"
        )


def trap(trap_bool_lists, check_switch):
    base_oid = (1, 3, 6, 1, 4, 1, 10876, 301, 1, 2, 1)
    global index
    index = 0

    m1_count = sum(
        1 for sublist in warning_alert_list if sublist and sublist[0].startswith("M1")
    )
    m2_count = sum(
        1 for sublist in warning_alert_list if sublist and sublist[0].startswith("M2")
    )
    m3_count = sum(
        1 for sublist in warning_alert_list if sublist and sublist[0].startswith("M3")
    )
    m4_count = sum(
        1 for sublist in warning_alert_list if sublist and sublist[0].startswith("M4")
    )

    level1 = m1_count
    level2 = m2_count + m1_count
    level3 = m3_count + m2_count + m1_count
    level4 = m4_count + m3_count + m2_count + m1_count
    
    size = m4_count + m3_count + m2_count + m1_count
    base_offsets = [n * 16 for n in range(size)]

    level1_reg = level1 * 16
    level2_reg = level2 * 16
    level3_reg = level3 * 16
    level4_reg = level4 * 16
    

    for i, trap_bool_list in enumerate(trap_bool_lists):
        if i < level1:
            severity_level = 1
        elif m1_count <= i < level2:
            severity_level = 2
        elif level2 <= i < level3:
            severity_level = 3
        elif level3 <= i < level4:
            severity_level = 4

        else:
            severity_level = 0
        for j, bool_value in enumerate(trap_bool_list):
            a_name = check_key_list[i][j]

            try:
                if bool_value:
                    if "Rack" in a_name:
                        oid = base_oid + (base_offsets[i] + j,)
                    else:
                        oid = base_oid + (base_offsets[i] + j + 1,)
                    # oid = base_oid + (base_offsets[i] + j + 1,)
                    if index < level1_reg:
                        if data_details["sensor_value_data"][a_name]["Warning"]:
                            # messages(oid, warning_alert_list[i][j])
                            if check_switch and (
                                a_name == "pH"
                                or a_name == "Conductivity"
                                or a_name == "Turbidity"
                            ):
                                continue

                            send_snmp_trap(
                                oid,
                                SNMP_TRAP_RECEIVER_IP,
                                severity=severity_level,
                                value=f"{warning_alert_list[i][j]}",
                            )
                    elif level1_reg <= index < level2_reg:
                        if data_details["sensor_value_data"][a_name]["Alert"]:
                            # messages(oid, warning_alert_list[i][j])
                            if check_switch and (
                                a_name == "pH"
                                or a_name == "Conductivity"
                                or a_name == "Turbidity"
                            ):
                                continue

                            send_snmp_trap(
                                oid,
                                SNMP_TRAP_RECEIVER_IP,
                                severity=severity_level,
                                value=f"{warning_alert_list[i][j]}",
                            )
                    elif level2_reg <= index < level3_reg:
                        if data_details["devices"][a_name]:
                            # messages(oid, warning_alert_list[i][j])
                            if check_switch and (
                                a_name == "pHComm"
                                or a_name == "ConductivityComm"
                                or a_name == "TurbidityComm"
                                or a_name == "Power12v1"
                                or a_name == "Power12v1"
                            ):
                                continue
                            
                            send_snmp_trap(
                                oid,
                                SNMP_TRAP_RECEIVER_IP,
                                severity=severity_level,
                                value=f"{warning_alert_list[i][j]}",
                            )
                    elif level3_reg <= index < level4_reg:
                        # journal_logger.info(f"有進到rack")
                        # journal_logger.info(a_name)
                        # journal_logger.info(oid)
                        # journal_logger.info(f"{warning_alert_list[i][j]}")
                        # journal_logger.info(
                        #     f"data_details:{data_details['devices'][a_name]}"
                        # )
                        if a_name in [
                            "RackLeakage1Leak",
                            "RackLeakage1Broken",
                            "RackLeakage2Leak",
                            "RackLeakage2Broken",
                            "RackLeakage3Leak",
                            "RackLeakage3Broken",
                            "RackLeakage4Leak",
                            "RackLeakage4Broken",
                            "RackLeakage5Leak",
                            "RackLeakage5Broken",
                        ]:
                            if data_details["devices"][a_name]:
                                send_snmp_trap(
                                    oid,
                                    SNMP_TRAP_RECEIVER_IP,
                                    severity=severity_level,
                                    value=f"{warning_alert_list[i][j]}",
                                )
                        elif data_details["devices"]["RackError"]:
                            # messages(a_name, oid, warning_alert_list[i][j])
                            send_snmp_trap(
                                oid,
                                SNMP_TRAP_RECEIVER_IP,
                                severity=severity_level,
                                value=f"{warning_alert_list[i][j]}",
                            )
                    else:
                        index = 0
            except Exception as e:
                print(f"snmp error: {e}")
            index += 1


def Mbus_get():
    global float_values, trap_bool_lists, ats_list, cnt, data_details

    while True:
        with open(
            f"{os.path.dirname(log_path)}/webUI/web/json/scc_data.json", "r"
        ) as file:
            data_details = json.load(file)

        with open(
            f"{os.path.dirname(log_path)}/webUI/web/json/version.json", "r"
        ) as file:
            version_data = json.load(file)
            check_switch = version_data[
                "coolant_quality_meter_switch"
            ]  # Enable = false、 Disabled = true

        if cnt > 14:
            try:
                with ModbusTcpClient(
                    host=MODBUS_SERVER_IP, port=MODBUS_SERVER_PORT
                ) as client:
                    sensor_reg = len(sensor) * 2
                    Mbus_DArr = client.read_holding_registers(5000, sensor_reg + 2)
                    if not Mbus_DArr.isError():
                        present_data_value = Mbus_DArr.registers
                        float_values = convert_registers_to_str(present_data_value)
                    ats_data = client.read_coils(address=(8192 + 10), count=2)
                    if not ats_data.isError():
                        if ats_data.bits[0]:
                            ats_list[0] = "OK"
                        else:
                            ats_list[0] = "NG"

                        if ats_data.bits[1]:
                            ats_list[1] = "OK"
                        else:
                            ats_list[1] = "NG"
                    else:
                        ats_list = ["NG", "NG"]

                    trap_list = client.read_holding_registers(1700, 18)
                    if not trap_list.isError():
                        trap_bool_lists = word_to_bool_list(trap_list.registers)
                        error_section = [
                            trap_bool_lists[i]
                            for i in [0, 1, 5, 6, 8, 9, 10, 11, 15, 16, 17]
                        ]
                        trap(error_section, check_switch)
                cnt = 0
            except Exception as e:
                journal_logger.info(f"trap list error: {e}")
                ###增加Plc異常發送trap
                if data_details["devices"]["ControlUnit"]:
                    send_snmp_trap(
                        (1, 3, 6, 1, 4, 1, 10876, 301, 1, 2, 1, 127),
                        SNMP_TRAP_RECEIVER_IP,
                        severity=3,
                        value="363 PLC Communication Broken Error",
                    )

        cnt += 1
        time.sleep(1)



######################## 測試分離Mbus_get和Mbus_trap的功能 ########################

# def Mbus_get():
#     global float_values, trap_bool_lists, ats_list, cnt, data_details, v2

#     while True:
#         # 讀取 JSON 設定
#         with open(f"{os.path.dirname(log_path)}/webUI/web/json/scc_data.json", "r") as f:
#             data_details = json.load(f)

#         with open(f"{os.path.dirname(log_path)}/webUI/web/json/version.json", "r") as f:
#             v2 = not json.load(f)["function_switch"]

#         if cnt > 15:
#             try:
#                 with ModbusTcpClient(host=MODBUS_SERVER_IP, port=MODBUS_SERVER_PORT) as client:
#                     # 感測值
#                     mbus_data = client.read_holding_registers(5000, 62)
#                     if not mbus_data.isError():
#                         float_values = convert_registers_to_str(mbus_data.registers)

#                     # ATS 狀態
#                     ats_data = client.read_coils(address=(8192 + 10), count=2)
#                     if not ats_data.isError():
#                         ats_list[0] = "OK" if ats_data.bits[0] else "NG"
#                         ats_list[1] = "OK" if ats_data.bits[1] else "NG"
#                     else:
#                         ats_list = ["NG", "NG"]

#                     # Trap register bit list
#                     trap_regs = client.read_holding_registers(1700, 19)
#                     if not trap_regs.isError():
#                         trap_bool_lists = word_to_bool_list(trap_regs.registers)

#                 cnt = 0
#             except Exception as e:
#                 print(f"Modbus error: {e}")
#         cnt += 1
#         time.sleep(1)

# def Mbus_trap():
#     global trap_bool_lists, v2, data_details

#     while True:
#         try:
#             if trap_bool_lists:
#                 error_indices = [0, 1, 2, 5, 6, 7, 8, 9, 10, 11, 15, 16, 17, 18]
#                 error_section = [trap_bool_lists[i] for i in error_indices]
#                 trap(error_section, v2)
#         except Exception as e:
#             print(f"trap error: {e}")
#             if data_details.get("devices", {}).get("ControlUnit"):
#                 send_snmp_trap(
#                     (1, 3, 6, 1, 4, 1, 10876, 301, 1, 2, 1, 148),
#                     SNMP_TRAP_RECEIVER_IP,
#                     severity=3,
#                     value="351 PLC Communication Broken Error",
#                 )
#         time.sleep(5)  # 每 5 秒做一次判斷，可調整

######################## 測試結束 ########################


def mib(jsondata):
    oid = (1, 3, 6, 1, 4, 1, 10876, 301, 1, 1, 4, 1, 1, 0)
    sensor_len = len(sensor)
    ats_start = sensor_len + 1
    ats_end = sensor_len + 2

    mibInstr = [SysDescr(), Uptime()]
    with data_lock:
        for num in range(1, ats_start):
            modified_oid = oid[:-2] + (num,) + oid[-1:]
            item = Bufferin()
            item.name = modified_oid
            if num > 4:
                item.value = {float_values[num]}
            else:    
                item.value = {float_values[num - 1]}   
            mibInstr.append(item)
        for num, ats_val in enumerate(ats_list, start=ats_start):
            modified_oid = oid[:-2] + (num,) + oid[-1:]
            item = Bufferin()
            item.name = modified_oid

            item.value = ats_val
            mibInstr.append(item)
        mibInstrIdx = {mibVar.name: mibVar for mibVar in mibInstr}

    def cbFun(transportDispatcher, transportDomain, transportAddress, wholeMsg):
        while wholeMsg:
            with data_lock:
                for mibVar in mibInstr:
                    if isinstance(mibVar, Bufferin):
                        if 1 <= mibVar.name[-2] <= sensor_len:
                            if mibVar.name[-2] > 4:
                                mibVar.value = float_values[mibVar.name[-2]]
                            else:
                                mibVar.value = float_values[mibVar.name[-2] - 1]
                        elif ats_start <= mibVar.name[-2] <= ats_end:
                            mibVar.value = ats_list[mibVar.name[-2] - ats_start]
            msgVer = api.decodeMessageVersion(wholeMsg)
            if msgVer in api.protoModules:
                pMod = api.protoModules[msgVer]
            else:
                print("Unsupported SNMP version %s" % msgVer)
                return

            reqMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=pMod.Message())
            rspMsg = pMod.apiMessage.getResponse(reqMsg)
            rspPDU = pMod.apiMessage.getPDU(rspMsg)
            reqPDU = pMod.apiMessage.getPDU(reqMsg)

            message = reqMsg
            community = message.getComponentByName("community").prettyPrint()

            if community not in jsondata["read_community"]:
                pMod.apiPDU.setErrorStatus(rspPDU, 16)
                transportDispatcher.sendMessage(
                    encoder.encode(rspMsg), transportDomain, transportAddress
                )
                continue

            varBinds = []
            pendingErrors = []
            errorIndex = 0

            if reqPDU.isSameTypeWith(pMod.GetRequestPDU()):
                for oid, val in pMod.apiPDU.getVarBinds(reqPDU):
                    if oid in mibInstrIdx:
                        varBinds.append((oid, mibInstrIdx[oid](msgVer)))
                    else:
                        varBinds.append((oid, val))
                        pendingErrors.append(
                            (pMod.apiPDU.setNoSuchInstanceError, errorIndex)
                        )
                        break
            # elif reqPDU.isSameTypeWith(pMod.GetNextRequestPDU()):
            #     for oid, val in pMod.apiPDU.getVarBinds(reqPDU):
            #         next_oids = sorted(k for k in mibInstrIdx if k > oid)
            #         if next_oids:
            #             next_oid = next_oids[0]
            #             varBinds.append((next_oid, mibInstrIdx[next_oid](msgVer)))
            #         else:
            #             pendingErrors.append(
            #                 (pMod.apiPDU.setNoSuchInstanceError, errorIndex)
            #             )
            #             break
            else:
                pMod.apiPDU.setErrorStatus(rspPDU, "genErr")
            pMod.apiPDU.setVarBinds(rspPDU, varBinds)
            for f, i in pendingErrors:
                f(rspPDU, i)
            transportDispatcher.sendMessage(
                encoder.encode(rspMsg), transportDomain, transportAddress
            )
        return wholeMsg

    transportDispatcher = AsyncoreDispatcher()
    transportDispatcher.registerRecvCbFun(cbFun)
    transportDispatcher.registerTransport(
        udp.domainName,
        udp.UdpSocketTransport().openServerMode((SNMP_AGENT_IP, SNMP_GET_PORT)),
    )
    transportDispatcher.jobStarted(1)

    try:
        logging.info("Starting SNMP agent")
        transportDispatcher.runDispatcher()
    except Exception as e:
        logging.error(f"Mib exception occurred: {e}")
        transportDispatcher.closeDispatcher()
        raise


if __name__ == "__main__":
    with open("snmp.json", "r") as file:
        data = json.load(file)
        snmp_data = data

    SNMP_TRAP_RECEIVER_IP = data["trap_ip_address"]

    Mbus = threading.Thread(target=Mbus_get, name="Mbus_get")
    Mib = threading.Thread(target=mib, name="Mib", args=(data,))
    
    
    #### 測試加入Mbus_trap的功能 ####
    # Mbus_trap = threading.Thread(target=Mbus_trap, name="Mbus_trap")

    Mib.daemon = True
    Mbus.daemon = True

    Mbus.start()
    Mib.start()

    Mbus.join()

    logging.info("Program has finished execution.")
