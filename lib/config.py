from os.path import join, dirname
import json


class Config:
    API_STAGING = "http://localhost:8888"

    URL_UPDATE_RULE_CODE = "/api/rules/"   # /api/rules/{ruleCode}
    URL_POST_VIDEO = "/api/videos"
    URL_ANALYZE_VIDEO = "/api/videos/analyze"

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