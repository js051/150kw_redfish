
import os
from dataclasses import dataclass
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
from typing_extensions import Self

from mylib.models.rf_base_model import RfResourceBaseModel, RfResourceCollectionBaseModel
from mylib.models.rf_status_model import RfStatusModel, RfStatusHealth, RfStatusState
from load_env import hardware_info

class RfLeakDetectorModel(RfResourceCollectionBaseModel):
    # Id: str = Field(default="1")
    # Status: RfStatusModel = Field(default=RfStatusModel())
    
    
    model_config = ConfigDict(
        extra='allow',
    )

    def __init__(self, cdu_id: str, **kwargs):
        """
        Example:
        {
            "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/{cdu_id}/LeakDetection/LeakDetectors",
            "@odata.type": "#LeakDetectorCollection.LeakDetectorCollection",
            "Name": "LeakDetectors",
            "Members@odata.count": 1,
            "Members": [{}]
        }
        """
        super().__init__(**kwargs)
        self.odata_id = f"/redfish/v1/ThermalEquipment/CDUs/{cdu_id}/LeakDetection/LeakDetectors"
        self.odata_type = "#LeakDetectorCollection.LeakDetectorCollection"
        self.Name = "LeakDetectors"
        
        self.Members_odata_count = len(hardware_info.get("leak_detectors", {}))
        self.Members = []
        for leak_detector_id in hardware_info.get("leak_detectors", {}).keys():
            member = {
                "@odata.id": f"/redfish/v1/ThermalEquipment/CDUs/{cdu_id}/LeakDetection/LeakDetectors/{leak_detector_id}"
            }
            self.Members.append(member)
        # self.Id = cdu_id






    