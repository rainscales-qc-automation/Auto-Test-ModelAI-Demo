from pathlib import Path
import json
import pandas as pd
from IPython.display import display
from config.settings import cf


class TestResultConverterCSV:
    def __init__(self, json_path: str, session_name: str):
        self.input_path = Path(json_path)
        self.input_file_name = self.input_path.stem
        self.output_path = self.input_path.parent
        self.data = None
        self.detail = None
        self.org = ""
        self.rule = ""
        self.rule_code = ""
        self.videos_cfg = {}
        self.vid_to_cam = {}

    def load_json(self):
        """Đọc file JSON đầu vào."""
        with self.input_path.open("r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.detail = next(iter(self.data["details"].values()))
        self.org = self.detail.get("tenant", "")
        self.rule = self.detail.get("rule_name", "")
        self.rule_code = self.detail.get("rule_code", "")
        self.videos_cfg = self.detail.get("videos_config", {})

        # Tạo map video_id -> camera
        for cam, vids in self.videos_cfg.items():
            for v in vids:
                self.vid_to_cam[str(v)] = cam

    @staticmethod
    def to_ms(x):
        """Chuyển giây epoch sang millisecond."""
        if x is None:
            return ""
        try:
            x = float(x)
            return int(x * 1000) if x < 1e12 else int(x)
        except Exception:
            return ""

    def build_dataframe(self):
        """Chuyển dữ liệu JSON sang DataFrame."""
        start_ms = self.to_ms(self.detail["timing"].get("start_time"))
        end_ms = self.to_ms(self.detail["timing"].get("end_time"))

        rows = []
        for tc in self.detail.get("test_case_validation_result", []):
            video_name = tc.get("video_name", "")
            video_id = video_name.replace(".mp4", "")
            camera = self.vid_to_cam.get(video_id, "")
            status = (tc.get("detect_result") or "").lower()
            test_case_id = tc.get("test_case_id", "")
            expected = tc.get("expected_status", "")
            message = tc.get("validation_note", "") or ""
            story = tc.get("test_case_description") or "Use phone"

            test_id = f"LFO-{self.rule_code}-{str(test_case_id).zfill(4)}"
            name = f"{self.org} | {self.rule} | {story} | {camera}"
            description = f"Auto case for {self.org}/{self.rule}/{story} on {camera}"
            steps = "Open;Check;Assert"
            attachments = f"videos/{video_name}" if video_name else ""

            rows.append({
                "TestCaseID": test_id,
                "Name": name,
                "Status": status,
                "Organization": self.org,
                "Rule": self.rule,
                "Camera": camera,
                "Story": story,
                "Description": description,
                "Steps": steps,
                "AttachmentLinks": attachments,
                "ExpectedResults": expected,
                "Message": message,
                "Trace": "",
                "Start": start_ms,
                "Stop": end_ms
            })

        df = pd.DataFrame(rows, columns=[
            "TestCaseID", "Name", "Status", "Organization", "Rule", "Camera", "Story",
            "Description", "Steps", "AttachmentLinks", "ExpectedResults",
            "Message", "Trace", "Start", "Stop"
        ])
        return df

    def convert(self, preview=True):
        """Chạy toàn bộ pipeline: đọc JSON → build DataFrame → lưu CSV."""
        self.load_json()
        df = self.build_dataframe()
        df.to_csv(f'{self.output_path}/{self.input_file_name}.csv', index=False)
        # if preview:
        #     display("Template CSV Preview", df)
        return str(f'{self.output_path}/{self.input_file_name}.csv')


if __name__ == "__main__":
    converter = TestResultConverterCSV(
        "test_results_20251105_141319.json"
    )
    output_file = converter.convert()
    print("Saved CSV:", output_file)