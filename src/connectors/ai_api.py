import logging
from typing import List, Dict, Optional, Tuple

import requests

from config.settings import cf

logger = logging.getLogger(__name__)


class AIAPIClient:

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: int = 20, debug = False):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or cf.API_KEY
        self.timeout = timeout or cf.TIMEOUT
        self.session = requests.Session()
        self.debug = debug
        self.hard_headers = {"X-API-Key": self.api_key} if self.api_key else {}

    def _headers(self) -> Dict[str, str]:
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def update_rule(self, rule_code: str, config: Dict) -> Dict:
        """Update rule"""
        if self.debug:
            return {}
        url = f"{self.base_url}{cf.URL_UPDATE_RULE_CODE}"
        data_update = {"rule_code": rule_code, "config": config}
        response = self.session.post(url, json=data_update, headers=self.hard_headers, timeout=self.timeout)
        response.raise_for_status()
        logger.info(f"API update rule: {rule_code}" )
        return response.json()

    def upload_videos(self, videos: List[Tuple[str, bytes]]) -> Dict:
        """Upload videos: [(filename, video_data), ...]"""
        if self.debug:
            return {}
        url = f"{self.base_url}{cf.URL_POST_VIDEO}"
        files = [('videos', (name, data, 'video/mp4')) for name, data in videos]
        response = self.session.post(url, files=files, headers=self.hard_headers, timeout=self.timeout)
        response.raise_for_status()
        logger.info(f"Uploaded {len(videos)} videos")
        return response.json()

    def check_missing_videos(self, filenames: List[str]) -> List[str]:
        """Check videos not yet upload"""
        url = f"{self.base_url}{cf.URL_CHECK_MISSING_VIDEO}"
        response = self.session.post(url, json={"videos": filenames}, headers=self.hard_headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json().get("missing_videos", [])

    def analyze_videos(self, batch_code: str, videos_config: Dict[str, List[str]]) -> int:
        """Analyze: batch_code + {cam_id: [video_codes]}"""
        if self.debug:
            return 200
        url = f"{self.base_url}{cf.URL_ANALYZE_VIDEO}"
        payload = {"batch_code": batch_code, "videos_config": videos_config}
        response = self.session.post(url, json=payload, headers=self.hard_headers, timeout=self.timeout)
        response.raise_for_status()
        logger.info(f"Started analysis: {batch_code}")
        return response.status_code

    def get_evidences(self, batch_code: Optional[str] = None, rule_code: Optional[str] = None,
                      page: int = 1, page_size: int = 20) -> Dict:
        """Get evidences with filter"""
        url = f"{self.base_url}/api/evidences"
        params = {"page": page, "page_size": page_size}
        if batch_code:
            params["batch_code"] = batch_code
        if rule_code:
            params["rule_code"] = rule_code

        response = self.session.get(url, params=params, headers=self.hard_headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_all_evidences(self, batch_code: str, rule_code: Optional[str] = None) -> List[Dict]:
        """Get all evidences (auto pagination)"""
        all_data = []
        page = 1
        while True:
            result = self.get_evidences(batch_code, rule_code, page, 100)
            data = result.get("data", [])
            all_data.extend(data)
            if len(all_data) >= result.get("total", 0):
                break
            page += 1
        logger.info(f"Got {len(all_data)} evidences")
        return all_data


class FileBrowserAPIClient:

    def __init__(self, base_url: str, user: str = cf.FILE_BROWSER_USER, password: str = cf.FILE_BROWSER_PASSWORD, timeout: int = 20, debug = False):
        self.user, self.password = user, password
        self.base_url = base_url.rstrip('/')
        self.api_login = '/api/login'
        self.api_raw_evidence = '/api/raw'
        self.timeout = timeout or cf.TIMEOUT
        self.session = requests.Session()
        self.debug = debug

    def get_cookies(self) -> Dict[str, str]:
        url = f"{self.base_url}{self.api_login}"
        payload = {"username": self.user, "password": self.password}
        response = self.session.post(url, json=payload, timeout=self.timeout)
        if response.status_code != 200:
            logger.warning(f"API File Browser login failed: {response.text}")
        cookies = response.text
        return {'Cookie': f'auth={cookies}'}

    def create_headers(self) -> Dict[str, str]:
        cookies = self.get_cookies()
        headers = cookies
        return headers

    def get_raw_video_evidence_by_code(self, rule_code: str, camera_code: str, event_code: str):
        pass

    def get_raw_video_evidence_by_filepath(self, file_path_raw: str):
        if file_path_raw.startswith("/evidence"):
            file_path_raw = file_path_raw[len("/evidence"):]
        header = self.create_headers()
        url_api = f"{self.base_url}{self.api_raw_evidence}{file_path_raw}"
        response = self.session.get(url_api, headers=header, timeout=self.timeout)
        if response.status_code != 200:
            logger.warning(f"API File Browser Get evidence video failed: {response.text}")
        return response

# Usage
if __name__ == "__main__":
    # api = AIAPIClient(cf.API_LOCAL)
    #
    # # Create rule
    # api.update_rule("USEPHONE", {"CAM_001": {"min_distance": 3.5}})
    #
    # # Check & upload
    # missing = api.check_missing_videos(["test.mp4"])
    # if missing:
    #     api.upload_videos([("test.mp4", b"data")])
    #
    # # Analyze
    # api.analyze_videos("batch_001", {"CAM_001": ["test"]})
    #
    # # Get results
    # evidences = api.get_all_evidences("batch_001", "USEPHONE")

    api_file_browser = FileBrowserAPIClient(cf.API_FILE_BROWSER)
    print(api_file_browser.get_cookies())
    print(api_file_browser.get_raw_video_evidence_by_filepath(
        "/evidence/PAR02/linfox_DCBD-192_168_253_22/deca944d-f6a0-433d-8a5a-7318b6f7490a_llava_True/event_07_02-07-19_now_07_02-08-13.mp4"
    ))