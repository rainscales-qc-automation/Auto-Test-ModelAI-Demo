import json
import os
import yaml
from os.path import join, dirname

from dotenv import load_dotenv

load_dotenv(join(dirname(dirname(__file__)), '.env'))

def load_config(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)


class Config:
    API_STAGING = "http://localhost:8888"

    URL_UPDATE_RULE_CODE = "/api/rules/"   # /api/rules/{ruleCode}
    URL_POST_VIDEO = "/api/videos"
    URL_ANALYZE_VIDEO = "/api/videos/analyze"

    SERVICE_ACCOUNT_FILE = (dirname(dirname(__file__)), 'service-google-sheet.json')
    SMB_SERVER = os.environ.get("SMB_SERVER")
    SMB_USER = os.environ.get("SMB_USER")
    SMB_PASSWORD = os.environ.get("SMB_PASSWORD")

    SMB_ROOT = "qc_ai_testing"

    RULES_CONFIG = load_config(join(dirname(__file__), 'rules.yaml'))


    @staticmethod
    def get_folder_video():
        dir_video = join(join(dirname(dirname(__file__)), 'data_test'), 'video')
        return dir_video

    @staticmethod
    def get_data_test_json():
        path_config = join(join(dirname(dirname(__file__)), 'data_test'), 'data_test.json')
        with open(path_config, 'r') as f:
            return json.load(f)


cf = Config()
print(cf.SMB_SERVER)

