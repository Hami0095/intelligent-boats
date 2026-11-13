"""Converts perception output into the obstacle summary sent to the FMS."""

from __future__ import annotations

from marine_contracts import ObstacleSummaryPayload, ObstacleTrack, Provenance

from ai_box.perception.frames import PerceptionFrame


def to_obstacle_summary(frame: PerceptionFrame) -> ObstacleSummaryPayload:
    tracks = [
        ObstacleTrack(
            track_id=f"{frame.sensor_id}-{index}",
            category=detection.category,
            relative_bearing_deg=detection.bearing_deg,
            range_m=detection.range_m,
            collision_risk=None,  # not estimated yet; never fabricate a risk value
            confidence=detection.confidence,
            provenance=Provenance(source=f"sensor:{frame.sensor_id}"),
        )
        for index, detection in enumerate(frame.detections)
    ]
    return ObstacleSummaryPayload(tracks=tracks)
