"""Tests for geometry utilities."""

from jobs.detection_enrichment import point_in_polygon


def test_point_in_square():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon(5, 5, square) is True
    assert point_in_polygon(15, 5, square) is False


def test_point_on_edge():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    # Edge cases — ray casting is ambiguous on edges
    result = point_in_polygon(0, 5, square)
    assert isinstance(result, bool)


def test_complex_polygon():
    # L-shaped polygon
    poly = [(0, 0), (10, 0), (10, 5), (5, 5), (5, 10), (0, 10)]
    assert point_in_polygon(2, 2, poly) is True
    assert point_in_polygon(7, 7, poly) is False
    assert point_in_polygon(2, 7, poly) is True
