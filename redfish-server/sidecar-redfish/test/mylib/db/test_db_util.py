import os
import json
import pytest
import sys
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from load_env import redfish_info
from mylib.models.setting_model import SettingModel
from mylib.db.db_util import reset_to_defaults
from mylib.utils.StringUtil import StringUtil
from mylib.db.extensions import ext_engine
from app import app

def test_reset_to_defaults(client):
    """[TestCase] reset to defaults"""
    with app.app_context():

        default_values = redfish_info.get('Settings', {}).get('DefaultValues', [])
        default_values_dict = {item.get('key'): item.get('value') for item in default_values}
        assert len(default_values) > 0
        print("PASS: len of default_values > 0")

        # update other value
        db = ext_engine.get_db()
        print(f"db: {db}")
        print("Assign random value to default values")
        for default_value in default_values:
            key = default_value.get('key')
            random_value = StringUtil.random(6)
            print(f"Assign random value for key={key} value={random_value}")
            SettingModel.save_key_value(key=key, value=random_value)

        # reset to default
        print("Run reset_to_defaults()")
        reset_to_defaults()

        # assert values
        settings = SettingModel.query.all()
        success_cnt = 0
        for setting in settings:
            default_value = default_values_dict.get(setting.key)
            try:
                assert setting.value == default_value
                print(f"PASS: value of key={setting.key} is expected to be {default_value}")
                success_cnt += 1
            except Exception as e:
                print(f"FAIL: value of key={setting.key} is expected to be {default_value} but actual value in db is {setting.value}")
        assert success_cnt == len(settings)
        print(f"PASS: reset_to_defaults() success. success_cnt={success_cnt}, total_cnt={len(settings)}")

