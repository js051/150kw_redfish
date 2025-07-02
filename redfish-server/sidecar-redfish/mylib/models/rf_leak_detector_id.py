
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

from mylib.models.rf_base_model import RfResourceBaseModel
from mylib.models.rf_leak_detector_collection_model import RfLeakDetectorCollectionModel
from mylib.models.rf_status_model import RfStatusModel, RfStatusHealth, RfStatusState
from mylib.models.rf_resource_model import RfLocationModel
from load_env import hardware_info

class RfLeakDetectionIdModel(RfResourceBaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/LeakDetection.v1_1_0.json#/definitions/LeakDetection
    """
    Odata_context: Optional[str] = Field(default=None, alias="@odata.context")
    # "@odata.id": {1 item},
    # "@odata.type": {1 item},
    Description: Optional[str] = Field(default=None)
    # "Id": {2 items},
    # "Name": {2 items},
    Oem: Optional[Dict[str, Any]] = Field(default=None)
    Status: Optional[RfStatusModel] = Field(default=None)
    DetectorState: Optional[str] = Field(default=None)
    LeakDetectorType: Optional[str] = Field(default=None)
    Location: Optional[RfLocationModel] = Field(default=None)
    
    model_config = ConfigDict(
        extra='allow',
    )
    
    def __init__(self, cdu_id: str, leak_detector_id: str, **kwargs):
        super().__init__(**kwargs)
        self.odata_type = "#LeakDetector.v1_3_0.LeakDetector"
        self.odata_id = f"/redfish/v1/ThermalEquipment/CDUs/{cdu_id}/LeakDetection/LeakDetectors/{leak_detector_id}"
        self.Id = leak_detector_id
        self.Name = f"Leak Detection {leak_detector_id}"
        self.Description = f"Leak Detector {leak_detector_id} for CDU {cdu_id}"
        
        self.LeakDetectorType = "Moisture"
        self.Location = RfLocationModel(**hardware_info["leak_detectors"][leak_detector_id]["Location"])

        
'''
{
  "@odata.id": "/redfish/v1/ThermalEquipment/CDUs/1/LeakDetection/LeakDetectors/1",
  "@odata.type": "#LeakDetector.v1_3_0.LeakDetector",
  "Id": "1",
  "Name": "Leak Detector 1",
  "Description": "Leak Detector 1 for CDU 1",
  
  "DetectorState": "OK",
  "LeakDetectorType": "Moisture",
  "Location": {
    "PartLocation": {
      "ServiceLabel": "Leak Detector 1",
      "LocationType": "Bay"
    }
  },
  "Status": {
    "State": "Enabled",
    "Health": "OK"
  }
}'''





    