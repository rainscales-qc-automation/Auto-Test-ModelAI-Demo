"""Validator - Compare AI results with expected results from Google Sheet"""
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class ExpectedResultBuilder:
    """Build expected detection results from sheet data"""

    def __init__(self, fps: int = 24, compression_ratio: float = 2.5):
        """
        Args:
            fps: Original video FPS (24)
            compression_ratio: Video compression ratio (2.5x faster)
        """
        self.fps = fps
        self.compression_ratio = compression_ratio
        # Frame conversion rate: original_fps / compression_ratio
        self.frame_rate = fps / compression_ratio  # 24 / 2.5 = 9.6

    def time_to_seconds(self, time_str: str) -> float:
        """Convert MM:SS to seconds"""
        if not time_str:
            return 0.0
        parts = time_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])

    def calculate_relative_frame_offset(self, event_time: str, event_start_time: str) -> int:
        """
        Calculate relative frame offset from event start
        Args:
            event_time: Time point in format "MM:SS"
            event_start_time: Event start time in format "MM:SS"
        Returns:
            Relative frame offset (will be added to first_detection_frame later)
        """
        event_seconds = self.time_to_seconds(event_time)
        start_seconds = self.time_to_seconds(event_start_time)
        # start_seconds = self.time_to_seconds(event_time)
        elapsed = event_seconds - start_seconds

        # Formula: elapsed_time * 24 / 2.5 = elapsed_time * 9.6
        relative_offset = int(elapsed * self.frame_rate)
        return relative_offset

    def area_to_bounding_box(self, area: List[int]) -> Dict:
        """
        Convert area [x1, y1, x2, y2] to bounding box format
        Args:
            area: [x1, y1, x2, y2]
        Returns:
            {"x": x1, "y": y1, "width": w, "height": h}
        """
        x1, y1, x2, y2 = area
        return {
            "x": x1,
            "y": y1,
            "width": x2 - x1,
            "height": y2 - y1
        }

    def build_expected_frames(
        self,
        expected_result: List[Dict],
        event_start_time: str,
        event_end_time: str,
        rule_code: str
    ) -> List[Dict]:
        """
        Build expected frame data with detected areas (RELATIVE frame offsets)

        Args:
            expected_result: List of detection events with eventStart, eventEnd, area
            event_start_time: Overall event start time "MM:SS"
            event_end_time: Overall event end time "MM:SS"
            rule_code: Rule code for this detection

        Returns:
            List of frame data with RELATIVE frameId: [{"frameId": int, "detectedAreas": [...]}, ...]
            Note: frameId here is relative offset, will be added to first_detection_frame later
        """
        if not expected_result:
            return []

        frames = []

        for index, detection in enumerate(expected_result):
            event_start = detection.get('eventStart', '')
            event_end = detection.get('eventEnd', '')
            area = detection.get('area', [])

            if not event_start or not event_end or not area:
                continue

            # Calculate relative frame offsets for start, middle, end
            start_offset = self.calculate_relative_frame_offset(event_start, event_start_time)
            end_offset = self.calculate_relative_frame_offset(event_end, event_start_time)

            # Calculate offset from detection start to end (for middle calculation)
            start_offset_frame = self.calculate_relative_frame_offset(event_start, event_start)
            end_offset_frame = self.calculate_relative_frame_offset(event_end, event_start)

            # Calculate middle offset
            middle_offset_frame = (start_offset_frame + end_offset_frame) // 2
            middle_offset = (start_offset + end_offset) // 2

            # Create bounding box
            bbox = self.area_to_bounding_box(area)

            # Generate 3 frames: start, middle, end (with relative offsets)
            offset_pairs = [
                (start_offset, start_offset_frame),
                (middle_offset, middle_offset_frame),
                (end_offset, end_offset_frame)
            ]

            for offset, offset_frame in offset_pairs:
                frames.append({
                    "frameId": offset,  # offset theo thời gian từ event_start_time
                    "offset_frame": offset_frame,  # offset theo frame từ detection start
                    "expect_id": index,  # index of detection event
                    "detectedAreas": [{
                        "ruleCode": rule_code,
                        "boundingBox": bbox
                    }]
                })

        # Sort by frameId
        frames.sort(key=lambda x: x['frameId'])

        return frames

    def build_from_sheet_row(self, row: Dict, rule_code: str) -> Dict:
        """
        Build expected result for one test case row

        Args:
            row: Sheet row with keys: TC, Video Name, Expected Status, ExpectedResult, etc.
            rule_code: Rule code being tested

        Returns:
            {
                "video_name": str,
                "test_case_id": str,
                "expected_status": str,
                "expected_frames": List[Dict],  # with RELATIVE frameIds
                "should_validate": bool
            }
        """
        video_name = row.get('Video Name', '')
        test_case_id = row.get('TC', '')
        test_case_description = row.get('Test Case Description', '')
        expected_status = row.get('Expected Status', '').strip()
        expected_result = row.get('ExpectedResult', [])
        event_start_time = row.get('EventStartTime', '')
        event_end_time = row.get('EventEndTime', '')

        # Always build expected frames for structure
        expected_frames = []
        if expected_result and isinstance(expected_result, list):
            expected_frames = self.build_expected_frames(
                expected_result,
                event_start_time,
                event_end_time,
                rule_code
            )

        return {
            "video_name": video_name,
            "test_case_id": test_case_id,
            "test_case_description": test_case_description,
            "expected_status": expected_status,
            "expected_frames": expected_frames,  # RELATIVE frameIds
            "should_validate": True
        }


class ResultValidator:
    """Validate AI results against expected results"""

    def __init__(self, iou_threshold: float = 0.5):
        self.iou_threshold = iou_threshold

    def calculate_iou(self, box1: Dict, box2: Dict) -> float:
        """
        Calculate Intersection over Union (IoU) between two bounding boxes
        Args:
            box1, box2: {"x": int, "y": int, "width": int, "height": int}
        Returns:
            IoU value (0.0 to 1.0)
        """
        x1_min = box1['x']
        y1_min = box1['y']
        x1_max = box1['x'] + box1['width']
        y1_max = box1['y'] + box1['height']

        x2_min = box2['x']
        y2_min = box2['y']
        x2_max = box2['x'] + box2['width']
        y2_max = box2['y'] + box2['height']

        # Calculate intersection
        x_inter_min = max(x1_min, x2_min)
        y_inter_min = max(y1_min, y2_min)
        x_inter_max = min(x1_max, x2_max)
        y_inter_max = min(y1_max, y2_max)

        if x_inter_max < x_inter_min or y_inter_max < y_inter_min:
            return 0.0

        inter_area = (x_inter_max - x_inter_min) * (y_inter_max - y_inter_min)

        # Calculate union
        box1_area = box1['width'] * box1['height']
        box2_area = box2['width'] * box2['height']
        union_area = box1_area + box2_area - inter_area

        if union_area == 0:
            return 0.0

        return round(inter_area / union_area, 2)

    def find_first_detection_frame_with_iou(
        self,
        frames: List[Dict],
        expected_first_frame: Dict
    ) -> int:
        """
        Find the first frame with detection that matches expected frame by IoU
        Args:
            frames: List of frames from AI results
            expected_first_frame: First expected frame to match against
        Returns:
            frameId of first matching frame, or 0 if none found
        """
        expected_areas = expected_first_frame.get('detectedAreas', [])
        if not expected_areas:
            logger.warning("No expected areas in first frame")
            return 0

        for frame in frames:
            detected_areas = frame.get('detectedAreas', [])
            if not detected_areas or len(detected_areas) == 0:
                continue

            # Check if this frame matches the expected first frame
            for exp_area in expected_areas:
                exp_box = exp_area.get('boundingBox', {})
                exp_rule = exp_area.get('ruleCode', '')

                for act_area in detected_areas:
                    act_box = act_area.get('boundingBox', {})
                    act_rule = act_area.get('ruleCode', '')

                    if exp_rule != act_rule:
                        continue

                    iou = self.calculate_iou(exp_box, act_box)
                    if iou >= self.iou_threshold:
                        first_frame_id = frame.get('frameId', 0)
                        logger.info(f"First matching detection found at frameId: {first_frame_id} (IoU: {iou:.2f})")
                        return first_frame_id

        logger.warning("No matching detection found for expected first frame")
        return 0

    def match_frame(
        self,
        expected_frame: Dict,
        actual_frame: Dict
    ) -> Tuple[bool, List[Dict]]:
        """
        Match expected frame with actual AI result frame
        Returns:
            (matched: bool, match_details: List[Dict])
        """
        expected_areas = expected_frame.get('detectedAreas', [])
        actual_areas = actual_frame.get('detectedAreas', [])

        if not expected_areas:
            return len(actual_areas) == 0, []

        match_details = []
        matched_count = 0

        for exp_area in expected_areas:
            exp_box = exp_area.get('boundingBox', {})
            exp_rule = exp_area.get('ruleCode', '')

            best_match = None
            best_iou = 0.0

            for act_area in actual_areas:
                act_box = act_area.get('boundingBox', {})
                act_rule = act_area.get('ruleCode', '')

                # Rule code must match
                if exp_rule != act_rule:
                    continue

                iou = self.calculate_iou(exp_box, act_box)
                if iou > best_iou:
                    best_iou = iou
                    best_match = act_area

            matched = best_iou >= self.iou_threshold
            if matched:
                matched_count += 1

            match_details.append({
                "expected": exp_area,
                "actual": best_match,
                "iou": best_iou,
                "matched": matched
            })

        all_matched = matched_count == len(expected_areas)
        return all_matched, match_details

    def validate_video(
        self,
        expected_data: Dict,
        actual_results: List[Dict]
    ) -> Dict:
        """
        Validate one video's results
        Args:
            expected_data: From build_from_sheet_row() with RELATIVE frameIds
            actual_results: AI detection results (list of frames)
        Returns:
            Validation report with enhanced structure
        """
        video_name = expected_data['video_name']
        expected_status = expected_data['expected_status']
        expected_frames = expected_data['expected_frames']

        # Case 1: Expected Status = "Reject"
        if expected_status.lower() == 'reject':
            has_detection = len(actual_results) > 0

            return {
                "video_name": video_name,
                "test_case_id": expected_data['test_case_id'],
                "test_case_description": expected_data.get('test_case_description', ''),
                "expected_status": expected_status,
                "total_frames": 0,
                "matched_frames": 0,
                "accuracy": None,
                "detect_result": "FAILED" if has_detection else "PASSED",
                "validation_note": "" if not has_detection else "Model detects violation when uploading a NO violation video",
                "frame_results": []
            }

        # Case 2: Expected Status = "Approve"

        # Check if actual_results is empty
        if not actual_results or len(actual_results) == 0:
            return {
                "video_name": video_name,
                "test_case_id": expected_data['test_case_id'],
                "test_case_description": expected_data.get('test_case_description', ''),
                "expected_status": expected_status,
                "total_frames": len(expected_frames),
                "matched_frames": 0,
                "accuracy": 0.0,
                "detect_result": "FAILED",
                "validation_note": "Model detects NO violation when uploading a violation video",
                "frame_results": []
            }

        # NEW LOGIC: Group expected frames by expect_id
        grouped_frames = {}
        for frame in expected_frames:
            expect_id = frame.get('expect_id', 0)
            if expect_id not in grouped_frames:
                grouped_frames[expect_id] = []
            grouped_frames[expect_id].append(frame)

        logger.info(f"Grouped into {len(grouped_frames)} detection events")

        # Create frame lookup from actual results
        actual_frames_map = {f['frameId']: f for f in actual_results}

        # Validate each group separately
        all_frame_results = []
        total_matched = 0

        for expect_id in sorted(grouped_frames.keys()):
            group_frames = grouped_frames[expect_id]
            logger.info(f"Validating expect_id={expect_id} with {len(group_frames)} frames")

            # Get first frame in this group
            first_expected_frame = group_frames[0]

            # Find first detection frame for this group with IoU matching
            first_detection_frame = self.find_first_detection_frame_with_iou(
                actual_results,
                first_expected_frame
            )

            if first_detection_frame == 0:
                logger.warning(f"No matching first frame found for expect_id={expect_id}")
                # Still validate but all will likely fail

            # Validate all frames in this group
            for exp_frame in group_frames:
                offset_frame = exp_frame.get('offset_frame', 0)
                absolute_frame_id = first_detection_frame + offset_frame

                # Get actual frame at this position
                act_frame = actual_frames_map.get(
                    absolute_frame_id,
                    {'frameId': absolute_frame_id, 'detectedAreas': []}
                )

                # Create expected frame for matching
                expected_for_match = {
                    'frameId': absolute_frame_id,
                    'detectedAreas': exp_frame['detectedAreas']
                }

                matched, details = self.match_frame(expected_for_match, act_frame)
                if matched:
                    total_matched += 1

                all_frame_results.append({
                    "frameId": absolute_frame_id,
                    "expect_id": expect_id,
                    "offset_frame": offset_frame,
                    "matched": matched,
                    "details": details
                })

        # Calculate overall statistics
        total_frames = len(expected_frames)
        accuracy = (total_matched / total_frames * 100) if total_frames > 0 else 0.0
        detect_result = "PASSED" if accuracy > 50.0 else "FAILED"

        return {
            "video_name": video_name,
            "test_case_id": expected_data['test_case_id'],
            "test_case_description": expected_data.get('test_case_description', ''),
            "expected_status": expected_status,
            "total_frames": total_frames,
            "matched_frames": total_matched,
            "accuracy": round(accuracy, 2),
            "detect_result": detect_result,
            "validation_note": f"Model detects violation but wrong bounding box ({total_matched}/{total_frames} frames matched)",
            "frame_results": all_frame_results
        }


if __name__ == "__main__":
    # Example usage
    builder = ExpectedResultBuilder(fps=24, compression_ratio=2.5)

    # Example sheet row
    sheet_row = {
        'TC': '1',
        'Video Name': '305948.mp4',
        'Test Case Description': 'Test phone usage',
        'Camera Name': '89_KV TOOLBOX',
        'EventStartTime': '02:22',
        'EventEndTime': '02:25',
        'Expected Status': 'Approve',
        'ExpectedResult': [
            {'eventStart': '02:22', 'eventEnd': '02:23', 'area': [156, 503, 331, 786]},
            {'eventStart': '02:24', 'eventEnd': '02:25', 'area': [364, 478, 562, 771]},
        ]
    }

    # Build expected result
    expected = builder.build_from_sheet_row(sheet_row, "PAR02")

    print(f"Video: {expected['video_name']}")
    print(f"Test Case: {expected['test_case_id']}")
    print(f"Expected Frames (RELATIVE): {len(expected['expected_frames'])}")
    print("\nFrame Details (RELATIVE offsets):")
    for frame in expected['expected_frames']:
        print(f"  expect_id={frame['expect_id']}, frameId={frame['frameId']}, offset_frame={frame['offset_frame']}")