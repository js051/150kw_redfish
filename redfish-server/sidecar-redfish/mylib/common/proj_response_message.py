'''
我們有一些api的設計是回傳純字串，並非json格式
為了統一api回傳為json，我們設計一個ProjResponseNormalMessage
'''
from typing import List, Dict, Any
from enum import Enum
from pydantic import (
    BaseModel,
    Field, 
    computed_field,
    model_validator,
    #validator, # deprecated
    field_validator,
    field_serializer
)
from mylib.models.rf_redfish_error_model import RfRedfishErrorModel, RfRedfishErrorContentsModel

class ProjResponseMessage(BaseModel):
    code: int = Field(default=None)
    message: str = Field(default="")
    
    def to_dict(self) -> dict:
        return self.model_dump(
                    by_alias=True,
                    include=set(self.__class__.model_fields.keys()),
                    exclude_none=True
                )


    
    


        
