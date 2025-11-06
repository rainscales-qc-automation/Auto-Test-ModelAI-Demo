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
    API_LOCAL = "http://localhost:8888"
    API_STAGING = "https://fake-agent.reg-stg.rainscales.xyz"
    API_KEY = os.environ.get("API_KEY", None)

    TIME_OUT_API = 60
    TIME_SLEEP = int(os.environ.get("TIME_SLEEP", 15))

    URL_GET_RULE_CODE = "/api/rules/"   # /api/rules/{ruleCode}
    URL_UPDATE_RULE_CODE = "/api/rule/"
    URL_POST_VIDEO = "/api/videos"
    URL_CHECK_MISSING_VIDEO = "/api/videos/check"
    URL_ANALYZE_VIDEO = "/api/videos/analyze"

    SERVICE_ACCOUNT_FILE = join(join(dirname(dirname(__file__)), 'config'), 'service-google-sheet.json')
    SHEET_ID = os.environ.get("SHEET_ID")
    SMB_SERVER = os.environ.get("SMB_SERVER")
    SMB_USER = os.environ.get("SMB_USER")
    SMB_PASSWORD = os.environ.get("SMB_PASSWORD")

    SMB_ROOT = "qc_ai_testing"

    RULES_CONFIG = load_config(join(dirname(__file__), 'rules.yaml'))
    DIR_RESULTS = join(join(dirname(dirname(__file__)), 'src'), 'results')

    DEBUG = False


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
if __name__ == '__main__':
    print(cf.RULES_CONFIG)
    print(cf.DIR_RESULTS)
    print(cf.SERVICE_ACCOUNT_FILE)



