import os
import sys
import json
from typing import List, Optional
from http import HTTPStatus
from flask import abort
from cachetools import cached, TTLCache
from mylib.common.proj_error import ProjError, ProjRedfishError, ProjRedfishErrorCode
from mylib.utils.FileUtil import FileUtil
from pydantic import BaseModel, Field

"""
讀取 /home/user/service/webUI/json/ 裡的json檔
error log (latest 500 entries): signal_records.json
"""
class WebAppSignalRecordModel(BaseModel):
    signal_name: str        = Field(default="")
    on_time: str            = Field(default="")
    off_time: Optional[str] = Field(default=None)
    signal_value: str       = Field(default="")

class WebAppJsonReader:
    

    @classmethod
    def _error_log_path(cls) -> str:
        json_root = os.getenv('ITG_WEBAPP_JSON_ROOT')
        if json_root is None:
            # raise ProjError(HTTPStatus.BAD_REQUEST.value, "`ITG_WEBAPP_JSON_ROOT` should be defined in .env file")
            raise ProjRedfishError(ProjRedfishErrorCode.RESOURCE_NOT_FOUND, "`ITG_WEBAPP_JSON_ROOT` should be defined in .env file")
        
        json_filepath = os.path.join(json_root, "signal_records.json")

        if FileUtil.exists(json_filepath) and FileUtil.is_file(json_filepath):
            return json_filepath
        else:
            # raise ProjError(HTTPStatus.NOT_FOUND.value, f"{json_filepath} is not exist!")
            raise ProjRedfishError(ProjRedfishErrorCode.RESOURCE_NOT_FOUND, f"{json_filepath} is not exist!")

    @classmethod
    @cached(cache=TTLCache(maxsize=1, ttl=10))
    def read_all_errorlog_entries(cls) -> List[WebAppSignalRecordModel]:
        """Read all error logs from signal_records.json
        @note: signal_records.json records max 500s records
        """
        error_log_path = cls._error_log_path()
        log_json_ary = json.loads(FileUtil.read(error_log_path))
        ret = []
        for info in log_json_ary:
            tmp_record = WebAppSignalRecordModel(**info)
            ret.append(tmp_record)
        return ret

 
