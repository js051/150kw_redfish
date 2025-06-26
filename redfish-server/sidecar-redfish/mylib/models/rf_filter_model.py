import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
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
from mylib.models.rf_status_model import RfStatusModel
from mylib.models.rf_resource_model import RfLocationModel, RfOemModel

from load_env import hardware_info


class RfFilterModel(RfResourceBaseModel):
    '''
    @see http://redfish.dmtf.org/schemas/v1/Filter_v1.xml
    '''
    
    Odata_context: Optional[str] = Field(default=None, alias="@odata.context")
    HotPluggable: Optional[bool] = Field(default=False)
    Replaceable: Optional[bool] = Field(default=False)
    ServicedDate: Optional[datetime] = Field(default=None, alias="ServicedDate")
    ServiceHours: Optional[int] = Field(default=-1)
    RatedServiceHours: Optional[int] = Field(default=None)
    Status: Optional[RfStatusModel] = Field(default=None)
    Location: Optional[RfLocationModel] = Field(default=None)
    Oem: Optional[RfOemModel] = Field(default=None)
    
    model_config = ConfigDict(
        extra='allow',
        arbitrary_types_allowed=True
    ) 
    
    def __init__(self, cdu_id: str, filter_id: str, **kwargs):
        super().__init__(**kwargs)
        self.odata_id = f"/redfish/v1/ThermalEquipment/CDUs/{cdu_id}/Filters/{filter_id}"
        self.odata_type = "#Filter.v1_0_2.Filter"
        self.Odata_context = "/redfish/v1/$metadata#Filter.Filter"
        
        self.Id = filter_id
        self.Name = f"Filter {filter_id}"
        self.Description = "Cooling Loop Filter"
        
        self.RatedServiceHours = hardware_info["Filters"][filter_id]["RatedServiceHours"]
        self.Location = RfLocationModel(**hardware_info["Filters"][filter_id]["Location"])
        
        