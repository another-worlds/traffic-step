import json
import os
from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
app = Celery("traffic_step", broker=redis_url, backend=redis_url)


def model_map():
    raw = os.getenv("YOLO_MODELS", '{"balanced":"yolov8m.pt"}')
    return json.loads(raw)


@app.task
def process_video(video_id: str, profile: str = "balanced"):
    models = model_map()
    model_name = models.get(profile, models.get("balanced", "yolov8m.pt"))

    result = {
        "video_id": video_id,
        "profile": profile,
        "model": model_name,
        "status": "processing",
    }

    try:
        from ultralytics import YOLO  # lazy import

        _ = YOLO(model_name)
        result["status"] = "ready_for_inference"
    except Exception as exc:  # model pull/runtime issues returned as payload
        result["status"] = "model_load_failed"
        result["error"] = str(exc)

    return result
