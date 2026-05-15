from __future__ import annotations

import io
import os
from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./traffic_step.db")
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


class VideoStatus(str, Enum):
    uploaded = "uploaded"
    queued = "queued"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    owner: Mapped[str] = mapped_column(String(100), default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    projects: Mapped[list[Project]] = relationship(back_populates="workspace", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"))
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    workspace: Mapped[Workspace] = relationship(back_populates="projects")
    videos: Mapped[list[Video]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Video(Base):
    __tablename__ = "videos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(512))
    size_mb: Mapped[float] = mapped_column(Float, default=0)
    duration_min: Mapped[float] = mapped_column(Float, default=0)
    resolution: Mapped[str] = mapped_column(String(20), default="unknown")
    status: Mapped[VideoStatus] = mapped_column(SAEnum(VideoStatus), default=VideoStatus.uploaded)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    project: Mapped[Project] = relationship(back_populates="videos")
    lines: Mapped[list[CountingLine]] = relationship(back_populates="video", cascade="all, delete-orphan")
    trajectories: Mapped[list[TrajectoryPoint]] = relationship(back_populates="video", cascade="all, delete-orphan")


class CountingLine(Base):
    __tablename__ = "counting_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    label: Mapped[str] = mapped_column(String(100))
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    x2: Mapped[float] = mapped_column(Float)
    y2: Mapped[float] = mapped_column(Float)
    layer: Mapped[str] = mapped_column(String(50), default="default")
    count_total: Mapped[int] = mapped_column(Integer, default=0)
    pct_total: Mapped[float] = mapped_column(Float, default=0)
    direction: Mapped[str] = mapped_column(String(50), default="unknown")
    video: Mapped[Video] = relationship(back_populates="lines")


class TrajectoryPoint(Base):
    __tablename__ = "trajectory_points"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    track_id: Mapped[str] = mapped_column(String(50))
    frame_no: Mapped[int] = mapped_column(Integer)
    x: Mapped[float] = mapped_column(Float)
    y: Mapped[float] = mapped_column(Float)
    vehicle_type: Mapped[str] = mapped_column(String(50), default="vehicle")
    video: Mapped[Video] = relationship(back_populates="trajectories")


class WorkflowAction(Base):
    __tablename__ = "workflow_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(100), default="admin")
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[int] = mapped_column(Integer)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkspaceIn(BaseModel):
    name: str
    owner: str = "admin"


class ProjectIn(BaseModel):
    workspace_id: int
    name: str


class VideoIn(BaseModel):
    project_id: int
    filename: str
    path: str
    size_mb: float = 0
    duration_min: float = 0
    resolution: str = "unknown"


class LineIn(BaseModel):
    video_id: int
    label: str
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)
    layer: str = "default"
    direction: str = "unknown"


class TrajectoryIn(BaseModel):
    video_id: int
    track_id: str
    frame_no: int
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    vehicle_type: str = "vehicle"


app = FastAPI(title="Traffic-Step API", version="0.4.0")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_actor(x_actor: Optional[str] = Header(default=None, alias="X-Actor")) -> str:
    return x_actor or os.getenv("DEFAULT_ACTOR", "admin")


def audit(db: Session, action: str, entity_type: str, entity_id: int, actor: str, payload: str = "{}"):
    db.add(WorkflowAction(actor=actor, action=action, entity_type=entity_type, entity_id=entity_id, payload=payload))
    db.commit()


def recalc_line_stats(db: Session, video_id: int):
    lines = db.query(CountingLine).filter(CountingLine.video_id == video_id).all()
    points = db.query(TrajectoryPoint).filter(TrajectoryPoint.video_id == video_id).all()
    if not lines:
        return
    total_tracks = len({p.track_id for p in points}) or 1
    for line in lines:
        counted = 0
        for p in points:
            dx = line.x2 - line.x1
            dy = line.y2 - line.y1
            det = abs((p.x - line.x1) * dy - (p.y - line.y1) * dx)
            if det <= 0.02:
                counted += 1
        line.count_total = counted
        line.pct_total = round((counted / total_tracks) * 100, 2)
    db.commit()


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"status": "ok", "debug": os.getenv("DEBUG", "1")}


@app.post("/workspaces")
def create_workspace(payload: WorkspaceIn, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    ws = Workspace(name=payload.name, owner=payload.owner)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    audit(db, "workspace_create", "workspace", ws.id, actor)
    return ws


@app.get("/workspaces")
def list_workspaces(db: Session = Depends(get_db)):
    return db.query(Workspace).all()


@app.post("/projects")
def create_project(payload: ProjectIn, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    ws = db.get(Workspace, payload.workspace_id)
    if not ws:
        raise HTTPException(404, "workspace not found")
    p = Project(workspace_id=payload.workspace_id, name=payload.name)
    db.add(p)
    db.commit()
    db.refresh(p)
    audit(db, "project_create", "project", p.id, actor)
    return p


@app.get("/projects")
def list_projects(workspace_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Project)
    if workspace_id:
        q = q.filter(Project.workspace_id == workspace_id)
    return q.all()


@app.post("/videos")
def create_video(payload: VideoIn, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    p = db.get(Project, payload.project_id)
    if not p:
        raise HTTPException(404, "project not found")
    v = Video(**payload.model_dump(), status=VideoStatus.queued)
    db.add(v)
    db.commit()
    db.refresh(v)
    audit(db, "video_upload", "video", v.id, actor)
    return v


@app.get("/videos")
def list_videos(project_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Video)
    if project_id:
        q = q.filter(Video.project_id == project_id)
    return q.all()


@app.post("/lines")
def add_line(payload: LineIn, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    v = db.get(Video, payload.video_id)
    if not v:
        raise HTTPException(404, "video not found")
    line = CountingLine(**payload.model_dump())
    db.add(line)
    db.commit()
    db.refresh(line)
    recalc_line_stats(db, payload.video_id)
    audit(db, "line_create", "line", line.id, actor)
    return line


@app.put("/lines/{line_id}")
def update_line(line_id: int, payload: LineIn, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    line = db.get(CountingLine, line_id)
    if not line:
        raise HTTPException(404, "line not found")
    for k, v in payload.model_dump().items():
        setattr(line, k, v)
    db.commit()
    recalc_line_stats(db, payload.video_id)
    audit(db, "line_update", "line", line_id, actor)
    return line


@app.delete("/lines/{line_id}")
def delete_line(line_id: int, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    line = db.get(CountingLine, line_id)
    if not line:
        raise HTTPException(404, "line not found")
    video_id = line.video_id
    db.delete(line)
    db.commit()
    recalc_line_stats(db, video_id)
    audit(db, "line_delete", "line", line_id, actor)
    return {"deleted": line_id}


@app.get("/lines")
def list_lines(video_id: int, db: Session = Depends(get_db)):
    return db.query(CountingLine).filter(CountingLine.video_id == video_id).all()


@app.post("/trajectories")
def add_trajectory_point(payload: TrajectoryIn, db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    v = db.get(Video, payload.video_id)
    if not v:
        raise HTTPException(404, "video not found")
    p = TrajectoryPoint(**payload.model_dump())
    db.add(p)
    db.commit()
    recalc_line_stats(db, payload.video_id)
    audit(db, "trajectory_add", "trajectory", p.id, actor)
    return p


@app.get("/heatmap/{video_id}")
def get_heatmap(video_id: int, bins: int = 10, db: Session = Depends(get_db)):
    points = db.query(TrajectoryPoint).filter(TrajectoryPoint.video_id == video_id).all()
    grid = [[0 for _ in range(bins)] for _ in range(bins)]
    for p in points:
        x = min(bins - 1, max(0, int(p.x * bins)))
        y = min(bins - 1, max(0, int(p.y * bins)))
        grid[y][x] += 1
    return {"video_id": video_id, "bins": bins, "grid": grid}


@app.get("/lines/suggest/{video_id}")
def suggest_lines(video_id: int, db: Session = Depends(get_db)):
    points = db.query(TrajectoryPoint).filter(TrajectoryPoint.video_id == video_id).all()
    if not points:
        return {"video_id": video_id, "suggestions": []}
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    avg_x = sum(xs) / len(xs)
    avg_y = sum(ys) / len(ys)
    return {
        "video_id": video_id,
        "suggestions": [
            {"label": "cluster_main", "x1": min(xs), "y1": avg_y, "x2": max(xs), "y2": avg_y},
            {"label": "cluster_vertical", "x1": avg_x, "y1": min(ys), "x2": avg_x, "y2": max(ys)},
        ],
    }


@app.get("/export/video/{video_id}")
def export_video_excel(video_id: int, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "video not found")
    lines = db.query(CountingLine).filter(CountingLine.video_id == video_id).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "line_stats"
    ws.append(["video_id", "filename", "line_id", "label", "direction", "count_total", "pct_total"])
    for ln in lines:
        ws.append([video.id, video.filename, ln.id, ln.label, ln.direction, ln.count_total, ln.pct_total])

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return StreamingResponse(
        out,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=video_{video_id}_lines.xlsx"},
    )


@app.get("/dashboard/workspace/{workspace_id}")
def workspace_dashboard(workspace_id: int, db: Session = Depends(get_db)):
    projects = db.query(Project).filter(Project.workspace_id == workspace_id).all()
    project_ids = [p.id for p in projects]
    videos = db.query(Video).filter(Video.project_id.in_(project_ids)).all() if project_ids else []
    return {
        "workspace_id": workspace_id,
        "projects_total": len(projects),
        "videos_total": len(videos),
        "minutes_total": round(sum(v.duration_min for v in videos), 2),
        "minutes_processed": round(sum(v.duration_min for v in videos if v.status == VideoStatus.processed), 2),
        "storage_mb_total": round(sum(v.size_mb for v in videos), 2),
    }


@app.get("/audit")
def list_audit(limit: int = 100, db: Session = Depends(get_db)):
    return db.query(WorkflowAction).order_by(WorkflowAction.id.desc()).limit(limit).all()
