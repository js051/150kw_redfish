'''
這是Redfish的managers service
'''
import subprocess, json
import requests
import datetime   
from zoneinfo import ZoneInfo
from flask import jsonify
from http import HTTPStatus
from load_env import hardware_info, redfish_info
from mylib.services.base_service import BaseService
from mylib.models.rf_networkprotocol_model import RfNetworkProtocolModel
from mylib.models.rf_snmp_model import RfSnmpModel, rf_SNMP
from mylib.adapters.webapp_api_adapter import WebAppAPIAdapter
from mylib.models.rf_resource_model import RfResetType
from mylib.common.proj_response_message import ProjResponseMessage
from mylib.models.setting_model import SettingModel
from mylib.utils.load_api import load_raw_from_api, CDU_BASE
from mylib.utils.system_info import get_physical_nics
from mylib.models.rf_ethernetinterfaces_model import RfEthernetInterfacesModel, RfEthernetInterfacesIdModel
from mylib.models.rf_status_model import RfStatusModel
from mylib.models.rf_manager_model import RfManagerModel
from mylib.utils.system_setting import set_ntp, set_NetwrokInterface
from mylib.common.proj_error import ProjRedfishError, ProjRedfishErrorCode
from mylib.db.db_util import reset_to_defaults


class RfManagersService(BaseService):
    # =================通用工具===================    
    def save_networkprotocol(self, service: str, setting):
        """
        儲存 network protocol 設定
        :param service: str, 協定名稱 (e.g., "SNMP", "NTP")
        :param setting: dict, 包含協定設定的字典(e.g., {"ProtocolEnabled": True, "Port": 123, "ntp_server": "pool.ntp.org"})
        """
        if service is "NTP" and setting["ntp_server"] is not None:
            SettingModel().save_key_value(f"Managers.{service}.NTPServer", setting["ntp_server"])
        SettingModel().save_key_value(f"Managers.{service}.ProtocolEnabled", setting["ProtocolEnabled"])
        SettingModel().save_key_value(f"Managers.{service}.Port", setting["Port"])
    
    def get_networkprotocol(self, servie: str):
        """
        取得 network protocol 設定
        :param servie: str, 協定名稱 (e.g., "SNMP", "NTP")
        :return: dict, 包含協定設定的字典(e.g., {"ProtocolEnabled": True, "Port": 123, "ntp_server": "pool.ntp.org"})
        """
        # SettingModel().get_by_key(f"Managers.{servie}.ProtocolEnabled")
        # SettingModel().get_by_key(f"Managers.{servie}.Port")  
        return {"ProtocolEnabled": bool(int(SettingModel().get_by_key(f"Managers.{servie}.ProtocolEnabled").value)), "Port": int(SettingModel().get_by_key(f"Managers.{servie}.Port").value)}
            
    def save_manager_setting(self, key: str, value: str):
        """
        儲存 managers 設定
        :param key: str, 設定的鍵名
        :param value: str, 設定的值
        """
        return SettingModel().save_key_value(f"Managers.{key}", value)
    
    def get_manager_setting(self, key: str) -> str:
        """
        取得 managers 設定
        :param key: str, 設定的鍵名
        :return: str, 設定的值
        """
        return SettingModel().get_by_key(f"Managers.{key}").value
    
    def get_hostname(self):
        """
        取得主機名稱
        :return: str, 主機名稱
        """
        return subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
    # =================系統時間===================
    # 取得目前時區 IANA 格式 
    def get_current_timezone(self):
        """
        Returns: Asia/Taipei
        """
        try:
            p = subprocess.run(
                ["/usr/bin/timedatectl", "show", "-p", "Timezone", "--value"],
                    capture_output=True, text=True, check=True
            )
            tz = p.stdout.strip()
            return tz 
        except:
            return None
        
    # 轉換 IANA 格式
    def offset_to_iana(self,offset: str) -> str:
        """
        從 yaml 轉換IANA時區格式
        :param offset: str, 時區偏移量 (e.g., "+08:00", "-02:00")
        :return: str, IANA 時區名稱 (e.g., "Asia/Taipei", "America/New_York")
        """
        return redfish_info["TimeZoneName"].get(offset, "UTC")
    
    # 設定系統時間
    def apply_system_time(self, date_time_iso: str,
                        offset: str ) -> bool:
        """
        date_time_iso:  "2025-06-24T10:00:00-02:00"
        offset:         "+08:00"
        """
        # print("date_time_iso:", date_time_iso)
        # print("offset:", offset)
        try:
            subprocess.run(["/usr/bin/sudo", "timedatectl", "set-ntp", "False"], check=True)
            if date_time_iso:
                # 轉換 ISO 8601 時間格式到 UTC
                utc = subprocess.run(
                    ["/usr/bin/date", "-u", "-d", date_time_iso, "+%Y-%m-%d %H:%M:%S"],
                    text=True, check=True, capture_output=True
                )
                utc = utc.stdout.strip()
                # 設定系統時間
                subprocess.run(["/usr/bin/sudo", "/usr/bin/date", "-u", "-s", utc])

            if offset:
                tz_name = self.offset_to_iana(offset)
                # print("tz_name:", tz_name)
                # 設定時區 沒有就設定 UTC +00:00
                subprocess.run(
                    ["/usr/bin/sudo", "timedatectl", "set-timezone", tz_name]
                )

            return bool(date_time_iso or offset)
        except subprocess.CalledProcessError:
            return False
    
    def get_ethernet_data(self):
        return get_physical_nics()      
    
    def get_ethernet_entry(self, target_name, data):
        entry = next((item for item in data if item['Name'] == target_name), None)
        return entry
    
    def net_info(self, interfaces): # 測試暫放
        print(f"共 {len(interfaces)} 張實體網卡：")
        for iface in interfaces:
            print(f"- {iface['Name']}:")
            print(f"    MAC           : {iface['MAC']}")
            print(f"    IPv4          : {iface['IPv4']}")
            print(f"    SubnetMask    : {iface['SubnetMask']}")
            print(f"    AddressOrigin : {iface['AddressOrigin']}")
            print(f"    Gateway       : {iface['Gateway']}")
            print(f"    NameServers   : {iface['NameServers']}")
            print(f"    IPv6          : {iface['IPv6']}")
            print(f"    Speed (Mbps)  : {iface['Speed_Mbps']}")
            print(f"    MTU           : {iface['MTU']}")
            print(f"    Duplex        : {iface['FullDuplex']}")
            print(f"    IsUp          : {iface['isUp']}")
            
    # ================Managers/cdu================  
    def get_managers(self, cdu_id):
        m = RfManagerModel(cdu_id)
        # time
        # 取得 IANA 時區
        tz = self.get_current_timezone() or "Asia/Taipei"
        date_now = datetime.datetime.now(ZoneInfo(tz)).replace(microsecond=0)
        # print(date_now)
        offset = date_now.strftime('%z')[:3] + ':' + date_now.strftime('%z')[3:]
        dt_str = date_now.strftime('%Y-%m-%dT%H:%M:%S') + "Z"

        m.DateTimeLocalOffset = offset
        m.DateTime            = dt_str
        
        m.TimeZoneName = tz
        # m.LastResetTime = "2025-01-24T07:08:48Z",
        # m.DateTimeSource = "NTP",
        m.ManagerType = "ManagementController"
        m.ServiceIdentification = self.get_manager_setting("ServiceIdentification")
        # m.PowerState = "On"
        m.WriteableProperties = [ # 告知客戶可修改的項目
            "DateTime",
            "DateTimeLocalOffset",
            "ServiceIdentification"
        ]
        
        return m.to_dict()
    
    # (時區問題 夏令、冬令 有些地區會差1小時)
    def patch_managers(self, cdu_id, body):
        DateTime = body.get("DateTime", None)
        DateTimeLocalOffset = body.get("DateTimeLocalOffset", None)
        ServiceIdentification = body.get("ServiceIdentification", None)
        
        try:
            if DateTime is not None or DateTimeLocalOffset is not None:
                self.apply_system_time(DateTime, DateTimeLocalOffset)
            self.save_manager_setting("ServiceIdentification", ServiceIdentification)
            
            return {"message": "Manager settings updated successfully"}, 200
        except Exception as e:
            raise ProjRedfishError(
                code=ProjRedfishErrorCode.GENERAL_ERROR, 
                message=f"{str(e)}"
            )
        
    # ================NetworkProtocol================
    def NetworkProtocol_service(self) -> dict:
        m = RfNetworkProtocolModel()
        m.HostName = self.get_hostname()
        m.FQDN = "null"
        m.SNMP = rf_SNMP(**self.get_networkprotocol("SNMP"))
        
        return m.to_dict()
    
    def NetworkProtocol_service_patch(self, body):
        snmp_ProtocolEnabled = body.get("SNMP", {}).get("ProtocolEnabled", None)
        ntp_ProtocolEnabled = body.get("NTP", {}).get("ProtocolEnabled", None)
        
        if snmp_ProtocolEnabled is not None:
            snmp_ProtocolEnabled = 1 if snmp_ProtocolEnabled else 0 
            snmp_setting ={
                "ProtocolEnabled": snmp_ProtocolEnabled,
                "Port": 9000
            } 
            self.save_networkprotocol("SNMP", snmp_setting)
            
        if ntp_ProtocolEnabled is not None:    
            ntp_ProtocolEnabled = 1 if ntp_ProtocolEnabled else 0
            ntp_servers = body.get("NTP", {}).get("NTPServers") or []
            ntp_setting = {
                "ProtocolEnabled": ntp_ProtocolEnabled,
                "Port": 123,
                "ntp_server": ntp_servers[0] if ntp_servers else None
            }
            # print("NTP setting:", ntp_setting)
            self.save_networkprotocol("NTP", ntp_setting)
            set_ntp(ntp_ProtocolEnabled, ntp_setting["ntp_server"])
            
            
        return self.NetworkProtocol_service(), 200
    
    def NetworkProtocol_Snmp_get(self) -> dict:
        '''
        取得 SNMP 設定
        '''
        snmp_data = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/Snmp")
        m = RfSnmpModel(
            TrapIP = snmp_data["trap_ip_address"],
            Community = snmp_data["read_community"]
        )
        

        return m.to_dict()
       
    def NetworkProtocol_Snmp_Post(self, body: dict) -> dict:
        trap_ip_address = body["TrapIP"]
        read_community = body["Community"]
        data = {
            "trap_ip_address": trap_ip_address,
            "read_community":  read_community
        }
        try:
            r = WebAppAPIAdapter().setting_snmp(data)
            return jsonify({ "message": r.text })      
            # return r.json(), r.status_code
        except requests.HTTPError as e:
            # 如果 CDU 回了 4xx/5xx，直接把它的 status code 和 body 回來
            raise ProjRedfishError(
                code=ProjRedfishErrorCode.INTERNAL_ERROR, 
                message=f"WebAppAPIAdapter#setting_snmp() FAIL: data={data}, details={str(e)}"
            )

        except requests.RequestException as e:
            # 純粹網路／timeout／連線失敗
            raise ProjRedfishError(
                code=ProjRedfishErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE, 
                message=f"WebAppAPIAdapter#setting_snmp() FAIL: data={data}, details={str(e)}"
            )
            
    # ================動態抓取本機網路(內網外網要分)================    
    def get_ethernetinterfaces(self):
        net_data = self.get_ethernet_data()
        
        m = RfEthernetInterfacesModel()
        m.Members_odata_count = len(net_data)
        for i in range(len(net_data)):
            s = {
                "@odata.id": f"/redfish/v1/Managers/CDU/EthernetInterfaces/{net_data[i]['Name']}"
            }
            
            m.Members.append(s)
        
        return m.to_dict(), 200
    
    def get_ethernetinterfaces_id(self, id: str):
        # net_data_from_rest = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/network")
        # print(net_data_from_rest)
        # print(len(net_data_from_rest))
        m = RfEthernetInterfacesIdModel(ethernet_interfaces_id=id)
        net_data = self.get_ethernet_data() 
        data = self.get_ethernet_entry(id, net_data)
        self.net_info(net_data) # 測試使用
        if data is None:
            return {"message": f"Ethernet interface {id} not found"}, 404
        m.LinkStatus = "LinkUp" if data["isUp"] else "LinkDown"
        m.InterfaceEnabled = data["isUp"]
        m.MACAddress = data["MAC"]
        m.SpeedMbps = data["Speed_Mbps"]
        m.FullDuplex = data["FullDuplex"]
        m.MTUSize = data["MTU"]
        
        m.Redfish_WriteableProperties = ["InterfaceEnabled"]
        m.HostName = id
        m.FQDN = None
        # Ipv4
        Ipv4 = RfEthernetInterfacesIdModel._ipv4_addresses()
        Ipv4.Address = data["IPv4"]
        Ipv4.SubnetMask = data["SubnetMask"]#"255.255.255.0" #TBD
        Ipv4.AddressOrigin = data["AddressOrigin"]#"DHCP" #TBD
        Ipv4.Gateway = data["Gateway"]#"192.168.3.1" #TBD
        
        m.IPv4Addresses = [Ipv4] 
        m.NameServers = data["NameServers"]#["8.8.8.8" ]#TBD
        
        status = {
            "State": "Enabled" if data["isUp"] else "Disabled",
            "Health": "OK"
        }
        m.Status = RfStatusModel.from_dict(status)
        return m.to_dict(), 200
    
    def patch_ethernetinterfaces(self, ethernet_interfaces_id: str, body: dict):
        """
        更新 EthernetInterfaces 的設定
        :param ethernet_interfaces_id: str, 網路介面的 ID (e.g., "eth0")
        :param body: dict, 包含要更新的屬性 (e.g., {"InterfaceEnabled": True})
        """
        interface_enabled = body.get("InterfaceEnabled", None)
        # print("interface_enabled:", interface_enabled)
        if interface_enabled is not None:
            set_NetwrokInterface(ethernet_interfaces_id, interface_enabled)
            return self.get_ethernetinterfaces_id(ethernet_interfaces_id), 200
    
        raise ProjRedfishError(code=ProjRedfishErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE, 
                message=f"Cannot found EthernetInterfaces {ethernet_interfaces_id} or InterfaceEnabled is not provided")    
    

    ##
    #      ___        ______ .___________. __    ______   .__   __.      _______.
    #     /   \      /      ||           ||  |  /  __  \  |  \ |  |     /       |
    #    /  ^  \    |  ,----'`---|  |----`|  | |  |  |  | |   \|  |    |   (----`
    #   /  /_\  \   |  |         |  |     |  | |  |  |  | |  . `  |     \   \
    #  /  _____  \  |  `----.    |  |     |  | |  `--'  | |  |\   | .----)   |
    # /__/     \__\  \______|    |__|     |__|  \______/  |__| \__| |_______/
    ##

    def reset_to_defaults(self, reset_type: str):
        """
        :param reset_type: str
            e.g., "ResetAll"
        @note:
            API will return jsonify(message="Reset all to factory settings Successfully")
        """
        resp = WebAppAPIAdapter().reset_to_defaults(reset_type)
        # if resp.status_code == HTTPStatus.OK.value:
        #     reset_to_defaults()
        return jsonify(ProjResponseMessage(code=resp.status_code, message=resp.text).to_dict())
    
    def reset(self, reset_type: str):
        """
        :param reset_type: str
            e.g., "ForceRestart" or "GracefulRestart"
        """
        resp = WebAppAPIAdapter().reset(reset_type)
        return jsonify(ProjResponseMessage(code=resp.status_code, message=resp.text).to_dict())

    def shutdown(self, reset_type: str):
        resp = WebAppAPIAdapter().shutdown(reset_type)
        return jsonify(ProjResponseMessage(code=resp.status_code, message=resp.text).to_dict())