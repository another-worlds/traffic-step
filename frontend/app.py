import os
import pandas as pd
import requests
import streamlit as st

API = os.getenv("API_BASE_URL", "http://backend:8000")

st.set_page_config(page_title="Traffic-Step", layout="wide")
st.title("Traffic-Step AI Counting")

section = st.sidebar.radio("Section", ["Workspace Control", "Project Control", "Counting Lines"])

if section == "Workspace Control":
    st.header("Workspace Dashboard")
    ws_id = st.number_input("Workspace ID", min_value=1, value=1)
    if st.button("Load Workspace Status"):
        r = requests.get(f"{API}/dashboard/workspace/{ws_id}", timeout=10)
        st.json(r.json() if r.ok else {"error": r.text})

elif section == "Project Control":
    st.header("Project Dashboard")
    proj_id = st.number_input("Project ID", min_value=1, value=1)
    if st.button("Load Project Videos"):
        r = requests.get(f"{API}/videos", params={"project_id": proj_id}, timeout=10)
        st.dataframe(pd.DataFrame(r.json() if r.ok else []))

else:
    st.header("Counting Lines Interface")
    video_id = st.number_input("Video ID", min_value=1, value=1)

    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Line Create / Update")
        line_id_edit = st.number_input("Line ID (for update)", min_value=0, value=0)
        cols = st.columns(3)
        label = cols[0].text_input("Label", value="L1")
        x1 = cols[1].number_input("x1", value=0.1)
        y1 = cols[2].number_input("y1", value=0.1)
        cols2 = st.columns(3)
        x2 = cols2[0].number_input("x2", value=0.9)
        y2 = cols2[1].number_input("y2", value=0.9)
        direction = cols2[2].text_input("Direction", value="northbound")
        payload = {"video_id": int(video_id), "label": label, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "direction": direction}
        b1, b2 = st.columns(2)
        if b1.button("Create line"):
            r = requests.post(f"{API}/lines", json=payload, timeout=10)
            st.write(r.json() if r.ok else r.text)
        if b2.button("Update line") and line_id_edit > 0:
            r = requests.put(f"{API}/lines/{line_id_edit}", json=payload, timeout=10)
            st.write(r.json() if r.ok else r.text)

        line_id_delete = st.number_input("Line ID to delete", min_value=0, value=0)
        if st.button("Delete line") and line_id_delete > 0:
            r = requests.delete(f"{API}/lines/{line_id_delete}", timeout=10)
            st.write(r.json() if r.ok else r.text)

    with c2:
        st.subheader("Tools")
        if st.button("Auto-suggest lines"):
            r = requests.get(f"{API}/lines/suggest/{int(video_id)}", timeout=10)
            st.json(r.json() if r.ok else {"error": r.text})

        if st.button("Show heatmap"):
            r = requests.get(f"{API}/heatmap/{int(video_id)}", timeout=10)
            data = r.json() if r.ok else {"grid": []}
            grid = data.get("grid", [])
            if grid:
                st.dataframe(pd.DataFrame(grid))

        st.markdown(f"[Download Excel export]({API}/export/video/{int(video_id)})")

    st.subheader("Current lines")
    if st.button("Refresh lines"):
        r = requests.get(f"{API}/lines", params={"video_id": int(video_id)}, timeout=10)
        st.dataframe(pd.DataFrame(r.json() if r.ok else []))
