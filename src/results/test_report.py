import json
from pathlib import Path
from datetime import datetime

class TestReportGenerator:
    def __init__(self, json_path: str):
        self.json_path = Path(json_path)
        with open(self.json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.output_dir = self.json_path.parent

    def generate_summary_html(self):
        details = self.data["details"]
        html_rows = ""
        for batch_name, info in details.items():
            stats = info["test_statistics"]
            html_rows += f"""
            <tr>
                <td>{batch_name}</td>
                <td>{info['tenant']}</td>
                <td>{info['rule_code']}</td>
                <td>{info['rule_name']}</td>
                <td>{stats['total']}</td>
                <td>{stats['passed']}</td>
                <td>{stats['failed']}</td>
                <td>{stats['pass_rate']}%</td>
                <td>{info['status']}</td>
            </tr>
            """

        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Test Summary Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ccc; padding: 8px; text-align: center; }}
                th {{ background-color: #f2f2f2; }}
                h1 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>Test Summary Report</h1>
            <table>
                <tr>
                    <th>Batch</th>
                    <th>Tenant</th>
                    <th>Rule Code</th>
                    <th>Rule Name</th>
                    <th>Total</th>
                    <th>Passed</th>
                    <th>Failed</th>
                    <th>Pass Rate</th>
                    <th>Status</th>
                </tr>
                {html_rows}
            </table>
        </body>
        </html>
        """
        out_path = self.output_dir / "summary.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"✅ Summary report generated: {out_path}")

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
                    <th>Accuracy</th>
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
                    <td>{case['accuracy'] if case['accuracy'] is not None else '-'}</td>
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
        out_path = self.output_dir / "detailed.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"✅ Detailed report generated: {out_path}")

    def generate_all(self):
        self.generate_summary_html()
        self.generate_detailed_html()


if __name__ == "__main__":
    report = TestReportGenerator("test_results_20251031_155241.json")
    report.generate_all()
