import json
import tempfile

import cv2

from config.settings import cf
from src.connectors.ai_api import FileBrowserAPIClient


class VideoVisualizer:
    def __init__(self, video_bytes: bytes, json_path: str, index_evidence: int = 0):
        self.video_bytes = video_bytes
        self.json_path = json_path
        self.tempfile = None
        self.cap = None
        self.frame_boxes = self._load_json()
        self.index_evidence = index_evidence

    def _load_json(self):
        """Đọc toàn bộ thông tin bounding box theo frameId"""
        with open(self.json_path, "r") as f:
            data = json.load(f)

        frames_data = data.get("data", {})[self.index_evidence].get("payload", {}).get("frames", [])
        mapping = {}
        for fitem in frames_data:
            frame_id = fitem.get("frameId")
            boxes = []
            for det in fitem.get("detectedAreas", []):
                bbox = det.get("boundingBox")
                if bbox:
                    boxes.append({
                        "x": bbox["x"],
                        "y": bbox["y"],
                        "w": bbox["width"],
                        "h": bbox["height"],
                        "confidence": det.get("confidence", 0),
                        "ruleCode": det.get("ruleCode", "")
                    })
            mapping[frame_id] = boxes
        return mapping

    def _write_temp_video(self):
        self.tempfile = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        self.tempfile.write(self.video_bytes)
        self.tempfile.flush()
        self.cap = cv2.VideoCapture(self.tempfile.name)
        if not self.cap.isOpened():
            raise ValueError("Không mở được video")

    def play(self):
        """Phát video và vẽ bounding box theo frame"""
        self._write_temp_video()
        frame_index = 0
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            # Vẽ box nếu có
            boxes = self.frame_boxes.get(frame_index, [])
            for b in boxes:
                x1, y1 = int(b["x"]), int(b["y"])
                x2, y2 = int(b["x"] + b["w"]), int(b["y"] + b["h"])

                # Vẽ khung đỏ, dày hơn (5px)
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)

                # # Vẽ label chữ to hơn, nền đỏ nhạt
                label = f'{b["ruleCode"]} {b["confidence"]:.2f}'
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
                cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw, y1), (0, 0, 255), -1)
                cv2.putText(frame, label, (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            cv2.imshow("Video with Bounding Boxes", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            frame_index += 1

        self.cap.release()
        cv2.destroyAllWindows()


if __name__=="__main__":
    api_file_browser = FileBrowserAPIClient(cf.API_FILE_BROWSER)
    response = api_file_browser.get_raw_video_evidence_by_filepath(
        "/evidence/PAR02/linfox_DCBN-192_168_10_14/366ecb03-78cd-4e10-9050-29c6c2078333_llava_True/event_11_06-31-42_now_11_06-33-06.mp4"
    )
    video_bytes = response.content
    # cv2.destroyAllWindows()
    visualizer = VideoVisualizer(video_bytes, '/home/viet/Desktop/project_local/Auto-ModelAI-Demo/data_test/data_test.json')
    visualizer.play()


