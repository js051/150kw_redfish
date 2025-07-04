'''
@see https://redfish.dmtf.org/schemas/v1/Resource.json
'''
from typing import *
from pydantic import (
    BaseModel,
    Field,
    validator, # deprecated
    field_validator,
)
from enum import Enum
from typing import Dict, Any
from pydantic import ConfigDict



        

class RfResetType(Enum):
    """
    @see https://redfish.dmtf.org/schemas/v1/Resource.json#/definitions/ResetType
    """
    On = "On"
    ForceOff = "ForceOff"
    GracefulShutdown = "GracefulShutdown"
    GracefulRestart = "GracefulRestart"
    ForceRestart = "ForceRestart"
    Nmi = "Nmi"
    ForceOn = "ForceOn"
    PushPowerButton = "PushPowerButton"
    PowerCycle = "PowerCycle"
    Suspend = "Suspend"
    Pause = "Pause"
    Resume = "Resume"
    FullPowerCycle = "FullPowerCycle"


class RfContactInfoModel(BaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/Resource.v1_21_0.json#/definitions/ContactInfo
    """
    ContactName: str
    EmailAddress: Optional[str] = None
    PhoneNumber: Optional[str] = None

class RfOemModel(Dict):
    """
    @see https://redfish.dmtf.org/schemas/v1/Resource.json#/definitions/Oem
    """
    # No any fields defined in `properties`.
    pass

class RfLocationModel(BaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/Resource.v1_21_0.json#/definitions/Location
    """
    model_config = ConfigDict(
        arbitrary_types_allowed=True # for Oem
    )


    AltitudeMeters: Optional[float] = Field(default=None, description="Altitude in meters.", extra={"units": "m"})
    Contacts: Optional[List[RfContactInfoModel]] = None
    Info: Optional[str] = None
    InfoFormat: Optional[str] = None
    Latitude: Optional[float] = Field(default=None, extra={"units": "deg"})
    Longitude: Optional[float] = Field(default=None, extra={"units": "deg"})
    Oem: Optional[RfOemModel] = Field(default=None)
    PartLocation: Optional[Dict[str, Any]] = Field(default=None, description="The part location for a resource within an enclosure.")
    PartLocationContext: Optional[str] = Field(default=None, description="Human-readable string to enable differentiation between `PartLocation` values for parts in the same enclosure, which might include hierarchical information of containing `PartLocation` values for the part.")
    PhysicalAddress: Optional[Dict[str, Any]] = Field(default=None)
    Placement: Optional[Dict[str, Any]] = Field(default=None)
    PostalAddress: Optional[Dict[str, Any]] = Field(default=None)


class RfResourceModel(BaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/Resource.v1_21_0.json#/definitions/Resource
        "required": [
            "Id",
            "Name",
            "@odata.id",
            "@odata.type"
        ]
    """
    Odata_context: Optional[str] = Field(default=None, alias="@odata.context")
    Odata_etag: Optional[str] = Field(default=None, alias="@odata.etag")
    Odata_id: str = Field(alias="@odata.id")
    Odata_type: str = Field(alias="@odata.type")
    Description: Optional[str] = Field(default=None)
    Id: str
    Name: str
    Oem: Optional[Dict[str, Any]] = Field(default=None)

        
