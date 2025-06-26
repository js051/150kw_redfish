'''
這是Redfish的managers service
'''
import os
import datetime
import subprocess, json
from load_env import redfish_info
from http import HTTPStatus
from mylib.services.base_service import BaseService
from mylib.models.rf_networkprotocol_model import RfNetworkProtocolModel
from mylib.models.rf_snmp_model import RfSnmpModel
from mylib.adapters.webapp_api_adapter import WebAppAPIAdapter
from mylib.models.rf_resource_model import RfResetType
from mylib.models.rf_log_service_model import (
    RfLogServiceCollectionModel, 
    RfLogServiceModel, 
    RfLogEntryTypes, 
    RfOverWritePolicy
)
from mylib.models.rf_log_entry_model import (
    RfLogEntryModel,
    RfEventSeverity,
    RfLogEntryType
)
from mylib.models.rf_status_model import RfStatusModel, RfStatusHealth, RfStatusState
from mylib.utils.DateTimeUtil import DateTimeUtil
from mylib.common.proj_error import ProjError, ProjRedfishError, ProjRedfishErrorCode
from mylib.adapters.webapp_json_reader import WebAppJsonReader, WebAppSignalRecordModel

class RfLogService(BaseService):
    def fetch_LogServices(self):
        """
        Example:
        {
            "@odata.id": "/redfish/v1/Managers/CDU/LogServices",
            "@odata.type": "#LogServiceCollection.LogServiceCollection",
            "@odata.context": "/redfish/v1/$metadata#LogServiceCollection.LogServiceCollection",

            "Name": "Log Service",
            "Description": "System Event and Error Log Service",
            
            "Members@odata.count": 1,
            "Members": [
                {"@odata.id": "/redfish/v1/Managers/CDU/LogServices/1"}
            ],
            "Oem": {}
        }
        """
        m = RfLogServiceCollectionModel()
        m.odata_id = "/redfish/v1/Managers/CDU/LogServices"
        m.odata_type = "#LogServiceCollection.LogServiceCollection"
        m.odata_context = "/redfish/v1/$metadata#LogServiceCollection.LogServiceCollection"
        m.Name = "Log Service"
        m.Description = "System Event and Error Log Service"

        m.Members = []
        for key, obj in redfish_info["LogServices"].items():
            m.Members.append({
                "@odata.id": f"/redfish/v1/Managers/CDU/LogServices/{key}"
            })
        m.Members_odata_count = len(m.Members)

        return m.to_dict()

    def fetch_LogServices_by_logserviceid(self, log_service_id: str):
        """
        對應URI: /redfish/v1/Managers/CDU/LogServices/{log_service_id}
        """
        if log_service_id != "1":
            raise ProjRedfishError(ProjRedfishErrorCode.RESOURCE_NOT_FOUND, f"/LogService/{log_service_id} is not exist!")
        
        log_entries = WebAppJsonReader.read_all_errorlog_entries()
        is_health = WebAppAPIAdapter.check_health()

        status = RfStatusModel()
        status.State = RfStatusState.Enabled
        status.Health = RfStatusHealth.OK if is_health else RfStatusHealth.Critical

        # TODO: 專案太趕，先不建rf_log_service_model
        resp_json = {
            "@odata.id": f"/redfish/v1/Managers/CDU/LogServices/{log_service_id}",
            "@odata.type": "#LogService.v1_8_0.LogService",
            "@odata.context": "/redfish/v1/$metadata#LogService.v1_8_0.LogService",

            "Id": str(log_service_id),
            "Name": "System Event Log Service",
            "Description": "System Event and Error Log Service",
            
            "Entries": { "@odata.id": f"/redfish/v1/Managers/CDU/LogServices/{log_service_id}/Entries" },
            "LogEntryType": RfLogEntryTypes.OEM,
            "DateTime": DateTimeUtil.format_string(os.getenv("DATETIME_FORMAT", "%Y-%m-%dT%H:%M:%SZ")),
            "DateTimeLocalOffset": DateTimeUtil.parse_timezone(datetime.datetime.now(), ':'), # '+08:00'
            "MaxNumberOfRecords": len(log_entries),
            "OverWritePolicy": RfOverWritePolicy.WrapsWhenFull,
            "ServiceEnabled": True,
            "Status": status.to_dict(),
            
            # Recommended field in interop validator
            "Actions": {
                "#LogService.ClearLog": {
                    "target": f"/redfish/v1/Managers/CDU/LogServices/{log_service_id}/Actions/LogService.ClearLog",
                }
            },
            "Oem": {}
        }

        return resp_json

    def fetch_LogServices_entries_by_logserviceid(self, log_service_id: str):
        """
        對應URI: /redfish/v1/Managers/CDU/LogServices/{log_service_id}/Entries
        """
        if log_service_id != "1":
            raise ProjRedfishError(ProjRedfishErrorCode.RESOURCE_NOT_FOUND, f"LogService {log_service_id} is not exist!")
        
        log_entries = WebAppJsonReader.read_all_errorlog_entries()

        # TODO: 專案太趕，先不建rf_log_service_model
        resp_json = {
            "@odata.id": f"/redfish/v1/Managers/CDU/LogServices/{log_service_id}/Entries",
            "@odata.type": "#LogEntryCollection.LogEntryCollection",
            "@odata.context": "/redfish/v1/$metadata#LogEntryCollection.LogEntryCollection",

            "Name": "System Event Log Service",
            "Description": "System Event and Error Log Service",
            
            "Members@odata.count": len(log_entries),
            "Members": [
                # { 
                #     # service validator 只能讀到這邊 要研究為甚麼
                #     "@odata.id": "/redfish/v1/Managers/CDU/LogServices/1/Entries/1",
                    
                #     "Id": "1",
                #     "Name": "Log Entry 1",
                #     "EntryType": "Event",
                # }
            ],
            "Oem": {}
        }
        
        for sn in range(1, len(log_entries)+1):
            resp_json['Members'].append({
                "@odata.id": f"/redfish/v1/Managers/CDU/LogServices/{log_service_id}/Entries/{sn}",
                "Id": str(sn),
                "Name": f"Log Entry {sn} of log_id:{log_service_id}",
                "EntryType": RfLogEntryType.Oem,
            })

        return resp_json
    

    def fetch_LogServices_entry_by_entryid(self, log_service_id: str, entry_id: str):
        """
        對應URI: /redfish/v1/Managers/CDU/LogServices/{log_service_id}/Entries/{entry_id}
        """
        if log_service_id != "1":
            raise ProjRedfishError(ProjRedfishErrorCode.RESOURCE_NOT_FOUND, f"/LogService/{log_service_id} is not exist!")
        
        log_entries = WebAppJsonReader.read_all_errorlog_entries()

        if int(entry_id) > len(log_entries) or int(entry_id) < 1:
            raise ProjRedfishError(ProjRedfishErrorCode.RESOURCE_NOT_FOUND, f"/LogService/{log_service_id}/Entries/{entry_id} is not exist!")

        signal_record = log_entries[int(entry_id) - 1]

        # TODO: 專案太趕，先不建rf_log_service_model
        resp_json = {
            "@odata.id": f"/redfish/v1/Managers/CDU/LogServices/{log_service_id}/Entries/{entry_id}",
            "@odata.type": "#LogEntry.v1_18_0.LogEntry",
            "@odata.context": "/redfish/v1/$metadata#LogEntry.LogEntry",

            "Id": str(entry_id),    
            "Name": "System Event Log Service",
            "Description": "System Event and Error Log Service",
            
            "EntryType": RfLogEntryType.Oem,
            "Created": DateTimeUtil.convert_format_string_to_another(signal_record.on_time, "%Y-%m-%d %H:%M:%S", os.getenv("DATETIME_FORMAT")),
            "MessageId": "CDU001",
            "Message": signal_record.signal_value,
            "Severity": RfEventSeverity.Critical, # assign `Critical` because it is error log
            
            "Oem": {}
        }    
        return resp_json