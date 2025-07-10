# 標準函式庫
import json
import logging
import os
import platform
import struct
import statistics
import time
import threading
from collections import deque

# 第三方套件
from dotenv import load_dotenv
from pymodbus.client.sync import ModbusTcpClient, ModbusSerialClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
from concurrent_log_handler import ConcurrentTimedRotatingFileHandler


if platform.system() == "Linux":
    project_root = os.path.dirname(os.getcwd())
    env_path = os.path.join(project_root, "webUI/web/.env")
    onLinux = True

else:
    env_path = "webUI/web/.env"
    onLinux = False


load_dotenv(env_path)

modbus_ip = os.getenv("MODBUS_IP")


if onLinux:
    modbus_host = modbus_ip
else:
    # modbus_host = "192.168.3.250"
    ## 測試用
    modbus_host = "127.0.0.1"
    # modbus_host = "192.168.3.250"
print("程序已開始")


modbus_port = 502
modbus_slave_id = 1
modbus_address = 0

port = "/dev/ttyS0"

switch_address = 0x0000

log_path = os.getcwd()


if onLinux:
    journal_dir = f"{log_path}/logs/journal"
else:
    journal_dir = f"{log_path}/PLC/logs/journal"

if not os.path.exists(journal_dir):
    os.makedirs(journal_dir)

max_bytes = 4 * 1024 * 1024 * 1024
backup_count = 1

file_name = "journal.log"
log_file = os.path.join(journal_dir, file_name)
journal_handler = ConcurrentTimedRotatingFileHandler(
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


f1_data = []
p1_data = []
p2_data = []
p3_data = []
p1_error_box = []
p2_error_box = []
p3_error_box = []


fan1_data = []
fan2_data = []
fan3_data = []
fan4_data = []
fan5_data = []
fan6_data = []
fan7_data = []
fan8_data = []
fan1_error_box = []
fan2_error_box = []
fan3_error_box = []
fan4_error_box = []
fan5_error_box = []
fan6_error_box = []
fan7_error_box = []
fan8_error_box = []
pump_signial = ""
change_back_mode = ""
count_f1 = 0
previous_inv = 4
x = 0
water_pv_set = 0
count = 0
diff = 0
previous_inv1 = False
previous_inv2 = False
oc_issue = False
warning_light = False
zero_flag = False
auto_flag = False
rtu_flag = False
previous_ver = None
oc_trigger = False

bit_output_regs = {
    "mc1": False,
    "mc2": False,
    "led_err": False,
    "mc3": False,
    "space1": False,
    "space2": False,
    "space3": False,
    "space4": False,
    "mc_fan1": False,
    "mc_fan2": False,
}
### pump 或 fan 有無啟動
inv = {
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
}

color_light = {
    "red": True,
    "green": True,
}

word_regs = {
    "pump_speed": 0,
    "pid_pump_out": 0,
    "p1_check": 0,
    "p2_check": 0,
    "p3_check": 0,
    "fan_speed": 0,
    "f1_check": False,
    "f2_check": False,
    "f3_check": False,
    "f4_check": False,
    "f5_check": False,
    "f6_check": False,
    "f7_check": False,
    "f8_check": False,
}

bit_input_regs = {
    "Inv1_Error": None,
    "Inv2_Error": None,
    "Inv3_Error": None,
    "leakage1_leak": None,
    "leakage1_broken": None,
    "main_mc_error": None,
    "fan1_error": None,
    "fan2_error": None,
    "fan3_error": None,
    "fan4_error": None,
    "fan5_error": None,
    "fan6_error": None,
    "fan7_error": None,
    "fan8_error": None,
}
# 測試用開始
raw_485_data_eletricity = {"average_voltage": 0, "apparent_power": 0}

raw_485_comm_eletricity = {"average_voltage": False, "apparent_power": False}
# 測試用結束
raw_485_data = {
    "Clnt_Flow": 0,
    "AmbientTemp": 0,
    "RelativeHumid": 0,
    "DewPoint": 0,
    "pH": 0,
    "conductivity": 0,
    "turbidity": 0,
    "inst_power": 0,
    "average_current": 0,
    "Inv1_Freq": 0,
    "Inv2_Freq": 0,
    "Inv3_Freq": 0,
    "Heat_Capacity": 0,
    "ATS1": False,
    "ATS2": False,
    "Fan1Com": 0,
    "Fan2Com": 0,
    "Fan3Com": 0,
    "Fan4Com": 0,
    "Fan5Com": 0,
    "Fan6Com": 0,
    "Fan7Com": 0,
    "Fan8Com": 0,
}

raw_485_comm = {
    "Inv1_Freq": False,
    "Inv2_Freq": False,
    "Inv3_Freq": False,
    "AmbientTemp": 0,
    "RelativeHumid": 0,
    "DewPoint": 0,
    "pH": False,
    "conductivity": False,
    "turbidity": False,
    "ATS1": False,
    "ATS2": False,
    "inst_power": False,
    "average_current": False,
    "Fan1Com": 0,
    "Fan2Com": 0,
    "Fan3Com": 0,
    "Fan4Com": 0,
    "Fan5Com": 0,
    "Fan6Com": 0,
    "Fan7Com": 0,
    "Fan8Com": 0,
}


sensor_raw = {
    "Temp_ClntSply": 0,
    "Temp_ClntSplySpare": 0,
    "Temp_ClntRtn": 0,
    "Temp_ClntRtnSpare": 0,
    "space": 0,
    "Prsr_ClntSply": 0,
    "Prsr_ClntSplySpare": 0,
    "Prsr_ClntRtn": 0,
    "Prsr_ClntRtnSpare": 0,
    "Prsr_FltIn": 0,
    "Prsr_FltOut": 0,
    "Clnt_Flow": 0,
    "AmbientTemp": 0,
    "RelativeHumid": 0,
    "DewPoint": 0,
    "pH": 0,
    "Cdct": 0,
    "Tbd": 0,
    "Power": 0,
    "AC": 0,
    "Inv1_Freq": 0,
    "Inv2_Freq": 0,
    "Inv3_Freq": 0,
    "Heat_Capacity": 0,
    "fan_freq1": 0,
    "fan_freq2": 0,
    "fan_freq3": 0,
    "fan_freq4": 0,
    "fan_freq5": 0,
    "fan_freq6": 0,
    "fan_freq7": 0,
    "fan_freq8": 0,
}

ad_sensor_value = {
    "Temp_ClntSply": 0,
    "Temp_ClntSplySpare": 0,
    "Temp_ClntRtn": 0,
    "Temp_ClntRtnSpare": 0,
    "space": 0,
    "Prsr_ClntSply": 0,
    "Prsr_ClntSplySpare": 0,
    "Prsr_ClntRtn": 0,
    "Prsr_ClntRtnSpare": 0,
    "Prsr_FltIn": 0,
    "Prsr_FltOut": 0,
}

serial_sensor_value = {
    "Clnt_Flow": 0,
    "AmbientTemp": 0,
    "RelativeHumid": 0,
    "DewPoint": 0,
    "pH": 0,
    "Cdct": 0,
    "Tbd": 0,
    "Power": 0,
    "AC": 0,
    "Inv1_Freq": 0,
    "Inv2_Freq": 0,
    "Inv3_Freq": 0,
    "Heat_Capacity": 0,
    "fan_freq1": 0,
    "fan_freq2": 0,
    "fan_freq3": 0,
    "fan_freq4": 0,
    "fan_freq5": 0,
    "fan_freq6": 0,
    "fan_freq7": 0,
    "fan_freq8": 0,
}


oc_detection = {
    "p1": False,
    "p2": False,
    "p3": False,
    "f1": False,
    "f2": False,
}

inspection_data = {
    "prev": {
        "inv1": False,
        "inv2": False,
        "inv3": False,
    },
    "result": {
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
    },
    "prog": {
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
        "pump_test1": 1,
        "pump_test2": 1,
        "pump_test3": 1,
        "pump_test4": 1,
        "pump_test5": 1,
        "pump_test6": 1,
        "pump_test7": 1,
        "fan_test1": 1,
        "fan_test2": 1,
        "fan_test3": 1,
    },
    "set": {"total_inspect_time": 95},
    "step": 1,
    "start_time": 0,
    "mid_time": 0,
    "end_time": 0,
    "final_end_time": 0,
    "force_change_mode": 0,
    "start_btn": False,
    "cancel_btn": False,
    "skip": False,
}

ver_switch = {
    "median_switch": False,
    "coolant_quality_meter_switch": False,
    "fan_count_switch": False,
    "liquid_level_1_switch": False,
    "liquid_level_2_switch": False,
    "liquid_level_3_switch": False,
}


measured_data_mapping = {
    9: "TempClntSply",
    11: "TempClntSplySpare",
    13: "TempClntRtn",
    15: "TempClntRtnSpare",
    17: "PrsrClntSply",
    19: "PrsrClntSplySpare",
    21: "PrsrClntRtn",
    23: "PrsrClntRtnSpare",
    25: "PrsrFltIn",
    27: "PrsrFltOut",
    29: "ClntFlow",
}

counter = {
    "start": 0,
    "end": 0,
    "pass": 0,
}


dword_regs = {
    "p_swap": 0,
    "swap_hr": 0,
    "swap_min": 0,
    "p1_run_min": 0,
    "p1_run_hr": 0,
    "p2_run_min": 0,
    "p2_run_hr": 0,
    "p3_run_min": 0,
    "p3_run_hr": 0,
    "f1_run_min": 0,
    "f1_run_hr": 0,
    "f2_run_min": 0,
    "f2_run_hr": 0,
    "f3_run_min": 0,
    "f3_run_hr": 0,
    "f4_run_min": 0,
    "f4_run_hr": 0,
    "f5_run_min": 0,
    "f5_run_hr": 0,
    "f6_run_min": 0,
    "f6_run_hr": 0,
    "f7_run_min": 0,
    "f7_run_hr": 0,
    "f8_run_min": 0,
    "f8_run_hr": 0,
    "filter_run_min":0,
    "filter_run_hr":0,
}

reset_current_btn = {"status": False, "press_reset": False}


sensor_factor = {
    "Temp_ClntSply": 0,
    "Temp_ClntSplySpare": 0,
    "Temp_ClntRtn": 0,
    "Temp_ClntRtnSpare": 0,
    "Prsr_ClntSply": 0,
    "Prsr_ClntSplySpare": 0,
    "Prsr_ClntRtn": 0,
    "Prsr_ClntRtnSpare": 0,
    "Prsr_FltIn": 0,
    "Prsr_FltOut": 0,
    "Clnt_Flow": 0,
    "AmbientTemp": 0,
    "RelativeHumid": 0,
    "DewPoint": 0,
    "pH": 0,
    "Cdct": 0,
    "Tbd": 0,
    "Power": 0,
    "AC": 0,
    "Heat_Capacity": 0,
}

sensor_offset = {
    "Temp_ClntSply": 0,
    "Temp_ClntSplySpare": 0,
    "Temp_ClntRtn": 0,
    "Temp_ClntRtnSpare": 0,
    "Prsr_ClntSply": 0,
    "Prsr_ClntSplySpare": 0,
    "Prsr_ClntRtn": 0,
    "Prsr_ClntRtnSpare": 0,
    "Prsr_FltIn": 0,
    "Prsr_FltOut": 0,
    "Clnt_Flow": 0,
    "AmbientTemp": 0,
    "RelativeHumid": 0,
    "DewPoint": 0,
    "pH": 0,
    "Cdct": 0,
    "Tbd": 0,
    "Power": 0,
    "AC": 0,
    "Heat_Capacity": 0,
}

mapping = {
    "AmbientTemp": "AmbientTemp",
    "RelativeHumid": "RelativeHumid",
    "DewPoint": "DewPoint",
    "pH": "pH",
    "conductivity": "Cdct",
    "turbidity": "Tbd",
    "inst_power": "Power",
    "Inv1_Freq": "Inv1_Freq",
    "Inv2_Freq": "Inv2_Freq",
    "Inv3_Freq": "Inv3_Freq",
    "average_current": "AC",
    "Fan1Com": "fan_freq1",
    "Fan2Com": "fan_freq2",
    "Fan3Com": "fan_freq3",
    "Fan4Com": "fan_freq4",
    "Fan5Com": "fan_freq5",
    "Fan6Com": "fan_freq6",
    "Fan7Com": "fan_freq7",
    "Fan8Com": "fan_freq8",
}

all_sensors_dict = {
    "Temp_ClntSply": 0,
    "Temp_ClntSplySpare": 0,
    "Temp_ClntRtn": 0,
    "Temp_ClntRtnSpare": 0,
    "space": 0,
    "Prsr_ClntSply": 0,
    "Prsr_ClntSplySpare": 0,
    "Prsr_ClntRtn": 0,
    "Prsr_ClntRtnSpare": 0,
    "Prsr_FltIn": 0,
    "Prsr_FltOut": 0,
    "Clnt_Flow": 0,
    "AmbientTemp": 0,
    "RelativeHumid": 0,
    "DewPoint": 0,
    "pH": 0,
    "Cdct": 0,
    "Tbd": 0,
    "Power": 0,
    "AC": 0,
    "Inv1_Freq": 0,
    "Inv2_Freq": 0,
    "Inv3_Freq": 0,
    "Heat_Capacity": 0,
    "fan_freq1": 0,
    "fan_freq2": 0,
    "fan_freq3": 0,
    "fan_freq4": 0,
    "fan_freq5": 0,
    "fan_freq6": 0,
    "fan_freq7": 0,
    "fan_freq8": 0,
}


thrshd_data = {
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
    # "Delay_Coolant_Flow_Meter_Communication": 0,
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
}

rack_data = {
    "rack_control": {
        "Rack_1_Enable": False,
        "Rack_2_Enable": False,
        "Rack_3_Enable": False,
        "Rack_4_Enable": False,
        "Rack_5_Enable": False,
        "Rack_6_Enable": False,
        "Rack_7_Enable": False,
        "Rack_8_Enable": False,
        "Rack_9_Enable": False,
        "Rack_10_Enable": False,
        "Rack_1_Control": False,
        "Rack_2_Control": False,
        "Rack_3_Control": False,
        "Rack_4_Control": False,
        "Rack_5_Control": False,
        "Rack_6_Control": False,
        "Rack_7_Control": False,
        "Rack_8_Control": False,
        "Rack_9_Control": False,
        "Rack_10_Control": False,
    },
    "rack_pass": {
        "Rack_1_Pass": False,
        "Rack_2_Pass": False,
        "Rack_3_Pass": False,
        "Rack_4_Pass": False,
        "Rack_5_Pass": False,
        "Rack_6_Pass": False,
        "Rack_7_Pass": False,
        "Rack_8_Pass": False,
        "Rack_9_Pass": False,
        "Rack_10_Pass": False,
    },
    "rack_opening": 0,
}


status_data = {
    "TempClntSply": 0,
    "TempClntSplySpare": 0,
    "TempClntRtn": 0,
    "TempClntRtnSpare": 0,
    "space": 0,
    "PrsrClntSply": 0,
    "PrsrClntSplySpare": 0,
    "PrsrClntRtn": 0,
    "PrsrClntRtnSpare": 0,
    "PrsrFltIn": 0,
    "PrsrFltOut": 0,
    "ClntFlow": 0,
    "AmbientTemp": 0,
    "RelativeHumid": 0,
    "DewPoint": 0,
    "pH": 0,
    "Cdct": 0,
    "Tbt": 0,
    "Power": 0,
    "AC": 0,
    "Inv1_Freq": 0,
    "Inv2_Freq": 0,
    "Inv3_Freq": 0,
    "Heat_Capacity": 0,
    "fan_freq1": 0,
    "fan_freq2": 0,
    "fan_freq3": 0,
    "fan_freq4": 0,
    "fan_freq5": 0,
    "fan_freq6": 0,
    "fan_freq7": 0,
    "fan_freq8": 0,
}


time_data = {
    "start": {
        "W_TempClntSply": 0,
        "W_TempClntSplySpare": 0,
        "W_TempClntRtn": 0,
        "W_TempClntRtnSpare": 0,
        "W_PrsrClntSply": 0,
        "W_PrsrClntSplySpare": 0,
        "W_PrsrClntRtn": 0,
        "W_PrsrClntRtnSpare": 0,
        "W_PrsrFltIn": 0,
        "W_PrsrFltOut": 0,
        "W_ClntFlow": 0,
        "W_AmbientTemp": 0,
        "W_RelativeHumid": 0,
        "W_DewPoint": 0,
        "W_pH": 0,
        "W_Cdct": 0,
        "W_Tbt": 0,
        "W_AC": 0,
        "W_Power": 0,
        "W_HeatCapacity": 0,
        "A_TempClntSply": 0,
        "A_TempClntSplySpare": 0,
        "A_TempClntRtn": 0,
        "A_TempClntRtnSpare": 0,
        "A_PrsrClntSply": 0,
        "A_PrsrClntSplySpare": 0,
        "A_PrsrClntRtn": 0,
        "A_PrsrClntRtnSpare": 0,
        "A_PrsrFltIn": 0,
        "A_PrsrFltOut": 0,
        "A_ClntFlow": 0,
        "A_AmbientTemp": 0,
        "A_RelativeHumid": 0,
        "A_DewPoint": 0,
        "A_pH": 0,
        "A_Cdct": 0,
        "A_Tbt": 0,
        "A_AC": 0,
        "A_Power": 0,
        "A_HeatCapacity": 0,
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
        # "Delay_Coolant_Flow_Meter_Communication": 0,
        "Delay_AmbientTemp_Communication": 0,
        "Delay_RelativeHumid_Communication": 0,
        "Delay_DewPoint_Communication": 0,
        "Delay_Conductivity_Sensor_Communication": 0,
        "Delay_pH_Sensor_Communication": 0,
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
    },
    "end": {
        "W_TempClntSply": 0,
        "W_TempClntSplySpare": 0,
        "W_TempClntRtn": 0,
        "W_TempClntRtnSpare": 0,
        "W_PrsrClntSply": 0,
        "W_PrsrClntSplySpare": 0,
        "W_PrsrClntRtn": 0,
        "W_PrsrClntRtnSpare": 0,
        "W_PrsrFltIn": 0,
        "W_PrsrFltOut": 0,
        "W_ClntFlow": 0,
        "W_AmbientTemp": 0,
        "W_RelativeHumid": 0,
        "W_DewPoint": 0,
        "W_pH": 0,
        "W_Cdct": 0,
        "W_Tbt": 0,
        "W_AC": 0,
        "W_Power": 0,
        "W_HeatCapacity": 0,
        "A_TempClntSply": 0,
        "A_TempClntSplySpare": 0,
        "A_TempClntRtn": 0,
        "A_TempClntRtnSpare": 0,
        "A_PrsrClntSply": 0,
        "A_PrsrClntSplySpare": 0,
        "A_PrsrClntRtn": 0,
        "A_PrsrClntRtnSpare": 0,
        "A_PrsrFltIn": 0,
        "A_PrsrFltOut": 0,
        "A_ClntFlow": 0,
        "A_AmbientTemp": 0,
        "A_RelativeHumid": 0,
        "A_DewPoint": 0,
        "A_pH": 0,
        "A_Cdct": 0,
        "A_Tbt": 0,
        "A_AC": 0,
        "A_Power": 0,
        "A_HeatCapacity": 0,
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
        # "Delay_Coolant_Flow_Meter_Communication": 0,
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
    },
    "check": {
        "W_TempClntSply": 0,
        "W_TempClntSplySpare": 0,
        "W_TempClntRtn": 0,
        "W_TempClntRtnSpare": 0,
        "W_PrsrClntSply": 0,
        "W_PrsrClntSplySpare": 0,
        "W_PrsrClntRtn": 0,
        "W_PrsrClntRtnSpare": 0,
        "W_PrsrFltIn": 0,
        "W_PrsrFltOut": 0,
        "W_ClntFlow": 0,
        "W_AmbientTemp": 0,
        "W_RelativeHumid": 0,
        "W_DewPoint": 0,
        "W_pH": 0,
        "W_Cdct": 0,
        "W_Tbt": 0,
        "W_AC": 0,
        "W_Power": 0,
        "W_HeatCapacity": 0,
        "A_TempClntSply": 0,
        "A_TempClntSplySpare": 0,
        "A_TempClntRtn": 0,
        "A_TempClntRtnSpare": 0,
        "A_PrsrClntSply": 0,
        "A_PrsrClntSplySpare": 0,
        "A_PrsrClntRtn": 0,
        "A_PrsrClntRtnSpare": 0,
        "A_PrsrFltIn": 0,
        "A_PrsrFltOut": 0,
        "A_ClntFlow": 0,
        "A_AmbientTemp": 0,
        "A_RelativeHumid": 0,
        "A_DewPoint": 0,
        "A_pH": 0,
        "A_Cdct": 0,
        "A_Tbt": 0,
        "A_AC": 0,
        "A_Power": 0,
        "A_HeatCapacity": 0,
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
        # "Delay_Coolant_Flow_Meter_Communication": 0,
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
    },
    "condition": {
        "low": {
            "W_pH": False,
            "W_AmbientTemp": False,
            "W_RelativeHumid": False,
            "W_DewPoint": False,
            "W_PrsrFltIn": False,
            "W_Cdct": False,
            "W_Tbt": False,
            "A_pH": False,
            "A_Cdct": False,
            "A_Tbt": False,
            "A_AmbientTemp": False,
            "A_RelativeHumid": False,
            "A_PrsrFltIn": False,
        },
        "high": {
            "W_pH": False,
            "W_AmbientTemp": False,
            "W_RelativeHumid": False,
            "W_DewPoint": False,
            "W_PrsrFltIn": False,
            "W_Cdct": False,
            "W_Tbt": False,
            "A_pH": False,
            "A_Cdct": False,
            "A_Tbt": False,
            "A_AmbientTemp": False,
            "A_RelativeHumid": False,
            "A_PrsrFltIn": False,
        },
    },
}


overload_error = {
    "Inv1_OverLoad": False,
    "Inv2_OverLoad": False,
    "Inv3_OverLoad": False,
    "Fan_OverLoad1": False,
    "Fan_OverLoad2": False,
}


restart_server = {"stage": 0, "start": 0, "diff": 0}

server_error = {"start": 0, "diff": 0}


warning_data = {
    "warning": {
        "TempClntSply_High": False,
        "TempClntSplySpare_High": False,
        "TempClntRtn_High": False,
        "TempClntRtnSpare_High": False,
        "PrsrClntSply_High": False,
        "PrsrClntSplySpare_High": False,
        "PrsrClntRtn_High": False,
        "PrsrClntRtnSpare_High": False,
        "PrsrFltIn_Low": False,
        "PrsrFltIn_High": False,
        "PrsrFltOut_High": False,
        "ClntFlow_Low": False,
        "AmbientTemp_Low": False,
        "AmbientTemp_High": False,
        "RelativeHumid_Low": False,
        "RelativeHumid_High": False,
        "DewPoint_Low": False,
        "pH_Low": False,
        "pH_High": False,
        "Cdct_Low": False,
        "Cdct_High": False,
        "Tbt_Low": False,
        "Tbt_High": False,
        "AC_High": False,
    },
    "alert": {
        "TempClntSply_High": False,
        "TempClntSplySpare_High": False,
        "TempClntRtn_High": False,
        "TempClntRtnSpare_High": False,
        "PrsrClntSply_High": False,
        "PrsrClntSplySpare_High": False,
        "PrsrClntRtn_High": False,
        "PrsrClntRtnSpare_High": False,
        "PrsrFltIn_Low": False,
        "PrsrFltIn_High": False,
        "PrsrFltOut_High": False,
        "ClntFlow_Low": False,
        "AmbientTemp_Low": False,
        "AmbientTemp_High": False,
        "RelativeHumid_Low": False,
        "RelativeHumid_High": False,
        "DewPoint_Low": False,
        "pH_Low": False,
        "pH_High": False,
        "Cdct_Low": False,
        "Cdct_High": False,
        "Tbt_Low": False,
        "Tbt_High": False,
        "AC_High": False,
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
        "ATS1_Error": False,
        "Inv1_Freq_communication": 0,
        "Inv2_Freq_communication": 0,
        "Inv3_Freq_communication": 0,
        # "coolant_flow_rate_communication": False,
        "AmbientTemp_communication": False,
        "RelativeHumid_communication": False,
        "DewPoint_communication": False,
        "pH_communication": False,
        "conductivity_communication": False,
        "turbidity_communication": False,
        "ATS1_communication": False,
        "ATS2_communication": False,
        "inst_power_communication": False,
        "average_current_communication": False,
        "Fan1Com_communication": False,
        "Fan2Com_communication": False,
        "Fan3Com_communication": False,
        "Fan4Com_communication": False,
        "Fan5Com_communication": False,
        "Fan6Com_communication": False,
        "Fan7Com_communication": False,
        "Fan8Com_communication": False,
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
    },
}

dpt_error_setting = {
    "t1": 0,
}

ats_status = {
    "ATS1": False,
    "ATS2": False,
}

level_sw = {
    "level1": None,
    "level2": None,
    "level3": None,
    "power24v1": None,
    "power24v2": None,
    "power12v1": None,
    "power12v2": None,
}

fan_raw_status = {
    "error": {
        "Fan1": 0,
        "Fan2": 0,
        "Fan3": 0,
        "Fan4": 0,
        "Fan5": 0,
        "Fan6": 0,
        "Fan7": 0,
        "Fan8": 0,
    },
    "warning": {
        "Fan1": 0,
        "Fan2": 0,
        "Fan3": 0,
        "Fan4": 0,
        "Fan5": 0,
        "Fan6": 0,
        "Fan7": 0,
        "Fan8": 0,
    },
    "current_power": {
        "Fan1": 0,
        "Fan2": 0,
        "Fan3": 0,
        "Fan4": 0,
        "Fan5": 0,
        "Fan6": 0,
        "Fan7": 0,
        "Fan8": 0,
    },
    "max_rpm": {
        "Fan1": 0,
        "Fan2": 0,
        "Fan3": 0,
        "Fan4": 0,
        "Fan5": 0,
        "Fan6": 0,
        "Fan7": 0,
        "Fan8": 0,
    },
    "actual_rpm": {
        "Fan1": 0,
        "Fan2": 0,
        "Fan3": 0,
        "Fan4": 0,
        "Fan5": 0,
        "Fan6": 0,
        "Fan7": 0,
        "Fan8": 0,
    },
    "cvt_rpm": {
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

temporary_data = {
    "raw_value": {
        "command_pressure": 0,
        "feedback_pressure": 0,
        "pressure_output": 0,
        "command_temperature": 0,
        "feedback_temperature": 0,
        "temperature_output": 0,
    },
    "cvt_value": {
        "command_pressure": 0,
        "feedback_pressure": 0,
        "pressure_output": 0,
        "command_temperature": 0,
        "feedback_temperature": 0,
        "temperature_output": 0,
    },
}

def save_fans_status():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            registers = []
            for key in fan_raw_status["error"]:
                registers.append(fan_raw_status["error"][key])
            for key in fan_raw_status["warning"]:
                registers.append(fan_raw_status["warning"][key])
            client.write_registers(2500, registers)
    except Exception as e:
        print(f"save fan status error:{e}")


def check_inverter(inv):
    return (
        warning_data["error"][f"{inv}_Error"]
        or warning_data["error"][f"{inv}_OverLoad"]
        or warning_data["error"][f"{inv}_Freq_communication"]
    )


def combine_bits(lower, upper):
    value = (upper << 16) | lower
    return value


def read_split_register(r, i):
    lower_16 = r[i]
    upper_16 = r[i + 1]
    value = combine_bits(lower_16, upper_16)
    return value


def split_double(Dword_list):
    registers = []

    for d in Dword_list:
        lower_16 = d & 0xFFFF
        upper_16 = (d >> 16) & 0xFFFF

        registers.append(lower_16)
        registers.append(upper_16)
    return registers


def cvt_registers_to_float(reg1, reg2):
    temp1 = [reg1, reg2]
    decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
        temp1, byteorder=Endian.Big, wordorder=Endian.Little
    )
    decoded_value_big_endian = decoder_big_endian.decode_32bit_float()
    return decoded_value_big_endian


def cvt_float_byte(value):
    float_as_bytes = struct.pack(">f", float(value))
    word1, word2 = struct.unpack(">HH", float_as_bytes)
    return word1, word2

###改變現在狀態(未送出給寄存器)
def change_progress(key, status):
    if status == "standby":
        inspection_data["prog"][key] = 4

    elif status == "finish":
        inspection_data["prog"][key] = 2

    elif status == "skip":
        inspection_data["prog"][key] = 5

    elif status == "cancel":
        inspection_data["prog"][key] = 1


###給寄存器inspection現在的狀態及結果
def send_all(number, key):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            # client.write_registers((800 + number), inspection_data["prog"][key])
            client.write_registers((2100 + number), inspection_data["prog"][key])

            result = [1 if inspection_data["result"][key] else 0]
            # client.write_registers((750 + number), result)

            client.write_registers((2000 + number), result)
    except Exception as e:
        print(f"result write-in:{e}")

###給寄存器inspection現在的狀態
def send_progress(number, key):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            # client.write_registers((800 + number), inspection_data["prog"][key])
            client.write_registers((2100 + number), inspection_data["prog"][key])
    except Exception as e:
        print(f"result write-in:{e}")
        
        
# def send_all_overload(number, key):
#     try:
#         with ModbusTcpClient(
#             host=modbus_host, port=modbus_port, unit=modbus_slave_id
#         ) as client:
#             # client.write_registers((800 + number), inspection_data["prog"][key])
#             client.write_registers((2100 + number), inspection_data["prog"][key])

#             result = 3
#             # client.write_registers((750 + number), result)
#             client.write_registers((2000 + number), result)
#     except Exception as e:
#         print(f"result write-in:{e}")




def thr_check():
    global thrshd_data
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            thr_reg = (sum(1 for key in thrshd_data if "Thr_" in key)) * 2
            delay_reg = sum(1 for key in thrshd_data if "Delay_" in key)
            start_address = 1000
            total_registers = thr_reg
            read_num = 120

            for counted_num in range(0, total_registers, read_num):
                count = min(read_num, total_registers - counted_num)
                result = client.read_holding_registers(
                    start_address + counted_num, count, unit=modbus_slave_id
                )

                if result.isError():
                    print(f"Modbus Errorxxx: {result}")
                    continue
                else:
                    keys_list = list(thrshd_data.keys())
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
                            thrshd_data[keys_list[j]] = decoded_value_big_endian
                            j += 1

            result = client.read_holding_registers(
                1000 + thr_reg, delay_reg, unit=modbus_slave_id
            )

            if result.isError():
                print(f"Modbus Error: {result}")
            else:
                keys_list = list(thrshd_data.keys())
                j = int(thr_reg / 2)
                for i in range(0, delay_reg):
                    thrshd_data[keys_list[j]] = result.registers[i]
                    j += 1
    except Exception as e:
        print(f"thrshd check error：{e}")


def status_check():
    global status_data
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            ad_count = len(ad_sensor_value.keys())
            serial_count = len(serial_sensor_value.keys())
            all_count = (ad_count * 2) + (serial_count * 2)
            # print(f"allcount:{all_count}")

            r = client.read_holding_registers(5000, all_count, unit=modbus_slave_id)

            if r.isError():
                print(f"modbus error:{r}")
            else:
                key_list = list(status_data.keys())
                # print(f"key_list:{key_list}")

                j = 0

                for i in range(0, all_count, 2):
                    temp1 = [r.registers[i], r.registers[i + 1]]
                    decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
                        temp1, byteorder=Endian.Big, wordorder=Endian.Little
                    )
                    decoded_value_big_endian = decoder_big_endian.decode_32bit_float()
                    status_data[key_list[j]] = decoded_value_big_endian
                    # print(f"{[key_list[j]]}:{status_data[key_list[j]]}")
                    j += 1

    except Exception as e:
        print(f"read status data error：{e}")


def check_input(delay, value_key, criteria):
    if criteria:
        try:
            if time_data["check"][delay]:
                if not bit_input_regs[value_key]:
                    time_data["check"][delay] = False
                    warning_data["error"][value_key] = False
                else:
                    time_data["end"][delay] = time.perf_counter()

                    passed_time = time_data["end"][delay] - time_data["start"][delay]

                    if passed_time > thrshd_data[delay]:
                        warning_data["error"][value_key] = True
            else:
                if bit_input_regs[value_key]:
                    time_data["start"][delay] = time.perf_counter()
                    time_data["check"][delay] = True
                else:
                    warning_data["error"][value_key] = False
        except Exception as e:
            print(f"check error：{e}")
    else:
        try:
            if time_data["check"][delay]:
                if bit_input_regs[value_key]:
                    time_data["check"][delay] = False
                    warning_data["error"][value_key] = False
                else:
                    time_data["end"][delay] = time.perf_counter()

                    passed_time = time_data["end"][delay] - time_data["start"][delay]

                    if passed_time > thrshd_data[delay]:
                        warning_data["error"][value_key] = True
            else:
                if not bit_input_regs[value_key]:
                    time_data["start"][delay] = time.perf_counter()
                    time_data["check"][delay] = True
                else:
                    warning_data["error"][value_key] = False
        except Exception as e:
            print(f"check error：{e}")


def check_high_warning(thr_key, rst_key, delay_key, type):
    short_key = thr_key.split("_")[2]

    prefix = "W_" if type == "W" else "A_"

    try:
        if time_data["check"][prefix + short_key]:
            if status_data[short_key] < thrshd_data[rst_key]:
                time_data["check"][prefix + short_key] = False
                if prefix.startswith("W_"):
                    warning_data["warning"][short_key + "_High"] = False
                else:
                    warning_data["alert"][short_key + "_High"] = False
                return False
            else:
                time_data["end"][prefix + short_key] = time.perf_counter()

                passed_time = (
                    time_data["end"][prefix + short_key]
                    - time_data["start"][prefix + short_key]
                )

                if passed_time > thrshd_data[delay_key]:
                    if prefix.startswith("W_"):
                        warning_data["warning"][short_key + "_High"] = True
                    else:
                        warning_data["alert"][short_key + "_High"] = True

                    return True
        else:
            if status_data[short_key] > thrshd_data[thr_key]:
                time_data["start"][prefix + short_key] = time.perf_counter()
                time_data["check"][prefix + short_key] = True
            else:
                time_data["check"][prefix + short_key] = False
                if prefix.startswith("W_"):
                    warning_data["warning"][short_key + "_High"] = False
                else:
                    warning_data["alert"][short_key + "_High"] = False
                return False
    except Exception as e:
        print(f"high warning check error：{e}")


def check_low_warning(thr_key, rst_key, delay_key, type):
    short_key = thr_key.split("_")[2]

    prefix = "W_" if type == "W" else "A_"

    try:
        if time_data["check"][prefix + short_key]:
            if status_data[short_key] > thrshd_data[rst_key]:
                time_data["check"][prefix + short_key] = False
                if prefix.startswith("W_"):
                    warning_data["warning"][short_key + "_Low"] = False
                else:
                    warning_data["alert"][short_key + "_Low"] = False
                return False
            else:
                time_data["end"][prefix + short_key] = time.perf_counter()

                passed_time = (
                    time_data["end"][prefix + short_key]
                    - time_data["start"][prefix + short_key]
                )

                if passed_time > thrshd_data[delay_key]:
                    if prefix.startswith("W_"):
                        warning_data["warning"][short_key + "_Low"] = True
                    else:
                        warning_data["alert"][short_key + "_Low"] = True
                    return True
        else:
            if status_data[short_key] < thrshd_data[thr_key]:
                time_data["start"][prefix + short_key] = time.perf_counter()
                time_data["check"][prefix + short_key] = True
            else:
                if prefix.startswith("W_"):
                    warning_data["warning"][short_key + "_Low"] = False
                else:
                    warning_data["alert"][short_key + "_Low"] = False
                return False
    except Exception as e:
        print(f"low warning check error：{e}")


def check_both_warning_p3(
    thr_key_low, thr_key_high, rst_key_low, rst_key_high, delay_key, type
):
    short_key = thr_key_low.split("_")[2]
    status = status_data[short_key]
    # inv["inv1"] = True
    prefix = "W_" if type == "W" else "A_"
    try:
        if time_data["check"][prefix + short_key]:
            if (
                thrshd_data[rst_key_low] < status and status < thrshd_data[rst_key_high]
            ) or (not inv["inv1"] and not inv["inv2"] and not inv["inv3"]):
                time_data["check"][prefix + short_key] = False
                time_data["condition"]["high"][prefix + short_key] = False
                time_data["condition"]["low"][prefix + short_key] = False

            else:
                if status > thrshd_data[thr_key_high]:
                    time_data["end"][prefix + short_key] = time.perf_counter()

                    passed_time = (
                        time_data["end"][prefix + short_key]
                        - time_data["start"][prefix + short_key]
                    )

                    if passed_time > thrshd_data[delay_key]:
                        time_data["condition"]["high"][prefix + short_key] = True

                if status < thrshd_data[thr_key_low]:
                    time_data["end"][prefix + short_key] = time.perf_counter()
                    passed_time = (
                        time_data["end"][prefix + short_key]
                        - time_data["start"][prefix + short_key]
                    )
                    if passed_time > thrshd_data[delay_key]:
                        time_data["condition"]["low"][prefix + short_key] = True
        else:
            if (
                status > thrshd_data[thr_key_high] or status < thrshd_data[thr_key_low]
            ) and (inv["inv1"] or inv["inv2"] or inv["inv3"]):
                time_data["start"][prefix + short_key] = time.perf_counter()
                time_data["check"][prefix + short_key] = True
            else:
                time_data["condition"]["high"][prefix + short_key] = False
                time_data["condition"]["low"][prefix + short_key] = False

        if time_data["condition"]["high"][prefix + short_key]:
            if prefix.startswith("W_"):
                warning_data["warning"][short_key + "_High"] = True
            else:
                warning_data["alert"][short_key + "_High"] = True

        if time_data["condition"]["low"][prefix + short_key]:
            if prefix.startswith("W_"):
                warning_data["warning"][short_key + "_Low"] = True
            else:
                warning_data["alert"][short_key + "_Low"] = True

        if (
            not time_data["condition"]["high"][prefix + short_key]
            and not time_data["condition"]["low"][prefix + short_key]
        ):
            if prefix.startswith("W_"):
                warning_data["warning"][short_key + "_High"] = False
                warning_data["warning"][short_key + "_Low"] = False
            else:
                warning_data["alert"][short_key + "_High"] = False
                warning_data["alert"][short_key + "_Low"] = False

    except Exception as e:
        print(f"check both warning error：{e}")


def check_low_warning_f1(thr_key, rst_key, delay_key, type):
    short_key = "ClntFlow"

    prefix = "W_" if type == "W" else "A_"

    try:
        if time_data["check"][prefix + short_key]:
            if (status_data[short_key] > thrshd_data[rst_key]) or (
                not inv["inv1"] and not inv["inv2"] and not inv["inv3"]
            ):
                time_data["check"][prefix + short_key] = False
                if prefix.startswith("W_"):
                    warning_data["warning"][short_key + "_Low"] = False
                else:
                    warning_data["alert"][short_key + "_Low"] = False
                return False
            else:
                time_data["end"][prefix + short_key] = time.perf_counter()

                passed_time = (
                    time_data["end"][prefix + short_key]
                    - time_data["start"][prefix + short_key]
                )

                if passed_time > thrshd_data[delay_key]:
                    if prefix.startswith("W_"):
                        warning_data["warning"][short_key + "_Low"] = True
                    else:
                        warning_data["alert"][short_key + "_Low"] = True

                    return True
        else:
            if (status_data[short_key] < thrshd_data[thr_key]) and (
                inv["inv1"] or inv["inv2"] or inv["inv3"]
            ):
                time_data["start"][prefix + short_key] = time.perf_counter()
                time_data["check"][prefix + short_key] = True
            else:
                if prefix.startswith("W_"):
                    warning_data["warning"][short_key + "_Low"] = False
                else:
                    warning_data["alert"][short_key + "_Low"] = False
                return False
    except Exception as e:
        print(f"low warning check error：{e}")


def check_both_warning(
    thr_key_low, thr_key_high, rst_key_low, rst_key_high, delay_key, type
):
    short_key = thr_key_low.split("_")[2]
    status = status_data[short_key]

    prefix = "W_" if type == "W" else "A_"

    try:
        if time_data["check"][prefix + short_key]:
            if thrshd_data[rst_key_low] < status and status < thrshd_data[rst_key_high]:
                time_data["check"][prefix + short_key] = False
                time_data["condition"]["high"][prefix + short_key] = False
                time_data["condition"]["low"][prefix + short_key] = False

            else:
                if status > thrshd_data[thr_key_high]:
                    time_data["end"][prefix + short_key] = time.perf_counter()

                    passed_time = (
                        time_data["end"][prefix + short_key]
                        - time_data["start"][prefix + short_key]
                    )

                    if passed_time > thrshd_data[delay_key]:
                        time_data["condition"]["high"][prefix + short_key] = True

                if status < thrshd_data[thr_key_low]:
                    time_data["end"][prefix + short_key] = time.perf_counter()
                    passed_time = (
                        time_data["end"][prefix + short_key]
                        - time_data["start"][prefix + short_key]
                    )
                    if passed_time > thrshd_data[delay_key]:
                        time_data["condition"]["low"][prefix + short_key] = True

        else:
            if status > thrshd_data[thr_key_high] or status < thrshd_data[thr_key_low]:
                time_data["start"][prefix + short_key] = time.perf_counter()
                time_data["check"][prefix + short_key] = True

        if time_data["condition"]["high"][prefix + short_key]:
            if prefix.startswith("W_"):
                warning_data["warning"][short_key + "_High"] = True
            else:
                warning_data["alert"][short_key + "_High"] = True

        if time_data["condition"]["low"][prefix + short_key]:
            if prefix.startswith("W_"):
                warning_data["warning"][short_key + "_Low"] = True
            else:
                warning_data["alert"][short_key + "_Low"] = True

        if (
            not time_data["condition"]["high"][prefix + short_key]
            and not time_data["condition"]["low"][prefix + short_key]
        ):
            if prefix.startswith("W_"):
                warning_data["warning"][short_key + "_High"] = False
                warning_data["warning"][short_key + "_Low"] = False
            else:
                warning_data["alert"][short_key + "_High"] = False
                warning_data["alert"][short_key + "_Low"] = False

    except Exception as e:
        print(f"check both warning error：{e}")


def check_overload_error(delay):
    short_key = delay.replace("Delay_", "")

    try:
        if time_data["check"][delay]:
            if not overload_error[short_key]:
                time_data["check"][delay] = False
                warning_data["error"][short_key] = False
            else:
                time_data["end"][delay] = time.perf_counter()

                passed_time = time_data["end"][delay] - time_data["start"][delay]

                if passed_time > thrshd_data[delay]:
                    warning_data["error"][short_key] = True
        else:
            if overload_error[short_key]:
                time_data["start"][delay] = time.perf_counter()
                time_data["check"][delay] = True
            else:
                warning_data["error"][short_key] = False
    except Exception as e:
        print(f"inverter overload error：{e}")


def check_ATS(delay):
    try:
        if time_data["check"][delay]:
            if ats_status["ATS1"]:
                warning_data["error"]["ATS1_Error"] = False
                time_data["check"][delay] = False
                return False
            else:
                time_data["end"][delay] = time.perf_counter()

                passed_time = time_data["end"][delay] - time_data["start"][delay]

                if passed_time > thrshd_data[delay]:
                    warning_data["error"]["ATS1_Error"] = True
                    return True
        else:
            if not ats_status["ATS1"]:
                time_data["start"][delay] = time.perf_counter()
                time_data["check"][delay] = True
            else:
                warning_data["error"]["ATS1_Error"] = False
                return False
    except Exception as e:
        print(f"ats check error：{e}")


def check_level(delay, value_key, criteria):
    if criteria:
        try:
            if time_data["check"][delay]:
                if level_sw[value_key]:
                    time_data["check"][delay] = False
                    warning_data["error"][value_key] = False
                else:
                    time_data["end"][delay] = time.perf_counter()

                    passed_time = time_data["end"][delay] - time_data["start"][delay]

                    if passed_time > thrshd_data[delay]:
                        warning_data["error"][value_key] = True
            else:
                if not level_sw[value_key]:
                    time_data["start"][delay] = time.perf_counter()
                    time_data["check"][delay] = True
                else:
                    warning_data["error"][value_key] = False
        except Exception as e:
            print(f"check level error：{e}")
    else:
        try:
            if time_data["check"][delay]:
                if not level_sw[value_key]:
                    time_data["check"][delay] = False
                    warning_data["error"][value_key] = False
                else:
                    time_data["end"][delay] = time.perf_counter()

                    passed_time = time_data["end"][delay] - time_data["start"][delay]

                    if passed_time > thrshd_data[delay]:
                        warning_data["error"][value_key] = True
            else:
                if level_sw[value_key]:
                    time_data["start"][delay] = time.perf_counter()
                    time_data["check"][delay] = True
                else:
                    warning_data["error"][value_key] = False
        except Exception as e:
            print(f"check level error：{e}")


def check_pressure_diff_error(thr_key, rst_key, delay_key, type):
    short_key = thr_key.split("_")[2]

    if type == "W":
        prefix = "W_"
    elif type == "A":
        prefix = "A_"

    try:
        if time_data["check"][prefix + short_key]:
            if (status_data["PrsrFltIn"] - status_data[short_key]) < thrshd_data[
                rst_key
            ]:
                time_data["check"][prefix + short_key] = False
                if prefix.startswith("W_"):
                    warning_data["warning"][short_key + "_High"] = False
                else:
                    warning_data["alert"][short_key + "_High"] = False
                return False
            else:
                time_data["end"][prefix + short_key] = time.perf_counter()

                passed_time = (
                    time_data["end"][prefix + short_key]
                    - time_data["start"][prefix + short_key]
                )

                if passed_time > thrshd_data[delay_key]:
                    if prefix.startswith("W_"):
                        warning_data["warning"][short_key + "_High"] = True
                    else:
                        warning_data["alert"][short_key + "_High"] = True
                    return True
        else:
            if (status_data["PrsrFltIn"] - status_data[short_key]) > thrshd_data[
                thr_key
            ]:
                time_data["start"][prefix + short_key] = time.perf_counter()
                time_data["check"][prefix + short_key] = True
            else:
                warning_data[short_key + "_High"] = False
                return False
    except Exception as e:
        print(f"inlet outlet warning error：{e}")


def check_communication(short_key, delay, criteria):
    if criteria:
        try:
            if time_data["check"][delay]:
                if not raw_485_comm[short_key]:
                    time_data["check"][delay] = False
                    warning_data["error"][short_key + "_communication"] = False
                else:
                    time_data["end"][delay] = time.perf_counter()

                    passed_time = time_data["end"][delay] - time_data["start"][delay]

                    if passed_time > thrshd_data[delay]:
                        warning_data["error"][short_key + "_communication"] = True
            else:
                if raw_485_comm[short_key]:
                    time_data["start"][delay] = time.perf_counter()
                    time_data["check"][delay] = True
                else:
                    warning_data["error"][short_key + "_communication"] = False
        except Exception as e:
            print(f"communication error：{e}")
    else:
        try:
            if time_data["check"][delay]:
                if raw_485_comm[short_key]:
                    time_data["check"][delay] = False
                    warning_data["error"][short_key + "_communication"] = False
                else:
                    time_data["end"][delay] = time.perf_counter()

                    passed_time = time_data["end"][delay] - time_data["start"][delay]

                    if passed_time > thrshd_data[delay]:
                        warning_data["error"][short_key + "_communication"] = True
            else:
                if not raw_485_comm[short_key]:
                    time_data["start"][delay] = time.perf_counter()
                    time_data["check"][delay] = True
                else:
                    warning_data["error"][short_key + "_communication"] = False
        except Exception as e:
            print(f"communication error：{e}")


def check_broken(key):
    broken_mapping = {
        "Temp_ClntSply": "Delay_TempClntSply_broken",
        "Temp_ClntSplySpare": "Delay_TempClntSplySpare_broken",
        "Temp_ClntRtn": "Delay_TempClntRtn_broken",
        "Temp_ClntRtnSpare": "Delay_TempClntRtnSpare_broken",
        "Prsr_ClntSply": "Delay_PrsrClntSply_broken",
        "Prsr_ClntSplySpare": "Delay_PrsrClntSplySpare_broken",
        "Prsr_ClntRtn": "Delay_PrsrClntRtn_broken",
        "Prsr_ClntRtnSpare": "Delay_PrsrClntRtnSpare_broken",
        "Prsr_FltIn": "Delay_PrsrFltIn_broken",
        "Prsr_FltOut": "Delay_PrsrFltOut_broken",
        "Clnt_Flow": "Delay_Clnt_Flow_broken",
    }

    delay_key = broken_mapping[key]
    error_key = f"{key}_broken"

    if "Temp" in key:
        try:
            if time_data["check"][delay_key]:
                if sensor_raw[key] < 1000 and sensor_raw[key] > -100:
                    time_data["check"][delay_key] = False
                    warning_data["error"][error_key] = False
                else:
                    time_data["end"][delay_key] = time.perf_counter()

                    passed_time = (
                        time_data["end"][delay_key] - time_data["start"][delay_key]
                    )

                    if passed_time > thrshd_data[delay_key]:
                        warning_data["error"][error_key] = True
            else:
                if sensor_raw[key] > 1000 or sensor_raw[key] < -100:
                    time_data["start"][delay_key] = time.perf_counter()
                    time_data["check"][delay_key] = True
                else:
                    warning_data["error"][error_key] = False
        except Exception as e:
            print(f"broken temp error：{e}")

    elif "Prsr" in key:
        try:
            if time_data["check"][delay_key]:
                if sensor_raw[key] > 1200:
                    time_data["check"][delay_key] = False
                    warning_data["error"][error_key] = False
                else:
                    time_data["end"][delay_key] = time.perf_counter()

                    passed_time = (
                        time_data["end"][delay_key] - time_data["start"][delay_key]
                    )

                    if passed_time > thrshd_data[delay_key]:
                        warning_data["error"][error_key] = True
            else:
                if sensor_raw[key] < 1200:
                    time_data["start"][delay_key] = time.perf_counter()
                    time_data["check"][delay_key] = True
                else:
                    warning_data["error"][error_key] = False
        except Exception as e:
            print(f"broken prsr error：{e}")

    if key == "Clnt_Flow":
        try:
            if time_data["check"][delay_key]:
                if serial_sensor_value[key] > 1000 and serial_sensor_value[key] < 20000:
                    time_data["check"][delay_key] = False
                    warning_data["error"][error_key] = False
                else:
                    time_data["end"][delay_key] = time.perf_counter()

                    passed_time = (
                        time_data["end"][delay_key] - time_data["start"][delay_key]
                    )

                    if passed_time > thrshd_data[delay_key]:
                        warning_data["error"][error_key] = True
            else:
                if serial_sensor_value[key] < 1000 or serial_sensor_value[key] > 20000:
                    time_data["start"][delay_key] = time.perf_counter()
                    time_data["check"][delay_key] = True
                else:
                    warning_data["error"][error_key] = False
        except Exception as e:
            print(f"broken flow error：{e}")


def check_dewPt_warning(thr_key, rst_key, delay_key, type):
    short_key = thr_key.split("_")[2]

    prefix = "W_" if type == "W" else "A_"

    t1 = warning_data["error"]["Temp_ClntSply_broken"]

    if t1:
        set_data = status_data["TempClntSplySpare"]
    else:
        set_data = status_data["TempClntSply"]

    try:
        if time_data["check"][prefix + short_key]:
            if set_data > status_data[short_key] + thrshd_data[rst_key]:
                time_data["check"][prefix + short_key] = False
                if prefix.startswith("W_"):
                    warning_data["warning"][short_key + "_Low"] = False
                else:
                    warning_data["alert"][short_key + "_Low"] = False
                return False
            else:
                time_data["end"][prefix + short_key] = time.perf_counter()

                passed_time = (
                    time_data["end"][prefix + short_key]
                    - time_data["start"][prefix + short_key]
                )

                if passed_time > thrshd_data[delay_key]:
                    # time_data["check"][prefix + short_key] = False
                    if prefix.startswith("W_"):
                        warning_data["warning"][short_key + "_Low"] = True
                    else:
                        warning_data["alert"][short_key + "_Low"] = True
                    return True
        else:
            if set_data < status_data[short_key] + thrshd_data[thr_key]:
                time_data["start"][prefix + short_key] = time.perf_counter()
                time_data["check"][prefix + short_key] = True
            else:
                if prefix.startswith("W_"):
                    warning_data["warning"][short_key + "_Low"] = False
                else:
                    warning_data["alert"][short_key + "_Low"] = False
                return False
    except Exception as e:
        print(f"check dewPt warning error：{e}")


def set_warning_registers(mode):
    global thrshd_data, status_data, x, warning_light

    ####檢查各上下限並送出警告

    thr_check()
    status_check()

    ###切換水質計開關邏輯
    if not ver_switch["coolant_quality_meter_switch"]:
        check_communication(
            "conductivity", "Delay_Conductivity_Sensor_Communication", True
        )
        check_communication("pH", "Delay_pH_Sensor_Communication", True)
        check_communication("turbidity", "Delay_Turbidity_Sensor_Communication", True)
        check_level("Delay_power12v1", "power12v1", True)
        check_level("Delay_power12v2", "power12v2", True)
        check_both_warning(
            "Thr_W_pH_L",
            "Thr_W_pH_H",
            "Thr_W_Rst_pH_L",
            "Thr_W_Rst_pH_H",
            "Delay_pH",
            "W",
        )

        check_both_warning(
            "Thr_A_pH_L",
            "Thr_A_pH_H",
            "Thr_A_Rst_pH_L",
            "Thr_A_Rst_pH_H",
            "Delay_pH",
            "A",
        )

        check_both_warning(
            "Thr_W_Cdct_L",
            "Thr_W_Cdct_H",
            "Thr_W_Rst_Cdct_L",
            "Thr_W_Rst_Cdct_H",
            "Delay_Cdct",
            "W",
        )

        check_both_warning(
            "Thr_A_Cdct_L",
            "Thr_A_Cdct_H",
            "Thr_A_Rst_Cdct_L",
            "Thr_A_Rst_Cdct_H",
            "Delay_Cdct",
            "A",
        )

        check_both_warning(
            "Thr_W_Tbt_L",
            "Thr_W_Tbt_H",
            "Thr_W_Rst_Tbt_L",
            "Thr_W_Rst_Tbt_H",
            "Delay_Tbt",
            "W",
        )

        check_both_warning(
            "Thr_A_Tbt_L",
            "Thr_A_Tbt_H",
            "Thr_A_Rst_Tbt_L",
            "Thr_A_Rst_Tbt_H",
            "Delay_Tbt",
            "A",
        )
    else:
        ###賦歸回false以免繼續傳warning_data
        warning_data["warning"]["pH_Low"] = False
        warning_data["warning"]["pH_High"] = False
        warning_data["warning"]["Cdct_Low"] = False
        warning_data["warning"]["Cdct_High"] = False
        warning_data["warning"]["Tbt_Low"] = False
        warning_data["warning"]["Tbt_High"] = False

        warning_data["alert"]["pH_Low"] = False
        warning_data["alert"]["pH_High"] = False
        warning_data["alert"]["Cdct_Low"] = False
        warning_data["alert"]["Cdct_High"] = False
        warning_data["alert"]["Tbt_Low"] = False
        warning_data["alert"]["Tbt_High"] = False

        warning_data["error"]["pH_communication"] = False
        warning_data["error"]["conductivity_communication"] = False
        warning_data["error"]["turbidity_communication"] = False
        warning_data["error"]["power12v1"] = False
        warning_data["error"]["power12v2"] = False
    ###切換水質計開關邏輯 結束

    ###切換fan count邏輯
    if ver_switch["fan_count_switch"]:
        check_communication("Fan1Com", "Delay_Fan1Com_Communication", True)
        check_communication("Fan2Com", "Delay_Fan2Com_Communication", True)
        check_communication("Fan3Com", "Delay_Fan3Com_Communication", True)

        check_communication("Fan4Com", "Delay_Fan4Com_Communication", True)
        check_communication("Fan5Com", "Delay_Fan5Com_Communication", True)
        check_communication("Fan6Com", "Delay_Fan6Com_Communication", True)

        check_input("Delay_fan1_error", "fan1_error", False)
        check_input("Delay_fan2_error", "fan2_error", False)
        check_input("Delay_fan3_error", "fan3_error", False)

        check_input("Delay_fan4_error", "fan4_error", False)
        check_input("Delay_fan5_error", "fan5_error", False)
        check_input("Delay_fan6_error", "fan6_error", False)

    else:
        warning_data["error"]["Fan1Com_communication"] = False
        warning_data["error"]["Fan2Com_communication"] = False
        warning_data["error"]["Fan3Com_communication"] = False
        warning_data["error"]["Fan4Com_communication"] = False
        warning_data["error"]["Fan5Com_communication"] = False
        warning_data["error"]["Fan6Com_communication"] = False
        warning_data["error"]["Fan7Com_communication"] = False
        warning_data["error"]["Fan8Com_communication"] = False
        check_input("Delay_fan1_error", "fan1_error", False)
        check_input("Delay_fan2_error", "fan2_error", False)
        check_input("Delay_fan3_error", "fan3_error", False)
        check_input("Delay_fan4_error", "fan4_error", False)
        check_input("Delay_fan5_error", "fan5_error", False)
        check_input("Delay_fan6_error", "fan6_error", False)
        check_input("Delay_fan7_error", "fan7_error", False)
        check_input("Delay_fan8_error", "fan8_error", False)
    ###切換fan count邏輯 結束

    check_communication("Inv1_Freq", "Delay_Inverter1_Communication", True)
    check_communication("Inv2_Freq", "Delay_Inverter2_Communication", True)
    check_communication("Inv3_Freq", "Delay_Inverter3_Communication", True)

    ### 跟RH TDp為同一個
    check_communication("AmbientTemp", "Delay_AmbientTemp_Communication", True)

    # check_communication("RelativeHumid", "Delay_RelativeHumid_Communication", True)
    # check_communication("DewPoint", "Delay_DewPoint_Communication", True)

    ###flow_rate不再從485抓
    # check_communication("coolant_flow_rate", "Delay_Coolant_Flow_Meter_Communication")

    check_communication("ATS1", "Delay_ATS1_Communication", True)
    # check_communication("ATS2", "Delay_ATS2_Communication", True)

    check_communication("inst_power", "Delay_Power_Meter_Communication", True)

    ###跟inst_power相同
    # check_communication("average_current", "Delay_average_current_Communication", True)

    if not ver_switch["liquid_level_1_switch"]:
        check_level("Delay_level1", "level1", True)
    else:
        warning_data["error"]["level1"] = False

    if not ver_switch["liquid_level_2_switch"]:
        check_level("Delay_level2", "level2", True)
    else:
        warning_data["error"]["level2"] = False

    if not ver_switch["liquid_level_3_switch"]:
        check_level("Delay_level3", "level3", True)
    else:
        warning_data["error"]["level3"] = False

    check_level("Delay_power24v1", "power24v1", True)
    check_level("Delay_power24v2", "power24v2", True)

    check_input("Delay_leakage1_leak", "leakage1_leak", True)
    check_input("Delay_leakage1_broken", "leakage1_broken", True)
    check_input("Delay_main_mc_error", "main_mc_error", False)
    check_input("Delay_Inv1_Error", "Inv1_Error", True)
    check_input("Delay_Inv2_Error", "Inv2_Error", True)
    check_input("Delay_Inv3_Error", "Inv3_Error", True)

    # print(f'warning_data["error"]["Inv1_error"]:{warning_data["error"]["Inv1_Error"]}')
    # print(f'warning_data["error"]["Inv2_error"]:{warning_data["error"]["Inv2_Error"]}')
    # print(f'warning_data["error"]["Inv3_error"]:{warning_data["error"]["Inv3_Error"]}')
    # print(f'bit_input_regs["Inv1_Error"]:{bit_input_regs["Inv1_Error"]}')
    # print(f'bit_input_regs["Inv2_Error"]:{bit_input_regs["Inv2_Error"]}')
    # print(f'bit_input_regs["Inv3_Error"]:{bit_input_regs["Inv3_Error"]}')

    check_overload_error("Delay_Inv1_OverLoad")
    check_overload_error("Delay_Inv2_OverLoad")
    check_overload_error("Delay_Inv3_OverLoad")

    check_overload_error("Delay_Fan_OverLoad1")
    check_overload_error("Delay_Fan_OverLoad2")

    check_ATS("Delay_ATS")

    check_high_warning(
        "Thr_W_TempClntSply",
        "Thr_W_Rst_TempClntSply",
        "Delay_TempClntSply",
        "W",
    )

    check_high_warning(
        "Thr_A_TempClntSply",
        "Thr_A_Rst_TempClntSply",
        "Delay_TempClntSply",
        "A",
    )

    check_high_warning(
        "Thr_W_TempClntSplySpare",
        "Thr_W_Rst_TempClntSplySpare",
        "Delay_TempClntSplySpare",
        "W",
    )

    check_high_warning(
        "Thr_A_TempClntSplySpare",
        "Thr_A_Rst_TempClntSplySpare",
        "Delay_TempClntSplySpare",
        "A",
    )

    check_high_warning(
        "Thr_W_TempClntRtn",
        "Thr_W_Rst_TempClntRtn",
        "Delay_TempClntRtn",
        "W",
    )
    check_high_warning(
        "Thr_A_TempClntRtn",
        "Thr_A_Rst_TempClntRtn",
        "Delay_TempClntRtn",
        "A",
    )

    check_high_warning(
        "Thr_W_TempClntRtnSpare",
        "Thr_W_Rst_TempClntRtnSpare",
        "Delay_TempClntRtnSpare",
        "W",
    )
    check_high_warning(
        "Thr_A_TempClntRtnSpare",
        "Thr_A_Rst_TempClntRtnSpare",
        "Delay_TempClntRtnSpare",
        "A",
    )

    check_high_warning(
        "Thr_W_PrsrClntSply",
        "Thr_W_Rst_PrsrClntSply",
        "Delay_PrsrClntSply",
        "W",
    )

    check_high_warning(
        "Thr_A_PrsrClntSply",
        "Thr_A_Rst_PrsrClntSply",
        "Delay_PrsrClntSply",
        "A",
    )

    check_high_warning(
        "Thr_W_PrsrClntSplySpare",
        "Thr_W_Rst_PrsrClntSplySpare",
        "Delay_PrsrClntSplySpare",
        "W",
    )

    check_high_warning(
        "Thr_A_PrsrClntSplySpare",
        "Thr_A_Rst_PrsrClntSplySpare",
        "Delay_PrsrClntSplySpare",
        "A",
    )

    check_high_warning(
        "Thr_W_PrsrClntRtn",
        "Thr_W_Rst_PrsrClntRtn",
        "Delay_PrsrClntRtn",
        "W",
    )

    check_high_warning(
        "Thr_A_PrsrClntRtn",
        "Thr_A_Rst_PrsrClntRtn",
        "Delay_PrsrClntRtn",
        "A",
    )

    check_high_warning(
        "Thr_W_PrsrClntRtnSpare",
        "Thr_W_Rst_PrsrClntRtnSpare",
        "Delay_PrsrClntRtnSpare",
        "W",
    )

    check_high_warning(
        "Thr_A_PrsrClntRtnSpare",
        "Thr_A_Rst_PrsrClntRtnSpare",
        "Delay_PrsrClntRtnSpare",
        "A",
    )

    check_both_warning_p3(
        "Thr_W_PrsrFltIn_L",
        "Thr_W_PrsrFltIn_H",
        "Thr_W_Rst_PrsrFltIn_L",
        "Thr_W_Rst_PrsrFltIn_H",
        "Delay_PrsrFltIn",
        "W",
    )

    check_both_warning_p3(
        "Thr_A_PrsrFltIn_L",
        "Thr_A_PrsrFltIn_H",
        "Thr_A_Rst_PrsrFltIn_L",
        "Thr_A_Rst_PrsrFltIn_H",
        "Delay_PrsrFltIn",
        "A",
    )

    check_pressure_diff_error(
        "Thr_W_PrsrFltOut_H",
        "Thr_W_Rst_PrsrFltOut_H",
        "Delay_PrsrFltOut",
        "W",
    )

    check_pressure_diff_error(
        "Thr_A_PrsrFltOut_H",
        "Thr_A_Rst_PrsrFltOut_H",
        "Delay_PrsrFltOut",
        "A",
    )

    check_both_warning(
        "Thr_W_RelativeHumid_L",
        "Thr_W_RelativeHumid_H",
        "Thr_W_Rst_RelativeHumid_L",
        "Thr_W_Rst_RelativeHumid_H",
        "Delay_RelativeHumid",
        "W",
    )

    check_both_warning(
        "Thr_A_RelativeHumid_L",
        "Thr_A_RelativeHumid_H",
        "Thr_A_Rst_RelativeHumid_L",
        "Thr_A_Rst_RelativeHumid_H",
        "Delay_RelativeHumid",
        "A",
    )

    check_both_warning(
        "Thr_W_AmbientTemp_L",
        "Thr_W_AmbientTemp_H",
        "Thr_W_Rst_AmbientTemp_L",
        "Thr_W_Rst_AmbientTemp_H",
        "Delay_AmbientTemp",
        "W",
    )

    check_both_warning(
        "Thr_A_AmbientTemp_L",
        "Thr_A_AmbientTemp_H",
        "Thr_A_Rst_AmbientTemp_L",
        "Thr_A_Rst_AmbientTemp_H",
        "Delay_AmbientTemp",
        "A",
    )

    check_high_warning(
        "Thr_W_AC_H",
        "Thr_W_Rst_AC_H",
        "Delay_AC",
        "W",
    )

    check_high_warning(
        "Thr_A_AC_H",
        "Thr_A_Rst_AC_H",
        "Delay_AC",
        "A",
    )

    check_low_warning_f1(
        "Thr_W_ClntFlow",
        "Thr_W_Rst_ClntFlow",
        "Delay_ClntFlow",
        "W",
    )

    check_low_warning_f1(
        "Thr_A_ClntFlow",
        "Thr_A_Rst_ClntFlow",
        "Delay_ClntFlow",
        "A",
    )
    # print(f'warning_data["alert"]["ClntFlow"]{warning_data["alert"]}')
    # print(f'inv["inv1"]{inv["inv1"]}')
    # print(f'inv["inv2"]{inv["inv2"]}')
    # print(f'inv["inv3"]{inv["inv3"]}')

    check_dewPt_warning(
        "Thr_W_DewPoint",
        "Thr_W_Rst_DewPoint",
        "Delay_DewPoint",
        "W",
    )

    check_dewPt_warning(
        "Thr_A_DewPoint",
        "Thr_A_Rst_DewPoint",
        "Delay_DewPoint",
        "A",
    )
    if warning_data["alert"]["DewPoint_Low"]:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils((8192 + 12), [True])
        except Exception as e:
            print(f"dewpt error document error: {e}")
    else:
        try:
            with ModbusTcpClient(
                host=modbus_host, port=modbus_port, unit=modbus_slave_id
            ) as client:
                client.write_coils((8192 + 12), [False])
        except Exception as e:
            print(f"dewpt error document error: {e}")

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            r = client.read_coils((8192 + 10), 2, unit=modbus_slave_id)
            ats_status["ATS1"] = r.bits[0]
            ats_status["ATS2"] = r.bits[1]
    except Exception as e:
        print(f"ATS issue:{e}")

    # for i in range(1, 4):
    #     if not bit_output_regs[f"mc{i}"]:
    #         warning_data["error"][f"Inv{i}_Freq_communication"] = True
    #     else:
    #         warning_data["error"][f"Inv{i}_Freq_communication"] = False

    warning_key = list(warning_data["warning"].keys())
    warning_key_len = len(warning_data["warning"].keys())
    warning_reg = (warning_key_len // 16) + (1 if warning_key_len % 16 != 0 else 0)
    value_w = [0] * warning_reg
    for i in range(0, warning_key_len):
        key = warning_key[i]
        # warning_data["warning"][key] = False
        # warning_data["warning"][key] = True
        # warning_data["warning"]["RelativeHumid_Low"] = False
        if (not warning_data["alert"][key]) & warning_data["warning"][key]:
            value_w[i // 16] |= 1 << (i % 16)

    alert_key = list(warning_data["alert"].keys())
    alert_key_len = len(warning_data["alert"].keys())
    alert_reg = (alert_key_len // 16) + (1 if alert_key_len % 16 != 0 else 0)
    value_a = [0] * alert_reg
    for i in range(0, alert_key_len):
        key = alert_key[i]
        # warning_data["alert"][key] = False
        # warning_data["alert"][key] = True
        # warning_data["alert"]["pH_Low"] = False
        if warning_data["alert"][key]:
            value_a[i // 16] |= 1 << (i % 16)

    error_key = list(warning_data["error"].keys())
    err_key_len = len(warning_data["error"].keys())
    err_reg = (err_key_len // 16) + (1 if err_key_len % 16 != 0 else 0)
    value_e = [0] * err_reg
    for i in range(0, err_key_len):
        key = error_key[i]
        # print(f'warning_data["error"][Inv1_Error]{warning_data["error"]["Inv1_Error"]}')
        # warning_data["error"][key] = False
        # warning_data["error"][key] = True
        # warning_data["error"]["Inv1_Error"] =True
        # warning_data["error"]["Fan1Com_communication"] = True
        # warning_data["error"]["Fan2Com_communication"] = True
        # warning_data["error"]["Fan3Com_communication"] = True
        # warning_data["error"]["Fan4Com_communication"] = True
        # warning_data["error"]["Fan5Com_communication"] = True
        # warning_data["error"]["Fan6Com_communication"] = True
        # warning_data["error"]["Fan7Com_communication"] = True
        # warning_data["error"]["Fan8Com_communication"] = True

        # warning_data["error"]["fan1_error"] = True
        # warning_data["error"]["fan2_error"] = True
        # warning_data["error"]["fan3_error"] = True
        # warning_data["error"]["fan4_error"] = True
        # warning_data["error"]["fan5_error"] = True
        # warning_data["error"]["fan6_error"] = True
        # warning_data["error"]["fan7_error"] = True
        # warning_data["error"]["Prsr_FltOut_broken"] = True
        # warning_data["error"]["pc2_error"] = True
        # warning_data["error"]["level1"] = False

        # warning_data["error"]["Fan_OverLoad1"] = True
        # warning_data["error"]["Fan_OverLoad2"] = True

        # warning_data["error"]["Prsr_ClntSply_broken"] = True #P1
        # warning_data["error"]["Prsr_ClntSplySpare_broken"] = False  #P1sp

        if warning_data["error"][key]:
            value_e[i // 16] |= 1 << (i % 16)

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers(1700, value_w)
            client.write_registers(1705, value_a)
            client.write_registers(1708, value_e)
    except Exception as e:
        print(f"store in 16 bits error{e}")

    ignore_key = ["ATS1_Error"]

    sensor_key_map = {
        "Temp_ClntSplySpare": ["Temp_ClntSplySpare_broken", "TempClntSplySpare_High"],
        "Temp_ClntRtnSpare": ["Temp_ClntRtnSpare_broken", "TempClntRtnSpare_High"],
        "Prsr_ClntSplySpare": ["PrsrClntSplySpare_High", "PrsrClntSplySpare_High"],
        "Prsr_ClntRtnSpare": ["PrsrClntRtnSpare_High", "PrsrClntRtnSpare_High"],
    }

    for sensor, keys in sensor_key_map.items():
        if sensor_factor.get(sensor) == 0:
            ignore_key.extend(keys)

    if (
        not any(
            value
            for key, value in warning_data["alert"].items()
            if key not in ignore_key
        )
        and not any(
            value
            for key, value in warning_data["error"].items()
            if key not in ignore_key
        )
        and not any(
            value
            for key, value in warning_data["warning"].items()
            if key not in ignore_key
        )
    ):
        color_light["green"] = True
        color_light["red"] = False
    elif any(
        value for key, value in warning_data["alert"].items() if key not in ignore_key
    ) or any(
        value for key, value in warning_data["error"].items() if key not in ignore_key
    ):
        color_light["green"] = False
        color_light["red"] = True
    elif (
        any(
            value
            for key, value in warning_data["warning"].items()
            if key not in ignore_key
        )
        and not any(
            value
            for key, value in warning_data["alert"].items()
            if key not in ignore_key
        )
        and not any(
            value
            for key, value in warning_data["error"].items()
            if key not in ignore_key
        )
    ):
        color_light["green"] = True
        color_light["red"] = True

    if onLinux:
        try:
            if mode == "inspection":
                bit_output_regs["led_err"] = False
            elif (
                any(
                    value
                    for key, value in warning_data["warning"].items()
                    if key not in ignore_key
                )
                or any(
                    value
                    for key, value in warning_data["alert"].items()
                    if key not in ignore_key
                )
                or any(
                    value
                    for key, value in warning_data["error"].items()
                    if key not in ignore_key
                )
            ):
                bit_output_regs["led_err"] = warning_light
                # bit_output_regs["led_err"] = False
                warning_light = not warning_light
            else:
                bit_output_regs["led_err"] = False
        except Exception as e:
            print(f"warning light error:{e}")


### 轉換 freq
def translate_pump_speed(speed):
    if speed == 0:
        return 0

    ps = (float(speed)) / 100.0 * 16000.0
    ps = int(ps)
    return ps


def translate_fan_speed(speed):
    fan = (float(speed)) / 100.0 * 16000.0
    fan = int(fan)
    return fan


def set_pump1_speed(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 6660), speed)

    except Exception as e:
        print(f"set pump1 speed error: {e}")


def set_pump2_speed(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 6700), speed)

    except Exception as e:
        print(f"set pump2 speed error: {e}")


def set_pump3_speed(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 6740), speed)

    except Exception as e:
        print(f"set pump3 speed error: {e}")


def set_f1(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 7020), speed)
    except Exception as e:
        print(f"set f1 speed error: {e}")


def set_f2(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 7060), speed)
    except Exception as e:
        print(f"set f2 speed error: {e}")


def set_f3(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 7100), speed)
    except Exception as e:
        print(f"set f3 speed error: {e}")


def set_f4(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 7140), speed)
    except Exception as e:
        print(f"set f4 speed error: {e}")


def set_f5(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 7380), speed)
    except Exception as e:
        print(f"set fan set1 speed error: {e}")


def set_f6(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 7420), speed)
    except Exception as e:
        print(f"set fan set2 speed error: {e}")


def set_f7(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 7460), speed)
    except Exception as e:
        print(f"set fan set3 speed error: {e}")


def set_f8(speed):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 7500), speed)
    except Exception as e:
        print(f"set fan set4 speed error: {e}")


def trigger_overload_from_oc_detection():
    if oc_detection["p1"]:
        overload_error["Inv1_OverLoad"] = True

    if oc_detection["p2"]:
        overload_error["Inv2_OverLoad"] = True

    if oc_detection["p3"]:
        overload_error["Inv3_OverLoad"] = True

    if oc_detection["f1"]:
        overload_error["Fan_OverLoad1"] = True

    if oc_detection["f2"]:
        overload_error["Fan_OverLoad2"] = True


def check_mc():
    # print(f'bit_input_regs["Inv1_Error"]{bit_input_regs["Inv1_Error"]}')

    # 抓取前端是否勾選MC開關
    try:
        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
            mc = client.read_coils((8192 + 840), 5, unit=modbus_slave_id)
            mc1_sw = mc.bits[0]
            mc2_sw = mc.bits[1]
            mc3_sw = mc.bits[2]
            mc_fan1_sw = mc.bits[3]
            mc_fan2_sw = mc.bits[4]
    except Exception as e:
        print(f"mc_switch read: {e}")
    ####嘗試做重啟不會讓pump關閉####
    if not mc1_sw:
        clear_p1_speed()
    if not mc2_sw:
        clear_p2_speed()
    if not mc3_sw:
        clear_p3_speed()
    if not mc_fan1_sw:
        clear_fan_group1_speed()
    if not mc_fan2_sw:
        clear_fan_group2_speed()

    ### mc..._sw 為前端各個開關是否為true
    if (
        not overload_error["Inv1_OverLoad"]
        # and not bit_input_regs["Inv1_Error"]
        and mc1_sw
    ):
        bit_output_regs["mc1"] = True
        # print(f'bit_output_regs["mc1"] {bit_output_regs["mc1"]}')
    else:
        bit_output_regs["mc1"] = False

    if (
        not overload_error["Inv2_OverLoad"]
        # and not bit_input_regs["Inv2_Error"]
        and mc2_sw
    ):
        bit_output_regs["mc2"] = True
    else:
        bit_output_regs["mc2"] = False

    if (
        not overload_error["Inv3_OverLoad"]
        # and not bit_input_regs["Inv3_Error"]
        and mc3_sw
    ):
        bit_output_regs["mc3"] = True
    else:
        bit_output_regs["mc3"] = False

    if not overload_error["Fan_OverLoad1"] and mc_fan1_sw:
        bit_output_regs["mc_fan1"] = True
    else:
        bit_output_regs["mc_fan1"] = False

    if not overload_error["Fan_OverLoad2"] and mc_fan2_sw:
        bit_output_regs["mc_fan2"] = True
    else:
        bit_output_regs["mc_fan2"] = False


def uint16_to_int16(value):
    if value >= 32768:
        return value - 65536
    return value


def reset_mc():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            # client.write_coils(800, [False])
            client.write_coils(2100, [False])
    except Exception as e:
        print(f"reset mc error:{e}")
    overload_error["Inv1_OverLoad"] = False
    overload_error["Inv2_OverLoad"] = False


def open_inv1_auto():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 870), [True])

    except Exception as e:
        print(f"open inv1: {e}")
    set_pump1_speed(word_regs["pid_pump_out"])


def open_inv2_auto():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 871), [True])

    except Exception as e:
        print(f"open inv1: {e}")
    set_pump2_speed(word_regs["pid_pump_out"])


def open_inv3_auto():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 872), [True])

    except Exception as e:
        print(f"open inv1: {e}")
    set_pump3_speed(word_regs["pid_pump_out"])


def close_inv1_auto():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 870), [False])

    except Exception as e:
        print(f"close inv1: {e}")
    set_pump1_speed(0)


def close_inv2_auto():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 871), [False])

    except Exception as e:
        print(f"close inv1: {e}")
    set_pump2_speed(0)


def close_inv3_auto():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 872), [False])

    except Exception as e:
        print(f"close inv1: {e}")
    set_pump3_speed(0)


def reset_btn_false():
    reset_current_btn["status"] = False
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 800), [False])
    except Exception as e:
        print(f"reset btn error:{e}")


def clear_p1_speed():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 820), [False])
            client.write_register((20480 + 6660), 0)
    except Exception as e:
        print(f"clear p1 speed error:{e}")


def clear_p2_speed():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 821), [False])
            client.write_register((20480 + 6700), 0)

    except Exception as e:
        print(f"clear p2 speed error:{e}")


def clear_p3_speed():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_coils((8192 + 822), [False])
            client.write_register((20480 + 6740), 0)

    except Exception as e:
        print(f"clear p3 speed error:{e}")


def clear_fan_group1_speed():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            # client.write_register((20480 + 7020), 320)
            # client.write_register((20480 + 7060), 320)
            # client.write_register((20480 + 7100), 320)
            # client.write_register((20480 + 7140), 320)
            client.write_register((20480 + 7020), 960)
            client.write_register((20480 + 7060), 960)
            client.write_register((20480 + 7100), 960)
            client.write_register((20480 + 7140), 960)
            client.write_coils((8192 + 850), [False])
            client.write_coils((8192 + 851), [False])
            client.write_coils((8192 + 852), [False])
            client.write_coils((8192 + 853), [False])

    except Exception as e:
        print(f"clear fan_group1_speed error:{e}")


def clear_fan_group2_speed():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            # client.write_register((20480 + 7380), 320)
            # client.write_register((20480 + 7420), 320)
            # client.write_register((20480 + 7460), 320)
            # client.write_register((20480 + 7500), 320)
            client.write_register((20480 + 7380), 960)
            client.write_register((20480 + 7420), 960)
            client.write_register((20480 + 7460), 960)
            client.write_register((20480 + 7500), 960)
            client.write_coils((8192 + 854), [False])
            client.write_coils((8192 + 855), [False])
            client.write_coils((8192 + 856), [False])
            client.write_coils((8192 + 857), [False])
    except Exception as e:
        print(f"clear fan_group2_speed error:{e}")


def stop_fan():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            ###寫入一伏特
            # client.write_register((20480 + 7020), 320)
            # client.write_register((20480 + 7060), 320)
            # client.write_register((20480 + 7100), 320)
            # client.write_register((20480 + 7140), 320)
            # client.write_register((20480 + 7380), 320)
            # client.write_register((20480 + 7420), 320)
            # client.write_register((20480 + 7460), 320)
            # client.write_register((20480 + 7500), 320)
            client.write_register((20480 + 7020), 960)
            client.write_register((20480 + 7060), 960)
            client.write_register((20480 + 7100), 960)
            client.write_register((20480 + 7140), 960)
            client.write_register((20480 + 7380), 960)
            client.write_register((20480 + 7420), 960)
            client.write_register((20480 + 7460), 960)
            client.write_register((20480 + 7500), 960)
            # client.write_coils((8192 + 850), [False])
            # client.write_coils((8192 + 851), [False])
            # client.write_coils((8192 + 852), [False])
            # client.write_coils((8192 + 853), [False])
            # client.write_coils((8192 + 854), [False])
            # client.write_coils((8192 + 855), [False])
            # client.write_coils((8192 + 856), [False])
            # client.write_coils((8192 + 857), [False])
    except Exception as e:
        print(f"clear fan error:{e}")


def stop_p1():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 6660), 0)
    except Exception as e:
        print(f"clear all speed error:{e}")


def stop_p2():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 6700), 0)
    except Exception as e:
        print(f"clear all speed error:{e}")


def stop_p3():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register((20480 + 6740), 0)
    except Exception as e:
        print(f"clear all speed error:{e}")


def get_key(item):
    return item[1]


def write_measured_data(number, data):
    registers = []

    word1, word2 = cvt_float_byte(data)
    registers.append(word2)
    registers.append(word1)

    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_registers((900 + number), registers)
    except Exception as e:
        print(f"send messure p1:{e}")


def cancel_inspection():
    try:
        value_list_status = list(inspection_data["prog"].values())
        value_list_status = [1 if value == 4 else value for value in value_list_status]
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            # client.write_registers(800, value_list_status)
            client.write_registers(2100, value_list_status)
    except Exception as e:
        print(f"result write-in:{e}")

    for key, status in inspection_data["prog"].items():
        if status == 1:
            inspection_data["result"][key] = False

    try:
        value_list_result = [
            1 if value else 0 for value in inspection_data["result"].values()
        ]
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            # client.write_registers(750, value_list_result)
            client.write_registers(2000, value_list_result)
            client.write_register(973, 2)
    except Exception as e:
        print(f"result write-in:{e}")

    inspection_data["step"] = 1
    inspection_data["start_time"] = 0
    inspection_data["mid_time"] = 0
    inspection_data["end_time"] = 0

    print("被切掉模式")


### 檢查是否強制轉換mode
def check_last_mode_from_inspection(mode_last):
    one_time = True
    if mode_last == "inspection":
        if one_time:
            try:
                with ModbusTcpClient(
                    host=modbus_host, port=modbus_port, unit=modbus_slave_id
                ) as client:
                    r = client.read_coils((8192 + 600), 1, unit=modbus_slave_id)
                    inspection_data["force_change_mode"] = r.bits[0]
            except Exception as e:
                print(f"read force change mode error:{e}")
            one_time = False
    else:
        inspection_data["force_change_mode"] = False


def check_inv_speed():
    try:
        ###  轉換 inv_freq
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            inv1 = client.read_holding_registers(address=(20480 + 6660), count=1)
            inv2 = client.read_holding_registers(address=(20480 + 6700), count=1)
            inv3 = client.read_holding_registers(address=(20480 + 6740), count=1)

            inv1_v = inv1.registers[0] / 16000 * 100
            inv2_v = inv2.registers[0] / 16000 * 100
            inv3_v = inv3.registers[0] / 16000 * 100

            return inv1_v, inv2_v, inv3_v
    except Exception as e:
        print(f"read inv_en error:{e}")


### 切換回強制轉換mode前的mode
def go_back_to_last_mode(mode):
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(950, 1)

            p1 = translate_pump_speed(inspection_data["prev"]["inv1"])
            p2 = translate_pump_speed(inspection_data["prev"]["inv2"])
            p3 = translate_pump_speed(inspection_data["prev"]["inv3"])

            p1 = p1 if inspection_data["prev"]["inv1"] != 0 else 0
            p2 = p2 if inspection_data["prev"]["inv2"] != 0 else 0
            p3 = p3 if inspection_data["prev"]["inv3"] != 0 else 0

            set_pump1_speed(p1)
            set_pump2_speed(p2)
            set_pump3_speed(p3)

            if mode == "manual":
                client.write_coils((8192 + 517), [False])
                client.write_coils((8192 + 505), [True])
            elif mode == "engineer":
                client.write_coils((8192 + 517), [False])
                client.write_coils((8192 + 516), [True])
            elif mode == "auto":
                client.write_coils((8192 + 517), [False])
                client.write_coils((8192 + 505), [False])
            elif mode == "stop":
                client.write_coils((8192 + 517), [False])
                client.write_coils((8192 + 514), [False])
            else:
                client.write_coils((8192 + 517), [False])
                client.write_coils((8192 + 505), [True])
    except Exception as e:
        print(f"respec error:{e}")


def reset_inspect_btn():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(900, 3)
            inspection_data["start_btn"] = 3
    except Exception as e:
        print(f"close inspection:{e}")


# def only_send_inspection_data(number, progress_value):
#     try:
#         with ModbusTcpClient(
#             host=modbus_host, port=modbus_port, unit=modbus_slave_id
#         ) as client:
#             # client.write_registers((800 + number), progress_value)
#             client.write_registers((2100 + number), progress_value)
#     except Exception as e:
#         print(f"result write-in:{e}")


# def send_inspection_data(number, progress_value, result_value):
#     try:
#         with ModbusTcpClient(
#             host=modbus_host, port=modbus_port, unit=modbus_slave_id
#         ) as client:
#             # client.write_registers((800 + number), progress_value)
#             client.write_registers((2100 + number), progress_value)
#     except Exception as e:
#         print(f"result write-in:{e}")

#     try:
#         with ModbusTcpClient(
#             host=modbus_host, port=modbus_port, unit=modbus_slave_id
#         ) as client:
#             change_result_value = [1 if result_value else 0]
#             # client.write_registers((750 + number), change_result_value)
#             client.write_registers((2000 + number), change_result_value)
#     except Exception as e:
#         print(f"result write-in:{e}")


def change_inspect_time():
    try:
        with ModbusTcpClient(
            host=modbus_host, port=modbus_port, unit=modbus_slave_id
        ) as client:
            client.write_register(950, 2)

    except Exception as e:
        print(f"change_inspect_time:{e}")

###與PLC 不同 開始
check_server1 = 0
pre_check_server1 = 0
change_to_server2 = False
server2_count = 0
###與PLC 不同 結束


def control():
    global change_to_server2

    mode_last = ""
    pump1_run_last_min = time.time()
    pump2_run_last_min = time.time()
    pump3_run_last_min = time.time()
    fan1_run_last_min = time.time()
    fan2_run_last_min = time.time()
    fan3_run_last_min = time.time()
    fan4_run_last_min = time.time()
    fan5_run_last_min = time.time()
    fan6_run_last_min = time.time()
    fan7_run_last_min = time.time()
    fan8_run_last_min = time.time()
    filter_run_last_min = time.time()
    
    
    swap_last = time.time()
    first_p = False
    mode = ""
    global \
        previous_inv, \
        previous_inv1, \
        previous_inv2, \
        change_back_mode, \
        oc_issue, \
        diff, \
        f1_data, \
        pump_signial, \
        water_pv_set
    global auto_flag, port
    global \
        count_f1, \
        p1_data, \
        p2_data, \
        p3_data, \
        fan1_data, \
        fan2_data, \
        fan3_data, \
        fan4_data, \
        fan5_data, \
        fan6_data, \
        fan7_data, \
        fan8_data, \
        zero_flag, \
        rtu_flag, \
        previous_ver, \
        oc_trigger, \
        p1_error_box, \
        p2_error_box, \
        p3_error_box, \
        fan1_error_box , \
        fan2_error_box , \
        fan3_error_box , \
        fan4_error_box , \
        fan5_error_box , \
        fan6_error_box , \
        fan7_error_box , \
        fan8_error_box 
    clnt_flow_data = deque(maxlen=20)

    while True:
        restart_server["start"] = time.time()
        server_error["start"] = time.time()
        try:
            global server2_count
            with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                r = client.read_holding_registers(301, 1, unit=modbus_slave_id)

                server2_count = r.registers[0]
                if r.registers[0] > 30000:
                    server2_count = 0
                    client.write_register(301, server2_count)
                else:
                    server2_count += 1
                    client.write_register(301, server2_count)
        except Exception as e:
            print(f"server 1 check error:{e}")

        time.sleep(1)
        try:
            global check_server1, pre_check_server1
            with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                r = client.read_holding_registers(300, 1, unit=modbus_slave_id)
                check_server1 = r.registers[0]

            # print(f"主機一：{pre_check_server1} => {check_server1}")
            # print(f"停滯時間：{server_error['diff']}")
            # print(f"確認異常：{change_to_server2}")
            # print(f"結果：{server_error}")

            try:
                json_dir = f"{log_path}/PLC/json"
                if not os.path.exists(json_dir):
                    os.makedirs(json_dir)
                with open(f"{json_dir}/pc_status.json", "w") as json_file3:
                    json.dump(change_to_server2, json_file3, indent=4)
            except Exception as e:
                print(f"pc_status.json:{e}")

            if zero_flag:
                server_error["diff"] = 0
                zero_flag = False

            if check_server1 == pre_check_server1:
                server_error["diff"] += time.time() - server_error["start"]
            else:
                server_error["diff"] = 0

            if server_error["diff"] >= 300:
                if restart_server["stage"] == 0:
                    restart_server["stage"] = 1
                else:
                    pass
            else:
                restart_server["stage"] = 0

            if server_error["diff"] >= 5:
                change_to_server2 = True
                pre_check_server1 = check_server1
                warning_data["error"]["pc1_error"] = True
            else:
                change_to_server2 = False
                warning_data["error"]["pc1_error"] = False
                pre_check_server1 = check_server1
                continue

        except Exception as e:
            print(f"server 2 replace error:{e}")

        if change_to_server2:
            ### 與PLC相同 開始 (要tab一次)

            try:
                restart_server["start"] = time.time()
                server_error["start"] = time.time()
                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        value_list = [
                            v
                            for key, v in raw_485_data.items()
                            if key != "ATS1" and key != "ATS2"
                        ]

                        new_list = []
                        # journal_logger.info(f'value_list:{value_list}')
                        for value in value_list:
                            r1, r2 = cvt_float_byte(value)
                            new_list.append(r2)
                            new_list.append(r1)
                            # journal_logger.info(f'new_list:{new_list}')

                        ### 將raw_485_data丟進D19
                        client.write_registers(19, new_list)
                except Exception as e:
                    print(f"485 data error:{e}")

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        client.write_coil((8192 + 10), raw_485_data["ATS1"])
                        client.write_coil((8192 + 11), raw_485_data["ATS2"])
                except Exception as e:
                    print(f"485 ATS 1&2 error:{e}")

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        r = client.read_coils((8192 + 800), 9)
                        reset_current_btn["status"] = r.bits[0]
                        ver_switch["median_switch"] = r.bits[3]
                        ver_switch["coolant_quality_meter_switch"] = r.bits[4]
                        ver_switch["fan_count_switch"] = r.bits[5]
                        ver_switch["liquid_level_1_switch"] = r.bits[6]
                        ver_switch["liquid_level_2_switch"] = r.bits[7]
                        ver_switch["liquid_level_3_switch"] = r.bits[8]

                        r2 = client.read_holding_registers(900, 1)
                        inspection_data["start_btn"] = r2.registers[0]
                except Exception as e:
                    print(f"check version: {e}")

                ### 檢查目前FAN數量

                # print(f'ver_switch["fan_count_switch"]:{ver_switch["fan_count_switch"]}')
                fan_count_6 = bool(ver_switch["fan_count_switch"])
                # print(f'fan_count_6:{fan_count_6}')

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        leak = client.read_discrete_inputs(2, 2, unit=modbus_slave_id)
                        bit_input_regs["leakage1_leak"] = leak.bits[0]
                        bit_input_regs["leakage1_broken"] = leak.bits[1]

                        mainMC = client.read_discrete_inputs(35, 1, unit=modbus_slave_id)
                        bit_input_regs["main_mc_error"] = mainMC.bits[0]

                        ### 增加fan數量判斷
                        if ver_switch["fan_count_switch"]:
                            ###抓取1~3
                            full_input = client.read_discrete_inputs(
                                40, 3, unit=modbus_slave_id
                            )
                            for i in range(3):
                                key_list = list(bit_input_regs.keys())
                                bit_input_regs[key_list[i + 6]] = full_input.bits[i]
                            ###抓取4~6
                            full_input_2 = client.read_discrete_inputs(
                                44, 3, unit=modbus_slave_id
                            )
                            for i in range(3):
                                key_list = list(bit_input_regs.keys())
                                bit_input_regs[key_list[i + 9]] = full_input_2.bits[i]
                        else:
                            full_input = client.read_discrete_inputs(
                                40, 8, unit=modbus_slave_id
                            )
                            for i in range(8):
                                key_list = list(bit_input_regs.keys())
                                bit_input_regs[key_list[i + 6]] = full_input.bits[i]

                        inv_error = client.read_discrete_inputs(0, 2, unit=modbus_slave_id)
                        bit_input_regs["Inv1_Error"] = inv_error.bits[0]
                        bit_input_regs["Inv2_Error"] = inv_error.bits[1]
                        # print(f'bit_input_regs["Inv1_Error"]{bit_input_regs["Inv1_Error"]}')
                        inv_error_3 = client.read_discrete_inputs(
                            26, 1, unit=modbus_slave_id
                        )
                        bit_input_regs["Inv3_Error"] = inv_error_3.bits[0]

                        level = client.read_discrete_inputs(12, 4)
                        level_sw["level1"] = level.bits[0]
                        level_sw["level2"] = level.bits[1]
                        level_sw["power24v1"] = level.bits[2]
                        level_sw["power24v2"] = level.bits[3]

                        level2 = client.read_discrete_inputs(18, 3)
                        level_sw["level3"] = level2.bits[0]
                        level_sw["power12v1"] = level2.bits[1]
                        level_sw["power12v2"] = level2.bits[2]

                        oc = client.read_discrete_inputs(16, 2)
                        oc_detection["p1"] = oc.bits[0]
                        oc_detection["p2"] = oc.bits[1]

                        oc2 = client.read_discrete_inputs(32, 3)
                        oc_detection["p3"] = oc2.bits[0]
                        oc_detection["f1"] = oc2.bits[1]
                        oc_detection["f2"] = oc2.bits[2]

                except Exception as e:
                    print(f"read leak error {e}")

                check_mc()

                # try:
                #     with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                #         mc = client.read_coils((8192 + 840), 5, unit=modbus_slave_id)
                #         bit_output_regs["mc1"] = mc.bits[0]
                #         bit_output_regs["mc2"] = mc.bits[1]
                #         bit_output_regs["mc3"] = mc.bits[2]
                #         bit_output_regs["mc_fan1"] = mc.bits[3]
                #         bit_output_regs["mc_fan2"] = mc.bits[4]
                # except Exception as e:
                #     print(f"output read: {e}")

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        word = client.read_holding_registers(246, 2, unit=modbus_slave_id)
                        word_regs["pump_speed"] = cvt_registers_to_float(
                            word.registers[0], word.registers[1]
                        )

                        word2 = client.read_holding_registers(470, 2, unit=modbus_slave_id)
                        word_regs["fan_speed"] = cvt_registers_to_float(
                            word2.registers[0], word2.registers[1]
                        )

                        word1 = client.read_coils((8192 + 820), 3, unit=modbus_slave_id)
                        word_regs["p1_check"] = word1.bits[0]
                        word_regs["p2_check"] = word1.bits[1]
                        word_regs["p3_check"] = word1.bits[2]

                        word2 = client.read_coils((8192 + 850), 8, unit=modbus_slave_id)
                        word_regs["f1_check"] = word2.bits[0]
                        word_regs["f2_check"] = word2.bits[1]
                        word_regs["f3_check"] = word2.bits[2]
                        word_regs["f4_check"] = word2.bits[3]
                        word_regs["f5_check"] = word2.bits[4]
                        word_regs["f6_check"] = word2.bits[5]
                        word_regs["f7_check"] = word2.bits[6]
                        word_regs["f8_check"] = word2.bits[7]

                        word3 = client.read_holding_registers(50, 1, unit=modbus_slave_id)
                        word_regs["pid_pump_out"] = word3.registers[0]
                except Exception as e:
                    print(f"read mc error: {e}")

                try:
                    with ModbusTcpClient(
                        host=modbus_host, port=modbus_port, unit=modbus_slave_id
                    ) as client:
                        inv1 = client.read_holding_registers(
                            address=(20480 + 6660), count=1
                        )
                        inv2 = client.read_holding_registers(
                            address=(20480 + 6700), count=1
                        )
                        inv3 = client.read_holding_registers(
                            address=(20480 + 6740), count=1
                        )
                        fan1 = client.read_holding_registers(address=(20480 + 7020), count=1)
                        fan2 = client.read_holding_registers(address=(20480 + 7060), count=1)
                        fan3 = client.read_holding_registers(address=(20480 + 7100), count=1)
                        fan4 = client.read_holding_registers(address=(20480 + 7140), count=1)
                        fan5 = client.read_holding_registers(address=(20480 + 7380), count=1)
                        fan6 = client.read_holding_registers(address=(20480 + 7420), count=1)
                        fan7 = client.read_holding_registers(address=(20480 + 7460), count=1)
                        fan8 = client.read_holding_registers(address=(20480 + 7500), count=1)
                        
                        ### 待確認  轉換 freq
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
                            
                            
                        if not bit_output_regs["mc1"] or not word_regs["p1_check"]:
                            inv1_v = 0

                        if not bit_output_regs["mc2"] or not word_regs["p2_check"]:
                            inv2_v = 0

                        if not bit_output_regs["mc3"] or not word_regs["p3_check"]:
                            inv3_v = 0

                        inv["inv1"] = inv1_v >= 25
                        inv["inv2"] = inv2_v >= 25
                        inv["inv3"] = inv3_v >= 25
                        if ver_switch["fan_count_switch"]:
                            inv["fan1"] = fan1_v >= 6
                            inv["fan2"] = fan2_v >= 6
                            inv["fan3"] = fan3_v >= 6
                            inv["fan4"] = fan4_v >= 6
                            inv["fan5"] = fan5_v >= 6
                            inv["fan6"] = fan6_v >= 6
                        else:
                            inv["fan1"] = fan1_v >= 6
                            inv["fan2"] = fan2_v >= 6
                            inv["fan3"] = fan3_v >= 6
                            inv["fan4"] = fan4_v >= 6
                            inv["fan5"] = fan5_v >= 6
                            inv["fan6"] = fan6_v >= 6
                            inv["fan7"] = fan7_v >= 6
                            inv["fan8"] = fan8_v >= 6
                except Exception as e:
                    print(f"read inv_en 2 error:{e}")

                ### 讀取 runtime
                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        time1 = client.read_holding_registers(270, 4, unit=modbus_slave_id)
                        dword_regs["p1_run_min"] = read_split_register(time1.registers, 0)
                        dword_regs["p1_run_hr"] = read_split_register(time1.registers, 2)

                        time2 = client.read_holding_registers(274, 4, unit=modbus_slave_id)
                        dword_regs["p2_run_min"] = read_split_register(time2.registers, 0)
                        dword_regs["p2_run_hr"] = read_split_register(time2.registers, 2)

                        time3 = client.read_holding_registers(278, 4, unit=modbus_slave_id)
                        dword_regs["p3_run_min"] = read_split_register(time3.registers, 0)
                        dword_regs["p3_run_hr"] = read_split_register(time3.registers, 2)

                        time_f_1 = client.read_holding_registers(
                            310, 4, unit=modbus_slave_id
                        )
                        dword_regs["f1_run_min"] = read_split_register(
                            time_f_1.registers, 0
                        )
                        dword_regs["f1_run_hr"] = read_split_register(time_f_1.registers, 2)

                        time_f_2 = client.read_holding_registers(
                            314, 4, unit=modbus_slave_id
                        )
                        dword_regs["f2_run_min"] = read_split_register(
                            time_f_2.registers, 0
                        )
                        dword_regs["f2_run_hr"] = read_split_register(time_f_2.registers, 2)

                        time_f_3 = client.read_holding_registers(
                            318, 4, unit=modbus_slave_id
                        )
                        dword_regs["f3_run_min"] = read_split_register(
                            time_f_3.registers, 0
                        )
                        dword_regs["f3_run_hr"] = read_split_register(time_f_3.registers, 2)

                        time_f_4 = client.read_holding_registers(
                            322, 4, unit=modbus_slave_id
                        )
                        dword_regs["f4_run_min"] = read_split_register(
                            time_f_4.registers, 0
                        )
                        dword_regs["f4_run_hr"] = read_split_register(time_f_4.registers, 2)

                        time_f_5 = client.read_holding_registers(
                            326, 4, unit=modbus_slave_id
                        )
                        dword_regs["f5_run_min"] = read_split_register(
                            time_f_5.registers, 0
                        )
                        dword_regs["f5_run_hr"] = read_split_register(time_f_5.registers, 2)

                        time_f_6 = client.read_holding_registers(
                            330, 4, unit=modbus_slave_id
                        )
                        dword_regs["f6_run_min"] = read_split_register(
                            time_f_6.registers, 0
                        )
                        dword_regs["f6_run_hr"] = read_split_register(time_f_6.registers, 2)

                        time_f_7 = client.read_holding_registers(
                            334, 4, unit=modbus_slave_id
                        )
                        dword_regs["f7_run_min"] = read_split_register(
                            time_f_7.registers, 0
                        )
                        dword_regs["f7_run_hr"] = read_split_register(time_f_7.registers, 2)

                        time_f_8 = client.read_holding_registers(
                            338, 4, unit=modbus_slave_id
                        )
                        dword_regs["f8_run_min"] = read_split_register(
                            time_f_8.registers, 0
                        )
                        dword_regs["f8_run_hr"] = read_split_register(time_f_8.registers, 2)

                        time_filter = client.read_holding_registers(
                            342, 4, unit=modbus_slave_id
                        )
                        dword_regs["filter_run_min"] = read_split_register(
                            time_filter.registers, 0
                        )
                        dword_regs["filter_run_hr"] = read_split_register(time_filter.registers, 2)


                        p_swap = client.read_holding_registers(303, 2, unit=modbus_slave_id)
                        swap = cvt_registers_to_float(
                            p_swap.registers[0], p_swap.registers[1]
                        )
                        dword_regs["p_swap"] = swap
                except Exception as e:
                    print(f"read pump and fan runtime error: {e}")

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        result = client.read_coils((8192 + 514), 1)

                        if not result.bits[0]:
                            mode = "stop"
                        else:
                            result = client.read_coils((8192 + 516), 1)

                            if result.bits[0]:
                                mode = "engineer"
                            else:
                                r = client.read_coils((8192 + 517), 1)

                                if r.bits[0]:
                                    mode = "inspection"
                                else:
                                    result = client.read_coils((8192 + 505), 1)

                                    if result.isError():
                                        print(f"Modbus Error: {result}")
                                    else:
                                        if not result.bits[0]:
                                            mode = "auto"
                                        else:
                                            mode = "manual"
                except Exception as e:
                    print(f"read mode & control data: {e}")

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        ad_count = len(ad_sensor_value.keys())
                        serial_count = len(serial_sensor_value.keys())
                        ### 增加八個固定PLC占用位置
                        all_count = ad_count + (serial_count * 2) + 8

                        all_sensors = client.read_holding_registers(
                            0, all_count, unit=modbus_slave_id
                        )

                        ##從D0開始讀ad sensor value
                        keys_list = list(ad_sensor_value.keys())
                        for i in range(0, ad_count):
                            value = all_sensors.registers[i]
                            value_translate = uint16_to_int16(value)
                            sensor_raw[keys_list[i]] = value_translate

                        key_list = list(sensor_raw.keys())

                        for key in key_list:
                            if ("Temp" in key or "Prsr" in key) and key != "AmbientTemp":
                                check_broken(key)

                        for key in key_list:
                            if "Prsr" in key:
                                if 6400 > sensor_raw[key] > 6080:
                                    sensor_raw[key] = 6400

                        ad_sensor_value["Temp_ClntSply"] = (
                            float(sensor_raw["Temp_ClntSply"]) / 10.0
                        )
                        ad_sensor_value["Temp_ClntSplySpare"] = (
                            float(sensor_raw["Temp_ClntSplySpare"]) / 10.0
                        )
                        ad_sensor_value["Temp_ClntRtn"] = (
                            float(sensor_raw["Temp_ClntRtn"]) / 10.0
                        )
                        ad_sensor_value["Temp_ClntRtnSpare"] = (
                            float(sensor_raw["Temp_ClntRtnSpare"]) / 10.0
                        )
                        ad_sensor_value["Prsr_ClntSply"] = (
                            float(sensor_raw["Prsr_ClntSply"]) - 6400
                        ) / 25600
                        ad_sensor_value["Prsr_ClntSplySpare"] = (
                            float(sensor_raw["Prsr_ClntSplySpare"]) - 6400
                        ) / 25600
                        ad_sensor_value["Prsr_ClntRtn"] = (
                            float(sensor_raw["Prsr_ClntRtn"] - 6400)
                        ) / 25600.0
                        ad_sensor_value["Prsr_ClntRtnSpare"] = (
                            float(sensor_raw["Prsr_ClntRtnSpare"] - 6400)
                        ) / 25600.0

                        ad_sensor_value["Prsr_FltIn"] = (
                            float(sensor_raw["Prsr_FltIn"]) - 6400
                        ) / 25600.0
                        ad_sensor_value["Prsr_FltOut"] = (
                            float(sensor_raw["Prsr_FltOut"]) - 6400
                        ) / 25600.0

                        keys_list = list(serial_sensor_value.keys())
                        # print(f'keys_list:{keys_list}')
                        j = 0
                        for i in range(19, all_count, 2):
                            temp1 = [all_sensors.registers[i], all_sensors.registers[i + 1]]
                            decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
                                temp1, byteorder=Endian.Big, wordorder=Endian.Little
                            )
                            try:
                                decoded_value = decoder_big_endian.decode_32bit_float()
                                if decoded_value != decoded_value:
                                    print(f"key {keys_list[j]} results NaN")
                                else:
                                    serial_sensor_value[keys_list[j]] = decoded_value
                            except Exception as e:
                                print(f"{keys_list[j]} value error：{e}")
                            j += 1
                        # journal_logger.info(f'serial_sensor_value{serial_sensor_value}')

                        # for k, v in mapping.items():
                        #     if k in raw_485_data:
                        #         serial_sensor_value[v] = raw_485_data[k]
                        # print(f'serial_sensor_value{serial_sensor_value}')

                        try:
                            flow_rate = client.read_holding_registers((20480 + 6380), 1)

                            if not flow_rate.isError():
                                serial_sensor_value["Clnt_Flow"] = flow_rate.registers[0]
                                if serial_sensor_value["Clnt_Flow"] > 32767:
                                    serial_sensor_value["Clnt_Flow"] = (
                                        65535 - serial_sensor_value["Clnt_Flow"]
                                    )
                                if 3200 > serial_sensor_value["Clnt_Flow"] > 3040:
                                    serial_sensor_value["Clnt_Flow"] = 3200
                                sensor_raw["Clnt_Flow"] = serial_sensor_value["Clnt_Flow"]
                                check_broken("Clnt_Flow")
                                serial_sensor_value["Clnt_Flow"] = (
                                    # (serial_sensor_value["Clnt_Flow"] - 3200) / 12800 * 280
                                    (serial_sensor_value["Clnt_Flow"] - 3200) / 12800 * 615
                                )
                            else:
                                print("flow_rate error")

                        except Exception as e:
                            print(f"check version flow_rate: {e}")
                except Exception as e:
                    print(f"ad and serial value error: {e}")

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        adjust_len = (
                            len(sensor_factor.keys()) + len(sensor_offset.keys())
                        ) * 2
                        sensor_adjs = client.read_holding_registers(
                            1400, adjust_len, unit=modbus_slave_id
                        )

                        if sensor_adjs.isError():
                            print(f"Modbus Error: {sensor_adjs}")
                        else:
                            keys_list = list(sensor_factor.keys())

                            for i in range(0, adjust_len, 4):
                                temp1 = [
                                    sensor_adjs.registers[i],
                                    sensor_adjs.registers[i + 1],
                                ]
                                decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
                                    temp1, byteorder=Endian.Big, wordorder=Endian.Little
                                )
                                decoded_value_big_endian = (
                                    decoder_big_endian.decode_32bit_float()
                                )
                                sensor_factor[keys_list[i // 4]] = decoded_value_big_endian

                            for i in range(2, adjust_len, 4):
                                temp1 = [
                                    sensor_adjs.registers[i],
                                    sensor_adjs.registers[i + 1],
                                ]
                                decoder_big_endian = BinaryPayloadDecoder.fromRegisters(
                                    temp1, byteorder=Endian.Big, wordorder=Endian.Little
                                )
                                decoded_value_big_endian = (
                                    decoder_big_endian.decode_32bit_float()
                                )
                                sensor_offset[keys_list[i // 4]] = decoded_value_big_endian

                        for key in ad_sensor_value.keys():
                            if key != "space":
                                all_sensors_dict[key] = (
                                    ad_sensor_value[key] * sensor_factor[key]
                                    + sensor_offset[key]
                                )
                        if not ver_switch["median_switch"]:
                            clnt_flow_data.append(serial_sensor_value["Clnt_Flow"])
                            if len(clnt_flow_data) > 20:
                                clnt_flow_data.popleft()
                            clnt_median = statistics.median(clnt_flow_data)
                            serial_sensor_value["Clnt_Flow"] = clnt_median

                        exclude_this_key = [
                            "Inv1_Freq",
                            "Inv2_Freq",
                            "Inv3_Freq",
                            "fan_freq1",
                            "fan_freq2",
                            "fan_freq3",
                            "fan_freq4",
                            "fan_freq5",
                            "fan_freq6",
                            "fan_freq7",
                            "fan_freq8",
                        ]
                        for key in serial_sensor_value.keys():
                            if key not in exclude_this_key:
                                all_sensors_dict[key] = (
                                    serial_sensor_value[key] * sensor_factor[key]
                                    + sensor_offset[key]
                                )

                        for i in range(1, 4):
                            # bit_output_regs[f"mc{i}"] = True
                            key = f"Inv{i}_Freq"
                            all_sensors_dict[key] = (
                                # 0.1664 * serial_sensor_value[key] + 0.0818
                                ### 將sensor數值 轉為 hz
                                # serial_sensor_value[key] /100
                                ### 將hz 轉為 %
                                serial_sensor_value[key] / 100 / 200 * 100
                            )

                            if not bit_output_regs[f"mc{i}"]:
                                all_sensors_dict[key] = 0

                        # bit_output_regs["mc_fan1"] = True
                        # print(f'bit_output_regs["mc_fan1"]:{bit_output_regs["mc_fan1"]}')

                        ###增加fan_count判斷###
                        if ver_switch["fan_count_switch"]:
                            for i in range(1,7):
                                cvt_rpm = (
                                    fan_raw_status["actual_rpm"][f"Fan{i}"]
                                    / 64000
                                    * fan_raw_status["max_rpm"][f"Fan{i}"]
                                )
                                fan_raw_status["cvt_rpm"][f"Fan{i}"] = cvt_rpm
                            for i in range(1, 4):
                                key = f"fan_freq{i}"
                                all_sensors_dict[key] = (
                                    ##轉速100%, RPM為4150
                                    ### 將RPM 轉為 %
                                    serial_sensor_value[key] / 4150 * 100
                                )
                                if not bit_output_regs["mc_fan1"]:
                                    all_sensors_dict[key] = 0
                            for i in range(4, 7):
                                key = f"fan_freq{i}"
                                all_sensors_dict[key] = (
                                    ##轉速100%, RPM為4150
                                    ### 將RPM 轉為 %
                                    serial_sensor_value[key] / 4150 * 100
                                )
                                if not bit_output_regs["mc_fan2"]:
                                    all_sensors_dict[key] = 0
                        else:
                            for i in range(1, 9):
                                cvt_rpm = (
                                    fan_raw_status["actual_rpm"][f"Fan{i}"]
                                    / 64000
                                    * fan_raw_status["max_rpm"][f"Fan{i}"]
                                )
                                fan_raw_status["cvt_rpm"][f"Fan{i}"] = cvt_rpm
                            for i in range(1, 5):
                                key = f"fan_freq{i}"
                                all_sensors_dict[key] = (
                                    ##轉速100%, RPM為4150
                                    ### 將RPM 轉為 %
                                    serial_sensor_value[key] / 4150 * 100
                                )
                                if not bit_output_regs["mc_fan1"]:
                                    all_sensors_dict[key] = 0
                            for i in range(5, 9):
                                key = f"fan_freq{i}"
                                all_sensors_dict[key] = (
                                    ##轉速100%, RPM為4150
                                    ### 將RPM 轉為 %
                                    serial_sensor_value[key] / 4150 * 100
                                )
                                if not bit_output_regs["mc_fan2"]:
                                    all_sensors_dict[key] = 0

                        heat_capacity = (
                            all_sensors_dict["Clnt_Flow"]
                            * 1.667
                            / 100
                            * 4.18
                            * (
                                #### Heat capacity =  T2 - T1
                                all_sensors_dict["Temp_ClntRtn"]
                                - all_sensors_dict["Temp_ClntSply"]
                            )
                        )

                        all_sensors_dict["Heat_Capacity"] = (
                            heat_capacity * sensor_factor["Heat_Capacity"]
                            + sensor_offset["Heat_Capacity"]
                        )

                except Exception as e:
                    print(f"translate adjust raw data error: {e}")

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        r = client.read_coils((8192 + 500), 1)

                        if r.bits[0]:
                            key_list = list(all_sensors_dict.keys())
                            for key in key_list:
                                if "Temp" in key or "DewPoint" in key:
                                    all_sensors_dict[key] = (
                                        all_sensors_dict[key] * 9.0 / 5.0 + 32.0
                                    )

                                if "Prsr" in key:
                                    all_sensors_dict[key] = all_sensors_dict[key] * 0.145038

                                if "Flow" in key:
                                    all_sensors_dict[key] = all_sensors_dict[key] * 0.2642
                except Exception as e:
                    print(f"change to imperial error: {e}")

                # journal_logger.info(f'serial_sensor_value:{serial_sensor_value}')

                # journal_logger.info(f'all_sensors_dict:{all_sensors_dict}')
                ###將all_sensor寫進D5000
                registers = []
                for key in all_sensors_dict.keys():
                    value = all_sensors_dict[key]

                    word1, word2 = cvt_float_byte(value)
                    registers.append(word2)
                    registers.append(word1)

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        client.write_registers(5000, registers)
                except Exception as e:
                    print(f"write into thrshd error: {e}")
                    
                save_fans_status()
                # 測試用開始
                registers_eletricity = []
                for key in raw_485_data_eletricity:
                    value = raw_485_data_eletricity[key]
                    word1, word2 = cvt_float_byte(value)
                    registers_eletricity.append(word2)
                    registers_eletricity.append(word1)

                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        client.write_registers(7000, registers_eletricity)
                except Exception as e:
                    print(f"write electricity data error: {e}")
                    
                fan_power_registers = []
                fan_rpm_registers = []
                for key in fan_raw_status["current_power"]:
                    value = fan_raw_status["current_power"][key]
                    word1, word2 = cvt_float_byte(value)
                    fan_power_registers.append(word2)
                    fan_power_registers.append(word1)
                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        client.write_registers(7016, fan_power_registers)
                except Exception as e:
                    print(f"write fan power data error: {e}")
                    
                for key in fan_raw_status["cvt_rpm"]:
                    value = fan_raw_status["cvt_rpm"][key]
                    word1, word2 = cvt_float_byte(value)
                    fan_rpm_registers.append(word2)
                    fan_rpm_registers.append(word1)
                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        client.write_registers(7032, fan_rpm_registers)
                except Exception as e:
                    print(f"write fan power data error: {e}")
                # 測試用結束
                # 追加臨時log開始
                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        r = client.read_holding_registers(80, 6, unit=modbus_slave_id)
                        if not r.isError():
                            for i, key in enumerate(temporary_data["raw_value"].keys()):
                                temporary_data["raw_value"][key] = r.registers[i]
                        key_list = list(temporary_data["raw_value"].keys())
                        for key in key_list:
                            if "pressure" in key:
                                if 6400 > temporary_data["raw_value"][key] > 6080:
                                    temporary_data["raw_value"][key] = 6400
                                temporary_data["cvt_value"][key] = (float(temporary_data["raw_value"][key]) - 6400) / 25600.0
                            elif "temperature" in key:
                                temporary_data["cvt_value"][key] = float(temporary_data["raw_value"][key]) / 10.0
                        unit_r = client.read_coils((8192 + 500), 1)
                        if unit_r.bits[0]:
                            for key in key_list:
                                if "temperature" in key:
                                    temporary_data["cvt_value"][key] = (
                                        temporary_data["cvt_value"][key] * 9.0 / 5.0 + 32.0
                                    )
                                elif "pressure" in key:
                                    temporary_data["cvt_value"][key] = (
                                        temporary_data["cvt_value"][key] * 0.145038
                                    )
                except Exception as e:
                    print(f"read temporary data error: {e}")
                    
                registers = []
                for key in temporary_data["cvt_value"].keys():
                    value = temporary_data["cvt_value"][key]
                    word1, word2 = cvt_float_byte(value)
                    registers.append(word2)
                    registers.append(word1)
                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        client.write_registers(7004, registers)
                except Exception as e:
                    print(f"write into temp data error: {e}")
                # 追加臨時log結束
                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        r = client.read_holding_registers(980, 1, unit=modbus_slave_id)

                        dpt_error_setting["t1"] = r.registers[0]

                except Exception as e:
                    print(f"read dew point error setting error: {e}")
                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        if (
                            status_data["TempClntSply"] > dpt_error_setting["t1"]
                        ):
                            client.write_coils((8192 + 751), [True])
                        else:
                            client.write_coils((8192 + 751), [False])

                except Exception as e:
                    print(f"control dpt error setting setting error: {e}")
                trigger_overload_from_oc_detection()

                if mode in ["auto", "stop"]:
                    
                    if (
                        not ver_switch["liquid_level_1_switch"]
                        and not ver_switch["liquid_level_2_switch"]
                        and not ver_switch["liquid_level_3_switch"]
                    ):
                        if (
                            warning_data["alert"]["ClntFlow_Low"]
                            and warning_data["error"]["level1"]
                            and warning_data["error"]["level2"]
                            and warning_data["error"]["level3"]
                        ):
                            warning_data["error"]["Low_Coolant_Level_Warning"] = True
                        elif warning_data["error"]["Low_Coolant_Level_Warning"]:
                            if count_f1 > 5:
                                warning_data["error"]["Low_Coolant_Level_Warning"] = False
                                count_f1 = 0
                            else:
                                count_f1 += 1
                    elif(
                        not ver_switch["liquid_level_1_switch"]
                        and not ver_switch["liquid_level_2_switch"]
                    ):
                        if (
                            warning_data["alert"]["ClntFlow_Low"]
                            and warning_data["error"]["level1"]
                            and warning_data["error"]["level2"]
                        ):
                            warning_data["error"]["Low_Coolant_Level_Warning"] = True
                        elif warning_data["error"]["Low_Coolant_Level_Warning"]:
                            if count_f1 > 5:
                                warning_data["error"]["Low_Coolant_Level_Warning"] = False
                                count_f1 = 0
                            else:
                                count_f1 += 1
                    elif (
                        not ver_switch["liquid_level_1_switch"]
                    ):
                        if (
                            warning_data["alert"]["ClntFlow_Low"]
                            and warning_data["error"]["level1"]
                        ):
                            warning_data["error"]["Low_Coolant_Level_Warning"] = True
                            
                        elif warning_data["error"]["Low_Coolant_Level_Warning"]:
                            if count_f1 > 5:
                                warning_data["error"]["Low_Coolant_Level_Warning"] = False
                                count_f1 = 0
                            else:
                                count_f1 += 1
                                
                if reset_current_btn["status"]:
                    overload_error["Inv1_OverLoad"] = False
                    overload_error["Inv2_OverLoad"] = False
                    overload_error["Inv3_OverLoad"] = False
                    overload_error["Fan_OverLoad1"] = False
                    overload_error["Fan_OverLoad2"] = False
                    reset_btn_false()

                oc_list = list(oc_detection.values())

                if any(oc_list):
                    oc_issue = True
                    if oc_detection["p1"]:
                        bit_output_regs["mc1"] = False
                        clear_p1_speed()

                    if oc_detection["p2"]:
                        bit_output_regs["mc2"] = False
                        clear_p2_speed()

                    if oc_detection["p3"]:
                        bit_output_regs["mc3"] = False
                        clear_p3_speed()

                    if oc_detection["f1"]:
                        bit_output_regs["mc_fan1"] = False
                        clear_fan_group1_speed()

                    if oc_detection["f2"]:
                        bit_output_regs["mc_fan2"] = False
                        clear_fan_group2_speed()

                elif not any(oc_list) and oc_issue:
                    ol_list = list(overload_error.values())
                    if not any(ol_list):
                        reset_mc()
                        oc_issue = False
                    else:
                        if oc_detection["p1"]:
                            bit_output_regs["mc1"] = False
                            clear_p1_speed()

                        if oc_detection["p2"]:
                            bit_output_regs["mc2"] = False
                            clear_p2_speed()

                        if oc_detection["p3"]:
                            bit_output_regs["mc3"] = False
                            clear_p3_speed()

                        if oc_detection["f1"]:
                            bit_output_regs["mc_fan1"] = False
                            clear_fan_group1_speed()

                        if oc_detection["f2"]:
                            bit_output_regs["mc_fan2"] = False
                            clear_fan_group2_speed()
                else:
                    oc_issue = False

                if mode == "manual":
                    check_last_mode_from_inspection(mode_last)
                    if inspection_data["force_change_mode"]:
                        cancel_inspection()
                    reset_inspect_btn()
                    change_inspect_time()
                    diff = 0
                    inspection_data["step"] = 1
                    flag1 = False
                    flag2 = False
                    flag3 = False
                    flag4 = False
                    flag5 = False

                    if overload_error["Inv1_OverLoad"]:
                        clear_p1_speed()
                        flag1 = True

                    if overload_error["Inv2_OverLoad"]:
                        clear_p2_speed()
                        flag2 = True

                    if overload_error["Inv3_OverLoad"]:
                        clear_p3_speed()
                        flag3 = True

                    if overload_error["Fan_OverLoad1"]:
                        clear_fan_group1_speed()
                        flag4 = True

                    if overload_error["Fan_OverLoad2"]:
                        clear_fan_group2_speed()
                        flag5 = True

                    if not flag1:
                        if word_regs["p1_check"]:
                            ps = translate_pump_speed(word_regs["pump_speed"])
                            set_pump1_speed(ps)
                        else:
                            set_pump1_speed(0)

                    if not flag2:
                        if word_regs["p2_check"]:
                            ps = translate_pump_speed(word_regs["pump_speed"])
                            set_pump2_speed(ps)
                        else:
                            set_pump2_speed(0)

                    if not flag3:
                        if word_regs["p3_check"]:
                            ps = translate_pump_speed(word_regs["pump_speed"])
                            set_pump3_speed(ps)
                        else:
                            set_pump3_speed(0)

                    if not flag4:
                        # print(f'word_regs["fan_speed"]:{word_regs["fan_speed"]}')
                        if word_regs["fan_speed"] > 0:
                            fs = translate_fan_speed(word_regs["fan_speed"])
                            ### 如果轉換後大於0
                            ### 等於0的話給 2 % = 320 , 以避免風扇全速轉
                            # print(f'fs:{fs}')
                            if fs > 0:
                                # set_f1(fs if word_regs["f1_check"] else 320)
                                # set_f2(fs if word_regs["f2_check"] else 320)
                                # set_f3(fs if word_regs["f3_check"] else 320)
                                # set_f4(fs if word_regs["f4_check"] else 320)
                                set_f1(fs if word_regs["f1_check"] else 960)
                                set_f2(fs if word_regs["f2_check"] else 960)
                                set_f3(fs if word_regs["f3_check"] else 960)
                                set_f4(fs if word_regs["f4_check"] else 960)
                        else:
                            # set_f1(320)
                            # set_f2(320)
                            # set_f3(320)
                            # set_f4(320)
                            set_f1(960)
                            set_f2(960)
                            set_f3(960)
                            set_f4(960)
                    if not flag5:
                        if word_regs["fan_speed"] > 0:
                            fs = translate_fan_speed(word_regs["fan_speed"])
                            ### 如果轉換後大於0
                            if fs > 0:
                                # set_f5(fs if word_regs["f5_check"] else 320)
                                # set_f6(fs if word_regs["f6_check"] else 320)
                                # set_f7(fs if word_regs["f7_check"] else 320)
                                # set_f8(fs if word_regs["f8_check"] else 320)
                                set_f5(fs if word_regs["f5_check"] else 960)
                                set_f6(fs if word_regs["f6_check"] else 960)
                                set_f7(fs if word_regs["f7_check"] else 960)
                                set_f8(fs if word_regs["f8_check"] else 960)
                        else:
                            # set_f5(320)
                            # set_f6(320)
                            # set_f7(320)
                            # set_f8(320)
                            set_f5(960)
                            set_f6(960)
                            set_f7(960)
                            set_f8(960)

                    mode_last = mode
                    change_back_mode = mode
                elif mode == "auto":
                    check_last_mode_from_inspection(mode_last)
                    if inspection_data["force_change_mode"]:
                        cancel_inspection()
                    diff = 0
                    change_inspect_time()
                    reset_inspect_btn()
                    inspection_data["step"] = 1
                    swap_current = time.time()
                    time_rank = []
                    inv_to_run = []

                    if not first_p:
                        for i in range(1, 4):
                            p_run_min = dword_regs[f"p{i}_run_min"]
                            p_run_hr = dword_regs[f"p{i}_run_hr"]

                            total_time = p_run_hr * 60 + p_run_min

                            time_rank.append((f"p{i}", total_time))

                        time_rank.sort(key=get_key)
                        lowest1 = time_rank[0][0]
                        lowest2 = time_rank[1][0]
                        top = time_rank[2][0]

                        first_p = True

                    try:
                        if swap_current - swap_last >= 60:
                            dword_regs["swap_min"] += 1
                            ##可以以float判斷
                            dword_regs["swap_hr"] = float(dword_regs["swap_min"] / 60)
                            swap_last = swap_current

                        if dword_regs["swap_hr"] >= dword_regs["p_swap"]:
                            for i in range(1, 4):
                                p_run_min = dword_regs[f"p{i}_run_min"]
                                p_run_hr = dword_regs[f"p{i}_run_hr"]

                                total_time = p_run_hr * 60 + p_run_min

                                time_rank.append((f"p{i}", total_time))

                            time_rank.sort(key=get_key)
                            lowest1 = time_rank[0][0]
                            lowest2 = time_rank[1][0]
                            top = time_rank[2][0]

                            # print(f"最小的是：{lowest1} 和 {lowest2}")

                            dword_regs["swap_hr"] = 0
                            dword_regs["swap_min"] = 0
                    except Exception as e:
                        print(f"auto error: {e}")

                    try:
                        l1_key = f"Inv{lowest1[-1]}"
                        l2_key = f"Inv{lowest2[-1]}"
                        t_key = f"Inv{top[-1]}"

                        if check_inverter(l1_key) and check_inverter(l2_key):
                            inv_to_run.append(top)
                        if not check_inverter(l1_key) and check_inverter(l2_key):
                            inv_to_run.append(lowest1)
                            inv_to_run.append(top)
                        if check_inverter(l1_key) and not check_inverter(l2_key):
                            inv_to_run.append(lowest2)
                            inv_to_run.append(top)
                        else:
                            inv_to_run.append(lowest1)
                            inv_to_run.append(lowest2)

                        if top in inv_to_run:
                            if check_inverter(t_key):
                                inv_to_run = []

                        if "p1" in inv_to_run:
                            open_inv1_auto()
                        else:
                            close_inv1_auto()

                        if "p2" in inv_to_run:
                            open_inv2_auto()
                        else:
                            close_inv2_auto()

                        if "p3" in inv_to_run:
                            open_inv3_auto()
                        else:
                            close_inv3_auto()
                    except Exception as e:
                        print(f"run inverter error: {e}")

                    change_back_mode = mode
                    mode_last = "auto"
                elif mode == "stop":
                    check_last_mode_from_inspection(mode_last)
                    if inspection_data["force_change_mode"]:
                        cancel_inspection()
                    diff = 0
                    change_inspect_time()
                    reset_inspect_btn()
                    inspection_data["step"] = 1
                    stop_p1()
                    stop_p2()
                    stop_p3()
                    stop_fan()

                    mode_last = mode
                    change_back_mode = mode
                elif mode == "inspection":
                    read_flow_time = 15
                    pump_open_time = 20
                    fan_open_time = 20
                    error_check_time = 18
                    pump_test_time = 300
                    overload_index = {
                        "Inv": [1, 2, 3],
                        "Fan": [1, 2],
                    }
                    error_index = {
                        "Inv": [1, 2, 3],
                        "fan": [1, 2, 3, 4, 5, 6, 7, 8],
                    }
                    mode_last = mode
                    change_inspect_time()
                    global count

                    ##不需要設定時間
                    # try:
                    #     with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                    #         r = client.read_holding_registers(740, 1)
                    #         pump_open_time = r.registers[0]
                    # except Exception as e:
                    #     print(f"read inspection time error:{e}")

                    if inspection_data["start_btn"] == 1:
                        try:
                            # 步驟一：重置數值
                            if inspection_data["step"] == 1:
                                print("1. 全部重置")

                                inspection_data["start_time"] = time.time()

                                inv1_v, inv2_v, inv3_v = check_inv_speed()
                                ### 紀錄inv速度
                                inspection_data["prev"]["inv1"] = inv1_v
                                inspection_data["prev"]["inv2"] = inv2_v
                                inspection_data["prev"]["inv3"] = inv3_v

                                # 重置所有 result_data

                                for key in inspection_data["result"]:
                                    if (
                                        key == "f1"
                                        or "_com" in key.lower()
                                        or "overload" in key.lower()
                                        or "error" in key.lower()
                                    ):
                                        inspection_data["result"][key] = []
                                    else:
                                        inspection_data["result"][key] = False

                                # 重置所有 status_data

                                for key in inspection_data["prog"]:
                                    change_progress(key, "cancel")

                                try:
                                    # with ModbusTcpClient(
                                    #     host=modbus_host, port=modbus_port
                                    # ) as client:
                                    #     client.write_registers(
                                    #         800, [3] * len(inspection_data["prog"])
                                    #     )
                                    with ModbusTcpClient(
                                        host=modbus_host, port=modbus_port
                                    ) as client:
                                        client.write_registers(
                                            2100, [3] * len(inspection_data["prog"])
                                        )
                                except Exception as e:
                                    print(f"reset inspection error:{e}")

                                # stop_p1()
                                # stop_p2()
                                # stop_p3()
                                # stop_fan()
                                # ###　增加延遲時間讓pump跟fan可關閉到更小數值
                                # time.sleep(2)
                                count += 1

                                if count > 3:
                                    inspection_data["step"] += 0.5
                                    
                            if inspection_data["step"] == 1.5:
                                print(f"1.5 關閉pump & fan : {pump_open_time} 秒")
                                stop_p1()
                                stop_p2()
                                stop_p3()
                                stop_fan()
                                
                                change_progress("p1_speed", "standby")
                                change_progress("p2_speed", "standby")
                                change_progress("p3_speed", "standby")
                                
                                send_progress(0, "p1_speed")
                                send_progress(1, "p2_speed")
                                send_progress(2, "p3_speed")
                                ###　增加延遲時間讓pump跟fan可關閉到更小數值
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["start_time"]
                                )
                                if diff >= pump_open_time:
                                    inspection_data["step"] += 0.5
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]
                                    
                            if inspection_data["step"] == 2:
                                print(f"2. 開啟 inv/mc: {pump_open_time} 秒")

                                bit_output_regs["mc1"] = True
                                bit_output_regs["mc2"] = True
                                bit_output_regs["mc3"] = True

                                speed = translate_pump_speed(40)
                                set_pump1_speed(speed)
                                set_pump2_speed(speed)
                                set_pump3_speed(speed)

                                p1_error_box.append(warning_data["error"]["Inv1_Error"])
                                p1_error_box.append(warning_data["error"]["Inv1_OverLoad"])
                                p1_error_box.append(oc_detection["p1"])

                                p2_error_box.append(warning_data["error"]["Inv2_Error"])
                                p2_error_box.append(warning_data["error"]["Inv2_OverLoad"])
                                p2_error_box.append(oc_detection["p2"])

                                p3_error_box.append(warning_data["error"]["Inv3_Error"])
                                p3_error_box.append(warning_data["error"]["Inv3_OverLoad"])
                                p3_error_box.append(oc_detection["p3"])

                                try:
                                    with ModbusTcpClient(
                                        host=modbus_host, port=modbus_port
                                    ) as client:
                                        r = client.read_holding_registers(5040, 2)

                                        p1 = cvt_registers_to_float(
                                            r.registers[0], r.registers[1]
                                        )
                                        p1_data.append(p1)
                                except Exception as e:
                                    print(f"pump1 speed check: {e}")

                                ### 檢查pump2流速
                                try:
                                    with ModbusTcpClient(
                                        host=modbus_host, port=modbus_port
                                    ) as client:
                                        r = client.read_holding_registers(5042, 2)

                                        p2 = cvt_registers_to_float(
                                            r.registers[0], r.registers[1]
                                        )
                                        p2_data.append(p2)
                                        # print(f'p2_data"{p2_data}')
                                except Exception as e:
                                    print(f"pump2 speed check: {e}")

                                ### 檢查pump3流速
                                try:
                                    with ModbusTcpClient(
                                        host=modbus_host, port=modbus_port
                                    ) as client:
                                        r = client.read_holding_registers(5044, 2)

                                        p3 = cvt_registers_to_float(
                                            r.registers[0], r.registers[1]
                                        )
                                        p3_data.append(p3)
                                except Exception as e:
                                    print(f"pump3 speed check: {e}")

                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_open_time:
                                    inspection_data["step"] += 1
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]

                                # 即時更新進度

                                send_progress(0, "p1_speed")
                                send_progress(1, "p2_speed")
                                send_progress(2, "p3_speed")

                            if inspection_data["step"] == 3:
                                print(f"3. 測所有 inv/mc：{pump_open_time} 秒")

                                if any(p1_error_box):
                                    print("跳過 p1")
                                    change_progress("p1_speed", "skip")

                                    ###送NG給前端
                                    inspection_data["result"]["p1_speed"] = True
                                    stop_p1()
                                    send_all(0, "p1_speed")
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]
                                else:
                                    # p1_data = [50]
                                    max_p1 = max(p1_data)
                                    print(f"max_p1:{max_p1}")

                                    ###超過範圍就送NG給前端
                                    inspection_data["result"]["p1_speed"] = not (
                                        45 > max_p1 > 35
                                    )
                                    write_measured_data(1, max_p1)
                                    change_progress("p1_speed", "finish")

                                if any(p2_error_box):
                                    print("跳過 p2")
                                    change_progress("p2_speed", "skip")
                                    inspection_data["result"]["p2_speed"] = True
                                    stop_p2()
                                    send_all(1, "p2_speed")
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]
                                else:
                                    max_p2 = max(p2_data)
                                    inspection_data["result"]["p2_speed"] = not (
                                        45 > max_p2 > 35
                                    )
                                    write_measured_data(3, max_p2)
                                    change_progress("p2_speed", "finish")

                                if any(p3_error_box):
                                    print("跳過 p3")
                                    change_progress("p3_speed", "skip")
                                    inspection_data["result"]["p3_speed"] = True
                                    stop_p3()
                                    send_all(2, "p3_speed")
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]
                                else:
                                    max_p3 = max(p3_data)
                                    inspection_data["result"]["p3_speed"] = not (
                                        45 > max_p3 > 35
                                    )
                                    write_measured_data(5, max_p3)
                                    change_progress("p3_speed", "finish")

                                inspection_data["step"] += 0.1
                                inspection_data["end_time"] = time.time()
                                inspection_data["mid_time"] = inspection_data["end_time"]
                                send_all(0, "p1_speed")
                                send_all(1, "p2_speed")
                                send_all(2, "p3_speed")

                            if inspection_data["step"] == 3.1:
                                print(f"3.1 開 f1：{read_flow_time} 秒")

                                speed = translate_pump_speed(40)
                                set_pump1_speed(speed)
                                set_pump2_speed(speed)
                                set_pump3_speed(speed)

                                if (
                                    warning_data["alert"]["ClntFlow_Low"]
                                    ### 測試是否換成broken
                                    # or warning_data["error"][
                                    #     "coolant_flow_rate_communication"
                                    # ]
                                    or warning_data["error"]["Clnt_Flow_broken"]
                                ):
                                    inspection_data["result"]["f1"].append(True)
                                else:
                                    inspection_data["result"]["f1"].append(False)

                                f1_data.append(status_data["ClntFlow"])

                                change_progress("f1", "standby")
                                send_progress(3, "f1")

                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff > read_flow_time:
                                    inspection_data["step"] += 0.1
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]

                            if inspection_data["step"] == 3.2:
                                print("3.2 測 f1")
                                max_f1 = max(f1_data)
                                ### 測試是否換成broken
                                # if warning_data["error"]["coolant_flow_rate_communication"]:
                                if warning_data["error"]["Clnt_Flow_broken"]:
                                    max_f1 = 0

                                write_measured_data(7, max_f1)
                                print(f"F1 結果：{max_f1}")

                                inspection_data["result"]["f1"] = not (150 >= max_f1 >= 50)
                                # if all_sensors_dict["Temp_ClntRtn"] >= 50:
                                #     inspection_data["result"]["f1"] = not (130 > max_f1 > 100)
                                # elif all_sensors_dict["Temp_ClntRtn"] >= 40 and all_sensors_dict["Temp_ClntRtn"] < 50:
                                #     inspection_data["result"]["f1"] = not (110 > max_f1 > 80)
                                # elif all_sensors_dict["Temp_ClntRtn"] >= 30 and all_sensors_dict["Temp_ClntRtn"] < 40:
                                #     inspection_data["result"]["f1"] = not (90 > max_f1 > 60)
                                # elif all_sensors_dict["Temp_ClntRtn"] >= 20 and all_sensors_dict["Temp_ClntRtn"] < 30:
                                #     inspection_data["result"]["f1"] = not (70 > max_f1 > 40)
                                
                                change_progress("f1", "finish")
                                send_all(3, "f1")

                                inspection_data["step"] += 0.3
                                inspection_data["end_time"] = time.time()
                                inspection_data["mid_time"] = inspection_data["end_time"]

                            if inspection_data["step"] == 3.5:
                                print("3.5 停pump")
                                # journal_logger.info("5.5 測 liquid & power")

                                stop_p1()
                                stop_p2()
                                stop_p3()

                                inspection_data["step"] += 0.5

                            if inspection_data["step"] == 4:
                                ###測fan
                                print(f"4. 開啟 Fan 的 inv/mc: {fan_open_time} 秒")
                                bit_output_regs["mc_fan1"] = True
                                bit_output_regs["mc_fan2"] = True
                                for i in range(1, 9):
                                    change_progress(f"fan{i}_speed", "standby")

                                speed = translate_fan_speed(30)
                                set_f1(speed)
                                set_f2(speed)
                                set_f3(speed)
                                set_f4(speed)
                                set_f5(speed)
                                set_f6(speed)
                                set_f7(speed)
                                set_f8(speed)

                                fan1_error_boxes = {
                                    "1": fan1_error_box,
                                    "2": fan2_error_box,
                                    "3": fan3_error_box,
                                    "4": fan4_error_box,
                                }

                                for i in ["1", "2", "3", "4"]:
                                    fan1_error_boxes[i].append(
                                        warning_data["error"][f"fan{i}_error"]
                                    )
                                    fan1_error_boxes[i].append(
                                        warning_data["error"]["Fan_OverLoad1"]
                                    )
                                    fan1_error_boxes[i].append(oc_detection["f1"])

                                fan2_error_boxes = {
                                    "5": fan5_error_box,
                                    "6": fan6_error_box,
                                    "7": fan7_error_box,
                                    "8": fan8_error_box,
                                }

                                for i in ["5", "6", "7", "8"]:
                                    fan2_error_boxes[i].append(
                                        warning_data["error"][f"fan{i}_error"]
                                    )
                                    fan2_error_boxes[i].append(
                                        warning_data["error"]["Fan_OverLoad2"]
                                    )
                                    fan2_error_boxes[i].append(oc_detection["f2"])

                                def read_fan_flow(address):
                                    try:
                                        with ModbusTcpClient(
                                            host=modbus_host, port=modbus_port
                                        ) as client:
                                            r = client.read_holding_registers(address, 2)
                                            return cvt_registers_to_float(
                                                r.registers[0], r.registers[1]
                                            )
                                    except Exception as e:
                                        print(
                                            f"Fan at address {address} speed check error: {e}"
                                        )
                                        return None

                                fan_addresses = [
                                    5048,
                                    5050,
                                    5052,
                                    5054,
                                    5056,
                                    5058,
                                    5060,
                                    5062,
                                ]
                                fan_data_lists = [
                                    fan1_data,
                                    fan2_data,
                                    fan3_data,
                                    fan4_data,
                                    fan5_data,
                                    fan6_data,
                                    fan7_data,
                                    fan8_data,
                                ]

                                for addr, data_list in zip(fan_addresses, fan_data_lists):
                                    flow = read_fan_flow(addr)
                                    if flow is not None:
                                        data_list.append(flow)
                                        # print(f'data_list:{data_list}')

                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= fan_open_time:
                                    inspection_data["step"] += 1
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]
                                send_progress(43, "fan1_speed")
                                send_progress(44, "fan2_speed")
                                send_progress(45, "fan3_speed")
                                send_progress(46, "fan4_speed")
                                send_progress(47, "fan5_speed")
                                send_progress(48, "fan6_speed")
                                send_progress(49, "fan7_speed")
                                send_progress(50, "fan8_speed")

                                # print(f"4. 開 f1：{read_flow_time} 秒")

                                # speed = translate_pump_speed(50)
                                # set_pump1_speed(speed)
                                # set_pump2_speed(speed)
                                # set_pump3_speed(speed)

                                # if (
                                #     warning_data["alert"]["ClntFlow_Low"]
                                #     ### 測試是否換成broken
                                #     # or warning_data["error"][
                                #     #     "coolant_flow_rate_communication"
                                #     # ]
                                #     or warning_data["error"][
                                #         "Clnt_Flow_broken"
                                #     ]
                                # ):
                                #     inspection_data["result"]["f1"].append(True)
                                # else:
                                #     inspection_data["result"]["f1"].append(False)

                                # f1_data.append(status_data["ClntFlow"])

                                # change_progress("f1", "standby")
                                # send_progress(3, "f1")

                                # inspection_data["end_time"] = time.time()
                                # diff = (
                                #     inspection_data["end_time"]
                                #     - inspection_data["mid_time"]
                                # )
                                # if diff > read_flow_time:
                                #     inspection_data["step"] += 1
                                #     inspection_data["mid_time"] = inspection_data[
                                #         "end_time"
                                #     ]

                            if inspection_data["step"] == 5:
                                print("5. 測所有 Fan 的 inv/mc")

                                fan_error_box = {
                                    "fan1": fan1_error_box,
                                    "fan2": fan2_error_box,
                                    "fan3": fan3_error_box,
                                    "fan4": fan4_error_box,
                                    "fan5": fan5_error_box,
                                    "fan6": fan6_error_box,
                                    "fan7": fan7_error_box,
                                    "fan8": fan8_error_box,
                                }

                                fan_data = {
                                    "fan1": fan1_data,
                                    "fan2": fan2_data,
                                    "fan3": fan3_data,
                                    "fan4": fan4_data,
                                    "fan5": fan5_data,
                                    "fan6": fan6_data,
                                    "fan7": fan7_data,
                                    "fan8": fan8_data,
                                }

                                for i in range(1, 9):
                                    fan_id = f"fan{i}"
                                    speed_key = f"{fan_id}_speed"

                                    if any(fan_error_box[fan_id]):
                                        print(f"跳過 {fan_id}")
                                        change_progress(speed_key, "skip")

                                        inspection_data["result"][speed_key] = True

                                        send_all(0, speed_key)
                                        inspection_data["mid_time"] = inspection_data[
                                            "end_time"
                                        ]
                                    else:
                                        max_value = max(fan_data[fan_id])
                                        # print(f"max_{fan_id}: {max_value}")

                                        # 判斷範圍
                                        ###RPM判斷範圍30% 為1245  1452~1037
                                        # inspection_data["result"][speed_key] = not (50 > max_value > 45)
                                        inspection_data["result"][speed_key] = not (
                                            35 > max_value > 25
                                        )
                                        write_measured_data(30 + (i * 2 - 1), max_value)
                                        change_progress(speed_key, "finish")

                                stop_fan()
                                inspection_data["step"] += 0.5
                                inspection_data["end_time"] = time.time()
                                inspection_data["mid_time"] = inspection_data["end_time"]
                                send_all(43, "fan1_speed")
                                send_all(44, "fan2_speed")
                                send_all(45, "fan3_speed")
                                send_all(46, "fan4_speed")
                                send_all(47, "fan5_speed")
                                send_all(48, "fan6_speed")
                                send_all(49, "fan7_speed")
                                send_all(50, "fan8_speed")


                            if inspection_data["step"] == 5.5:
                                print("5.5 測 liquid & power")
                            #     journal_logger.info("5.5 測 liquid & power")

                                for k, level in enumerate(level_sw):
                                    inspection_data["result"][level] = not level_sw[level]
                                    change_progress(level, "finish")
                                    send_all(36 + k, level)

                                ###讓broken standby
                            #     for x, key in enumerate(inspection_data["result"], start=0):
                            #         if "_broken" in key:
                            #             change_progress(key, "standby")
                            #             send_progress(4 + x, key)

                                inspection_data["step"] += 0.5

                            if inspection_data["step"] == 6:
                                print("6. 測 broken")

                                i = j = z = 0

                                for key in inspection_data["result"]:
                                    if "_broken" in key:
                                        delete_part = "_broken"
                                        raw_key = key.replace(delete_part, "")

                                        if "Temp_" in key:
                                            temp_check = (
                                                sensor_raw[raw_key] > 1000
                                                or sensor_raw[raw_key] < -100
                                            )
                                            inspection_data["result"][key] = temp_check
                                            change_progress(key, "finish")
                                            send_all(4 + i, key)
                                            i += 1

                                        if "Prsr_" in key:
                                            prsr_check = sensor_raw[raw_key] < 1200
                                            inspection_data["result"][key] = prsr_check
                                            change_progress(key, "finish")
                                            send_all(8 + j, key)
                                            j += 1

                                        if "Flow_" in key:
                                            # journal_logger.info(f'serial_sensor_value')
                                            flow_check = (
                                                sensor_raw[raw_key] < 1000
                                                or sensor_raw[raw_key] > 20000
                                            )
                                            inspection_data["result"][key] = flow_check
                                            change_progress(key, "finish")
                                            send_all(14 + z, key)
                                            z += 1

                                for (
                                    register,
                                    status_key,
                                ) in measured_data_mapping.items():
                                    write_measured_data(register, status_data[status_key])

                                for n, key in enumerate(raw_485_comm):
                                    key_name = f"{key}_com"
                                    change_progress(key_name, "standby")
                                    send_progress(15 + n, key_name)

                                inspection_data["step"] += 1
                                inspection_data["end_time"] = time.time()
                                inspection_data["mid_time"] = inspection_data["end_time"]

                            if inspection_data["step"] == 7:
                                print(f"7. 測 communication：{error_check_time} 秒")

                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )

                                if int(diff) % 4 == 0 and diff <= error_check_time:
                                    for key, value in raw_485_comm.items():
                                        key_name = f"{key}_com"
                                        inspection_data["result"][key_name].append(
                                            not value
                                        )

                                if int(diff) > error_check_time:
                                    for key, index_list in overload_index.items():
                                        for i in index_list:
                                            key_name = f"{key}{i}_OverLoad"
                                            if key == "Inv":
                                                change_progress(key_name, "standby")
                                                send_progress(50 + i, key_name)
                                            elif key == "Fan":
                                                change_progress(key_name, "standby")
                                                send_progress(53 + i, key_name)

                                    for k, key in enumerate(raw_485_comm):
                                        key_name = f"{key}_com"
                                        inspection_data["result"][key_name] = not any(
                                            inspection_data["result"][key_name]
                                        )
                                        change_progress(key_name, "finish")
                                        send_all(15 + k, key_name)
                                    inspection_data["step"] += 1
                                    inspection_data["end_time"] = time.time()
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]

                            if inspection_data["step"] == 8:
                                print(f"8. 測inv/fan OverLoad：{error_check_time} 秒")

                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )

                                if int(diff) % 4 == 0 and diff <= error_check_time:
                                    for key, index_list in overload_index.items():
                                        for i in index_list:
                                            if key == "Inv":
                                                key_name = f"Inv{i}_OverLoad"
                                                value = (
                                                    1
                                                    if warning_data["error"][key_name]
                                                    else 0
                                                )
                                                inspection_data["result"][key_name].append(
                                                    not value
                                                )
                                            elif key == "Fan":
                                                key_name = f"Fan_OverLoad{i}"
                                                value = (
                                                    1
                                                    if warning_data["error"][key_name]
                                                    else 0
                                                )
                                                inspection_data["result"][key_name].append(
                                                    not value
                                                )
                                if int(diff) > error_check_time:
                                    for key, index_list in error_index.items():
                                        for i in index_list:
                                            if key == "Inv":
                                                key_name = f"Inv{i}_Error"
                                                change_progress(key_name, "standby")
                                                send_progress(55 + i, key_name)
                                            elif key == "fan":
                                                key_name = f"fan{i}_error"
                                                change_progress(key_name, "standby")
                                                send_progress(58 + i, key_name)

                                    for key, index_list in overload_index.items():
                                        for i in index_list:
                                            if key == "Inv":
                                                key_name = f"Inv{i}_OverLoad"
                                                inspection_data["result"][
                                                    key_name
                                                ] = not any(
                                                    inspection_data["result"][key_name]
                                                )
                                                change_progress(key_name, "finish")
                                                send_all(50 + i, key_name)
                                            elif key == "Fan":
                                                key_name = f"Fan_OverLoad{i}"
                                                inspection_data["result"][
                                                    key_name
                                                ] = not any(
                                                    inspection_data["result"][key_name]
                                                )
                                                change_progress(key_name, "finish")
                                                send_all(53 + i, key_name)
                                    inspection_data["step"] += 1
                                    inspection_data["end_time"] = time.time()
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]

                            if inspection_data["step"] == 9:
                                print(f"9. 測inv/fan error：{error_check_time} 秒")

                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )

                                if int(diff) % 4 == 0 and diff <= error_check_time:
                                    for key, index_list in error_index.items():
                                        for i in index_list:
                                            if key == "Inv":
                                                key_name = f"Inv{i}_Error"
                                                value = (
                                                    1
                                                    if warning_data["error"][key_name]
                                                    else 0
                                                )
                                                inspection_data["result"][key_name].append(
                                                    not value
                                                )
                                            elif key == "fan":
                                                key_name = f"fan{i}_error"
                                                value = (
                                                    1
                                                    if warning_data["error"][key_name]
                                                    else 0
                                                )
                                                inspection_data["result"][key_name].append(
                                                    not value
                                                )
                                if int(diff) > error_check_time:
                                    inspection_data["step"] +=1
                                    
                                    
                                    change_progress("pump_test1", "standby")
                                    send_progress(67, "pump_test1")
                                    
                                    
                                    for key, index_list in error_index.items():
                                        for i in index_list:
                                            if key == "Inv":
                                                key_name = f"Inv{i}_Error"
                                                inspection_data["result"][
                                                    key_name
                                                ] = not any(
                                                    inspection_data["result"][key_name]
                                                )
                                                change_progress(key_name, "finish")
                                                send_all(55 + i, key_name)
                                            elif key == "fan":
                                                key_name = f"fan{i}_error"
                                                inspection_data["result"][
                                                    key_name
                                                ] = not any(
                                                    inspection_data["result"][key_name]
                                                )
                                                change_progress(key_name, "finish")
                                                send_all(58 + i, key_name)
                                                
                            if inspection_data["step"] == 10:
                                print(f"10. 測pump1, 2, 3 全開60% ：{pump_test_time} 秒")
                                
                                bit_output_regs["mc1"] = True
                                bit_output_regs["mc2"] = True
                                bit_output_regs["mc3"] = True

                                speed = translate_pump_speed(60)
                                set_pump1_speed(speed)
                                set_pump2_speed(speed)
                                set_pump3_speed(speed)
                                
                                
                                test_t1_1 = status_data["TempClntSply"]
                                test_ac_1 = status_data["AC"]
                                test_av_1 = raw_485_data_eletricity["average_voltage"]
                                test_flow_rate_1 = status_data["ClntFlow"]
                                test_prsr_rtn_1 = status_data["PrsrClntRtn"]  
                                test_prsr_sup_1 = status_data["PrsrClntSply"]   
                                
                                ####2900開始寫measured data
                                write_measured_data(2000, test_t1_1) 
                                write_measured_data(2002, test_ac_1)
                                write_measured_data(2004, test_av_1)
                                write_measured_data(2006, test_flow_rate_1)
                                write_measured_data(2008, test_prsr_rtn_1)
                                write_measured_data(2010, test_prsr_sup_1)
                                
                                
                                
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    
                                    change_progress("pump_test1", "finish")
                                    send_progress(67, "pump_test1")
                                    
                                    change_progress("pump_test2", "standby")
                                    send_progress(68, "pump_test2")
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]

                                
                                
                            if inspection_data["step"] == 11:
                                print(f"11. 測pump1, 2 :40% ：{pump_test_time} 秒")
                                

                                speed = translate_pump_speed(40)
                                set_pump1_speed(speed)
                                set_pump2_speed(speed)
                                set_pump3_speed(0)

                                test_t1_2 = status_data["TempClntSply"]
                                test_ac_2 = status_data["AC"]
                                test_av_2 = raw_485_data_eletricity["average_voltage"]
                                test_flow_rate_2 = status_data["ClntFlow"]
                                test_prsr_rtn_2 = status_data["PrsrClntRtn"]  
                                test_prsr_sup_2 = status_data["PrsrClntSply"]   
                                
                                ####2900開始寫measured data
                                write_measured_data(2012, test_t1_2) 
                                write_measured_data(2014, test_ac_2)
                                write_measured_data(2016, test_av_2)
                                write_measured_data(2018, test_flow_rate_2)
                                write_measured_data(2020, test_prsr_rtn_2)
                                write_measured_data(2022, test_prsr_sup_2)
                                
                                
                                
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    change_progress("pump_test2", "finish")
                                    send_progress(68, "pump_test2")
                                    
                                    change_progress("pump_test3", "standby")
                                    send_progress(69, "pump_test3")
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]

                                
                            if inspection_data["step"] == 12:
                                print(f"12. 測pump1, 2 :80% ：{pump_test_time} 秒")                     
                                
                                
                                speed = translate_pump_speed(80)
                                set_pump1_speed(speed)
                                set_pump2_speed(speed)
                                set_pump3_speed(0)

                                test_t1_3 = status_data["TempClntSply"]
                                test_ac_3 = status_data["AC"]
                                test_av_3 = raw_485_data_eletricity["average_voltage"]
                                test_flow_rate_3 = status_data["ClntFlow"]
                                test_prsr_rtn_3 = status_data["PrsrClntRtn"]  
                                test_prsr_sup_3 = status_data["PrsrClntSply"]   
                                
                                ####2900開始寫measured data
                                write_measured_data(2024, test_t1_3) 
                                write_measured_data(2026, test_ac_3)
                                write_measured_data(2028, test_av_3)
                                write_measured_data(2030, test_flow_rate_3)
                                write_measured_data(2032, test_prsr_rtn_3)
                                write_measured_data(2034, test_prsr_sup_3)
                                
                                
                                print(f'inspection_data["step"]:{inspection_data["step"]}')
                                
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    
                                    # print(f'inspection_data["step"]:{inspection_data["step"]}')
                                    
                                    change_progress("pump_test3", "finish")
                                    send_progress(69, "pump_test3")
                                    
                                    change_progress("pump_test4", "standby")
                                    send_progress(70, "pump_test4")
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]


                                
                            if inspection_data["step"] == 13:
                                print(f"13 測pump1, 3 :40% ：{pump_test_time} 秒")
                                
                                
                                speed = translate_pump_speed(40)
                                set_pump1_speed(speed)
                                set_pump2_speed(0)
                                set_pump3_speed(speed)
                                
                                test_t1_4 = status_data["TempClntSply"]
                                test_ac_4 = status_data["AC"]
                                test_av_4 = raw_485_data_eletricity["average_voltage"]
                                test_flow_rate_4 = status_data["ClntFlow"]
                                test_prsr_rtn_4 = status_data["PrsrClntRtn"]  
                                test_prsr_sup_4 = status_data["PrsrClntSply"]   
                                
                                ####2900開始寫measured data
                                write_measured_data(2036, test_t1_4) 
                                write_measured_data(2038, test_ac_4)
                                write_measured_data(2040, test_av_4)
                                write_measured_data(2042, test_flow_rate_4)
                                write_measured_data(2044, test_prsr_rtn_4)
                                write_measured_data(2046, test_prsr_sup_4)
                                
                                
                                
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    
                                    change_progress("pump_test4", "finish")
                                    send_progress(70, "pump_test4")
                                    
                                    change_progress("pump_test5", "standby")
                                    send_progress(71, "pump_test5")
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]


                                
                            if inspection_data["step"] == 14:
                                print(f"14 測pump1, 3 :80% ：{pump_test_time} 秒")
                                
                                speed = translate_pump_speed(80)
                                set_pump1_speed(speed)
                                set_pump2_speed(0)
                                set_pump3_speed(speed)
                                
                                test_t1_5 = status_data["TempClntSply"]
                                test_ac_5 = status_data["AC"]
                                test_av_5 = raw_485_data_eletricity["average_voltage"]
                                test_flow_rate_5 = status_data["ClntFlow"]
                                test_prsr_rtn_5 = status_data["PrsrClntRtn"]  
                                test_prsr_sup_5 = status_data["PrsrClntSply"]   
                                
                                ####2900開始寫measured data
                                write_measured_data(2048, test_t1_5) 
                                write_measured_data(2050, test_ac_5)
                                write_measured_data(2052, test_av_5)
                                write_measured_data(2054, test_flow_rate_5)
                                write_measured_data(2056, test_prsr_rtn_5)
                                write_measured_data(2058, test_prsr_sup_5)
                                
                                
                                
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    
                                    change_progress("pump_test5", "finish")
                                    send_progress(71, "pump_test5")
                                    
                                    change_progress("pump_test6", "standby")
                                    send_progress(72, "pump_test6")
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]


                                
                                
                            if inspection_data["step"] == 15:
                                print(f"15 測pump2, 3 :40% ：{pump_test_time} 秒")
                                
                                speed = translate_pump_speed(40)
                                set_pump1_speed(0)
                                set_pump2_speed(speed)
                                set_pump3_speed(speed)
                                
                                test_t1_6 = status_data["TempClntSply"]
                                test_ac_6 = status_data["AC"]
                                test_av_6 = raw_485_data_eletricity["average_voltage"]
                                test_flow_rate_6 = status_data["ClntFlow"]
                                test_prsr_rtn_6 = status_data["PrsrClntRtn"]  
                                test_prsr_sup_6 = status_data["PrsrClntSply"]   
                                
                                ####2900開始寫measured data
                                write_measured_data(2060, test_t1_6) 
                                write_measured_data(2062, test_ac_6)
                                write_measured_data(2064, test_av_6)
                                write_measured_data(2066, test_flow_rate_6)
                                write_measured_data(2068, test_prsr_rtn_6)
                                write_measured_data(2070, test_prsr_sup_6)
                                
                                
                                
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    change_progress("pump_test6", "finish")
                                    send_progress(72, "pump_test6")
                                    
                                    change_progress("pump_test7", "standby")
                                    send_progress(73, "pump_test7")
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]




                                
                            if inspection_data["step"] == 16:
                                print(f"16 測pump2, 3 :80% ：{pump_test_time} 秒") 
                                
                                
                                speed = translate_pump_speed(80)
                                set_pump1_speed(0)
                                set_pump2_speed(speed)
                                set_pump3_speed(speed) 
                                
                                
                                test_t1_7 = status_data["TempClntSply"]
                                test_ac_7 = status_data["AC"]
                                test_av_7 = raw_485_data_eletricity["average_voltage"]
                                test_flow_rate_7 = status_data["ClntFlow"]
                                test_prsr_rtn_7 = status_data["PrsrClntRtn"]  
                                test_prsr_sup_7 = status_data["PrsrClntSply"]   
                                
                                ####2900開始寫measured data
                                write_measured_data(2072, test_t1_7) 
                                write_measured_data(2074, test_ac_7)
                                write_measured_data(2076, test_av_7)
                                write_measured_data(2078, test_flow_rate_7)
                                write_measured_data(2080, test_prsr_rtn_7)
                                write_measured_data(2082, test_prsr_sup_7)
                                
                                
                                
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    change_progress("pump_test7", "finish")
                                    send_progress(73, "pump_test7")
                                    
                                    ##關pump
                                    set_pump1_speed(0)
                                    set_pump2_speed(0)
                                    set_pump3_speed(0) 
                                                                
                                    change_progress("fan_test1", "standby")
                                    send_progress(74, "fan_test1")
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]


                                
                                
                            if inspection_data["step"] == 17:
                                print(f"17. 測風扇全開:15% ：{pump_test_time} 秒") 
                                                        
                                bit_output_regs["mc_fan1"] = True
                                bit_output_regs["mc_fan2"] = True
                                
                                speed = translate_fan_speed(15)
                                set_f1(speed)
                                set_f2(speed)
                                set_f3(speed)
                                set_f4(speed)
                                set_f5(speed)
                                set_f6(speed)
                                set_f7(speed)
                                set_f8(speed)
                                
                                test_ac_8 = status_data["AC"]
                                test_ap_1 = raw_485_data_eletricity["apparent_power"]
                                
                                write_measured_data(2084, test_ac_8) 
                                write_measured_data(2086, test_ap_1)
                                
                                                            
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    
                                    change_progress("fan_test1", "finish")
                                    send_progress(74, "fan_test1")
                                    
                                    change_progress("fan_test2", "standby")
                                    send_progress(75, "fan_test2")
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]

                                
                            if inspection_data["step"] == 18:
                                print(f"18 測風扇全開:40% ：{pump_test_time} 秒")    
                                
                                speed = translate_fan_speed(40)
                                set_f1(speed)
                                set_f2(speed)
                                set_f3(speed)
                                set_f4(speed)
                                set_f5(speed)
                                set_f6(speed)
                                set_f7(speed)
                                set_f8(speed)
                            
                            
                                test_ac_9 = status_data["AC"]
                                test_ap_2 = raw_485_data_eletricity["apparent_power"]
                                
                                write_measured_data(2088, test_ac_9) 
                                write_measured_data(2090, test_ap_2)
                                
                                                            
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    
                                    change_progress("fan_test2", "finish")
                                    send_progress(75, "fan_test2")
                                    
                                    change_progress("fan_test3", "standby")
                                    send_progress(76, "fan_test3")
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]

                                
                                
                            if inspection_data["step"] == 19:
                                print(f"19 測風扇全開:80% ：{pump_test_time} 秒")    
                                            
                                speed = translate_fan_speed(80)
                                set_f1(speed)
                                set_f2(speed)
                                set_f3(speed)
                                set_f4(speed)
                                set_f5(speed)
                                set_f6(speed)
                                set_f7(speed)
                                set_f8(speed)
                            
                                test_ac_10 = status_data["AC"]
                                test_ap_3 = raw_485_data_eletricity["apparent_power"]
                                
                                write_measured_data(2092, test_ac_10) 
                                write_measured_data(2094, test_ap_3)
                                
                                                            
                                inspection_data["end_time"] = time.time()
                                diff = (
                                    inspection_data["end_time"]
                                    - inspection_data["mid_time"]
                                )
                                if diff >= pump_test_time:
                                    inspection_data["step"] += 1
                                    change_progress("fan_test3", "finish")
                                    send_progress(76, "fan_test3")
                                    
                                    set_f1(0)
                                    set_f2(0)
                                    set_f3(0)
                                    set_f4(0)
                                    set_f5(0)
                                    set_f6(0)
                                    set_f7(0)
                                    set_f8(0)
                                    
                                    inspection_data["mid_time"] = inspection_data[
                                        "end_time"
                                    ]



                            if inspection_data["step"] == 20:
                                print("20. 最後收尾")

                                f1_data = []
                                p1_data = []
                                p2_data = []
                                p3_data = []
                                fan1_data = []
                                fan2_data = []
                                fan3_data = []
                                fan4_data = []
                                fan5_data = []
                                fan6_data = []
                                fan7_data = []
                                fan8_data = []
                                p1_error_box = []
                                p2_error_box = []
                                p3_error_box = []
                                fan1_error_box = []
                                fan2_error_box = []
                                fan3_error_box = []
                                fan4_error_box = []
                                fan5_error_box = []
                                fan6_error_box = []
                                fan7_error_box = []
                                fan8_error_box = []

                                try:
                                    with ModbusTcpClient(
                                        host=modbus_host, port=modbus_port
                                    ) as client:
                                        value_list_status = list(
                                            inspection_data["prog"].values()
                                        )
                                        # client.write_registers(800, value_list_status)
                                        client.write_registers(2100, value_list_status)
                                except Exception as e:
                                    print(f"result write-in:{e}")

                                for key, status in inspection_data["prog"].items():
                                    if status == 1:
                                        inspection_data["result"][key] = False

                                try:
                                    with ModbusTcpClient(
                                        host=modbus_host, port=modbus_port
                                    ) as client:
                                        value_list_result = [
                                            1 if value else 0
                                            for value in inspection_data["result"].values()
                                        ]
                                        # client.write_registers(750, value_list_result)
                                        client.write_registers(2000, value_list_result)

                                except Exception as e:
                                    print(f"result write-in:{e}")

                                reset_inspect_btn()

                                go_back_to_last_mode(change_back_mode)
                                mode_last = mode

                                inspection_data["step"] = 1
                                inspection_data["start_time"] = 0
                                inspection_data["mid_time"] = 0
                                inspection_data["end_time"] = 0
                                diff = 0

                                try:
                                    with ModbusTcpClient(
                                        host=modbus_host, port=modbus_port
                                    ) as client:
                                        client.write_register(973, 2)
                                except Exception as e:
                                    print(f"reset error: {e}")
                        except Exception as e:
                            print(f"inspect error:{e}")

                    elif inspection_data["start_btn"] == 2:
                        print("被 cancel")

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                value_list_status = list(inspection_data["prog"].values())
                                value_list_status = [
                                    1 if value == 4 else value
                                    for value in value_list_status
                                ]

                                # client.write_registers(800, value_list_status)
                                client.write_registers(2100, value_list_status)

                        except Exception as e:
                            print(f"result write-in:{e}")

                        for key, status in inspection_data["prog"].items():
                            if status == 1:
                                inspection_data["result"][key] = False

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                value_list_result = [
                                    1 if value else 0
                                    for value in inspection_data["result"].values()
                                ]
                                # client.write_registers(750, value_list_result)
                                client.write_registers(2000, value_list_result)

                        except Exception as e:
                            print(f"result write-in:{e}")

                        reset_inspect_btn()

                        go_back_to_last_mode(change_back_mode)

                        mode_last = mode

                        inspection_data["step"] = 1
                        inspection_data["start_time"] = 0
                        inspection_data["mid_time"] = 0
                        inspection_data["end_time"] = 0
                        diff = 0
                        print("結束囉")

                ### inspection 部分結束

                # for i in range(1, 4):
                #     if (
                #         not bit_output_regs[f"mc{i}"]
                #         or warning_data["error"][f"Inv{i}_Error"]
                #     ):
                #         if i == 1:
                #             clear_p1_speed()
                #         elif i == 2:
                #             clear_p2_speed()
                #         elif i == 3:
                #             clear_p3_speed()

                try:
                    output_value = list(bit_output_regs.values())
                    light_value = list(color_light.values())
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        client.write_coils(2, output_value)
                        client.write_coils(14, light_value)
                        client.write_coils((8192 + 700), [oc_issue])
                except Exception as e:
                    print(f"set output data error: {e}")

                ### 計算pump runtime
                if (raw_485_data["Inv1_Freq"] / 200) > 25:
                    pump1_run_current_time = time.time()

                    if pump1_run_current_time - pump1_run_last_min >= 60:
                        dword_regs["p1_run_min"] += 1
                        dword_regs["p1_run_hr"] = int(dword_regs["p1_run_min"] / 60)
                        pump1_run_last_min = pump1_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                rt1_min = split_double([dword_regs["p1_run_min"]])
                                rt1_hr = split_double([dword_regs["p1_run_hr"]])

                                client.write_registers(270, rt1_min)
                                client.write_registers(272, rt1_hr)

                                client.write_registers(200, rt1_hr)

                        except Exception as e:
                            print(f"read pump1 runtime error: {e}")
                else:
                    pump1_run_last_min = time.time()

                # if inv["inv2"]:
                if (raw_485_data["Inv2_Freq"] / 200) > 25:
                    
                    pump2_run_current_time = time.time()

                    if pump2_run_current_time - pump2_run_last_min >= 60:
                        dword_regs["p2_run_min"] += 1
                        dword_regs["p2_run_hr"] = int(dword_regs["p2_run_min"] / 60)
                        pump2_run_last_min = pump2_run_current_time
                        registers = []
                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                rt2_min = split_double([dword_regs["p2_run_min"]])
                                rt2_hr = split_double([dword_regs["p2_run_hr"]])

                                client.write_registers(274, rt2_min)
                                client.write_registers(276, rt2_hr)

                                client.write_registers(202, rt2_hr)

                        except Exception as e:
                            print(f"read pump2 runtime error: {e}")
                else:
                    pump2_run_last_min = time.time()

                # if inv["inv3"]:
                if (raw_485_data["Inv3_Freq"] / 200) > 25:
                
                    pump3_run_current_time = time.time()

                    if pump3_run_current_time - pump3_run_last_min >= 60:
                        dword_regs["p3_run_min"] += 1
                        dword_regs["p3_run_hr"] = int(dword_regs["p3_run_min"] / 60)
                        pump3_run_last_min = pump3_run_current_time
                        registers = []
                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                rt3_min = split_double([dword_regs["p3_run_min"]])
                                rt3_hr = split_double([dword_regs["p3_run_hr"]])

                                client.write_registers(278, rt3_min)
                                client.write_registers(280, rt3_hr)
                                client.write_registers(204, rt3_hr)

                        except Exception as e:
                            print(f"read pump3 runtime error: {e}")
                else:
                    pump3_run_last_min = time.time()

                ### 計算 fan1 runtime
                ###如果有速度
                if raw_485_data["Fan1Com"] or inv["fan1"]:
                    fan1_run_current_time = time.time()

                    if fan1_run_current_time - fan1_run_last_min >= 60:
                        dword_regs["f1_run_min"] += 1
                        dword_regs["f1_run_hr"] = int(dword_regs["f1_run_min"] / 60)
                        fan1_run_last_min = fan1_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                f_rt1_min = split_double([dword_regs["f1_run_min"]])
                                f_rt1_hr = split_double([dword_regs["f1_run_hr"]])

                                client.write_registers(310, f_rt1_min)
                                client.write_registers(312, f_rt1_hr)

                                client.write_registers(350, f_rt1_hr)

                        except Exception as e:
                            print(f"read fan1 runtime error: {e}")
                else:
                    fan1_run_last_min = time.time()

                ### 計算 fan2 runtime
                if raw_485_data["Fan2Com"] or inv["fan2"]:
                    fan2_run_current_time = time.time()

                    if fan2_run_current_time - fan2_run_last_min >= 60:
                        dword_regs["f2_run_min"] += 1
                        dword_regs["f2_run_hr"] = int(dword_regs["f2_run_min"] / 60)
                        fan2_run_last_min = fan2_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                f_rt2_min = split_double([dword_regs["f2_run_min"]])
                                f_rt2_hr = split_double([dword_regs["f2_run_hr"]])

                                client.write_registers(314, f_rt2_min)
                                client.write_registers(316, f_rt2_hr)

                                client.write_registers(352, f_rt2_hr)

                        except Exception as e:
                            print(f"read fan2 runtime error: {e}")
                else:
                    fan2_run_last_min = time.time()

                ### 計算 fan3 runtime
                if raw_485_data["Fan3Com"] or inv["fan3"]:
                    fan3_run_current_time = time.time()

                    if fan3_run_current_time - fan3_run_last_min >= 60:
                        dword_regs["f3_run_min"] += 1
                        dword_regs["f3_run_hr"] = int(dword_regs["f3_run_min"] / 60)
                        fan3_run_last_min = fan3_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                f_rt3_min = split_double([dword_regs["f3_run_min"]])
                                f_rt3_hr = split_double([dword_regs["f3_run_hr"]])

                                client.write_registers(318, f_rt3_min)
                                client.write_registers(320, f_rt3_hr)

                                client.write_registers(354, f_rt3_hr)

                        except Exception as e:
                            print(f"read fan3 runtime error: {e}")
                else:
                    fan3_run_last_min = time.time()

                ### 計算 fan4 runtime
                if raw_485_data["Fan4Com"] or inv["fan4"]:
                    fan4_run_current_time = time.time()

                    if fan4_run_current_time - fan4_run_last_min >= 60:
                        dword_regs["f4_run_min"] += 1
                        dword_regs["f4_run_hr"] = int(dword_regs["f4_run_min"] / 60)
                        fan4_run_last_min = fan4_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                f_rt4_min = split_double([dword_regs["f4_run_min"]])
                                f_rt4_hr = split_double([dword_regs["f4_run_hr"]])

                                client.write_registers(322, f_rt4_min)
                                client.write_registers(324, f_rt4_hr)

                                client.write_registers(356, f_rt4_hr)

                        except Exception as e:
                            print(f"read fan4 runtime error: {e}")
                else:
                    fan4_run_last_min = time.time()

                ### 計算 fan5 runtime
                if raw_485_data["Fan5Com"] or inv["fan5"]:
                    fan5_run_current_time = time.time()

                    if fan5_run_current_time - fan5_run_last_min >= 60:
                        dword_regs["f5_run_min"] += 1
                        dword_regs["f5_run_hr"] = int(dword_regs["f5_run_min"] / 60)
                        fan5_run_last_min = fan5_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                f_rt5_min = split_double([dword_regs["f5_run_min"]])
                                f_rt5_hr = split_double([dword_regs["f5_run_hr"]])

                                client.write_registers(326, f_rt5_min)
                                client.write_registers(328, f_rt5_hr)

                                client.write_registers(358, f_rt5_hr)

                        except Exception as e:
                            print(f"read fan5 runtime error: {e}")
                else:
                    fan5_run_last_min = time.time()

                ### 計算 fan6 runtime
                if raw_485_data["Fan6Com"] or inv["fan6"]:
                    fan6_run_current_time = time.time()

                    if fan6_run_current_time - fan6_run_last_min >= 60:
                        dword_regs["f6_run_min"] += 1
                        dword_regs["f6_run_hr"] = int(dword_regs["f6_run_min"] / 60)
                        fan6_run_last_min = fan6_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                f_rt6_min = split_double([dword_regs["f6_run_min"]])
                                f_rt6_hr = split_double([dword_regs["f6_run_hr"]])

                                client.write_registers(330, f_rt6_min)
                                client.write_registers(332, f_rt6_hr)

                                client.write_registers(360, f_rt6_hr)

                        except Exception as e:
                            print(f"read fan6 runtime error: {e}")
                else:
                    fan6_run_last_min = time.time()

                ### 計算 fan7 runtime
                if raw_485_data["Fan7Com"] or inv["fan7"]:
                    fan7_run_current_time = time.time()

                    if fan7_run_current_time - fan7_run_last_min >= 60:
                        dword_regs["f7_run_min"] += 1
                        dword_regs["f7_run_hr"] = int(dword_regs["f7_run_min"] / 60)
                        fan7_run_last_min = fan7_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                f_rt7_min = split_double([dword_regs["f7_run_min"]])
                                f_rt7_hr = split_double([dword_regs["f7_run_hr"]])

                                client.write_registers(334, f_rt7_min)
                                client.write_registers(336, f_rt7_hr)

                                client.write_registers(362, f_rt7_hr)

                        except Exception as e:
                            print(f"read fan7 runtime error: {e}")
                else:
                    fan7_run_last_min = time.time()

                ### 計算 fan8 runtime
                if raw_485_data["Fan8Com"] or inv["fan8"]:
                    fan8_run_current_time = time.time()

                    if fan8_run_current_time - fan8_run_last_min >= 60:
                        dword_regs["f8_run_min"] += 1
                        dword_regs["f8_run_hr"] = int(dword_regs["f8_run_min"] / 60)
                        fan8_run_last_min = fan8_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                f_rt8_min = split_double([dword_regs["f8_run_min"]])
                                f_rt8_hr = split_double([dword_regs["f8_run_hr"]])

                                client.write_registers(338, f_rt8_min)
                                client.write_registers(340, f_rt8_hr)

                                client.write_registers(364, f_rt8_hr)

                        except Exception as e:
                            print(f"read fan8 runtime error: {e}")
                else:
                    fan8_run_last_min = time.time()

                ### 計算 filter runtime
                if (raw_485_data["Inv1_Freq"] / 200) > 25 or (raw_485_data["Inv2_Freq"] / 200) > 25 or (raw_485_data["Inv3_Freq"] / 200) > 25:
                    filter_run_current_time = time.time()

                    if filter_run_current_time - filter_run_last_min >= 60:
                        dword_regs["filter_run_min"] += 1
                        dword_regs["filter_run_hr"] = int(dword_regs["filter_run_min"] / 60)
                        filter_run_last_min = filter_run_current_time

                        try:
                            with ModbusTcpClient(
                                host=modbus_host, port=modbus_port
                            ) as client:
                                filter_rt1_min = split_double([dword_regs["filter_run_min"]])
                                filter_rt1_hr = split_double([dword_regs["filter_run_hr"]])

                                client.write_registers(342, filter_rt1_min)
                                client.write_registers(344, filter_rt1_hr)
                                client.write_registers(366, filter_rt1_hr)

                        except Exception as e:
                            print(f"read pump runtime error: {e}")
                else:
                    filter_run_last_min = time.time()


                set_warning_registers(mode)

                time.sleep(1)
            except Exception as e:
                print(f"TCP Client Error: {e}")

            ### 與PLC相同 結束
            try:
                if restart_server["stage"] == 1:
                    client.write_coils(12, [True])
                    print("按10秒 on")

                    restart_server["diff"] += time.time() - restart_server["start"]

                    if restart_server["diff"] > 10:
                        restart_server["stage"] = 2

                elif restart_server["stage"] == 2:
                    client.write_coils(12, [False])
                    print("按1秒 off")
                    restart_server["diff"] += time.time() - restart_server["start"]
                    if restart_server["diff"] > 16:
                        restart_server["stage"] = 3

                elif restart_server["stage"] == 3:
                    client.write_coils(12, [True])
                    print("按1秒 on")
                    restart_server["diff"] += time.time() - restart_server["start"]
                    if restart_server["diff"] > 18:
                        restart_server["stage"] = 4

                elif restart_server["stage"] == 4:
                    client.write_coils(12, [False])
                    restart_server["diff"] = 0
                    restart_server["start"] = 0
                    zero_flag = True
                    print("回歸 off")

            except Exception as e:
                print(f"server 1 restart error:{e}")


duration = 0.5


def rtu_thread():
    prev_plc_error = False  # 追踪上一次的 PLC 錯誤狀態
    
    global change_to_server2

    client = ModbusSerialClient(
        method="rtu",
        port="/dev/ttyS0",
        baudrate=19200,
        parity="E",
        stopbits=1,
        bytesize=8,
        timeout=0.5,
    )

    try:
        while True:
            global ver_switch
            time.sleep(1)
            # journal_logger.info("RS485 is not waiting....")

            if change_to_server2:
            ### 與PLC相同 開始 (要tab一次)
         
                try:
                    # journal_logger.info(f'start first')
                    if not client.connect():
                        # journal_logger.info(f'not in first')
                        for key in raw_485_data.keys():
                            raw_485_data[key] = 0
                            raw_485_comm[key] = True
                        if not prev_plc_error:  # 避免重複記錄
                            print("Failed to connect to Modbus server")
                            journal_logger.info("Failed to connect to Modbus server")
                            prev_plc_error = True  # 記錄錯誤狀態

                        time.sleep(2)
                        continue

                    try:
                        # journal_logger.info(f'in first')
                        r = client.read_holding_registers(2, 2, unit=4)
                        prev_plc_error = False  # 連接恢復正常時，重置 prev_plc_error

                        t3 = cvt_registers_to_float(r.registers[0], r.registers[1])
                        raw_485_data["AmbientTemp"] = t3
                        raw_485_comm["AmbientTemp"] = False
                    except Exception as e:
                        raw_485_comm["AmbientTemp"] = True
                        journal_logger.info(f"Ambient Temperature error: {e}")

                    time.sleep(duration)

                    try:
                        r = client.read_holding_registers(0, 2, unit=4)
                        rh = cvt_registers_to_float(r.registers[0], r.registers[1])
                        raw_485_data["RelativeHumid"] = rh
                        raw_485_comm["RelativeHumid"] = False
                    except Exception as e:
                        raw_485_comm["RelativeHumid"] = True
                        print(f"Relative Humidity error: {e}")

                    time.sleep(duration)

                    try:
                        r = client.read_holding_registers(8, 2, unit=4)
                        dewPt = cvt_registers_to_float(r.registers[0], r.registers[1])
                        raw_485_data["DewPoint"] = dewPt
                        raw_485_comm["DewPoint"] = False
                    except Exception as e:
                        raw_485_comm["DewPoint"] = False
                        print(f"Dew Point Temperature error: {e}")

                    time.sleep(duration)

                    try:
                        r = client.read_holding_registers(0, 2, unit=9)
                        pH = cvt_registers_to_float(r.registers[0], r.registers[1])
                        raw_485_data["pH"] = pH
                        raw_485_comm["pH"] = False
                    except Exception as e:
                        raw_485_comm["pH"] = True
                        print(f"pH error: {e}")

                    time.sleep(duration)

                    try:
                        r = client.read_holding_registers(0, 2, unit=7)
                        CON = cvt_registers_to_float(r.registers[0], r.registers[1])
                        raw_485_data["conductivity"] = CON
                        raw_485_comm["conductivity"] = False
                    except Exception as e:
                        raw_485_comm["conductivity"] = True
                        print(f"CON error: {e}")

                    time.sleep(duration)

                    try:
                        r = client.read_holding_registers(0, 2, unit=8)
                        Tur = cvt_registers_to_float(r.registers[0], r.registers[1])
                        raw_485_data["turbidity"] = Tur
                        raw_485_comm["turbidity"] = False
                    except Exception as e:
                        raw_485_comm["turbidity"] = True
                        print(f"Turbidity error: {e}")

                    time.sleep(duration)

                    try:
                        r = client.read_holding_registers(3059, 2, unit=3)

                        instant = cvt_registers_to_float(r.registers[1], r.registers[0])
                        # journal_logger.info(f'instant:{instant}')
                        raw_485_data["inst_power"] = instant
                        raw_485_comm["inst_power"] = False
                    except Exception as e:
                        raw_485_comm["inst_power"] = True
                        print(f"Instant Power Consumption error: {e}")

                    time.sleep(duration)

                    try:
                        r = client.read_holding_registers(3009, 2, unit=3)
                        # journal_logger.info(f'r.registers[0]:{r.registers[0]}')
                        # journal_logger.info(f'r.registers[1]:{r.registers[1]}')
                        ac = cvt_registers_to_float(r.registers[1], r.registers[0])
                        # journal_logger.info(f'ac:{ac}')

                        raw_485_data["average_current"] = ac
                        raw_485_comm["average_current"] = False
                    except Exception as e:
                        raw_485_comm["average_current"] = True
                        print(f"Average Current error: {e}")
                    # 測試用開始
                    time.sleep(duration)

                    try:
                        r = client.read_holding_registers(3025, 2, unit=3)
                        average_voltage = cvt_registers_to_float(
                            r.registers[1], r.registers[0]
                        )
                        raw_485_data_eletricity["average_voltage"] = average_voltage
                        raw_485_comm_eletricity["average_voltage"] = False
                    except Exception as e:
                        raw_485_comm_eletricity["average_voltage"] = True
                        print(f"Average Voltage error: {e}")

                    time.sleep(duration)
                    # Apparent Power
                    try:
                        r = client.read_holding_registers(3075, 2, unit=3)
                        apparent_power = cvt_registers_to_float(
                            r.registers[1], r.registers[0]
                        )
                        raw_485_data_eletricity["apparent_power"] = apparent_power
                        raw_485_comm_eletricity["apparent_power"] = False
                    except Exception as e:
                        raw_485_comm_eletricity["apparent_power"] = True
                        print(f"Average Voltage error: {e}")
                    # 測試用結束
                    time.sleep(duration)

                    pump_units = [1, 2, 11]

                    for i, pump in enumerate(pump_units, start=1):
                        try:
                            r = client.read_holding_registers(
                                address=8451, count=1, unit=pump
                            )
                            raw_485_data[f"Inv{i}_Freq"] = r.registers[0]
                            raw_485_comm[f"Inv{i}_Freq"] = False
                        except Exception as e:
                            raw_485_comm[f"Inv{i}_Freq"] = True
                            print(f"Pump{i} error: {e}")

                        time.sleep(duration)

                    fan_units = [12, 13, 14, 15, 16, 17, 18, 19]
                    # fan_units_6 = [16, 17, 18, 12, 13, 14]
                    fan_units_6 = [12, 13, 14, 16, 17, 18]

                    if ver_switch["fan_count_switch"]:
                        for i, unit in enumerate(fan_units_6, start=1):
                            try:
                                r = client.read_input_registers(53293, 1, unit=unit)
                                
                                energy_r = client.read_input_registers(53287, 1, unit=unit)
                                actual_rpm = client.read_input_registers(53264, 1, unit=unit)
                                max_rpm = client.read_holding_registers(53529, 1, unit=unit)
                                fan_raw_status["current_power"][f"Fan{i}"] = energy_r.registers[0]
                                fan_raw_status["max_rpm"][f"Fan{i}"] = max_rpm.registers[0]
                                fan_raw_status["actual_rpm"][f"Fan{i}"] = (
                                    actual_rpm.registers[0]
                                )
                                ###fan status(error、warning)
                                status_r = client.read_input_registers(53265, 2, unit=unit)
                                fan_raw_status["error"][f"Fan{i}"] = status_r.registers[0]
                                fan_raw_status["warning"][f"Fan{i}"] = status_r.registers[1]
                                ###fan speed freq
                                raw_485_data[f"Fan{i}Com"] = r.registers[0]
                                raw_485_comm[f"Fan{i}Com"] = False
                            except Exception as e:
                                raw_485_comm[f"Fan{i}Com"] = True
                                print(f"Fan {i} error: {e}")

                            time.sleep(duration)
                    else:
                        for i, unit in enumerate(fan_units, start=1):
                            try:
                                r = client.read_input_registers(53293, 1, unit=unit)
                                
                                energy_r = client.read_input_registers(53287, 1, unit=unit)
                                actual_rpm = client.read_input_registers(
                                    53264, 1, unit=unit
                                )
                                max_rpm = client.read_holding_registers(53529, 1, unit=unit)
                                fan_raw_status["current_power"][f"Fan{i}"] = (
                                    energy_r.registers[0]
                                )
                                fan_raw_status["max_rpm"][f"Fan{i}"] = max_rpm.registers[0]
                                fan_raw_status["actual_rpm"][f"Fan{i}"] = (
                                    actual_rpm.registers[0]
                                )
                                ###fan status(error、warning)
                                status_r = client.read_input_registers(53265, 2, unit=unit)
                                fan_raw_status["error"][f"Fan{i}"] = status_r.registers[0]
                                fan_raw_status["warning"][f"Fan{i}"] = status_r.registers[1]
                                ###fan speed freq
                                raw_485_data[f"Fan{i}Com"] = r.registers[0]
                                raw_485_comm[f"Fan{i}Com"] = False
                            except Exception as e:
                                raw_485_comm[f"Fan{i}Com"] = True
                                print(f"Fan {i} error: {e}")

                            time.sleep(duration)

                    # try:
                    #     r = client.read_discrete_inputs(6, 9, unit=10)
                    #     # 嘗試只讀一個
                    #     # r = client.read_discrete_inputs(6, 1, unit=10)
                    #     # r = client.read_discrete_inputs(14, 1, unit=10)
                    #     ats1 = bool(r.bits[0])
                    #     ats2 = bool(r.bits[8])
                    #     raw_485_data["ATS1"] = ats1 == 1
                    #     raw_485_data["ATS2"] = ats2 == 1
                    #     raw_485_comm["ATS1"] = False
                    #     raw_485_comm["ATS2"] = False

                    # except Exception as e:
                    #     raw_485_comm["ATS1"] = True
                    #     raw_485_comm["ATS2"] = True
                    #     print(f"ATS error: {e}")

                    # time.sleep(duration)

                    # ### 嘗試讀取 add = 40, 並拆分出第3及第9個位元
                    try:
                        r = client.read_input_registers(40, 1, unit=10)
                        reg_value = r.registers[0]
                        bit_index1 = 3  # 第 3 個位元
                        bit_index2 = 9  # 第 9 個位元
                        bit_value1 = (reg_value >> bit_index1) & 1
                        bit_value2 = (reg_value >> bit_index2) & 1
                        # print(f'bit_value2:{bit_value2}')
                        ats1 = bool(bit_value1)
                        ats2 = bool(bit_value2)
                        raw_485_data["ATS1"] = ats1 == 1
                        raw_485_data["ATS2"] = ats2 == 1
                        raw_485_comm["ATS1"] = False
                        raw_485_comm["ATS2"] = False

                    except Exception as e:
                        raw_485_comm["ATS1"] = True
                        # raw_485_comm["ATS2"] = True
                        print(f"ATS error: {e}")

                    time.sleep(duration)

                    # journal_logger.info(f"485 數據：{raw_485_data}")
                    # journal_logger.info(f"485 通訊：{raw_485_comm}")
                except Exception as e:
                    print(f"enclosed: {e}")

            ### 與PLC相同 結束

    except Exception as e:
        print(f"485 issue: {e}")
    finally:
        client.close()


def rack_thread():
    global change_to_server2

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

    while True:
        time.sleep(1)
        # journal_logger.info("RS485 is not waiting....")
        if change_to_server2:
            
            ### 與PLC相同 開始 (要tab一次)
    
            try:
                try:
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        r = client.read_coils((8192 + 710), 20)
                        for x, key in enumerate(rack_data["rack_control"].keys()):
                            rack_data["rack_control"][key] = r.bits[x]
                except Exception as e:
                    print(f"rack control error: {e}")
                    continue

                try:
                    # rack_sw_count = 0
                    # for i in range(10):
                    #     control_key = f"Rack_{i + 1}_Control"
                    #     if rack_data["rack_control"][control_key]:
                    #         rack_sw_count += 1
                    # percent = 35 + (rack_sw_count - 1) * 5 if rack_sw_count >= 1 else 0
                    # opening_value = 4095 * percent / 100
                    try:
                        with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                            r = client.read_holding_registers(370, 1)
                            rack_data["rack_opening"] = r.registers[0]
                    except Exception as e:
                        print(f"rack control error: {e}")

                    for i in range(10):
                        enable_key = f"Rack_{i + 1}_Enable"
                        control_key = f"Rack_{i + 1}_Control"
                        ip_key = f"rack{i + 1}"
                        rack_ip = host[ip_key]
                        pass_key = f"Rack_{i + 1}_Pass"
                        opening_value = 4095 * rack_data["rack_opening"] / 100
                        if rack_data["rack_control"][enable_key]:
                            try:
                                with ModbusTcpClient(
                                    host=rack_ip, port=modbus_port, timeout=0.5
                                ) as client:
                                    if rack_data["rack_control"][control_key]:
                                        client.write_register(0, round(opening_value))
                                    else:
                                        client.write_register(0, 0)
                                    rack_data["rack_pass"][pass_key] = True
                            except Exception as e:
                                rack_data["rack_pass"][pass_key] = False
                                print(f"rack input error: {e}")
                                # journal_logger.info(f"rack input error: {e}")
                except Exception as e:
                    print(f"rack key error: {e}")

                try:
                    coil_values = list(rack_data["rack_pass"].values())
                    with ModbusTcpClient(host=modbus_host, port=modbus_port) as client:
                        client.write_coils((8192 + 730), coil_values)
                except Exception as e:
                    print(f"pass error: {e}")
            except Exception as e:
                print(f"enclosed: {e}")

            ### 與PLC相同 結束

            time.sleep(2)


rack_thread_obj = threading.Thread(target=rack_thread)
rack_thread_obj.daemon = True
rack_thread_obj.start()


thread = threading.Thread(target=control)
thread.daemon = True
thread.start()


if onLinux:
    rtu_thread_obj = threading.Thread(target=rtu_thread)
    rtu_thread_obj.daemon = True
    rtu_thread_obj.start()

try:
    while True:
        time.sleep(30)
except KeyboardInterrupt:
    print("程序已终止")

except Exception as e:
    print(f"異常：{e}")
