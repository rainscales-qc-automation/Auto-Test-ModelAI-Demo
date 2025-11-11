"""Evidence Video Processor - Extract and annotate frames from test videos"""
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import cv2

logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """Store video information"""
    fps: float
    total_frames: int
    width: int
    height: int
    duration_seconds: float

    def __str__(self):
        return (f"VideoInfo(fps={self.fps:.2f}, frames={self.total_frames}, "
                f"size={self.width}x{self.height}, duration={self.duration_seconds:.2f}s)")


@dataclass
class BoundingBox:
    """Bounding box information"""
    x: int
    y: int
    width: int
    height: int
    confidence: Optional[float] = None
    rule_code: Optional[str] = None
    label: Optional[str] = None

    def to_coords(self) -> Tuple[int, int, int, int]:
        """Convert to (x1, y1, x2, y2) coordinates"""
        return (self.x, self.y, self.x + self.width, self.y + self.height)


class VideoProcessor:
    """Process video: extract frames, draw bounding boxes, analyze metadata"""

    def __init__(self, video_bytes: bytes):
        """
        Initialize with video bytes
        Args:
            video_bytes: Raw video file bytes
        """
        self.video_bytes = video_bytes
        self._tempfile = None
        self._cap = None
        self._video_info = None

    def __enter__(self):
        """Context manager entry"""
        self._open_video()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def _open_video(self):
        """Open video from bytes"""
        if self._cap is not None:
            return

        self._tempfile = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        self._tempfile.write(self.video_bytes)
        self._tempfile.flush()

        self._cap = cv2.VideoCapture(self._tempfile.name)
        if not self._cap.isOpened():
            raise ValueError("Failed to open video")

        logger.debug(f"Video opened: {self._tempfile.name}")

    def close(self):
        """Release resources"""
        if self._cap is not None:
            self._cap.release()
            self._cap = None

        if self._tempfile is not None:
            try:
                Path(self._tempfile.name).unlink()
            except:
                pass
            self._tempfile = None

    def get_video_info(self) -> VideoInfo:
        """Get video metadata"""
        if self._video_info is not None:
            return self._video_info

        if self._cap is None:
            self._open_video()

        fps = self._cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        self._video_info = VideoInfo(
            fps=fps,
            total_frames=total_frames,
            width=width,
            height=height,
            duration_seconds=duration
        )

        logger.debug(f"Video info: {self._video_info}")
        return self._video_info

    def timestamp_to_frame_id(self, timestamp_seconds: float) -> int:
        """Convert timestamp to frame ID"""
        info = self.get_video_info()
        frame_id = int(timestamp_seconds * info.fps)
        return min(frame_id, info.total_frames - 1)

    def extract_frame_at_timestamp(self, timestamp_seconds: float) -> Optional[cv2.Mat]:
        """Extract frame at specific timestamp"""
        if self._cap is None:
            self._open_video()

        frame_id = self.timestamp_to_frame_id(timestamp_seconds)
        return self.extract_frame_at_id(frame_id)

    def extract_frame_at_id(self, frame_id: int) -> Optional[cv2.Mat]:
        """Extract frame at specific frame ID"""
        if self._cap is None:
            self._open_video()

        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ret, frame = self._cap.read()

        if not ret:
            logger.warning(f"Failed to extract frame {frame_id}")
            return None

        return frame

    def draw_bounding_boxes(
        self,
        frame: cv2.Mat,
        boxes: List[BoundingBox],
        color: Tuple[int, int, int] = (0, 0, 255),
        thickness: int = 2,
        show_label: bool = True,
        label_bg_color: Tuple[int, int, int] = (0, 0, 255),
        label_text_color: Tuple[int, int, int] = (255, 255, 255)
    ) -> cv2.Mat:
        """Draw bounding boxes on frame"""
        annotated = frame.copy()

        for box in boxes:
            x1, y1, x2, y2 = box.to_coords()

            # Draw rectangle
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)

            # Draw label if requested
            if show_label and (box.label or box.rule_code):
                label = box.label or box.rule_code or ""
                if box.confidence is not None:
                    label += f" {box.confidence:.2f}"

                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                font_thickness = 2
                (text_width, text_height), baseline = cv2.getTextSize(
                    label, font, font_scale, font_thickness
                )

                label_y = max(y1 - text_height - 10, 0)
                cv2.rectangle(
                    annotated,
                    (x1, label_y),
                    (x1 + text_width + 10, label_y + text_height + 10),
                    label_bg_color,
                    -1
                )

                cv2.putText(
                    annotated,
                    label,
                    (x1 + 5, label_y + text_height + 5),
                    font,
                    font_scale,
                    label_text_color,
                    font_thickness
                )

        return annotated


class EvidenceVideoProcessor:
    """Process evidence videos: extract frames with bounding boxes"""

    def __init__(self, smb_connector, output_base_dir: str, frame_rate: float = 9.6):
        """
        Initialize processor
        Args:
            smb_connector: SMB connector instance
            output_base_dir: Base directory to save evidence images
            frame_rate: Frame rate conversion (default 24/2.5 = 9.6)
        """
        self.smb = smb_connector
        self.output_base_dir = Path(output_base_dir)
        self.frame_rate = frame_rate

    def _time_str_to_seconds(self, time_str: str) -> float:
        """Convert MM:SS to seconds"""
        if not time_str:
            return 0.0
        parts = time_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])

    def _download_video(self, smb_dir: str, video_name: str) -> bytes:
        """Download video from SMB"""
        videos = self.smb.get_video_by_list(smb_dir, [video_name])

        if not videos or videos[0][1] is None:
            raise FileNotFoundError(f"Failed to download video: {video_name}")

        return videos[0][1]

    def process_expected_results(
        self,
        expected_results: Dict[str, Dict],
        smb_dir: str,
        draw_kwargs: Dict = None
    ) -> Dict[str, Dict]:
        """
        Process expected results: download videos and extract annotated frames
        Args:
            expected_results: Dict from get_expected_results()
            smb_dir: SMB directory path to download videos
            draw_kwargs: Additional drawing parameters
        Returns:
            Updated expected_results with image_path in each expected_frames element
        """
        if draw_kwargs is None:
            draw_kwargs = {
                'color': (0, 255, 0),  # Green for expected
                'thickness': 3,
                'show_label': True
            }

        total_videos = len(expected_results)
        logger.info(f"Processing {total_videos} videos for evidence extraction")

        for idx, (video_name, expected_data) in enumerate(expected_results.items(), 1):
            try:
                logger.info(f"[{idx}/{total_videos}] Processing: {video_name}")

                # Get event_start_time
                event_start_time = expected_data.get('event_start_time', '')

                # Skip if no expected frames
                expected_frames = expected_data.get('expected_frames', [])
                if not expected_frames:
                    logger.info(f"No expected frames for {video_name}, skipping")
                    continue

                # Calculate actual timestamps for each frame
                event_start_seconds = self._time_str_to_seconds(event_start_time)

                # Create output directory
                output_dir = self.output_base_dir / video_name.replace('.mp4', '')
                output_dir.mkdir(parents=True, exist_ok=True)

                # Group frames by actual timestamp and check if images exist
                frames_to_process = []
                for frame_info in expected_frames:
                    frame_id = frame_info.get('frameId', 0)

                    # Calculate actual timestamp
                    offset_seconds = frame_id / self.frame_rate
                    actual_timestamp = event_start_seconds + offset_seconds

                    # Generate filename (simple format with frameId only)
                    filename = f"{video_name.replace('.mp4', '')}_frame_{frame_id:06d}.webp"
                    image_path = output_dir / filename

                    # Add image_path to frame_info
                    frame_info['image_path'] = str(image_path)

                    # Check if image already exists
                    if image_path.exists():
                        logger.debug(f"  Image exists: {filename}")
                        continue

                    # Add to processing list
                    frames_to_process.append({
                        'frame_id': frame_id,
                        'actual_timestamp': actual_timestamp,
                        'image_path': image_path,
                        'bounding_boxes': self._extract_bounding_boxes(frame_info)
                    })

                if not frames_to_process:
                    logger.info(f"  All images exist, skipping video processing")
                    continue

                logger.info(f"  Need to create {len(frames_to_process)} images")

                # Download video
                logger.info(f"  Downloading video from SMB...")
                video_bytes = self._download_video(smb_dir, video_name)
                logger.info(f"  Downloaded {len(video_bytes)} bytes")

                # Process video and create images
                created_count = self._process_video(
                    video_bytes,
                    frames_to_process,
                    draw_kwargs
                )

                logger.info(f"  Created {created_count} new images")

            except Exception as e:
                logger.error(f"  Failed to process {video_name}: {e}")

        # Return updated expected_results with image_path
        return expected_results

    def process_actual_results(
        self,
        validation_results: List[Dict],
        api_file_browser,
        output_base_dir: str = None,
        draw_kwargs: Dict = None
    ) -> List[Dict]:
        """
        Process actual/evidence results: download evidence videos and extract annotated frames
        Args:
            validation_results: List of validation results (each contains frame_results with actual data)
            api_file_browser: FileBrowserAPIClient instance
            output_base_dir: Override output base directory (optional, uses self.output_base_dir if None)
            draw_kwargs: Additional drawing parameters
        Returns:
            Updated validation_results with image_path in each actual element
        """
        if draw_kwargs is None:
            draw_kwargs = {
                'color': (255, 0, 0),  # Red for actual/evidence
                'thickness': 3,
                'show_label': True
            }

        output_dir = Path(output_base_dir) if output_base_dir else self.output_base_dir
        total_validations = len(validation_results)
        logger.info(f"Processing {total_validations} validation results for evidence images")

        for idx, validation in enumerate(validation_results, 1):
            try:
                video_name = validation.get('video_name', '')
                url_video_evidence = validation.get('url_video_evidence', '')
                frame_results = validation.get('frame_results', [])

                # Skip if no evidence video URL
                if not url_video_evidence:
                    logger.debug(f"[{idx}/{total_validations}] No evidence video for {video_name}, skipping")
                    continue

                # Skip if no frame results
                if not frame_results:
                    logger.debug(f"[{idx}/{total_validations}] No frame results for {video_name}, skipping")
                    continue

                logger.info(f"[{idx}/{total_validations}] Processing evidence for: {video_name}")

                # Create output directory for this video
                video_output_dir = output_dir / video_name.replace('.mp4', '')
                video_output_dir.mkdir(parents=True, exist_ok=True)

                # Collect frames that need processing
                frames_to_process = []
                for frame_result in frame_results:
                    details = frame_result.get('details', [])

                    for detail in details:
                        actual = detail.get('actual')
                        if not actual:
                            continue

                        frame_id = actual.get('frameID')
                        if frame_id is None:
                            continue

                        # Generate filename
                        filename = f"{video_name.replace('.mp4', '')}_evidence_frame_{frame_id:06d}.webp"
                        image_path = video_output_dir / filename

                        # Check if image already exists
                        if image_path.exists():
                            actual['image_path'] = str(image_path)
                            logger.debug(f"  Image exists: {filename}")
                            continue

                        # Extract bounding box
                        bbox_data = actual.get('boundingBox', {})
                        bbox = BoundingBox(
                            x=bbox_data.get('x', 0),
                            y=bbox_data.get('y', 0),
                            width=bbox_data.get('width', 0),
                            height=bbox_data.get('height', 0),
                            confidence=actual.get('confidence'),
                            rule_code=actual.get('ruleCode')
                        )

                        frames_to_process.append({
                            'frame_id': frame_id,
                            'image_path': image_path,
                            'bounding_boxes': [bbox],
                            'actual_ref': actual  # Keep reference to update image_path
                        })

                if not frames_to_process:
                    logger.info(f"  All evidence images exist for {video_name}, skipping")
                    continue

                logger.info(f"  Need to create {len(frames_to_process)} evidence images")

                # Download evidence video
                logger.info(f"  Downloading evidence video from: {url_video_evidence}")
                response = api_file_browser.get_raw_video_evidence_by_filepath(url_video_evidence)
                video_bytes = response.content
                logger.info(f"  Downloaded {len(video_bytes)} bytes")

                # Process video and create images
                created_count = self._process_evidence_video(
                    video_bytes,
                    frames_to_process,
                    draw_kwargs
                )

                logger.info(f"  Created {created_count} new evidence images for {video_name}")

            except Exception as e:
                logger.error(f"  Failed to process evidence for validation {idx}: {e}")
                import traceback
                logger.error(traceback.format_exc())

        return validation_results

    def _extract_bounding_boxes(self, frame_info: Dict) -> List[BoundingBox]:
        """Extract bounding boxes from frame info"""
        boxes = []
        detected_areas = frame_info.get('detectedAreas', [])

        for area in detected_areas:
            bbox_data = area.get('boundingBox', {})
            bbox = BoundingBox(
                x=bbox_data.get('x', 0),
                y=bbox_data.get('y', 0),
                width=bbox_data.get('width', 0),
                height=bbox_data.get('height', 0),
                rule_code=area.get('ruleCode'),
                confidence=None
            )
            boxes.append(bbox)

        return boxes

    def _process_video(
        self,
        video_bytes: bytes,
        frames_to_process: List[Dict],
        draw_kwargs: Dict
    ) -> int:
        """
        Process video and create images
        Args:
            video_bytes: Video content
            frames_to_process: List of {frame_id, actual_timestamp, image_path, bounding_boxes}
            draw_kwargs: Drawing parameters
        Returns:
            Number of images created
        """
        created_count = 0

        with VideoProcessor(video_bytes) as vp:
            # Get video info
            info = vp.get_video_info()
            logger.debug(f"  Video info: {info}")

            # Process each frame
            for frame_data in frames_to_process:
                actual_timestamp = frame_data['actual_timestamp']
                image_path = frame_data['image_path']
                bounding_boxes = frame_data['bounding_boxes']

                try:
                    # Extract frame at actual timestamp
                    frame = vp.extract_frame_at_timestamp(actual_timestamp)
                    if frame is None:
                        logger.warning(f"    Failed to extract frame at {actual_timestamp:.2f}s")
                        continue

                    # Draw bounding boxes
                    annotated = vp.draw_bounding_boxes(frame, bounding_boxes, **draw_kwargs)

                    # Save as WebP with quality 85 (good balance: size vs quality)
                    cv2.imwrite(
                        str(image_path),
                        annotated,
                        [cv2.IMWRITE_WEBP_QUALITY, 85]
                    )
                    created_count += 1
                    logger.debug(f"    Created: {image_path.name}")

                except Exception as e:
                    logger.error(f"    Failed to process frame at {actual_timestamp:.2f}s: {e}")

        return created_count

    def _process_evidence_video(
        self,
        video_bytes: bytes,
        frames_to_process: List[Dict],
        draw_kwargs: Dict
    ) -> int:
        """
        Process evidence video and create images
        Args:
            video_bytes: Video content
            frames_to_process: List of {frame_id, image_path, bounding_boxes, actual_ref}
            draw_kwargs: Drawing parameters
        Returns:
            Number of images created
        """
        created_count = 0

        with VideoProcessor(video_bytes) as vp:
            # Get video info
            info = vp.get_video_info()
            logger.debug(f"  Video info: {info}")

            # Process each frame
            for frame_data in frames_to_process:
                frame_id = frame_data['frame_id']
                image_path = frame_data['image_path']
                bounding_boxes = frame_data['bounding_boxes']
                actual_ref = frame_data['actual_ref']

                try:
                    # Extract frame by frame ID
                    frame = vp.extract_frame_at_id(frame_id)
                    if frame is None:
                        logger.warning(f"    Failed to extract frame {frame_id}")
                        continue

                    # Draw bounding boxes
                    annotated = vp.draw_bounding_boxes(frame, bounding_boxes, **draw_kwargs)

                    # Save as WebP with quality 85
                    cv2.imwrite(
                        str(image_path),
                        annotated,
                        [cv2.IMWRITE_WEBP_QUALITY, 85]
                    )

                    # Update actual reference with image path
                    actual_ref['image_path'] = str(image_path)

                    created_count += 1
                    logger.debug(f"    Created: {image_path.name}")

                except Exception as e:
                    logger.error(f"    Failed to process evidence frame {frame_id}: {e}")

        return created_count

    def process_single_video(
        self,
        video_name: str,
        expected_data: Dict,
        smb_dir: str,
        draw_kwargs: Dict = None
    ) -> Dict:
        """Process single video (convenience method)"""
        results = self.process_expected_results(
            {video_name: expected_data},
            smb_dir,
            draw_kwargs
        )
        return results[video_name]