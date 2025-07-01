# mylib/services/rf_telemetry_service.py

import time
import threading
from typing import List, Dict, Any
from collections import deque, defaultdict
from datetime import datetime, timezone, timedelta
from cachetools import cached, TTLCache
from http import HTTPStatus
from mylib.common.proj_error import ProjRedfishError, ProjRedfishErrorCode
from mylib.services.base_service import BaseService
from mylib.adapters.sensor_csv_adapter import SensorCsvAdapter
from mylib.models.sensor_log_model import SensorLogModel
from mylib.models.rf_metric_definition_model import RfMetricDefinitionCollectionModel, RfMetricDefinitionModel
from mylib.models.rf_metric_report_definition_model import (
    RfMetricReportDefinitionCollectionModel,
    RfMetricReportDefinitionModel,
    RfReportActionsEnum,
    RfMetric,
    RfMetricReportDefinitionType,
    RfReportUpdatesEnum,
)


class RfTelemetryService(BaseService):
    """
    提供 Redfish Telemetry Service 的業務邏輯。
    負責從 CSV 數據計算和緩存遙測報告。
    僅在需要時處理數據，並將結果快取一段時間。
    """

    # --- 類別級別的配置和緩存 ---
    SAMPLING_INTERVAL = timedelta(seconds=10)
    REPORTING_INTERVAL_MINUTES = 3

    MAX_REPORTS = 2048
    REPORT_ID_PREFIX = "CDU_Report_"

    # --- 快取與過期管理 ---
    _reports_cache = deque(maxlen=MAX_REPORTS)
    _cache_lock = threading.Lock()  # 仍然需要鎖，以防極端情況下的並發請求

    # 新增：快取過期時間配置（秒）
    CACHE_EXPIRATION_SECONDS = 5  # 5s

    # 新增：記錄上次快取更新的時間戳
    _last_update_timestamp = 0

    @classmethod
    def _update_cache_if_expired(cls):
        """
        檢查快取是否過期，如果過期則執行一次更新。
        這是一個線程安全的操作。
        讀取所有CSV數據，將其分組，並創建包含原始採樣數據的報告。
        """
        # 第一次檢查（無鎖），快速判斷大多數情況
        if (time.time() - cls._last_update_timestamp) < cls.CACHE_EXPIRATION_SECONDS:
            return

        # 快取可能已過期，現在獲取鎖來進行同步和第二次檢查
        with cls._cache_lock:
            current_time = time.time()
            # 雙重檢查：確認在等待鎖的期間，沒有其他線程已經完成了更新
            if (
                time.time() - cls._last_update_timestamp
            ) < cls.CACHE_EXPIRATION_SECONDS:
                return

        # --- 快取已過期，執行更新邏輯 ---
        print(f"[{datetime.now()}] Cache expired. Updating telemetry data...")

        all_records = SensorCsvAdapter.get_all_sensor_data_as_list_of_dicts()

        if not all_records:
            print("No sensor data found during update.")
            # 更新時間戳，即使沒有數據，也避免在下一個週期內立即重試
            cls._last_update_timestamp = time.time()
            return

        sampled_data = []
        if all_records:
            last_sample_time = all_records[0]["time"] - cls.SAMPLING_INTERVAL
            for record in all_records:
                if record["time"] - last_sample_time >= cls.SAMPLING_INTERVAL:
                    sampled_data.append(record)
                    last_sample_time = record["time"]

        reports_in_groups = defaultdict(list)
        for sample in sampled_data:
            ts = sample["time"]
            bucket_minute = (
                ts.minute // cls.REPORTING_INTERVAL_MINUTES
            ) * cls.REPORTING_INTERVAL_MINUTES
            bucket_timestamp = ts.replace(minute=bucket_minute, second=0, microsecond=0)
            reports_in_groups[bucket_timestamp].append(sample)

        generated_reports = []
        sorted_buckets = sorted(reports_in_groups.items())

        for i, (period_timestamp, group_of_samples) in enumerate(sorted_buckets):
            report_id = f"{cls.REPORT_ID_PREFIX}{i + 1}"
            report_timestamp_iso = period_timestamp.replace(
                tzinfo=timezone.utc
            ).isoformat()
            metric_values = []
            for sample_row in group_of_samples:
                entry_timestamp_iso = (
                    sample_row["time"].replace(tzinfo=timezone.utc).isoformat()
                )
                for key, value in sample_row.items():
                    if key == "time":
                        continue
                    metric_values.append(
                        {
                            "MetricId": key,
                            "MetricValue": str(value),
                            "Timestamp": entry_timestamp_iso,
                        }
                    )
            report = {
                "@odata.id": f"/redfish/v1/TelemetryService/MetricReports/{report_id}",
                "@odata.type": "#MetricReport.v1_5_2.MetricReport",
                "Id": report_id,
                "Name": f"CDU 3-Minute Data Collection Report - {report_timestamp_iso}",
                "Timestamp": report_timestamp_iso,
                "MetricValues": metric_values,
            }
            generated_reports.append(report)

        cls._reports_cache.clear()
        cls._reports_cache.extend(generated_reports)

        # 更新完成後，記錄新的更新時間
        cls._last_update_timestamp = time.time()
        print(
            f"[{datetime.now()}] Telemetry cache update complete. {len(cls._reports_cache)} reports are cached."
        )

    def get_all_reports(self) -> dict:
        """
        獲取 MetricReports 集合，直接從緩存中讀取。
        """
        # 每次被調用時，都先檢查快取是否需要更新
        self._update_cache_if_expired()

        # 直接從快取中讀取數據（此時快取可能是新更新的，也可能是未過期的舊數據）
        with self._cache_lock:
            members_list = [
                {"@odata.id": report["@odata.id"]} for report in self._reports_cache
            ]

        return {
            "@odata.id": "/redfish/v1/TelemetryService/MetricReports",
            "@odata.type": "#MetricReportCollection.MetricReportCollection",
            "Name": "CDU Metric Reports Collection",
            "Members@odata.count": len(members_list),
            "Members": members_list,
        }

    def get_report_by_id(self, report_id: str) -> dict | None:
        """
        獲取單個 MetricReport 的詳細資訊，直接從緩存中查找。
        """
        # 直接從快取中讀取數據（此時快取可能是新更新的，也可能是未過期的舊數據）
        self._update_cache_if_expired()

        with self._cache_lock:
            for report in self._reports_cache:
                if report["Id"] == report_id:
                    return report.copy()
        return None


    @cached(cache=TTLCache(maxsize=1, ttl=30))
    def load_metric_definitions(self) -> tuple:
        metrics: List[Dict] = SensorLogModel.to_metric_definitions()
        metric_dicts = {}
        for metric in metrics:
            metric_dicts[ metric['FieldName'] ] = metric
        return metrics, metric_dicts

    
    def fetch_TelemetryService_MetricDefinitions(self, metric_definition_id=None) -> dict:
        """
        """
        metrics, metric_dicts = self.load_metric_definitions()

        if metric_definition_id == None:
            m = RfMetricDefinitionCollectionModel()

            for metric in metrics:
                m.Members.append(
                    {
                        "@odata.id": f"/redfish/v1/TelemetryService/MetricDefinitions/{metric['FieldName']}"
                    }
                )
            
            m.odata_context = "/redfish/v1/$metadata#MetricDefinitionCollection.MetricDefinitionCollection"
            m.odata_id = "/redfish/v1/TelemetryService/MetricDefinitions"
            m.odata_type = "#MetricDefinitionCollection.MetricDefinitionCollection"
            m.Name = "Metric Definition Collection"
            m.Members_odata_count = len(m.Members)
            
            return m.to_dict()
        else:
            metric = metric_dicts.get(metric_definition_id, None)
            if metric == None:
                raise ProjRedfishError(ProjRedfishErrorCode.RESOURCE_NOT_FOUND, f"MetricDefinition, {metric_definition_id}, not found")

            m = RfMetricDefinitionModel()
            m.Id = metric['FieldName']
            m.Name = metric['FieldName']
            m.MetricDataType = metric['MetricDataType']
            m.Units = metric['Units']
            m.odata_context = "/redfish/v1/$metadata#MetricDefinition.MetricDefinition"
            m.odata_id = f"/redfish/v1/TelemetryService/MetricDefinitions/{metric['FieldName']}"
            m.odata_type = "#MetricDefinition.v1_0_0.MetricDefinition"
            
            return m.to_dict()
            
            
    def fetch_TelemetryService_MetricReportDefinitions(self, metric_report_definition_id=None) -> dict:
        """
        """

        metrics, metric_dicts = self.load_metric_definitions()

        if metric_report_definition_id == None:
            m = RfMetricReportDefinitionCollectionModel()

            m.Members.append(
                {
                    "@odata.id": "/redfish/v1/TelemetryService/MetricReportDefinitions/1"
                }
            )

            m.odata_context = "/redfish/v1/$metadata#MetricReportDefinitionCollection.MetricReportDefinitionCollection"
            m.odata_id = "/redfish/v1/TelemetryService/MetricReportDefinitions"
            m.odata_type = "#MetricReportDefinitionCollection.MetricReportDefinitionCollection"
            m.Name = "Metric Report Definition Collection"
            m.Members_odata_count = len(m.Members)
            return m.to_dict()
        else:
            if metric_report_definition_id != "1":
                raise ProjRedfishError(ProjRedfishErrorCode.RESOURCE_NOT_FOUND, f"MetricReportDefinition, {metric_report_definition_id}, not found")
            
            m = RfMetricReportDefinitionModel()
            m.Metrics = []
            
            for metric in metrics:
                ## Warning: PydanticSerializationUnexpectedValue(Expected `RfMetric` - serialized value may not be as expected [input_value={'@odata.id': '/redfish/v...MetricDefinitions/time'}, input_type=dict])
                # m.Metrics.append(
                #     {
                #         "@odata.id": f"/redfish/v1/TelemetryService/MetricDefinitions/{metric['FieldName']}"
                #     }
                # )

                metric_model = RfMetric()
                metric_model.MetricId = metric['FieldName']
                metric_model.Oem = {
                    "@odata.id": f"/redfish/v1/TelemetryService/MetricDefinitions/{metric['FieldName']}",
                    # "Units": metric['Units']
                }
                m.Metrics.append(metric_model)
            
            m.odata_context = "/redfish/v1/$metadata#MetricReportDefinition.MetricReportDefinition"
            m.odata_id = "/redfish/v1/TelemetryService/MetricReportDefinitions/1"
            m.odata_type = "#MetricReportDefinition.v1_0_0.MetricReportDefinition"
            m.Id = "1" # metric_report_definition_id
            m.Name = "Periodic Reort" 
            m.MetricReportDefinitionType = RfMetricReportDefinitionType.Periodic
            m.Schedule = {
                "RecurrenceInterval": "PT3M"  # ISO 8601 duration format for 3 minutes
            }
            m.ReportActions = [
                RfReportActionsEnum.LogToMetricReportsCollection
            ]
            m.ReportUpdates = RfReportUpdatesEnum.AppendWrapsWhenFull
            
            return m.to_dict()