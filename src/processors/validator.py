"""Validator - Compare AI results with expected results from Google Sheet"""
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


class ExpectedResultBuilder:
    """Build expected detection results from sheet data"""

    def __init__(self, fps: int = 60):
        self.fps = fps

    def time_to_seconds(self, time_str: str) -> float:
        """Convert MM:SS to seconds"""
        if not time_str:
            return 0.0
        parts = time_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])

    def calculate_frame_id(self, event_time: str, event_start_time: str) -> int:
        """
        Calculate frame ID based on time from event start

        Args:
            event_time: Time point in format "MM:SS"
            event_start_time: Event start time in format "MM:SS"

        Returns:
            Frame ID (starting from 1)
        """
        event_seconds = self.time_to_seconds(event_time)
        start_seconds = self.time_to_seconds(event_start_time)
        elapsed = event_seconds - start_seconds
        return int(elapsed * self.fps) + 1

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
        Build expected frame data with detected areas

        Args:
            expected_result: List of detection events with eventStart, eventEnd, area
            event_start_time: Overall event start time "MM:SS"
            event_end_time: Overall event end time "MM:SS"
            rule_code: Rule code for this detection

        Returns:
            List of frame data: [{"frameId": int, "detectedAreas": [...]}, ...]
        """
        if not expected_result:
            return []

        frames = []

        for detection in expected_result:
            event_start = detection.get('eventStart', '')
            event_end = detection.get('eventEnd', '')
            area = detection.get('area', [])

            if not event_start or not event_end or not area:
                continue

            # Calculate frame IDs for start, middle, end
            start_frame = self.calculate_frame_id(event_start, event_start_time)
            end_frame = self.calculate_frame_id(event_end, event_start_time)

            # Calculate middle frame
            middle_frame = (start_frame + end_frame) // 2

            # Create bounding box
            bbox = self.area_to_bounding_box(area)

            # Generate 3 frames: start, middle, end
            for frame_id in [start_frame, middle_frame, end_frame]:
                frames.append({
                    "frameId": frame_id,
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
                "expected_frames": List[Dict],
                "should_validate": bool
            }
        """
        video_name = row.get('Video Name', '')
        test_case_id = row.get('TC', '')
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
            "expected_status": expected_status,
            "expected_frames": expected_frames,
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

        return inter_area / union_area

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
            expected_data: From build_from_sheet_row()
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
                "expected_status": expected_status,
                "total_frames": 0,
                "matched_frames": 0,
                "accuracy": None,
                "detect_result": "FAILED" if has_detection else "PASSED",
                "validation_note": "No detection expected" if not has_detection else "Unexpected detection found",
                "frame_results": []
            }

        # Case 2: Expected Status = "Approve"
        # Create frame lookup
        actual_frames_map = {f['frameId']: f for f in actual_results}

        total_frames = len(expected_frames)
        matched_frames = 0
        frame_results = []

        for exp_frame in expected_frames:
            frame_id = exp_frame['frameId']
            act_frame = actual_frames_map.get(frame_id, {'frameId': frame_id, 'detectedAreas': []})

            matched, details = self.match_frame(exp_frame, act_frame)
            if matched:
                matched_frames += 1

            frame_results.append({
                "frameId": frame_id,
                "matched": matched,
                "details": details
            })

        # Calculate accuracy
        accuracy = (matched_frames / total_frames * 100) if total_frames > 0 else 0.0

        # Determine detect_result based on >50% match
        detect_result = "PASSED" if accuracy > 50.0 else "FAILED"

        return {
            "video_name": video_name,
            "test_case_id": expected_data['test_case_id'],
            "expected_status": expected_status,
            "total_frames": total_frames,
            "matched_frames": matched_frames,
            "accuracy": round(accuracy, 2),
            "detect_result": detect_result,
            "validation_note": f"{matched_frames}/{total_frames} frames matched",
            "frame_results": frame_results
        }


if __name__ == "__main__":
    # Example usage
    builder = ExpectedResultBuilder(fps=60)

    # Example sheet row
    sheet_row = {
        'TC': '1',
        'Video Name': '305948.mp4',
        'Camera Name': '89_KV TOOLBOX',
        'EventStartTime': '02:22',
        'EventEndTime': '02:25',
        'Expected Status': 'Approve',
        'ExpectedResult': [
            {'eventStart': '02:22', 'eventEnd': '02:23', 'area': [156, 503, 331, 786]},
            {'eventStart': '02:24', 'eventEnd': '02:25', 'area': [364, 478, 562, 771]},
            {'eventStart': '02:24', 'eventEnd': '02:25', 'area': [475, 459, 609, 724]}
        ]
    }

    # Build expected result
    expected = builder.build_from_sheet_row(sheet_row, "PAR02")

    print(f"Video: {expected['video_name']}")
    print(f"Test Case: {expected['test_case_id']}")
    print(f"Expected Frames: {len(expected['expected_frames'])}")
    print("\nFrame Details:")
    for frame in expected['expected_frames']:
        print(f"  Frame {frame['frameId']}: {len(frame['detectedAreas'])} detections")