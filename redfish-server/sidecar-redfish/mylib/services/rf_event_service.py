'''
這是Redfish的event service
'''
import subprocess, json
import requests
import ipaddress
from flask import jsonify, Response
from mylib.services.base_service import BaseService
from mylib.models.rf_networkprotocol_model import RfNetworkProtocolModel
from mylib.models.rf_snmp_model import RfSnmpModel
from mylib.adapters.webapp_api_adapter import WebAppAPIAdapter
from mylib.models.rf_resource_model import RfResetType
from mylib.common.proj_response_message import ProjResponseMessage
from mylib.utils.load_api import load_raw_from_api, CDU_BASE
from mylib.models.rf_event_service_model import RfEventServiceModel, RfEventSubscriptionsModel, RfEventSubscriptionIdModel
from mylib.models.rf_status_model import RfStatusModel
from mylib.services.rf_managers_service import RfManagersService
from mylib.models.setting_model import SettingModel
from mylib.utils.ServerSentEvent import event_stream

event_setting = {
    "ServiceEnabled": True,
    "DeliveryRetryAttempts": 3,
    "DeliveryRetryIntervalSeconds": 60
}

event_subscriptions = [
    {"@odata.id": "/redfish/v1/EventService/Subscriptions/1"}
]

event_subscriptions_Id = [
   {
    "Context": "1",
    "Destination":"127.0.0.1",
    "TrapCommunity": "public",
   }
]
class RfEventService(BaseService):
    #==========================================
    # 共用函數
    #==========================================
    def get_ServiceEnabled(self):
        return bool(int(SettingModel().get_by_key("EventService.ServiceEnabled").value))
    
    def save_ServiceEnabled(self, value):
        return SettingModel().save_key_value("EventService.ServiceEnabled", value)
    
    def get_Destination(self):
        return SettingModel().get_by_key("EventService.Destination").value
    
    def save_Destination(self, value):
        return SettingModel().save_key_value("EventService.Destination", value)
    
    def get_TrapCommunity(self):
        return SettingModel().get_by_key("EventService.TrapCommunity").value
    
    def save_TrapCommunity(self, value):
        return SettingModel().save_key_value("EventService.TrapCommunity", value)
    
    # 檢查 IP
    def is_valid_ip(self,addr: str) -> bool:
        try:
            ipaddress.ip_address(addr)
            return True
        except ValueError:
            return False
    #==========================================
    # EventService
    #==========================================
    def get_event_service(self):
        m = RfEventServiceModel()
        m.ExcludeMessageId = False
        m.ExcludeRegistryPrefix = False
        m.IncludeOriginOfConditionSupported = False
        m.SubordinateResourcesSupported = False
        m.ServiceEnabled = self.get_ServiceEnabled() #event_setting["ServiceEnabled"]
        m.DeliveryRetryAttempts = event_setting["DeliveryRetryAttempts"] 
        m.DeliveryRetryIntervalSeconds = event_setting["DeliveryRetryIntervalSeconds"]
        m.EventTypesForSubscription = ["Alert"]
        m.ServerSentEventUri = "None"
        SSEFilterPropertiesSupported = {
            "RegistryPrefix": True,
            "ResourceType": True
        }
        m.SSEFilterPropertiesSupported = RfEventServiceModel._SSEFilterPropertiesSupported(**SSEFilterPropertiesSupported)
        m.ResourceTypes = []
        m.RegistryPrefixes=[]
        m.Subscriptions = {
            "@odata.id": "/redfish/v1/EventService/Subscriptions"
        }
        status = {
            "State": "Enabled" if self.get_ServiceEnabled() else "Disabled",
            "Health": "OK"
        }
        m.Status = RfStatusModel(**status)
        
        return m.to_dict(), 200
    
    def patch_event_service(self, body):
        '''
        ServiceEnabled: 是否啟用服務
        DeliveryRetryAttempts: 重試次數
        DeliveryRetryIntervalSeconds: 重試間隔
        '''
        ServiceEnabled = body.get("ServiceEnabled")
        DeliveryRetryAttempts = body.get("DeliveryRetryAttempts")
        DeliveryRetryIntervalSeconds = body.get("DeliveryRetryIntervalSeconds")
        if ServiceEnabled is not None:
            # event_setting["ServiceEnabled"] = ServiceEnabled
            if ServiceEnabled is True:
                s = 1
            
            if ServiceEnabled == False:
                s = 0
                snmp_post = {
                    "TrapIP": "",
                    "Community": "",
                }
                RfManagersService().NetworkProtocol_Snmp_Post(snmp_post)
        self.save_ServiceEnabled(s)      
        # self.save_Destination(snmp_post["TrapIP"])
        # self.save_TrapCommunity(snmp_post["Community"])
        if DeliveryRetryAttempts is not None:
            event_setting["DeliveryRetryAttempts"] = DeliveryRetryAttempts
        if DeliveryRetryIntervalSeconds is not None:
            event_setting["DeliveryRetryIntervalSeconds"] = DeliveryRetryIntervalSeconds
            
        return self.get_event_service()
    #==========================================
    # EventSubscriptions
    #==========================================
    def get_subscriptions(self):
        m = RfEventSubscriptionsModel()
        m.Members_odata_count = len(event_subscriptions)
        m.Members = event_subscriptions
        
        return m.to_dict(), 200
    
    # def post_subscriptions(self, body):
    #     return self.get_subscriptions()
    
    #==========================================
    # EventSubscriptionId
    #==========================================
    def get_subscriptions_id(self, subscription_id: str):
        m = RfEventSubscriptionIdModel(Subscriptions_id=subscription_id)
        
        m.SubscriptionType = "SNMPTrap"
        m.Context = event_subscriptions_Id[0]["Context"]
        m.DeliveryRetryPolicy = "RetryForever"
        m.Destination = self.get_Destination()
        m.Protocol = "SNMPv2c"
        m.EventFormatType = "Event"
        m.RegistryPrefixes = []
        m.ResourceTypes = []
        status = {
            "State": "Enabled" if self.get_ServiceEnabled() else "Disabled",
            "Health": "OK"
        }
        m.Status = RfStatusModel(**status)
        
        return m.to_dict(), 200
    
    def patch_subscriptions_id(self, subscription_id: str, body):
        Destination = body.get("Destination")
        TrapCommunity = body.get("TrapCommunity")
        event_subscriptions_Id[0]["Context"] = body.get("Context")
        
        # 檢查 IP 格式
        if self.is_valid_ip(Destination) is False:
            return "error: Invalid IP address format", 400
        
        self.save_Destination(Destination)
        self.save_TrapCommunity(TrapCommunity)
        
        
        snmp_post = {
            "TrapIP": self.get_Destination(),# event_subscriptions_Id[0]["Destination"],
            "Community": self.get_TrapCommunity(),
        }
        if self.get_ServiceEnabled() == True:
            RfManagersService().NetworkProtocol_Snmp_Post(snmp_post)
        else:
            return "error: Service not enabled", 400   
        
        return self.get_subscriptions_id(subscription_id)
    
    #==========================================
    # ServerSentEvent
    #==========================================   
    def subscriptions_SSE(self): 
        """
        1.先判斷EventService是否有啟動
        2.取得要過濾的事件
        3.設定SSE發送事件
        """
        if self.get_ServiceEnabled() is not True:
            event_stream(Enabled=False)
            return {"error": "EventService not Enabled"}
    
        # 過濾條件
        filters = {}
        return Response(event_stream(True, filters), mimetype="text/event-stream")    