"""Tests for ByteTrack implementation."""

import numpy as np
from jobs.byte_tracker import ByteTrack


def test_iou_same_box():
    a = np.array([0, 0, 10, 10])
    b = np.array([0, 0, 10, 10])
    assert ByteTrack._iou(a, b) == 1.0


def test_iou_no_overlap():
    a = np.array([0, 0, 10, 10])
    b = np.array([20, 20, 30, 30])
    assert ByteTrack._iou(a, b) == 0.0


def test_track_creation():
    tracker = ByteTrack()
    detections = [
        {"y1": 0, "x1": 0, "y2": 10, "x2": 10, "confidence": 0.9, "class_id": 0},
    ]
    tracks = tracker.update(detections, frame_id=1)
    assert len(tracks) == 0  # Need 2 frames to confirm track

    tracks = tracker.update(detections, frame_id=2)
    assert len(tracks) == 1
    assert tracks[0].track_id == 1
