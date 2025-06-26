
from typing import Union
from enum import Enum
from mylib.models.rf_redfish_error_model import (
    RfRedfishErrorModel, 
    RfRedfishErrorContentsModel
)
from http import HTTPStatus


class ProjRedfishErrorCode(Enum):
    """
    @see https://redfish.dmtf.org/registries/
    
    @note We just list the redfish error codes the project need, not all of them.
    """
    EVENT_SUBSCRIPTION_LIMIT_EXCEEDED = (400, "Base.1.19.0.EventSubscriptionLimitExceeded")
    GENERAL_ERROR = (400, "Base.1.19.0.GeneralError")
    MALFORMED_JSON = (400, "Base.1.19.0.MalformedJSON")
    PROPERTY_MISSING = (400, "Base.1.19.0.PropertyMissing")
    PROPERTY_UNKNOWN = (400, "Base.1.19.0.PropertyUnknown")
    PROPERTY_VALUE_FORMAT_ERROR = (400, "Base.1.19.0.PropertyValueFormatError")
    PROPERTY_VALUE_TYPE_ERROR = (400, "Base.1.19.0.PropertyValueTypeError")
    
    # HTTP Status: 401 Unauthorized
    ACCESS_DENIED = (401, "Base.1.19.0.AccessDenied")
    
    # HTTP Status: 403 Forbidden
    CREATE_LIMIT_REACHED_FOR_RESOURCE = (403, "Base.1.19.0.CreateLimitReachedForResource")
    INSUFFICIENT_PRIVILEGE = (403, "Base.1.19.0.InsufficientPrivilege")
    RESOURCE_LIMIT_EXCEEDED = (403, "Base.1.19.0.ResourceLimitExceeded")
    
    # HTTP Status: 404 Not Found
    NO_VALID_SESSION = (404, "Base.1.19.0.NoValidSession")
    RESOURCE_NOT_FOUND = (404, "Base.1.19.0.ResourceNotFound")
    
    # HTTP Status: 405 Method Not Allowed
    ACTION_NOT_SUPPORTED = (405, "Base.1.19.0.ActionNotSupported")
    
    # HTTP Status: 409 Conflict
    RESOURCE_ALREADY_EXISTS = (409, "Base.1.19.0.ResourceAlreadyExists")
    RESOURCE_CREATION_CONFLICT = (409, "Base.1.19.0.ResourceCreationConflict")
    
    # HTTP Status: 411 Length Required
    ACTION_PARAMETER_MISSING = (411, "Base.1.19.0.ActionParameterMissing")
    
    # HTTP Status: 412 Precondition Failed
    PRECONDITION_FAILED = (412, "Base.1.19.0.PreconditionFailed")
    
    # HTTP Status: 413 Payload Too Large
    PAYLOAD_TOO_LARGE = (413, "Base.1.19.0.PayloadTooLarge")
    PROPERTY_VALUE_OUT_OF_RANGE = (413, "Base.1.19.0.PropertyValueOutOfRange")
    
    # HTTP Status: 422 Unprocessable Entity
    RESOURCE_IN_USE = (422, "Base.1.19.0.ResourceInUse")
    
    # HTTP Status: 500 Internal Server Error
    INTERNAL_ERROR = (500, "Base.1.19.0.InternalError")
    OPERATION_TIMEOUT = (500, "Base.1.19.0.OperationTimeout")
    PROPERTY_NOT_UPDATED = (500, "Base.1.19.0.PropertyNotUpdated")

    SOURCE_DOES_NOT_SUPPORT_PROTOCOL = (502, "Base.1.19.0.SourceDoesNotSupportProtocol")
    COULD_NOT_ESTABLISH_CONNECTION = (502, "Base.1.19.0.CouldNotEstablishConnection")
    SERVICE_TEMPORARILY_UNAVAILABLE = (503, "Base.1.19.0.ServiceTemporarilyUnavailable")

    @property
    def http_status(self) -> int:
        """Get HTTP status code"""
        return self.value[0]
    
    @property
    def message_id(self) -> str:
        """Get Redfish error code (MessageId)"""
        return self.value[1]


class ProjError(Exception):
    def __init__(self, 
        code: int, 
        message: str, 
        rf_message_id: ProjRedfishErrorCode = None
    ):
        """
        @param code: HTTP status code
        @param message: Error message
        @param rf_message_id: Redfish error code
        """
        self.code = code
        self.message = message
        self.rf_message_id = rf_message_id
    
    def to_dict(self):
        return {
            "code": self.code,
            "message": self.message
        }
    
    def to_dict_v2(self):
        return {
            "error": {
                "code": self.code,
                "message": self.message
            }
        }
        
    def to_redfish_error_dict(self):
        try:
            self.rf_message_id = self.rf_message_id or ProjRedfishErrorCode.GENERAL_ERROR
            err = RfRedfishErrorModel(error=RfRedfishErrorContentsModel(
                    code=self.rf_message_id.message_id, 
                    message=self.message,
                    Message_ExtendedInfo=None
                )
            )
            return err.to_dict()
        except Exception as e:
            print(e)
            return self.to_dict_v2()






class ProjRedfishError(Exception):
    """
    For Redfish error response
    @Usage:
        ## Raise Exception
        raise ProjRedfishError(
            code=ProjRedfishErrorCode.GENERAL_ERROR,
            message="some exception"
        )
        ## Handle Exception
        @app.errorhandler(ProjRedfishError)
        def handle_proj_redfish_error(e):
            return e.to_dict(), e.http_status
    """

    def __init__(self, 
        code: ProjRedfishErrorCode, 
        message: str
    ):
        """
        @param code: Enum of ProjRedfishErrorCode
        @param message: Error message
        """
        self.code = code
        self.message = message

    
    def to_dict(self):
        err = RfRedfishErrorModel(error=RfRedfishErrorContentsModel(
                    code=self.code.message_id, 
                    message=self.message,
                    Message_ExtendedInfo=None
                )
            )
        return err.to_dict()
    

    @property
    def http_status(self):
        return self.code.http_status    
