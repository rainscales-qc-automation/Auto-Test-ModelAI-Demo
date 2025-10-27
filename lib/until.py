import pandas as pd
import requests
from loguru import logger

from lib.config import Config

cf = Config()

# ===============================
# 1️⃣ Utility: Compute IoU between two bounding boxes
# ===============================
def calculate_iou(boxA, boxB):
    xA = max(boxA["x"], boxB["x"])
    yA = max(boxA["y"], boxB["y"])
    xB = min(boxA["x"] + boxA["width"], boxB["x"] + boxB["width"])
    yB = min(boxA["y"] + boxA["height"], boxB["y"] + boxB["height"])

    inter_area = max(0, xB - xA) * max(0, yB - yA)
    if inter_area == 0:
        return 0.0

    areaA = boxA["width"] * boxA["height"]
    areaB = boxB["width"] * boxB["height"]
    union_area = areaA + areaB - inter_area
    return inter_area / union_area


# ===============================
# 2️⃣ Send Video to AI API and receive JSON result
# ===============================
def call_api_update_rule_code(api_url: str, rule_code: str = "rule_code_01", config: dict = cf.get_data_test_json()) -> dict:
    api_url = api_url + cf.URL_UPDATE_RULE_CODE + rule_code
    try:
        response = requests.post(api_url, json=config, timeout=300)
        if response.status_code != 200:
            raise RuntimeError(f"API error {response.status_code}: {response.text}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API error {e}")
        return {}


def call_api_post_video_to_ai(api_url: str, video_path: str) -> dict:
    files = {"video": open(video_path, "rb")}
    api_url = api_url + cf.URL_POST_VIDEO
    try:
        response = requests.post(api_url, files=files, timeout=300)
        if response.status_code != 200:
            raise RuntimeError(f"API error {response.status_code}: {response.text}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API error {e}")
        return {}


def call_api_analyze(api_url: str, batch_data: dict = cf.get_data_test_json()) -> dict:
    api_url = api_url + cf.URL_ANALYZE_VIDEO
    try:
        response = requests.post(api_url, json=batch_data, timeout=300)
        if response.status_code != 200:
            raise RuntimeError(f"API error {response.status_code}: {response.text}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API error {e}")
        return {}


# ===============================
# 3️⃣ Compare AI output with ground truth data
# ===============================
def compare_ai_vs_ground_truth(ai_json: dict, gt_json: dict, iou_threshold: float = 0.5):
    records = []

    for ai_frame in ai_json.get("frames", []):
        frame_id = ai_frame["frameId"]
        gt_frame = next((x for x in gt_json["frames"] if x["frameId"] == frame_id), None)
        if not gt_frame:
            logger.warning(f"Frame {frame_id} not found in ground truth")
            continue

        for ai_area, gt_area in zip(ai_frame["detectedAreas"], gt_frame["detectedAreas"]):
            iou_val = calculate_iou(ai_area["boundingBox"], gt_area["boundingBox"])
            is_match = iou_val >= iou_threshold
            records.append({
                "frameId": frame_id,
                "ruleCode": ai_area.get("ruleCode"),
                "confidence": round(ai_area.get("confidence", 0), 3),
                "iou": round(iou_val, 3),
                "match": is_match
            })

    logger.info(f"Comparison finished: {len(records)} records processed")
    return records


# ===============================
# 4️⃣ Export results to Excel
# ===============================
def export_report_to_excel(records, output_path="ai_test_result.xlsx"):
    df = pd.DataFrame(records)
    df.to_excel(output_path, index=False)
    logger.success(f"Report exported: {output_path}")


call_api_update_rule_code('http://localhost:8888', )
call_api_post_video_to_ai('http://localhost:8888', "/home/viet/Desktop/project_local/Auto-ModelAI-Demo/data_test/video/test_01.mp4")
call_api_analyze('http://localhost:8888')

# import requests
#
# url = "http://localhost:8888/api/videos"
# file_path = "/home/viet/Desktop/project_local/Auto-ModelAI-Demo/data_test/video/test_01.mp4"  # đường dẫn tới file của bạn
#
# with open(file_path, "rb") as f:
#     files = {"video": f}
#     response = requests.post(url, files=files)
#
# print("Status:", response.status_code)
# print("Response:", response.json())
