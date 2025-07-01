import os
from http import HTTPStatus
import requests
import platform
from cachetools import cached, TTLCache
from mylib.models.rf_resource_model import RfResetType
from mylib.common.proj_error import ProjError
from mylib.utils.SystemCommandUtil import SystemCommandUtil


"""
webapp 就是 大家稱為webUI的東西
名字容易讓人誤會成UI的服務，但事實上就是web app for cdu

@note:
    `webUI` is a confused naming. in fact it is a CDU web app, including backend api.
"""



class WebAppAPIAdapter:

    def __init__(self):
        """
        webUI使用的認證機制是flask user_login，是session cookie機制
        """
        self.username = os.getenv("ITG_WEBAPP_USERNAME")
        self.password = os.getenv("ITG_WEBAPP_PASSWORD")
        self.host = os.getenv("ITG_WEBAPP_HOST")

        self.session = self.create_login_session()
 
    @classmethod
    @cached(cache=TTLCache(maxsize=1, ttl=60))
    def check_health(cls) -> bool:
        """Check whether webapp(webUI) is running|healthy
        @note: 
            ex. LogService of Redfish requires `Status` field
        @note: 
            方案一：看webapp的process是否存在
            方案二：以 webUI/logs/sensor 與 webUI/web/json 的檔案內容，如果3秒內，則判定為health
        """
        try:
            host = os.getenv("ITG_WEBAPP_HOST", "")
            port = host.split(":")[-1]
            linux_cmd = f"lsof -i -P| grep LISTEN | grep {port} | wc -l"
            result = SystemCommandUtil.exec(linux_cmd)
            return len(result["stdout_lines"]) >= 1
        except Exception as e:
            if platform.system().lower() == "windows":
               return True
            else:
                return False

    @cached(cache=TTLCache(maxsize=1, ttl=30))
    def create_login_session(self):
        session = requests.Session()
        
        # For check_auth() in scc_app.py
        session.auth = (self.username, self.password)
        
        # For @login_required() decorator in flask process
        login_url = f"{self.host}/login"
        payload = {
            "username": self.username,
            "password": self.password
        }
        login_response = session.post(login_url, data=payload)

        return session

    def _handle_response(self, response):
        # response.raise_for_status() # for Authentication
        if response.status_code != HTTPStatus.OK:
            raise ProjError(response.status_code, response.text)
        return response

    def reset_to_defaults(self, reset_type: str) -> dict:
        """Reset to defaults
        @note:
            Fetch /restore_factory_setting_all from webUI
            {
            }
        """
        url = f"{self.host}/restore_factory_setting_all"
        post_body = {
            "ResetType": reset_type
        }
        response = self.session.post(url, data=post_body)
        self._handle_response(response)
        return response

    def reset(self, reset_type: str=RfResetType.ForceRestart.value) -> dict:
        """Reset
        @note:
            Fetch scc api: /api/v1/reboot, is delay reboot
        """
        if reset_type == RfResetType.ForceRestart.value:
            url = f"{self.host}/api/v1/reboot"
        elif reset_type == RfResetType.GracefulRestart.value:
            url = f"{self.host}/api/v1/reboot"
        else:
            raise ProjError(HTTPStatus.BAD_REQUEST.value, f"Invalid reset type: {reset_type}")
        response = self.session.get(url) # raise NewConnectionError if server is not running
        self._handle_response(response)
        return response

    def shutdown(self, reset_type: str=RfResetType.ForceRestart.value) -> dict:
        """Shutdown
        @note:
            Fetch webUI api: /shutdown
        """
        if reset_type == RfResetType.ForceRestart.value:
            url = f"{self.host}/shutdown"
        elif reset_type == RfResetType.GracefulRestart.value:
            url = f"{self.host}/shutdown"
        else:
            raise ProjError(HTTPStatus.BAD_REQUEST.value, f"Invalid reset type: {reset_type}")
        response = self.session.get(url)
        self._handle_response(response)
        return response

    def read_version(self) -> dict:
        """read version from webUI
        """
        url = f"{self.host}/read_version"
        response = self.session.get(url)
        self._handle_response(response)
        return response
    
    def setting_snmp(self, data: dict) -> dict:
        '''
        POST SNMP setting
        '''
        url = f"{self.host}/store_snmp_setting"
        response = self.session.post(url, json=data)
        self._handle_response(response)

        return response
    
    def sync_time(self, data: dict) -> dict:
        '''
        POST NTP
        data:{
            ntp_server: "ntp.ubuntu.com",
            timezone: "(UTC+08:00) Taipei"
        }
        '''
        data = {
            "ntp_server": data["ntp_server"],
            "timezone": "Asia/Taipei"
        }
        url = f"{self.host}/sync_time"
        response = self.session.post(url, json=data)
        self._handle_response(response)

        return response