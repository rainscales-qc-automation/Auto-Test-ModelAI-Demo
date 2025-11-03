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

        filepath = self.results_dir / f"test_results_{session_name}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.all_results, f, indent=2, ensure_ascii=False)
        logger.info(f"All results saved: {filepath}")

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        for rule_key, status in self.all_results['summary'].items():
            logger.info(f"{rule_key}: {status.upper()}")


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
                logger.warning(f"Camera code not found for: {v['camera_name']}")
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
        validation_results: List[Dict] = None
) -> Dict:
    """Build result data structure with enhanced format"""

    # Calculate statistics from validation results
    total_testcases = len(validation_results) if validation_results else 0
    passed_count = sum(1 for v in validation_results if v.get('detect_result') == 'PASSED')
    failed_count = sum(1 for v in validation_results if v.get('detect_result') == 'FAILED')

    return {
        "batch_code": batch_code,
        "timestamp": timestamp,
        "tenant": rule.tenant_name,
        "rule_name": rule.rule_name,
        "rule_code": rule.rule_code,
        "total_testcases": total_testcases,
        "uploaded_videos": missing_count,
        "videos_config": videos_config,
        "test_statistics": {
            "total": total_testcases,
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": round((passed_count / total_testcases * 100), 2) if total_testcases > 0 else 0.0
        },
        "test_case_validation_result": validation_results or [],
        "status": "success"
    }