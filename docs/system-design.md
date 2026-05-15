# System Design Notes

## Processing pipeline

1. Upload/sync video to local storage.
2. Backend creates video record and queue job.
3. Worker loads configured YOLO profile and runs detection/tracking.
4. Worker persists trajectories, per-frame metadata, and summary tables.
5. Counting UI loads 100-frame preview, line layers, and trajectory stats.
6. User edits lines; backend recomputes line intersections incrementally.
7. Export service generates Excel workbook (per-line and aggregate stats).

## GPU optimization strategy

- Use batched frame inference where memory allows.
- Separate decode, infer, and post-process stages.
- Prefer mixed precision (`fp16`) on L4 where accuracy tolerance permits.
- Track utilization and queue depth metrics for autoscaling decisions.
- Keep workers stateless; allocate one process per GPU by default.

## Counting-line analytics model

- `line`: geometry, label, layer, author, timestamps.
- `line_stats`: counts per class/direction and percentages.
- `trajectory`: tracked object polyline with class and confidence.
- `sector`: start/end zone confidence and loose-coverage diagnostics.
- `heatmap`: binned spatial density raster by video/project.

## Extendability

Store counting-line features as versioned JSON schema attached to project:
- allows adding new analytics controls without DB-breaking migrations for every feature.
