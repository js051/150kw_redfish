from flask_restx import Namespace, Resource
from flask import request
from datetime import datetime
import requests
import os
from mylib.utils.load_api import load_raw_from_api 
from mylib.utils.load_api import CDU_BASE
from mylib.common.proj_error import ProjRedfishError, ProjRedfishErrorCode



update_ns = Namespace('', description='update service')

UpdateService_data = {
    "@odata.id": "/redfish/v1/UpdateService",
    "@odata.type": "#UpdateService.v1_14_0.UpdateService",
    
    "Id": "UpdateService",
    "Name": "Update cdu",
    
    "ServiceEnabled": True,
    "FirmwareInventory": {
        "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory"
    },
    "Actions": {
        "#UpdateService.SimpleUpdate": {
            "target": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            "@Redfish.ActionInfo": "/redfish/v1/UpdateService/SimpleUpdateActionInfo"
        }
    },
}

FirmwareInventory_data = {
    "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory",
    "@odata.type": "#SoftwareInventoryCollection.SoftwareInventoryCollection",
    "Name": "Firmware Inventory",

    "Members@odata.count": 2, # 未串
    "Members": [
        {"@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/System_Software"},
        {"@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/Control_Firmware"}
    ],
}

System_Software_data = {
    "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/System_Software" ,
    "@odata.type": "#SoftwareInventory.v1_12_0.SoftwareInventory",
    "Id": "System_Software",
    "Name": "System_Software",
    "Manufacturer": "Supermicro",
    # 更新日
    "ReleaseDate": "2025-02-21T06:02:08Z",
    # 是否可更新
    "Updateable": True,    
    "Version": "ok",
    "SoftwareId": "WEB-INTERFACE",
    "Oem": {
        # "supermicro": {
        #     "@odata.type": "#SMC.supermicro.Redfish",
        #     "Redfish": "N/A",
        # }
    }
}

@update_ns.route("/UpdateService")
class UpdateService(Resource):
    def get(self):

        return UpdateService_data  

@update_ns.route("/UpdateService/FirmwareInventory")
class FirmwareInventory(Resource):
    def get(self):

        return FirmwareInventory_data  
# System Software
@update_ns.route("/UpdateService/FirmwareInventory/System_Software")
class FirmwareInventoryWebInterface(Resource):
    def get(self):
        release_date = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/display/version")["version"]["Release_Time"]
        # fmt = os.getenv("DATETIME_FORMAT") 
        # dt = datetime.strptime(release_date, "%Y-%m-%d %H:%M:%S")
        # release_date = dt.strftime(fmt)
        System_Software_data["ReleaseDate"] = release_date + "T"
        System_Software_data["Version"] = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/display/version")["version"]["WebUI"]
        # WebInterface_data["Oem"]["supermicro"]["Redfish"] = load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/display/version")["version"]["Redfish_Server"]
        return System_Software_data  

# Control Firmware
@update_ns.route("/UpdateService/FirmwareInventory/Control_Firmware")
class FirmwareInventoryControlUnit_1(Resource):
    def get(self):
        controlunit1_data = {
            "@odata.id": "/redfish/v1/UpdateService/FirmwareInventory/Control_Firmware" ,
            "@odata.type": "#SoftwareInventory.v1_12_0.SoftwareInventory",
            "Id": "Control_Firmware",
            "Name": "Control_Firmware",
            "Manufacturer": "Supermicro",
            # 更新日
            # "ReleaseDate": "2025-02-21T06:02:08Z", # TBD
            # 是否可更新
            "Updateable": False,    
            "Version": "0" +str(load_raw_from_api(f"{CDU_BASE}/api/v1/cdu/components/display/version")["version"]["PLC"]),
            "SoftwareId": "PLC-VERSION",
            "Oem": {}
        }
        return controlunit1_data

@update_ns.route("/UpdateService/SimpleUpdateActionInfo")
class SimpleUpdateActionInfo(Resource):
    def get(self):
        return {
          "@odata.context": "/redfish/v1/$metadata#ActionInfo.ActionInfo",
          "@odata.id": "/redfish/v1/UpdateService/SimpleUpdateActionInfo",
          "@odata.type": "#ActionInfo.v1_4_2.ActionInfo",
          "Id": "SimpleUpdateActionInfo",
          "Description": "SimpleUpdate ActionInfo",
          "Name": "SimpleUpdate ActionInfo",
          
          "Parameters": [
            {"Name":"ImageURI",        "Required":True,  "DataType":"String"}, # 必填欄位
            {"Name":"TransferProtocol","Required":True, "DataType":"String","AllowableValues":["HTTP","HTTPS"]}, # FTP先拿掉
            # {"Name":"Targets",         "Required":False, "DataType":"StringArray"},
            # {"Name":"UserName",        "Required":False, "DataType":"String"},
            # {"Name":"Password",        "Required":False, "DataType":"String"}
          ]
        }, 200

from werkzeug.datastructures import FileStorage 
upload_parser = update_ns.parser()
upload_parser.add_argument(
    'File',
    location='files',
    type=FileStorage,
    required=True,
    help='Firmware zip file'
)
AllowableValues = {"http","https"}
@update_ns.route("/UpdateService/Actions/UpdateService.SimpleUpdate")
class ActionsUpdateCduSimpleUpdate(Resource):
    @update_ns.expect(upload_parser) 
    @update_ns.doc(consumes=['multipart/form-data'])       
    def post(self):
        ORIGIN_UPLOAD_API = f"{CDU_BASE}/api/v1/update_firmware"

        # 檢查是否是 JSON 請求
        if request.is_json:
            try:
                data = request.get_json()
                image_uri = data.get("ImageURI")
                proto = data.get("TransferProtocol") or ""
                proto = proto.lower()
                # 若 client 指定了 TransferProtocol，要檢查是否合法
                if proto and proto not in AllowableValues:
                    # return {"error": f"TransferProtocol must be one of {list(AllowableValues)}"}, 400
                    raise ProjRedfishError(ProjRedfishErrorCode.GENERAL_ERROR, f"TransferProtocol must be one of {list(AllowableValues)}")

                # 如果 URI 裡沒有 scheme，就套用 TransferProtocol（或預設 HTTP）
                if "://" not in image_uri:
                    scheme = proto.lower() if proto else "http"
                    image_uri = f"{scheme}://{image_uri}"

                if image_uri:
                    # 下載檔案

                    file_download = requests.get(image_uri, timeout=60)
                    if file_download.status_code != 200:
                        # return {"error": f"Download failed: HTTP {file_download.status_code}"}, 400
                        raise ProjRedfishError(ProjRedfishErrorCode.GENERAL_ERROR, f"Download failed: HTTP {file_download.status_code}")

                    # 下載成功後，準備檔案傳遞給內部 API
                    files = {"file": ("upload.gpg", file_download.content, "application/pgp-encrypted")}
                    r = requests.post(ORIGIN_UPLOAD_API, files=files, timeout=(10, None))
                    return "upload success, it will reboot", 200
                else:
                    # return {"error": "Missing ImageURI in JSON"}, 400
                    raise ProjRedfishError(ProjRedfishErrorCode.PROPERTY_MISSING, "Missing ImageURI in JSON")
            except requests.RequestException as e:
                # return {"error": "Download or upload failed", "details": str(e)}, 502
                raise ProjRedfishError(ProjRedfishErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE, f"Download or upload failed: {str(e)}")
            except Exception as e:
                # return {"error": f"Internal Error: {str(e)}"}, 500
                raise ProjRedfishError(ProjRedfishErrorCode.INTERNAL_ERROR, f"Internal Error: {str(e)}")

        # 檢查是否有檔案上傳
        elif 'ImageFile' in request.files:
            try:
                file = request.files.get("ImageFile")
                if not file:
                    # return {"error": "No file uploaded"}, 400
                    raise ProjRedfishError(ProjRedfishErrorCode.PROPERTY_MISSING, "No file uploaded")
                files = {"file": (file.filename, file.stream, file.mimetype)}
                r = requests.post(ORIGIN_UPLOAD_API, files=files, timeout=(10, None))
                return "upload success, it will reboot", 200
            except requests.HTTPError:
                return r.json() if r.headers.get("Content-Type","").startswith("application/json") else {"error": r.text}, r.status_code
            except requests.RequestException as e:
                # return {"error": "upload failed", "details": str(e)}, 502
                raise ProjRedfishError(ProjRedfishErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE, f"upload failed: {str(e)}")
        
        # 如果既沒有檔案也沒有 ImageURI，返回錯誤
        raise ProjRedfishError(ProjRedfishErrorCode.PROPERTY_MISSING, "No file or ImageURI provided")
        