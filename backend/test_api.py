from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_workflow_and_line_stats_and_export():
    ws = client.post("/workspaces", json={"name": "ws1", "owner": "admin"}, headers={"X-Actor": "alice"})
    assert ws.status_code == 200
    ws_id = ws.json()["id"]

    pr = client.post("/projects", json={"workspace_id": ws_id, "name": "p1"}, headers={"X-Actor": "alice"})
    assert pr.status_code == 200
    p_id = pr.json()["id"]

    vd = client.post(
        "/videos",
        json={"project_id": p_id, "filename": "v.mp4", "path": "/data/v.mp4", "size_mb": 100, "duration_min": 12.4, "resolution": "1920x1080"},
        headers={"X-Actor": "alice"},
    )
    assert vd.status_code == 200
    v_id = vd.json()["id"]

    line = client.post(
        "/lines",
        json={"video_id": v_id, "label": "L1", "x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 0.1, "direction": "east"},
        headers={"X-Actor": "bob"},
    )
    assert line.status_code == 200

    t1 = client.post("/trajectories", json={"video_id": v_id, "track_id": "t1", "frame_no": 1, "x": 0.5, "y": 0.1}, headers={"X-Actor": "bob"})
    assert t1.status_code == 200

    lines = client.get("/lines", params={"video_id": v_id})
    assert lines.status_code == 200
    assert len(lines.json()) == 1
    assert lines.json()[0]["count_total"] >= 1

    heatmap = client.get(f"/heatmap/{v_id}")
    assert heatmap.status_code == 200
    assert len(heatmap.json()["grid"]) == 10

    suggest = client.get(f"/lines/suggest/{v_id}")
    assert suggest.status_code == 200
    assert len(suggest.json()["suggestions"]) == 2

    dashboard = client.get(f"/dashboard/workspace/{ws_id}")
    assert dashboard.status_code == 200
    assert dashboard.json()["videos_total"] == 1

    export = client.get(f"/export/video/{v_id}")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    audit = client.get("/audit")
    assert audit.status_code == 200
    actors = {a["actor"] for a in audit.json()}
    assert "alice" in actors
    assert "bob" in actors
