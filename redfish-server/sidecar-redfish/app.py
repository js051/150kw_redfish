"""
Run:
    python app.py --env=dev
"""

##############################################################################
#             eeeeeeeeeeee    nnnn  nnnnnnnn vvvvvvv           vvvvvvv
#           ee::::::::::::ee  n:::nn::::::::nnv:::::v         v:::::v
#          e::::::eeeee:::::een::::::::::::::nnv:::::v       v:::::v
#         e::::::e     e:::::enn:::::::::::::::nv:::::v     v:::::v
#         e:::::::eeeee::::::e  n:::::nnnn:::::n v:::::v   v:::::v
#         e:::::::::::::::::e   n::::n    n::::n  v:::::v v:::::v
#         e::::::eeeeeeeeeee    n::::n    n::::n   v:::::v:::::v
#         e:::::::e             n::::n    n::::n    v:::::::::v
#         e::::::::e            n::::n    n::::n     v:::::::v
#  ......  e::::::::eeeeeeee    n::::n    n::::n      v:::::v
#  .::::.   ee:::::::::::::e    n::::n    n::::n       v:::v
#  ......     eeeeeeeeeeeeee    nnnnnn    nnnnnn        vvv
##############################################################################
##
# Note! Must the first line!
##
import load_env


# from argparse import ArgumentParser
# from dotenv import load_dotenv
from flask import Flask, request, Response, jsonify, make_response
from flask_restx import Api
import sys, os
from werkzeug.exceptions import HTTPException
from http import HTTPStatus
from mylib.db.extensions import ext_engine
from mylib.db.db_util import init_orm
from mylib.common.proj_error import ProjError, ProjRedfishError
from mylib.auth.rf_auth import check_basic_auth, check_session_auth, AuthStatus
from mylib.services.debug_service import DebugService
from mylib.managements.FlaskConfiger import FlaskConfiger
from flask.json.provider import DefaultJSONProvider
import json


class CustomApi(Api):
    def handle_validation_error(self, error, bundle_errors):
        return {
            "code": HTTPStatus.BAD_REQUEST,
            "message": "Validation Failed",
            "errors": error.data.get("errors", {}),
        }, HTTPStatus.BAD_REQUEST


class MyJSONProvider(DefaultJSONProvider):
    """Provide JSON operations using Python’s built-in json library.
    @see https://flask.palletsprojects.com/en/stable/api/#flask.json.provider.DefaultJSONProvider
    @note: 高力想直接顯示utf8內容，不要轉成unicode編碼
    """

    def dumps(self, obj, **kwargs):
        kwargs.setdefault(
            "ensure_ascii", False
        )  # 強制所有回傳不轉 Unicode (ex: "μs/cm" 不會轉成 "\u03bcs/cm")
        # kwargs.setdefault("indent", None)  # 如需 pretty，可調整這一行
        return json.dumps(obj, **kwargs)

    # def loads(self, s, **kwargs):
    #     return json.loads(s, **kwargs)


app = Flask(__name__)

db_filename_suffix = "-test" if os.getenv("env") == "test" else ""
db_filename = f"mydb{db_filename_suffix}.sqlite"

# initialize sqlalchemy
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_filename}"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 5,
    "max_overflow": 1,
    "pool_timeout": 10,
}
app.config["JSON_SORT_KEYS"] = False
app.config['JSON_AS_ASCII'] = False

app.json_provider_class = MyJSONProvider
app.json = app.json_provider_class(app)

ext_engine.init_db(app)
init_orm(ext_engine.get_app(), ext_engine.get_db())

api = Api(
    app,
    version="0.6.6",
    title="Redfish API",
    description="API for redfish system",
    doc="/",
)


@app.route("/redfish", methods=["GET"], strict_slashes=False)
def redfish_root():
    root = {
        "@odata.id": "/redfish",
        "@odata.type": "#RedfishVersionCollection.RedfishVersionCollection",
        "Name": "Redfish Service Versions",
        "Members@odata.count": 1,
        "Members": [
            { "@odata.id": "/redfish/v1" }
        ]
    }
    return root, 200


@app.route("/debug", methods=["GET"])
def debug():
    return jsonify(DebugService().load_report())


# 引入資料夾中的所有路由模組
from mylib.routers.root_router import root_ns

api.add_namespace(root_ns, path="/redfish/v1")

from mylib.routers.updateService_router import update_ns

api.add_namespace(update_ns, path="/redfish/v1")

from mylib.routers.Chassis_router import Chassis_ns

api.add_namespace(Chassis_ns, path="/redfish/v1")

from mylib.routers.mangers_router import managers_ns

api.add_namespace(managers_ns, path="/redfish/v1")

from mylib.routers.TelemetryService_router import TelemetryService_ns

api.add_namespace(TelemetryService_ns, path="/redfish/v1")

from mylib.routers.ThermalEquipment_router import ThermalEquipment_ns

api.add_namespace(ThermalEquipment_ns, path="/redfish/v1")

from mylib.routers.account_service_router import AccountService_ns

api.add_namespace(AccountService_ns, path="/redfish/v1")

from mylib.routers.session_service_router import SessionService_ns

api.add_namespace(SessionService_ns, path="/redfish/v1")

from mylib.routers.CertificateService_router import CertificateService_ns

api.add_namespace(CertificateService_ns, path="/redfish/v1")

from mylib.routers.EventService_couter import EventService_ns

api.add_namespace(EventService_ns, path="/redfish/v1")

# from mylib.routers.systems_router import system_ns
# api.add_namespace(system_ns, path='/redfish/v1')

# from mylib.routers.ComponentIntegrity_router import ComponentIntegrity_ns
# api.add_namespace(ComponentIntegrity_ns, path='/redfish/v1')

from mylib.models.example_model import ExampleModel


@app.route("/examples")
def examples():
    all_examples = ExampleModel.all()
    return jsonify({"examples": all_examples})


def check_auth(username, password):
    """檢查是否為有效的用戶名和密碼"""
    return username == os.getenv("ADMIN_USERNAME") and password == os.getenv(
        "ADMIN_PASSWORD"
    )


def authenticate():
    """請求身份驗證"""
    return Response(
        "Authentication required.",
        401,
        {"WWW-Authenticate": "Basic realm='Login Required'"},
    )


# 將要使用的 $ 放入
SUPPORTED_DOLLAR_PARAMS = {
    "$filter",
    "$select",
    "$expand",
    "$orderby",
    "$top",
    "$skip",
    "$count",
    "$format",
}


###------------------------------------------------------
@app.before_request
def require_auth_on_all_routes():
    ###----------------處理$--------------------------------------
    if not request.path.startswith("/"):
        return

    for param in request.args.keys():
        if param.startswith("$") and param not in SUPPORTED_DOLLAR_PARAMS:
            return Response(status=501)
    ###----------------移除Auth--------------------------------------
    p = request.path.rstrip("/")

    public = {"/redfish", "/redfish/v1", "/redfish/v1/$metadata", "/redfish/v1/odata"}

    if p in public:
        return

    if (
        p == "/redfish/v1/SessionService/Sessions"
        or p == "/redfish/v1/SessionService/Sessions/Members"
    ) and request.method == "POST":
        return
    ###----------------一般Auth--------------------------------------
    auth = request.authorization
    # if not auth or not check_auth(auth.username, auth.password):
    #     return authenticate()
    if auth and "username" in auth and "password" in auth:
        status = check_basic_auth(auth.username, auth.password)
        if status == AuthStatus.SUCCESS:
            return
        elif status == AuthStatus.ACCOUNT_LOCKED:
            return Response("Account is locked", 403)
        elif status == AuthStatus.ACCOUNT_DISABLE:
            return Response("Account is disabled", 401)
    if "X-Auth-Token" in request.headers:
        token = request.headers["X-Auth-Token"]
        if check_session_auth(token) == AuthStatus.SUCCESS:
            return
    return authenticate()


###----------------處理標頭--------------------------------------
@app.after_request
def add_link_describedby(response):
    if request.method in ("GET", "HEAD") and request.path.startswith("/redfish/v1"):
        response.headers["Link"] = '</redfish/v1/$metadata>; rel="describedby"'
        response.headers["OData-Version"] = "4.0"
    return response

@app.after_request
def remove_message_from_response(response):
    """
    @note If there is no `message` in response, Flask-restx will add `message` to response automatically!
    """
    try:
        if response.content_type == 'application/json':
            """
            redfish error format:
            {
                "error": {
                    "code": "Base.1.19.0.GeneralError",
                    "message": "some exception"
                }
            }
            """
            if response.status_code != HTTPStatus.OK:
                resp_body = json.loads(response.get_data(as_text=True))
                if 'error' in resp_body and 'message' in resp_body: 
                    del resp_body['message']
                    response.set_data(json.dumps(resp_body))
    except Exception as e:
        pass
    return response

@api.errorhandler(HTTPException)
def handle_http_exception(e):
    """
    Catch exception from Flask abort().
    """
    return {
        "code": e.code,
        "name": e.name,
        "message": e.description,
    }, e.code


@api.errorhandler(ProjError)
def handle_proj_error(e):
    """
    Catch exception from custom exception, ProjError.
    @note:
        1) Not use jsonify() to return ProjError
        2) flask-restx will add `message` to response automatically.
    """
    status_code = e.code if e.code < 1000 else HTTPStatus.INTERNAL_SERVER_ERROR.value
    return e.to_redfish_error_dict(), status_code

@api.errorhandler(ProjRedfishError)
def handle_proj_redfish_error(e):
    """
    Catch exception from custom redfish error, ProjRedfishError.
    @note:
        1) Not use jsonify() to return ProjRedfishError
        2) flask-restx will add `message` to response automatically.
    """
    return e.to_dict(), e.http_status

@api.errorhandler(Exception)
def handle_exception(e):
    """
    Catch other exception
    """
    return {"code": 500, "message": str(e)}, 500


if __name__ == "__main__":
    proj_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(proj_root)

    # 取得憑證檔和私鑰檔的路徑
    cert_pem_path = os.path.join(proj_root, "cert.pem")
    key_pem_path = os.path.join(proj_root, "key.pem")

    # disable strict slashes
    FlaskConfiger.disable_strict_slashes_for_all_urls(app, "/redfish/v1")

    # ssl_context=(憑證檔, 私鑰檔)
    redfish_port = int(os.environ.get("ITG_REDFISH_API_PORT", "5000"))
    app.run(
        host="0.0.0.0", port=redfish_port, ssl_context=(cert_pem_path, key_pem_path)
    )
