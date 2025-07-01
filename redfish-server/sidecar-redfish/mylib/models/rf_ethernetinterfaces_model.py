from typing import Optional, List, Dict, Any
from pydantic import (
    BaseModel,
    ConfigDict,
    Field, 
    computed_field,
    model_validator,
    #validator, # deprecated
    field_validator,
)
from mylib.models.rf_base_model import RfResourceBaseModel
from mylib.utils.network_info import get_network_protocol_status
from mylib.models.rf_snmp_model import rf_SNMP
from mylib.models.rf_base_model import RfResourceCollectionBaseModel
from mylib.models.rf_status_model import RfStatusModel

class RfEthernetInterfacesModel(RfResourceCollectionBaseModel):
    Odata_context: Optional[str] = Field(default=None, alias="@odata.context")
    
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)    
        self.odata_id = "/redfish/v1/Managers/CDU/EthernetInterfaces"
        self.odata_type = "#EthernetInterfaceCollection.EthernetInterfaceCollection"
        self.Odata_context = "/redfish/v1/$metadata#EthernetInterfaceCollection.EthernetInterfaceCollection"
        
        self.Name = "Ethernet Network Interface Collection"
        self.Description = "Network Interface Collection for the CDU Management Controller"
        
        
        
        
class RfEthernetInterfacesIdModel(RfResourceBaseModel):
    # ipv4
    class _ipv4_addresses(BaseModel):
        Address: Optional[str] = Field(default=None)
        SubnetMask: Optional[str] = Field(default=None)
        AddressOrigin: Optional[str] = Field(default=None)
        Gateway: Optional[str] = Field(default=None)
        Oem: Optional[Any] = Field(default=None)
    
    # ipv6
    class _ipv6_addresses(BaseModel):
        Address: Optional[str] = Field(default=None)
        PrefixLength: Optional[str] = Field(default=None)
        AddressOrigin: Optional[str] = Field(default=None)
        AddressState: Optional[str] = Field(default=None)
        Oem: Optional[Any] = Field(default=None)
    
    # models
    Odata_context: Optional[str] = Field(default=None, alias="@odata.context")
    Description: Optional[str] = Field(default=None)
    Status: Optional[RfStatusModel] = Field(default=None)
    LinkStatus: Optional[str] = Field(default=None)
    InterfaceEnabled: Optional[bool] = Field(default=None)
    PermanentMACAddress: Optional[str] = Field(default=None)
    MACAddress: Optional[str] = Field(default=None)
    SpeedMbps: Optional[int] = Field(default=None)
    AutoNeg: Optional[bool] = Field(default=None)
    FullDuplex: Optional[bool] = Field(default=None)
    MTUSize: Optional[int] = Field(default=None)
    
    Redfish_WriteableProperties: Optional[List[str]] = Field(default=None, alias="@Redfish.WriteableProperties")
    
    HostName: Optional[str] = Field(default=None)
    FQDN: Optional[str] = Field(default=None)
    
    IPv4Addresses: Optional[List[_ipv4_addresses]] = Field(default=None)
    MaxIPv6StaticAddresses: Optional[int] = Field(default=None)
    # IPv6AddressPolicyTable: Optional[_ipv6addresspolicytable] = Field(default=None)
    # IPv6StaticAddresses: Optional[List[_ipv6_addresses]] = Field(default=None)
    # IPv6DefaultGateway: Optional[_ipv6_addresses] = Field(default=None)
    IPv6Addresses: Optional[List[_ipv6_addresses]] = Field(default=None)
    NameServers: Optional[List[str]] = Field(default=None)
    
    Oem: Optional[Any] = Field(default=None)
    
    def __init__(self, ethernet_interfaces_id: str, **kwargs):
        super().__init__(**kwargs)
        self.odata_id = f"/redfish/v1/Managers/CDU/EthernetInterfaces/{ethernet_interfaces_id}"
        self.odata_type = "#EthernetInterface.v1_12_4.EthernetInterface"
        self.Odata_context = "/redfish/v1/$metadata#EthernetInterface.v1_12_4.EthernetInterface"
        
        self.Id = ethernet_interfaces_id
        self.Name = f"Manager Ethernet Interface {ethernet_interfaces_id}"
        self.Description = "Network Interface of the CDU Management Controller"
