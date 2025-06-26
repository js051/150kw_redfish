from typing import Optional, List
from pydantic import (
    BaseModel,
    Field,
    validator, # deprecated
    field_validator,
)
from enum import Enum
from mylib.models.rf_status_model import RfStatusHealth

class RfMessageRegistryModel(BaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/MessageRegistry.v1_6_3.json
    """
    ...

class RfMessageModel(BaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/Message.json#/definitions/Message
    @see https://redfish.dmtf.org/schemas/v1/Message.v1_3_0.json#/definitions/Message
    @note
    required": [
        "MessageId",
    ]
    @see MessageId format: 
        https://www.dmtf.org/sites/default/files/standards/documents/DSP0266_1.22.0.html#messageid-format 
    @see MessageId
        https://redfish.dmtf.org/registries/Base.1.21.0.json
        ex: "Base.1.21.0.AccessDenied"
        ex: "Base.1.21.0.GeneralError"
    """
    Message: Optional[str] = Field(default=None, description="")
    MessageArgs: Optional[List[str]] = Field(default=None, description="")
    MessageId: str = Field(description="The identifier for the message.") # @see
    MessageSeverity: Optional[RfStatusHealth] = Field(default=None, description="")
    Oem: Optional[dict] = Field(default=None, description="")
    RelatedProperties: Optional[List[str]] = Field(default=None, description="A set of properties described by the message.")
    Resolution: Optional[str] = Field(default=None, description="Used to provide suggestions on how to resolve the situation that caused the message.")
    # ResolutionSteps: Optional[List[xxxxx]] = Field(default=None, description="")
    Severity: Optional[str] = Field(default=None, description="This property has been deprecated in favor of `MessageSeverity`, which ties the values to the enumerations defined for the `Health` property within `Status`.")
    UserAuthenticationSource: Optional[str] = Field(description="The source of authentication for the username property associated with the message.")
    Username: Optional[str] = Field(description="")

    @classmethod
    def from_dict(cls, status_dict: dict):
        health = status_dict.get("Health") or status_dict.get("health")
        state = status_dict.get("State") or status_dict.get("state")
        return cls(Health=health, State=state)

    def to_dict(self) -> dict:
        """
        Only dump fields that are defined in the model
        (i.e., drop None values and extra fields)
        """
        return self.model_dump(
                    by_alias=True,
                    include=set(self.__class__.model_fields.keys()),
                    exclude_none=True
                )
    
