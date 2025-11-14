"""Test Orchestrator - Handles workflow orchestration"""
import logging
import time
import uuid
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class TestOrchestrator:
    """Orchestrates the test execution workflow"""

    def __init__(self, processor):
        self.processor = processor

    def execute_phase1_upload(self, rules: List) -> tuple:
        """
        Phase 1: Upload videos and trigger analysis

        Returns:
            (processed_rules, failed_rules)
        """
        logger.info("=" * 80)
        logger.info("PHASE 1: UPLOADING VIDEOS AND TRIGGERING ANALYSIS")
        logger.info("=" * 80)

        processed_rules = []
        failed_rules = []

        for rule in rules:
            try:
                processed = self.processor.upload_and_trigger_analysis(rule)
                processed_rules.append(processed)
                logger.info(f"✓ Triggered: {rule.tenant_name} - {rule.rule_name}")
            except Exception as e:
                logger.error(f"✗ Failed to process {rule.rule_name}: {e}")
                failed_rules.append({
                    "rule": f"{rule.tenant_name} - {rule.rule_name}",
                    "status": "error",
                    "message": str(e)
                })

        return processed_rules, failed_rules

    def wait_for_ai_processing(self, processed_rules: List, debug: bool):
        """Wait for AI to process all videos"""
        if not processed_rules or debug:
            return

        # Trigger dummy analysis to wake up system
        time.sleep(10)
        self.processor.api.analyze_videos(
            batch_code=self.processor.timestamp + '__' + str(uuid.uuid4()),
            videos_config={"linfox_DCBN-192_168_10_8": ["USEPHONE_VIP_1"]},
        )

        # Calculate and wait
        from config.settings import cf
        wait_time = cf.TIME_SLEEP * self.processor.total_video
        logger.info(f"{'=' * 80}")
        logger.info(
            f"Waiting {wait_time} ({cf.TIME_SLEEP} * {self.processor.total_video}) seconds for AI to process videos...")
        logger.info(f"{'=' * 80}")
        time.sleep(wait_time)

    def execute_phase2_validation(self, processed_rules: List, debug: bool, batch_debug) -> List[Dict]:
        """
        Phase 2: Fetch and validate results
        Returns:
            List of validation results
        """
        logger.info("=" * 80)
        logger.info("PHASE 2: FETCHING AND VALIDATING RESULTS")
        logger.info("=" * 80)

        results = []

        for processed in processed_rules:
            rule = processed.rule
            try:
                # Debug mode: override batch_code
                if debug:
                    # processed.batch_code = 'Linfox_Viet_Nam_LOADHIGH_20251113_105848'
                    # processed.batch_code = 'Linfox_Viet_Nam_USEPHONE_20251113_152617'
                    processed.batch_code = batch_debug

                result = self.processor.validate_results(processed)
                results.append({
                    "rule": f"{rule.tenant_name} - {rule.rule_name}",
                    **result
                })
                logger.info(f"✓ Validated: {rule.tenant_name} - {rule.rule_name}")
            except Exception as e:
                logger.error(f"✗ Failed to validate {rule.rule_name}: {e}")
                results.append({
                    "rule": f"{rule.tenant_name} - {rule.rule_name}",
                    "status": "error",
                    "message": str(e)
                })

        return results

    def print_final_summary(self, results: List[Dict]):
        """Print final test summary"""
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

    def generate_reports(self, timestamp: str) -> Dict[str, str]:
        """
        Generate all reports (JSON, HTML, CSV)

        Returns:
            Dict with paths to generated reports
        """
        logger.info("CREATE REPORT SIMPLE")

        filepath_output, dir_session_name = self.processor.result_writer.save_all(timestamp)

        # HTML Simple Report
        from src.utils.simp_report import SimpReportGenerator
        report_html_simp = SimpReportGenerator(filepath_output, dir_session_name)
        dir_report_html_simp = report_html_simp.generate_all()

        # CSV Report
        from src.utils.convert_json_to_csv import TestResultConverterCSV
        csv_report = TestResultConverterCSV(filepath_output, dir_session_name)
        dir_csv_report = csv_report.convert()

        # Log report paths
        logger.info(f"JSON Report: {filepath_output}")
        logger.info(f"HTML Simple Report: {dir_report_html_simp}")
        logger.info(f"CSV Report: {dir_csv_report}")

        return {
            "json": str(filepath_output),
            "html": str(dir_report_html_simp),
            "csv": str(dir_csv_report)
        }
