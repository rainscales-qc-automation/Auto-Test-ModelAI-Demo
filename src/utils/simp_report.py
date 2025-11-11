import base64
import json
import mimetypes
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image


def image_to_base64(image_path: str) -> str:
    """Convert image file to base64 with 50% resized resolution"""
    if not image_path:
        return ""

    try:
        # Detect MIME type
        mime = mimetypes.guess_type(image_path)[0] or "image/png"

        # Open original image
        img = Image.open(image_path)

        # Resize to half width/height
        w, h = img.size
        img = img.resize((w // 3, h // 3))

        # Save resized to memory buffer
        buffer = BytesIO()
        img_format = img.format if img.format else "PNG"  # fallback
        img.save(buffer, format=img_format)

        # Encode buffer to base64
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return f"data:{mime};base64,{encoded}"

    except Exception as e:
        return ""


class SimpReportGenerator:
    def __init__(self, json_path: str, session_name: str):
        self.json_path = Path(json_path)
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
                    <td style="color:{'green' if case['detect_result'] == 'PASSED' else 'red'}">
                        {case['detect_result']}
                    </td>
                    <td>{case['validation_note']}</td>
                </tr>
                """

                # Frame-level details
                if case["frame_results"]:
                    html_sections += """
                    <tr><td colspan="7">
                        <details>
                            <summary><b>Frame Details</b></summary>
                            <table class="frame-detail-table">
                                <tr>
                                    <th>Frame ID</th>
                                    <th>Matched</th>
                                    <th>Expected Box</th>
                                    <th>Actual Box</th>
                                    <th>IOU</th>
                                    <th>Evidence Images</th>
                                </tr>
                    """

                    for frame in case["frame_results"]:
                        for d in frame["details"]:
                            exp = d["expected"]["boundingBox"]
                            exp_image = d["expected"].get("image_path", "")

                            act = d["actual"]["boundingBox"] if d["actual"] else None
                            act_image = d["actual"].get("image_path", "") if d["actual"] else ""

                            # Convert to base64
                            exp_b64 = image_to_base64(exp_image)
                            act_b64 = image_to_base64(act_image)

                            row_id_exp = f"exp-{frame['frameId']}-{hash(exp_image)}"
                            row_id_act = f"act-{frame['frameId']}-{hash(act_image)}"
                            row_id_cmp = f"cmp-{frame['frameId']}-{hash(exp_image + act_image)}"

                            image_buttons = ""
                            if exp_b64:
                                image_buttons += f'''
                                <button class="img-btn" onclick="toggleExclusive(
                                    ['{row_id_exp}', '{row_id_act}', '{row_id_cmp}'],
                                    '{row_id_exp}'
                                )">Expected</button>
                                '''
                            if act_b64:
                                image_buttons += f'''
                                <button class="img-btn" onclick="toggleExclusive(
                                    ['{row_id_exp}', '{row_id_act}', '{row_id_cmp}'],
                                    '{row_id_act}'
                                )">Actual</button>
                                '''
                            if exp_b64 and act_b64:
                                image_buttons += f'''
                                <button class="img-btn compare-btn" onclick="toggleExclusive(
                                    ['{row_id_exp}', '{row_id_act}', '{row_id_cmp}'],
                                    '{row_id_cmp}'
                                )">Compare</button>
                                '''

                            html_sections += f"""
                                <tr>
                                    <td>{frame['frameId']}</td>
                                    <td>{'✅' if frame['matched'] else '❌'}</td>
                                    <td>{exp}</td>
                                    <td>{act if act else '-'}</td>
                                    <td>{d['iou']}</td>
                                    <td>{image_buttons}</td>
                                </tr>
                            """

                            # Expected row
                            if exp_b64:
                                html_sections += f"""
                                <tr id="{row_id_exp}" style="display:none;">
                                    <td colspan="6">
                                        <div class="image-row-horizontal">
                                            <img src="{exp_b64}">
                                        </div>
                                    </td>
                                </tr>
                                """

                            # Actual row
                            if act_b64:
                                html_sections += f"""
                                <tr id="{row_id_act}" style="display:none;">
                                    <td colspan="6">
                                        <div class="image-row-horizontal">
                                            <img src="{act_b64}">
                                        </div>
                                    </td>
                                </tr>
                                """

                            # Compare row
                            if exp_b64 and act_b64:
                                html_sections += f"""
                                <tr id="{row_id_cmp}" style="display:none;">
                                    <td colspan="6">
                                        <div class="image-row-horizontal">
                                            <img src="{exp_b64}">
                                            <img src="{act_b64}">
                                        </div>
                                    </td>
                                </tr>
                                """

                    html_sections += "</table></details></td></tr>"

            html_sections += "</table><hr>"

        # Full HTML
        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <title>Detailed Test Report</title>
            <style>
                body {{
                    font-family: Arial;
                    margin: 20px;
                    background-color: #f5f5f5;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    background: white;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                }}
                details summary {{ 
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    cursor: pointer; 
                    color: #2196F3;
                    font-weight: bold;
                    padding: 12px;
                    background-color: #e3f2fd;
                    border-radius: 6px;
                    margin: 5px 0;
                    transition: all 0.3s;
                }}
                
                details summary:hover {{
                    background-color: #bbdefb;
                    transform: translateX(5px);
                }}
                
                details[open] summary {{
                    background-color: #2196F3;
                    color: white;
                }}
                    .image-row-horizontal {{
                    display: flex;
                    justify-content: center;
                    gap: 20px;
                }}
                .image-row-horizontal img {{
                    max-width: 45%;
                    border: 2px solid #ccc;
                    border-radius: 4px;
                }}
                .img-btn {{
                    padding: 6px 10px;
                    border: none;
                    background: #2196F3;
                    color: white;
                    border-radius: 4px;
                    margin: 2px;
                    cursor: pointer;
                }}
                .compare-btn {{
                    background: #FF9800;
                }}
            </style>

            <script>
                function toggleExclusive(ids, activeId) {{
                    ids.forEach(id => {{
                        let el = document.getElementById(id);
                        if (!el) return;
                        if (id === activeId) {{
                            el.style.display = (el.style.display === "none") ? "table-row" : "none";
                        }} else {{
                            el.style.display = "none";
                        }}
                    }});
                }}
            </script>
        </head>
        <body>
            <h1>📊 Detailed Test Report</h1>
            <p><i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i></p>
            {html_sections}
        </body>
        </html>
        """

        out_path = self.output_dir / f"{self.json_file_name}_detailed.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"✅ Detailed report generated: {out_path}")
        return out_path

    def generate_all(self):
        return self.generate_detailed_html()



if __name__ == "__main__":
    report = SimpReportGenerator("test_results_20251111_104724.json", "test_session")
    report.generate_all()
