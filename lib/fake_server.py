from fastapi import FastAPI, Body, UploadFile, File
import json

from lib.config import Config

app = FastAPI()
cf = Config()
@app.get("/")
def read_root():
    return {"message": "Hello FastAPI!"}


@app.post("/api/rules/{rule_code}")
def update_rule_code(rule_code: str, config: dict = Body(...)):
    return {"message": f"Update {rule_code} success"}


@app.post("/api/videos")
def upload_video(video: UploadFile = File(...)):
    return {"message": f"Upload {video} success"}


@app.post("/api/videos/analyze")
def read_root(input: dict = Body(...)):
    with open("/home/viet/Desktop/project_local/Auto-ModelAI-Demo/data_test/video/test_01.mp4", "r") as f:
        res = json.load(f)
    return res
