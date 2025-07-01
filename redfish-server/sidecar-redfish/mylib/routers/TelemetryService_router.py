from flask_restx import Namespace, Resource
from flask import abort, jsonify
from mylib.services.rf_telemetry_service import RfTelemetryService
from mylib.models.sensor_log_model import SensorLogModel

telemetry_service = RfTelemetryService()

# load_dotenv(dotenv_path=".env-dev") # marked by welson (`load_dotenv()` is only allowed in app.p)
TelemetryService_ns = Namespace("TelemetryService", path="/redfish/v1")

TelemetryService_data = {
    "@odata.id": "/redfish/v1/TelemetryService",
    "@odata.type": "#TelemetryService.v1_3_4.TelemetryService",
    "@odata.context": "/redfish/v1/$metadata#TelemetryService.v1_3_4.TelemetryService",
    "Id": "TelemetryService",
    "Name": "CDU Telemetry Service",
    # "Description": "Telemetry Service",
    "Status": {"State": "Enabled", "Health": "OK"},

    # 0513 profile新增 v1.0.0
    "MetricDefinitions": {
        "@odata.id": "/redfish/v1/TelemetryService/MetricDefinitions"
    },
    # 20250616 marked by welson: interop validator not required for SMC
    # "MetricReportDefinitions": {
    #     "@odata.id": "/redfish/v1/TelemetryService/MetricReportDefinitions"
    # },

    "MetricReports": {"@odata.id": "/redfish/v1/TelemetryService/MetricReports"},
    # "Triggers": {
    #     "@odata.id": "/redfish/v1/TelemetryService/Triggers"
    # },
    "Oem": {},
}


@TelemetryService_ns.route("/TelemetryService")
@TelemetryService_ns.doc("Provides the entry point for the Telemetry Service.")
class TelemetryService(Resource):
    def get(self):
        """Returns the Telemetry Service root resource."""
        # 返回固定的靜態服務入口點資訊
        return jsonify(TelemetryService_data)


@TelemetryService_ns.route("/TelemetryService/MetricReports")
@TelemetryService_ns.doc("Provides the collection of available metric reports.")
class MetricReportCollection(Resource):
    def get(self):
        """Returns the collection of available MetricReports."""
        # 直接調用 service 方法並返回結果
        return jsonify(
            telemetry_service.get_all_reports()
        )


@TelemetryService_ns.route("/TelemetryService/MetricReports/<string:report_id>")
@TelemetryService_ns.doc(params={"report_id": "The ID of the report to retrieve."})
class MetricReport(Resource):
    def get(self, report_id):
        """Returns a specific MetricReport by its ID."""
        # 直接調用 service 方法並返回結果
        report = telemetry_service.get_report_by_id(report_id)
        if not report:
            abort(404, f"MetricReport with ID '{report_id}' not found.")
        return jsonify(report)


# 0513新增
METRIC_DEFS = [
    {
        "Id": "test1",
        "Name": "fan speed",
        "MetricDataType": "String",
        "Units": "RPM",
    }
]
REPORT_DEFS = [
    {
        "Id": "1",
        "Name": "Periodic Report",
        "MetricReportDefinitionType": "Periodic",           #產生報告的方式:定期產生報告
        "ReportUpdates": "AppendWrapsWhenFull",             #更新報告的方式:覆蓋
        "Schedule": {
            "RecurrenceInterval": "PT3M"                    #每3分鐘產生一次報告
        },
        "ReportActions": [
                "LogToMetricReportsCollection"
            ],
        "Metrics": [
            {"@odata.id": f"/redfish/v1/TelemetryService/MetricDefinitions/{m['Id']}"}
            for m in METRIC_DEFS
        ],
    }
]
# TRIGGERS = [
#     {
#       "Id": "HighTemp",
#       "Name": "HighTemp",
#       "Metric": {"@odata.id": "/redfish/v1/TelemetryService/MetricDefinitions/CPU_Temp"},
#       "Condition": { "Comparison": "GreaterThan", "Value": 85 }
#     }
# ]


# MetricDefinitions Collection
@TelemetryService_ns.route("/TelemetryService/MetricDefinitions")
class MetricDefinitionCollection(Resource):
    def get(self):
        # members = []
        # for m in METRIC_DEFS:
        #     members.append(
        #         {
        #             "@odata.id": f"/redfish/v1/TelemetryService/MetricDefinitions/{m['Id']}"
        #         }
        #     )
        # return {
        #     "@odata.context": "/redfish/v1/$metadata#MetricDefinitionCollection.MetricDefinitionCollection",
        #     "@odata.id": "/redfish/v1/TelemetryService/MetricDefinitions",
        #     "@odata.type": "#MetricDefinitionCollection.MetricDefinitionCollection",
        #     "Name": "Metric Definition Collection",
        #     "Members@odata.count": len(members),
        #     "Members": members,
        # }, 200
        return jsonify(
            telemetry_service.fetch_TelemetryService_MetricDefinitions()
        )


# Individual MetricDefinition
@TelemetryService_ns.route("/TelemetryService/MetricDefinitions/<string:metric_definition_id>")
class MetricDefinition(Resource):
    def get(self, metric_definition_id):
        # for m in METRIC_DEFS:
        #     if m["Id"] == metric_definition_id:
        #         m = m.copy()
        #         m["@odata.context"] = (
        #             "/redfish/v1/$metadata#MetricDefinition.MetricDefinition"
        #         )
        #         m["@odata.id"] = (
        #             f"/redfish/v1/TelemetryService/MetricDefinitions/{metric_definition_id}"
        #         )
        #         m["@odata.type"] = "#MetricDefinition.v1_0_0.MetricDefinition"
        #         return m, 200
        return jsonify(
            telemetry_service.fetch_TelemetryService_MetricDefinitions(metric_definition_id)
        )


# MetricReportDefinitions Collection
@TelemetryService_ns.route("/TelemetryService/MetricReportDefinitions")
class MetricReportDefCollection(Resource):
    def get(self):
        return jsonify(
            telemetry_service.fetch_TelemetryService_MetricReportDefinitions()
        )
        """
        members = [
            {
                "@odata.id": f"/redfish/v1/TelemetryService/MetricReportDefinitions/{r['Id']}"
            }
            for r in REPORT_DEFS
        ]
        return {
            "@odata.context": "/redfish/v1/$metadata#MetricReportDefinitionCollection.MetricReportDefinitionCollection",
            "@odata.id": "/redfish/v1/TelemetryService/MetricReportDefinitions",
            "@odata.type": "#MetricReportDefinitionCollection.MetricReportDefinitionCollection",
            "Name": "Metric Report Definition Collection",
            "Members@odata.count": len(members),
            "Members": members,
        }, 200
        """


# Individual MetricReportDefinition
@TelemetryService_ns.route("/TelemetryService/MetricReportDefinitions/<string:metric_report_definition_id>")
class MetricReportDef(Resource):
    def get(self, metric_report_definition_id):
        return jsonify(
            telemetry_service.fetch_TelemetryService_MetricReportDefinitions(metric_report_definition_id)
        )
        '''
        for r in REPORT_DEFS:
            if r["Id"] == report_id:
                r = r.copy()
                r["@odata.context"] = (
                    "/redfish/v1/$metadata#MetricReportDefinition.MetricReportDefinition"
                )
                r["@odata.id"] = (
                    f"/redfish/v1/TelemetryService/MetricReportDefinitions/{report_id}"
                )
                r["@odata.type"] = (
                    "#MetricReportDefinition.v1_0_0.MetricReportDefinition"
                )
                return r, 200
        return {"error": "Not found"}, 404
        '''


# Triggers Collection
# @TelemetryService_ns.route('/TelemetryService/Triggers')
# class TriggerCollection(Resource):
#     def get(self):
#         members = [{"@odata.id": f"/redfish/v1/TelemetryService/Triggers/{t['Id']}"} for t in TRIGGERS]
#         return {
#             "@odata.context": "/redfish/v1/$metadata#TriggerCollection.TriggerCollection",
#             "@odata.id": "/redfish/v1/TelemetryService/Triggers",
#             "@odata.type": "#TriggerCollection.TriggerCollection",
#             "Name": "Trigger Collection",
#             "Members@odata.count": len(members),
#             "Members": members
#         }, 200

# Individual Trigger
# @TelemetryService_ns.route('/TelemetryServiceTriggers/<string:trigger_id>')
# class Trigger(Resource):
#     def get(self, trigger_id):
#         for t in TRIGGERS:
#             if t['Id'] == trigger_id:
#                 t = t.copy()
#                 t["@odata.context"] = "/redfish/v1/$metadata#Trigger.Trigger"
#                 t["@odata.id"] = f"/redfish/v1/TelemetryService/Triggers/{trigger_id}"
#                 t["@odata.type"] = "#Trigger.v1_0_0.Trigger"
#                 return t, 200
#         return {"error": "Not found"}, 404
