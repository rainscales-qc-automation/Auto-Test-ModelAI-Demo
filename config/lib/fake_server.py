import json

from fastapi import FastAPI, Body, UploadFile, File, Header, HTTPException, Depends

from config.lib.config import cf

app = FastAPI()

# Define a reusable dependency for API key checking
def verify_api_key(x_api_key: str = Header(...)):
    """Verify X-API-Key header"""
    if not x_api_key:
        raise HTTPException(status_code=400, detail="Missing X-API-Key header")
    # Optionally check value if you have one in config or env
    expected_key = cf.API_KEY if hasattr(cf, "API_KEY") else None
    if expected_key and x_api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid X-API-Key")
    return x_api_key


@app.get("/", dependencies=[Depends(verify_api_key)])
def read_root():
    return {"message": "Hello FastAPI!"}


@app.post("/api/rules/{rule_code}", dependencies=[Depends(verify_api_key)])
def update_rule_code(rule_code: str, config: dict = Body(...)):
    return {"message": f"Update {rule_code} success"}


@app.post("/api/videos", dependencies=[Depends(verify_api_key)])
def upload_videos(videos: list[UploadFile] = File(...)):
    result = []
    for file in videos:
        result.append(file.filename)
    return {"message": f"Upload {result} success"}


@app.post("/api/videos/check", dependencies=[Depends(verify_api_key)])
def upload_video(videos: dict = Body(...)):
    return {"message": f"Check {videos} success", "missing_videos": videos['videos']}

@app.post("/api/videos/analyze", dependencies=[Depends(verify_api_key)])
def analyze_video(input: dict = Body(...)):
    with open("/home/viet/Desktop/project_local/Auto-ModelAI-Demo/data_test/video/test_01.mp4", "r") as f:
        res = json.load(f)
    return res
