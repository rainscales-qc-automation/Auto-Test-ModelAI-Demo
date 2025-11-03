import json
import os
from os.path import join, dirname

from dotenv import load_dotenv

load_dotenv('.env')

class Config:
    API_STAGING = "http://localhost:8888"

    URL_UPDATE_RULE_CODE = "/api/rules/"   # /api/rules/{ruleCode}
    URL_POST_VIDEO = "/api/videos"
    URL_ANALYZE_VIDEO = "/api/videos/analyze"

    SERVICE_ACCOUNT_FILE = (dirname(dirname(__file__)), 'service-google-sheet.json')
    SMB_SERVER = os.environ.get("SMB_SERVER")
    SMB_USER = os.environ.get("SMB_USER")
    SMB_PASSWORD = os.environ.get("SMB_PASSWORD")


    @staticmethod
    def get_folder_video():
        dir_video = join(join(dirname(dirname(__file__)), 'data_test'), 'video')
        return dir_video

    @staticmethod
    def get_folder_expected_result():
        dir_expected_result = join(join(dirname(dirname(__file__)), 'data_test'), 'expected_result')
        return dir_expected_result

    @staticmethod
    def get_data_test_json():
        path_config = join(join(dirname(dirname(__file__)), 'data_test'), 'data_test.json')
        with open(path_config, 'r') as f:
            return json.load(f)


import requests

url = "http://localhost:8888/api/rules/abc123"
data = {"threshold": 0.9, "enabled": True}

response = requests.post(url, json=data)
print(response.json())