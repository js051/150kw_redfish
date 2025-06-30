from typing import Optional, List
from pydantic import (
    BaseModel,
    Field,
    validator, # deprecated
    field_validator,
)
from enum import Enum
from mylib.models.rf_message_model import RfMessageModel

class RfRedfishErrorContentsModel(BaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/redfish-error.v1_0_2.json#/definitions/RedfishErrorContents
    @note
    required": [
        "code",
        "message"
    ]
    """
    code: str = Field(description="A string indicating a specific `MessageId` from a message registry.")
    message: str = Field(description="A human-readable error message corresponding to the message in a message registry.")
    Message_ExtendedInfo: Optional[List[RfMessageModel]] = Field(default=None, description="", alias="@Message.ExtendedInfo")

    # @classmethod
    # def from_dict(cls, error_dict: dict):
    #     code = error_dict.get("code") or error_dict.get("Code")
    #     message = error_dict.get("message") or error_dict.get("Message")
    #     Message_ExtendedInfo = error_dict.get("Message_ExtendedInfo")
    #     return cls(code=code, message=message, Message_ExtendedInfo=Message_ExtendedInfo)

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
    
class RfRedfishErrorModel(BaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/redfish-error.v1_0_2.json
    """
    error: RfRedfishErrorContentsModel = Field(description="The properties that describe an error from a Redfish service.")
    
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