from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import (
    BaseModel,
    Field, 
    computed_field,
    model_validator,
    #validator, # deprecated
    field_validator,
)
from mylib.models.rf_base_model import RfResourceBaseModel, RfResourceCollectionBaseModel
from mylib.models.rf_metric_report_model import RfMetricReportModel
from mylib.models.rf_status_model import RfStatusModel

class RfActions(BaseModel):
    # Oem: Optional[RfOemActions] = Field(default=None) # why fail?
    Oem: Optional[Dict[str, Any]] = Field(default=None)

class RfCalculationAlgorithmEnum(str, Enum):
    Average = "Average"
    Maximum = "Maximum"
    Minimum = "Minimum"
    Summation = "Summation"

class RfCollectionTimeScope(str, Enum):
    Point = "Point"
    Interval = "Interval"
    StartupInterval = "StartupInterval"

class RfLink(BaseModel):
    Oem: Optional[Dict[str, Any]] = Field(default=None)
    Triggers: Optional[Dict[str, Any]] = Field(default=None) 
    Triggers_odata_count: Optional[int] = Field(default=None, alias="@odata.count")

class RfMetric(BaseModel):
    CollectionDuration: Optional[str] = Field(default=None)
    CollectionFunction: Optional[RfCalculationAlgorithmEnum] = Field(default=None)
    CollectionTimeScope: Optional[RfCollectionTimeScope] = Field(default=None)
    MetricId: Optional[str] = Field(default=None)
    MetricProperty: Optional[str] = Field(default=None)
    Oem: Optional[Dict[str, Any]] = Field(default=None)

class RfMetricReportDefinitionType(str, Enum):
    Periodic = "Periodic"
    Onchange = "OnChange"
    OnRequest = "OnRequest"

class RfReportActionsEnum(str, Enum):
    LogToMetricReportsCollection = "LogToMetricReportsCollection"
    RedfishEvent = "RedfishEvent"

class RfReportUpdatesEnum(str, Enum):
    Overwrite = "Overwrite"
    AppendWrapsWhenFull = "AppendWrapsWhenFull"
    AppendStopsWhenFull = "AppendStopsWhenFull"
    NewReport = "NewReport"

class RfWildcard(BaseModel):
    Keys: Optional[List[Optional[str]]] = Field(default=None)
    Name: Optional[str] = Field(default=None)
    Values: Optional[List[Optional[str]]] = Field(default=None)





class RfMetricReportDefinitionModel(RfResourceBaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/MetricReportDefinition.json
    @see https://redfish.dmtf.org/schemas/v1/MetricReportDefinition.v1_4_7.json#/definitions/MetricReportDefinition
    @note properties 24 items
    @note 
        required: [
            "@odata.id",
            "@odata.type",
            "Id",
            "Name"
        ]
    """

    odata_context: Optional[str] = Field(default=None, alias="@odata.context")
    odata_etag: Optional[str] = Field(default=None, alias="@odata.etag") 
    # odata_id: Optional[str] = Field(default=None, alias="@odata.id")
    # odata_type: Optional[str] = Field(default=None, alias="@odata.type")
    Actions: Optional[RfActions] = Field(default=None)
    AppendLimit: Optional[int] = Field(default=None)
    Description: Optional[str] = Field(default=None)
    # Id: Optional[str] = Field(default=None)
    Links: Optional[RfLink] = Field(default=None)
    MetricProperties: Optional[List[Optional[str]]] = Field(default=None)
    MetricReport: Optional[RfMetricReportModel] = Field(default=None)
    MetricReportDefinitionEnabled: Optional[bool] = Field(default=None)
    MetricReportDefinitionType: Optional[RfMetricReportDefinitionType] = Field(default=None)
    MetricReportHeartbeatInterval: Optional[str] = Field(default=None)
    Metrics: Optional[List[RfMetric]] = Field(default=None)
    # Name: Optional[str] = Field(default=None)
    Oem: Optional[dict[str, Any]] = Field(default=None)
    ReportActions: Optional[List[RfReportActionsEnum]] = Field(default=None)
    ReportTimespan: Optional[str] = Field(default=None)
    ReportUpdates: Optional[List[RfReportUpdatesEnum]] = Field(default=None)
    Schedule: Optional[Dict[str, Any]] = Field(default=None)
    Status: Optional[RfStatusModel] = Field(default=None)
    SuppressRepeatedMetricValue: Optional[bool] = Field(default=None)
    Wildcards: Optional[List[Optional[RfWildcard]]] = Field(default=None)


class RfMetricReportDefinitionCollectionModel(RfResourceCollectionBaseModel):
    """
    @see https://redfish.dmtf.org/schemas/v1/MetricReportDefinitionCollection.json
    @note properties 10 items
    @note "required": [
            "Members",
            "Members@odata.count",
            "@odata.id",
            "@odata.type",
            "Name"
        ],
    """
    # odata_id: Optional[str] = Field(default=None, alias="@odata.id")
    # odata_type: Optional[str] = Field(default=None, alias="@odata.type")
    # Members: List[Dict[str, Any]] = Field(default=[], description="")
    # Members_odata_count: int = Field(default=0, description="", alias="Members@odata.count")
    # Name: str = Field(default="", description="")
    odata_context: Optional[str] = Field(default=None, alias="@odata.context")
    odata_etag: Optional[str] = Field(default=None, alias="@odata.etag")
    Description: Optional[str] = Field(default=None)
    Members_odata_nextLink: Optional[str] = Field(default=None, description="", alias="@odata.nextLink")
    Oem: Optional[Dict[str, Any]] = Field(default=None, description="")