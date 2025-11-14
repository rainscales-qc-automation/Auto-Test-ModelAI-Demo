"""Processor Utils - Helper functions for TestProcessor"""
import json
import logging
from typing import Dict, List, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def gen_timestamp() -> str:
    """Generate timestamp string"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to readable string
    Args:
        seconds: Duration in seconds
    Returns:
        Formatted string like "2h 15m 30s" or "45m 20s" or "25s"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:  # Always show seconds if nothing else
        parts.append(f"{secs}s")

    return " ".join(parts)


def to_bbox_xywh(coords):
    """
    Chuyển mảng [x1, y1, x2, y2] sang [x, y, w, h]
    x, y: góc trên bên trái
    w, h: chiều rộng và chiều cao
    """
    if len(coords) != 4:
        raise ValueError("Mảng phải gồm đúng 4 phần tử: [x1, y1, x2, y2]")

    x_min, y_min, x_max, y_max = coords
    width = x_max - x_min
    height = y_max - y_min
    return [x_min, y_min, width, height]


class ResultWriter:
    """Handle writing results to files"""

    def __init__(self, results_dir: str = "results"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
        self.all_results = {
            "summary": {},
            "details": {}
        }

    def add_result(self, batch_code: str, rule_key: str, data: Dict):
        """Add result for a rule"""
        # Add to summary
        status = data.get('status', 'unknown')
        self.all_results['summary'][rule_key] = status

        # Add to details
        self.all_results['details'][batch_code] = data

    def save_all(self, session_name: str = None):
        """Save all results to single JSON file"""
        if not session_name:
            session_name = datetime.now().strftime("%Y%m%d_%H%M%S")

        filepath = self.results_dir / session_name / f"test_results_{session_name}.json"
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.all_results, f, indent=2, ensure_ascii=False)
        logger.info(f"All results saved: {filepath}")

        # Print summary
        logger.info("=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        for rule_key, status in self.all_results['summary'].items():
            logger.info(f"{rule_key}: {status.upper()}")
        return filepath, session_name


class VideoConfigBuilder:
    """Build videos_config grouped by camera_code"""

    @staticmethod
    def build(videos_metadata: List[Dict]) -> Dict[str, List[str]]:
        """
        Group videos by camera_code

        Args:
            videos_metadata: [{'video_name': '...', 'camera_code': '...'}, ...]

        Returns:
            {'camera_code': ['video_001', 'video_002'], ...}
        """
        config = {}
        for v in videos_metadata:
            video_code = v['video_name'].replace('.mp4', '')
            camera_code = v['camera_code']
            if camera_code not in config:
                config[camera_code] = []
            config[camera_code].append(video_code)
        return config


class BatchCodeGenerator:
    """Generate batch codes with timestamp"""

    @staticmethod
    def generate(tenant_name: str, rule_name: str, timestamp: str) -> str:
        """
        Generate batch code
        Returns:
            batch_code
        """
        batch_code = f"{tenant_name}_{rule_name}_{timestamp}".replace(" ", "_")
        return batch_code


class CameraMapper:
    """Handle camera name to code mapping"""

    def __init__(self):
        self.mapping = {}

    def update(self, camera_mapping: Dict[str, str]):
        """Update mapping cache"""
        self.mapping.update(camera_mapping)

    def get_code(self, camera_name: str) -> str:
        """Get camera code by name"""
        return self.mapping.get(camera_name)

    def add_codes_to_metadata(self, videos_data: List[Dict]) -> List[Dict]:
        """
        Add camera_code to videos metadata
        Args:
            videos_data: [{'video_name': '...', 'camera_name': '...'}, ...]
        Returns:
            [{'video_name': '...', 'camera_name': '...', 'camera_code': '...'}, ...]
        """
        result = []
        for v in videos_data:
            camera_code = self.get_code(v['camera_name'])
            if not camera_code:
                logger.warning(f"Camera code is not configured for rule: {v['camera_name']}")
                continue
            result.append({
                'video_name': v['video_name'],
                'camera_name': v['camera_name'],
                'camera_code': camera_code
            })
        return result


class ConfigParser:
    """Parse rule config from Google Sheet data"""

    @staticmethod
    def parse(all_configs: List[Dict], rule_code: str) -> Tuple[Dict, Dict]:
        """
        Parse config for specific rule
        Returns:
            (config_dict, camera_mapping)
        """
        rule_configs = [cfg for cfg in all_configs if cfg.get('rule_code') == rule_code]

        if not rule_configs:
            logger.warning(f"No config found for rule {rule_code}")
            return {}, {}

        config = {}
        camera_mapping = {}

        for cfg in rule_configs:
            camera_code = cfg.get('camera_code')
            camera_name = cfg.get('camera_name')
            json_str = cfg.get('Json', '{}')

            # Build camera mapping
            if camera_name and camera_code:
                camera_mapping[camera_name] = camera_code

            # Parse JSON config
            json_str = json_str.replace("'", '"')
            camera_config = json.loads(json_str)
            config[camera_code] = camera_config

        logger.info(f"Loaded config for {len(config)} cameras")
        return config, camera_mapping


def build_result_data(
        batch_code: str,
        timestamp: str,
        rule,
        videos_metadata: List[Dict],
        missing_count: int,
        videos_config: Dict,
        rule_config: Dict,
        validation_results: List[Dict] = None,
        start_time: datetime = None,
        end_time: datetime = None,
        duration_seconds: float = None
) -> Dict:
    """Build result data structure with enhanced format and timing"""
    # Calculate statistics from validation results
    total_testcases = len(validation_results) if validation_results else 0
    passed_count = sum(1 for v in validation_results if v.get('detect_result') == 'PASSED')
    failed_count = sum(1 for v in validation_results if v.get('detect_result') == 'FAILED')

    # Build timing info
    timing_info = {}
    if start_time:
        timing_info['start_time'] = int(start_time.timestamp())
    if end_time:
        timing_info['end_time'] = int(end_time.timestamp())
    if duration_seconds is not None:
        timing_info['duration_seconds'] = round(duration_seconds, 2)
        timing_info['duration_formatted'] = format_duration(duration_seconds)

    return {
        "batch_code": batch_code,
        "timestamp": timestamp,
        "tenant": rule.tenant_name,
        "rule_name": rule.rule_name,
        "rule_code": rule.rule_code,
        "total_testcases": total_testcases,
        "uploaded_videos": missing_count,
        "videos_config": videos_config,
        "rule_config": rule_config,
        "test_statistics": {
            "total": total_testcases,
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": round((passed_count / total_testcases * 100), 2) if total_testcases > 0 else 0.0
        },
        "timing": timing_info,
        "test_case_validation_result": validation_results or [],
        "status": "success"
    }


def merge_video_url_into_expected(expected_results, evidences_by_video):
    """
    expected_results: dict dạng {'317213.mp4': {...}, ...}
    evidences_by_video: dict dạng {'317213': {'frames': [...], 'url_video_evidence': 'xxx.mp4'}, ...}
    """
    for video_key, info in expected_results.items():
        key_without_ext = video_key.replace('.mp4', '')

        if key_without_ext in evidences_by_video:
            url_video = evidences_by_video[key_without_ext]
            if url_video:
                info['url_video_evidence'] = url_video


def get_first_frame_id_reject_video(actual_results: List[Dict]):
    valid = [item for item in actual_results if item["detectedAreas"]]

    if len(valid) >= 2:
        i1 = len(valid) // 3
        i2 = (len(valid) * 2) // 3
        result = [valid[i1], valid[i2]]
    else:
        result = valid  # nếu ít hơn 2 phần tử

    return result
