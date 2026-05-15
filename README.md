# Traffic-Step

Containerized AI traffic counting service with FastAPI + Streamlit + Celery GPU workers.

## Run
```bash
docker compose -f infra/docker-compose.yml up -d --build
```

## Implemented now
- Workspace / Project / Video / CountingLine domain with persistent SQLAlchemy models.
- Workflow action audit log with actor and timestamp.
- Workspace dashboard rollups (projects/videos/minutes/storage).
- Counting-line CRUD (create, update, delete) with auto-recalculated counts/percentages.
- Trajectory ingestion endpoint and heatmap generation endpoint.
- Line auto-suggestions from trajectory distribution clusters (heuristic baseline).
- Excel export endpoint for line stats per video.
- Streamlit UI sections:
  - Workspace control
  - Project control
  - Counting lines control + suggest + heatmap + export link

## API
- `GET /health`
- `POST|GET /workspaces`
- `POST|GET /projects`
- `POST|GET /videos`
- `POST|GET /lines`, `PUT /lines/{line_id}`, `DELETE /lines/{line_id}`
- `POST /trajectories`
- `GET /heatmap/{video_id}`
- `GET /lines/suggest/{video_id}`
- `GET /export/video/{video_id}`
- `GET /dashboard/workspace/{workspace_id}`
- `GET /audit`

## GPU model selection
Worker uses env-driven YOLO map:
- `YOLO_MODELS={"fast":"yolov8n.pt","balanced":"yolov8m.pt","accurate":"yolov8x.pt"}`
- Default profile: `balanced`
