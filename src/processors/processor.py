"""Test Processor - Main workflow for AI model testing"""
import logging
import time
from datetime import datetime
import uuid
from dataclasses import dataclass
from typing import List, Dict, Tuple

from config.settings import cf
from src.connectors.ai_api import AIAPIClient
from src.connectors.google_sheet import GoogleSheetConnector
from src.connectors.smb_storage import SMBConnector
from src.processors.validator import ResultValidator, ExpectedResultBuilder
from src.utils.simp_report import SimpReportGenerator
from src.utils.convert_json_to_csv import TestResultConverterCSV
from src.utils.helpers import (
    ResultWriter, VideoConfigBuilder, BatchCodeGenerator,
    CameraMapper, ConfigParser, build_result_data, gen_timestamp, format_duration
)

logger = logging.getLogger(__name__)


@dataclass
class TestRule:
    """Rule need test"""
    tenant_name: str
    tenant_dir: str
    tenant_config_sheet: str
    rule_name: str
    rule_code: str
    sheet_name: str


@dataclass
class ProcessedRule:
    """Store processed rule info for validation"""
    rule: TestRule
    batch_code: str
    videos_metadata: List[Dict]
    videos_config: Dict
    missing_count: int
    video_names: List[str]
    start_time: datetime  # NEW: Track start time


class TestProcessor:
    """Process workflow test"""

    def __init__(self, api_url: str = cf.API_LOCAL, debug = cf.DEBUG, iou_threshold=0.5):
        self.gs = GoogleSheetConnector()
        self.smb = SMBConnector(cf.SMB_SERVER, cf.SMB_USER, cf.SMB_PASSWORD, cf.SMB_ROOT)
        self.api = AIAPIClient(base_url=api_url, debug=debug)
        self.camera_mapper = CameraMapper()
        self.result_writer = ResultWriter()
        self.timestamp = gen_timestamp()
        self.debug = debug
        self.iou_threshold = iou_threshold
        self.total_video = 0

    def get_enabled_rules(self) -> List[TestRule]:
        """Get list rules for test"""
        rules = []
        for tenant in cf.RULES_CONFIG['tenant']:
            if not tenant['enabled']:
                continue
            config_sheet = tenant.get('config rule', 'Rule_Config_Details')
            for rule in tenant['rules']:
                if not rule['enabled']:
                    continue
                rules.append(TestRule(
                    tenant_name=tenant['name'],
                    tenant_dir=tenant['dir'],
                    tenant_config_sheet=config_sheet,
                    rule_name=rule['name'],
                    rule_code=rule['code'],
                    sheet_name=rule['sheet']
                ))
        logger.info(f"Found {len(rules)} enabled rules")
        return rules

    def get_rule_config(self, rule: TestRule) -> Tuple[Dict, Dict]:
        """Get rule config from Google Sheet"""
        all_configs = self.gs.get_filled_blank_merged_cell(rule.tenant_config_sheet)
        return ConfigParser.parse(all_configs, rule.rule_code)

    def update_rule_config(self, rule: TestRule):
        """Update rule config via API"""
        config, camera_mapping = self.get_rule_config(rule)
        self.camera_mapper.update(camera_mapping)

        if not config:
            logger.warning(f"Skip config update for {rule.rule_code}")
            return

        logger.info(f"Updating rule: {rule.rule_code} {list(config.keys())}")
        self.api.update_rule(rule.rule_code, config)

    def get_videos_metadata(self, rule: TestRule) -> List[Dict]:
        """Get videos metadata from sheet"""
        videos_data = self.gs.get_videos_with_camera(rule.sheet_name)
        logger.info(f"Sheet '{rule.sheet_name}': {len(videos_data)} videos")
        return self.camera_mapper.add_codes_to_metadata(videos_data)

    def download_videos(self, rule: TestRule, video_names: List[str]) -> List[Tuple[str, bytes]]:
        """Download specific videos from SMB"""
        smb_dir = f"{rule.tenant_dir}/{rule.rule_name}"
        videos = self.smb.get_video_by_list(smb_dir, video_names)
        success = [(name, data) for name, data in videos if data is not None]

        failed = len(videos) - len(success)
        if failed > 0:
            logger.warning(f"Failed to download {failed}/{len(videos)} videos")

        return success

    def get_expected_results(self, rule: TestRule, video_names: List[str]) -> Dict[str, Dict]:
        """Get expected results from Google Sheet"""
        sheet_rows = self.gs.get_info_rows_by_video_names(rule.sheet_name, video_names)

        expected_builder = ExpectedResultBuilder(fps=24, compression_ratio=2.5)
        expected_results = {}

        for row in sheet_rows:
            video_name = row.get('Video Name', '')

            if video_name:
                expected = expected_builder.build_from_sheet_row(row, rule.rule_code)
                expected_results[video_name] = expected

        logger.info(f"Built expected results for {len(expected_results)} test cases")
        return expected_results

    def upload_and_trigger_analysis(self, rule: TestRule) -> ProcessedRule:
        """Phase 1: Upload videos and trigger AI analysis"""
        start_time = datetime.now()  # Track start time

        logger.info(f"{'=' * 60}")
        logger.info(f"[PHASE 1] Uploading: {rule.tenant_name} - {rule.rule_name}")
        logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'=' * 60}")

        # 1. Update rule config
        try:
            self.update_rule_config(rule)
        except Exception as e:
            logger.error(f"Config update failed: {e}")
            raise

        # 2. Get videos metadata
        videos_metadata = self.get_videos_metadata(rule)
        if not videos_metadata:
            logger.error("No videos found in sheet!")
            raise ValueError("No videos found")

        # 3. Check missing videos
        all_names = [v['video_name'] for v in videos_metadata]
        self.total_video += len(all_names)
        missing = self.api.check_missing_videos(all_names)
        logger.info(f"Missing: {len(missing)}/{len(all_names)} videos")

        # 4. Download and upload missing
        if missing:
            logger.info(f"Downloading {len(missing)} videos...")
            missing_videos = self.download_videos(rule, missing)
            if missing_videos:
                logger.info(f"Uploading {len(missing_videos)} videos...")
                self.api.upload_videos(missing_videos)
        else:
            logger.info("All videos already uploaded")

        # 5. Build videos config
        videos_config = VideoConfigBuilder.build(videos_metadata)
        logger.info(f"Videos config: {[(k, len(v)) for k, v in videos_config.items()]}")

        # 6. Generate batch code and trigger analysis
        batch_code = BatchCodeGenerator.generate(rule.tenant_name, rule.rule_name, self.timestamp)
        logger.info(f"Starting analysis: {batch_code}")

        self.api.analyze_videos(batch_code, videos_config)

        return ProcessedRule(
            rule=rule,
            batch_code=batch_code,
            videos_metadata=videos_metadata,
            videos_config=videos_config,
            missing_count=len(missing),
            video_names=all_names,
            start_time=start_time
        )

    def validate_results(self, processed: ProcessedRule) -> Dict:
        """Phase 2: Get AI results and validate"""
        rule = processed.rule
        batch_code = processed.batch_code
        start_time = processed.start_time

        logger.info(f"{'=' * 60}")
        logger.info(f"[PHASE 2] Validating: {rule.tenant_name} - {rule.rule_name}")
        logger.info(f"{'=' * 60}")

        # 1. Get expected results from sheet
        expected_results = self.get_expected_results(rule, processed.video_names)

        # 2. Get AI results from evidences API
        logger.info(f"Fetching evidences for batch: {batch_code}")
        evidences = self.api.get_all_evidences(batch_code, rule.rule_code)
        logger.info(f"Got {len(evidences)} evidences")

        # 3. Group evidences by video_code
        evidences_by_video = {}
        for evidence in evidences:
            video_code = evidence.get('video_code', '')
            frames = evidence.get('payload', {}).get('frames', [])
            if video_code:
                evidences_by_video[video_code] = frames

        # 4. Validate each video
        validator = ResultValidator(iou_threshold=self.iou_threshold)
        validation_results = []
        passed_count = 0
        failed_count = 0

        for video_name, expected in expected_results.items():
            video_code = video_name.replace('.mp4', '')
            actual_results = evidences_by_video.get(video_code, [])

            validation = validator.validate_video(expected, actual_results)
            validation_results.append(validation)

            detect_result = validation.get('detect_result', 'UNKNOWN')
            note = validation.get('validation_note', '')

            if detect_result == 'PASSED':
                passed_count += 1
                logger.info(f"  ✓ {video_name} (TC{validation['test_case_id']}): PASSED - {note}")
            else:
                failed_count += 1
                logger.info(f"  ✗ {video_name} (TC{validation['test_case_id']}): FAILED - {note}")

        # Calculate timing
        end_time = datetime.now()
        duration_seconds = (end_time - start_time).total_seconds()

        total_testcases = len(validation_results)
        pass_rate = (passed_count / total_testcases * 100) if total_testcases > 0 else 0.0

        logger.info(f"\nValidation Summary:")
        logger.info(f"  Total Test Cases: {total_testcases}")
        logger.info(f"  Passed: {passed_count}")
        logger.info(f"  Failed: {failed_count}")
        logger.info(f"  Pass Rate: {pass_rate:.2f}%")
        logger.info(f"  Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"  End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"  Duration: {format_duration(duration_seconds)}")

        # 5. Build result data with timing
        result_data = build_result_data(
            batch_code=batch_code,
            timestamp=self.timestamp,
            rule=rule,
            videos_metadata=processed.videos_metadata,
            missing_count=processed.missing_count,
            videos_config=processed.videos_config,
            validation_results=validation_results,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration_seconds
        )

        self.result_writer.add_result(batch_code, rule.rule_code, result_data)

        return {
            "status": "success",
            "batch_code": batch_code,
            "total_testcases": total_testcases,
            "uploaded": processed.missing_count,
            "cameras": list(processed.videos_config.keys()),
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": round(pass_rate, 2),
            "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
            "end_time": end_time.strftime('%Y-%m-%d %H:%M:%S'),
            "duration": format_duration(duration_seconds)
        }

    def run(self):
        """Run test all rules - 2 phases"""
        if not self.smb.connect():
            logger.error("Failed to connect SMB")
            return

        rules = self.get_enabled_rules()
        if not rules:
            logger.warning("No enabled rules found")
            return

        # ========== PHASE 1: Upload and Trigger Analysis ==========
        logger.info("=" * 80)
        logger.info("PHASE 1: UPLOADING VIDEOS AND TRIGGERING ANALYSIS")
        logger.info("=" * 80)

        processed_rules = []
        failed_rules = []

        for rule in rules:
            try:
                processed = self.upload_and_trigger_analysis(rule)
                processed_rules.append(processed)
                logger.info(f"✓ Triggered: {rule.tenant_name} - {rule.rule_name}")
            except Exception as e:
                logger.error(f"✗ Failed to process {rule.rule_name}: {e}")
                failed_rules.append({
                    "rule": f"{rule.tenant_name} - {rule.rule_name}",
                    "status": "error",
                    "message": str(e)
                })

        # ========== Wait for AI Processing ==========
        if processed_rules and not self.debug:
            time.sleep(10)
            self.api.analyze_videos(
                batch_code=self.timestamp + '__' + str(uuid.uuid4()),
                videos_config={"linfox_DCBN-192_168_10_8": ["USEPHONE_VIP_1"]},
            )
            wait_time = cf.TIME_SLEEP * self.total_video
            logger.info(f"{'=' * 80}")
            logger.info(f"Waiting {wait_time} ({cf.TIME_SLEEP} * {self.total_video}) seconds for AI to process videos...")
            logger.info(f"{'=' * 80}")
            time.sleep(wait_time)

        # ========== PHASE 2: Validate Results ==========
        logger.info("=" * 80)
        logger.info("PHASE 2: FETCHING AND VALIDATING RESULTS")
        logger.info("=" * 80)

        results = []
        for processed in processed_rules:
            rule = processed.rule
            try:
                if self.debug:
                    processed.batch_code = 'Linfox_Viet_Nam_USEPHONE_20251105_112714'
                result = self.validate_results(processed)
                results.append({"rule": f"{rule.tenant_name} - {rule.rule_name}", **result})
                logger.info(f"✓ Validated: {rule.tenant_name} - {rule.rule_name}")
            except Exception as e:
                logger.error(f"✗ Failed to validate {rule.rule_name}: {e}")
                results.append({
                    "rule": f"{rule.tenant_name} - {rule.rule_name}",
                    "status": "error",
                    "message": str(e)
                })

        # Add failed rules from phase 1
        results.extend(failed_rules)

        # ========== Summary ==========
        logger.info(f"{'=' * 80}")
        logger.info("FINAL SUMMARY")
        logger.info(f"{'=' * 80}")
        for r in results:
            status = r['status']
            rule_name = r['rule']
            if status == 'success':
                logger.info(f"✓ {rule_name}: TEST SUCCESS")
                logger.info(f"  - Test Cases: {r.get('total_testcases', 0)}")
                logger.info(f"  - Passed: {r.get('passed', 0)}")
                logger.info(f"  - Failed: {r.get('failed', 0)}")
                logger.info(f"  - Pass Rate: {r.get('pass_rate', 0)}%")
                logger.info(f"  - Duration: {r.get('duration', 'N/A')}")
            else:
                logger.info(f"✗ {rule_name}: FAILED - {r.get('message', 'Unknown error')}")

        logger.info("CREATE REPORT SIMPLE")
        filepath_output, dir_session_name = self.result_writer.save_all(self.timestamp)
        report_htmp_simp = SimpReportGenerator(filepath_output, dir_session_name)
        dir_report_htmp_simp = report_htmp_simp.generate_all()
        csv_report = TestResultConverterCSV(filepath_output, dir_session_name)
        dir_csv_report = csv_report.convert()
        logger.info(f"JSON Report: {filepath_output}")
        logger.info(f"HTML Simple Report: {dir_report_htmp_simp}")
        logger.info(f"CSV Report: {dir_csv_report}")
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    processor = TestProcessor(api_url=cf.API_STAGING, debug=True, iou_threshold=0.3)
    processor.run()
