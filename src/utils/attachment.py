import json
import tempfile
import cv2
import os

from config.settings import cf
from src.connectors.ai_api import FileBrowserAPIClient


class VideoVisualizer:
    def __init__(self, video_bytes: bytes, json_path: str, index_evidence: int = 0):
        self.video_bytes = video_bytes
        self.json_path = json_path
        self.tempfile = None
        self.cap = None
        self.frame_boxes = self._load_json(index_evidence)

    def _load_json(self, index_evidence):
        """Đọc toàn bộ thông tin bounding box theo frameId"""
        with open(self.json_path, "r") as f:
            data = json.load(f)

        frames_data = data.get("data", {})[index_evidence].get("payload", {}).get("frames", [])
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

    def play_and_save(self, output_path: str = None, scale: float = 1.0):
        """Phát video, vẽ bounding box, và lưu lại ra file"""
        self._write_temp_video()
        frame_index = 0

        # Lấy thông tin video gốc
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Áp dụng scale (nếu có)
        if scale != 1.0:
            width = int(width * scale)
            height = int(height * scale)

        # Tạo file output
        if not output_path:
            output_path = os.path.join(tempfile.gettempdir(), "output_annotated.mp4")

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        print(f"🎥 Đang ghi video ra: {output_path}")

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            # Vẽ box nếu có
            boxes = self.frame_boxes.get(frame_index, [])
            for b in boxes:
                x1, y1 = int(b["x"]), int(b["y"])
                x2, y2 = int(b["x"] + b["w"]), int(b["y"] + b["h"])

                # Khung đỏ, dày 4px
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 4)

                # Label to, nền đỏ
                label = f'{b["ruleCode"]} {b["confidence"]:.2f}'
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
                cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw, y1), (0, 0, 255), -1)
                cv2.putText(frame, label, (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # Giảm độ phân giải hiển thị/lưu (nếu có)
            if scale != 1.0:
                frame = cv2.resize(frame, (width, height))

            # Ghi ra file
            out.write(frame)

            # Hiển thị đồng thời
            cv2.imshow("Annotated Video", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            frame_index += 1

        self.cap.release()
        out.release()
        cv2.destroyAllWindows()
        print(f"✅ Video đã được lưu tại: {output_path}")


if __name__ == "__main__":
    api_file_browser = FileBrowserAPIClient(cf.API_FILE_BROWSER)
    response = api_file_browser.get_raw_video_evidence_by_filepath(
        "/evidence/PAR02/linfox_DCBN-192_168_10_14/50da4c30-95fb-4c87-9a11-78f86112c95e_llava_True/event_12_08-37-27_now_12_08-40-22.mp4"
    )
    video_bytes = response.content

    visualizer = VideoVisualizer(
        video_bytes,
        '/home/viet/Desktop/project_local/Auto-ModelAI-Demo/data_test/data_test.json',
        index_evidence=0
    )

    # Phát và lưu nửa độ phân giải
    visualizer.play_and_save(
        output_path="/home/viet/Desktop/project_local/Auto-ModelAI-Demo/data_test/video_test/output_annotated3.mp4",
        scale=0.8
    )



# if __name__=="__main__":
#     api_file_browser = FileBrowserAPIClient(cf.API_FILE_BROWSER)
#     response = api_file_browser.get_raw_video_evidence_by_filepath(
#         "/evidence/HM05/linfox_DCBD-192_168_253_15/2fda68f8-f639-4da2-95d0-7d829417cfee_llava_True/event_06_07-03-46_now_06_07-04-41.mp4"
#     )
#     video_bytes = response.content
#     visualizer = VideoVisualizer(video_bytes, '/home/viet/Desktop/project_local/Auto-ModelAI-Demo/data_test/data_test.json')
#     visualizer.play()
#
#     # response = api_file_browser.get_raw_video_evidence_by_filepath(
#     #     "/evidence/HM05/linfox_DCBD-192_168_253_15/591d389a-3fdc-480a-b670-de06eb0021ee_llava_True/event_12_04-42-51_now_12_04-44-33.mp4"
#     # )
#     # video_bytes = response.content
#     # visualizer = VideoVisualizer(video_bytes, '/home/viet/Desktop/project_local/Auto-ModelAI-Demo/data_test/data_test2.json')
#     # visualizer.play()


