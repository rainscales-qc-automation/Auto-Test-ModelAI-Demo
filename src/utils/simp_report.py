import json
from pathlib import Path
from datetime import datetime
from config.settings import cf


class SimpReportGenerator:
    def __init__(self, json_path: str, session_name: str):
        self.json_path = Path(f'{cf.DIR_RESULTS}/{session_name}/{json_path}')
        self.json_file_name = self.json_path.stem
        with open(self.json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.output_dir = self.json_path.parent


    def generate_detailed_html(self):
        details = self.data["details"]
        html_sections = ""

        for batch_name, info in details.items():
            stats = info["test_statistics"]
            html_sections += f"""
            <h2>{batch_name} — {info['tenant']} ({info['rule_code']})</h2>
            <p><b>Total:</b> {stats['total']} | 
               <b>Passed:</b> {stats['passed']} | 
               <b>Failed:</b> {stats['failed']} | 
               <b>Pass rate:</b> {stats['pass_rate']}%</p>
            <table>
                <tr>
                    <th>Video</th>
                    <th>Expected</th>
                    <th>Matched Frames</th>
                    <th>Total Frames</th>
                    <th>Result</th>
                    <th>Note</th>
                </tr>
            """

            for case in info["test_case_validation_result"]:
                html_sections += f"""
                <tr>
                    <td>{case['video_name']}</td>
                    <td>{case['expected_status']}</td>
                    <td>{case['matched_frames']}</td>
                    <td>{case['total_frames']}</td>
                    <td style="color:{'green' if case['detect_result']=='PASSED' else 'red'}">
                        {case['detect_result']}
                    </td>
                    <td>{case['validation_note']}</td>
                </tr>
                """

                # Chi tiết từng frame
                if case["frame_results"]:
                    html_sections += """
                    <tr><td colspan="7">
                        <details>
                            <summary><b>Frame Details</b></summary>
                            <table>
                                <tr>
                                    <th>Frame ID</th>
                                    <th>Matched</th>
                                    <th>Expected Box</th>
                                    <th>Actual Box</th>
                                    <th>IOU</th>
                                </tr>
                    """
                    for frame in case["frame_results"]:
                        for d in frame["details"]:
                            exp = d["expected"]["boundingBox"]
                            act = d["actual"]["boundingBox"] if d["actual"] else None
                            html_sections += f"""
                                <tr>
                                    <td>{frame['frameId']}</td>
                                    <td>{'✅' if frame['matched'] else '❌'}</td>
                                    <td>{exp}</td>
                                    <td>{act if act else '-'}</td>
                                    <td>{d['iou']}</td>
                                </tr>
                            """
                    html_sections += "</table></details></td></tr>"

            html_sections += "</table><hr>"

        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Detailed Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ccc; padding: 6px; text-align: center; }}
                th {{ background-color: #eee; }}
                details summary {{ cursor: pointer; color: blue; }}
            </style>
        </head>
        <body>
            <h1>Detailed Test Report</h1>
            {html_sections}
        </body>
        </html>
        """
        out_path = self.output_dir / f"{self.json_file_name}detailed.html"
        # out_path = f'{self.output_dir}/{self.json_file_name}detailed.html'
        out_path.write_text(html, encoding="utf-8")
        print(f"✅ Detailed report generated: {out_path}")

    def generate_all(self):
        self.generate_detailed_html()


if __name__ == "__main__":
    report = SimpReportGenerator("test_results_20251105_085048.json")
    report.generate_all()
