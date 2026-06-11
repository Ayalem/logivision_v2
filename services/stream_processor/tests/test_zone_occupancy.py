"""ZoneOccupancyAggregator — presence tracking, expiry, snapshot cadence."""

from __future__ import annotations

from services.stream_processor.cep import CEPConfig, Zone, ZoneOccupancyAggregator

SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def _zones() -> list[Zone]:
    return [
        Zone(name="shelf_A1", forbidden=False, polygon=SQUARE, kind="shelf", capacity=4),
        Zone(name="entrance", forbidden=False, polygon=SQUARE, kind="entry", capacity=2),
    ]


def _agg(snapshot_s: float = 300.0) -> ZoneOccupancyAggregator:
    cfg = CEPConfig(occupancy_snapshot_s=snapshot_s, occupancy_idle_expiry_s=30.0)
    return ZoneOccupancyAggregator(_zones(), cfg)


def test_first_call_arms_the_interval_without_emitting() -> None:
    agg = _agg()
    assert agg.maybe_snapshot(1_000_000) == []


def test_snapshot_after_interval_counts_distinct_tracks() -> None:
    agg = _agg(snapshot_s=300.0)
    t0 = 1_000_000
    agg.maybe_snapshot(t0)  # arm
    # Observations must be fresh (<30 s before the snapshot) to count —
    # the snapshot reflects LIVE occupancy, not everything in the interval.
    agg.observe("shelf_A1", "cam:1", t0 + 290_000)
    agg.observe("shelf_A1", "cam:2", t0 + 292_000)
    agg.observe("shelf_A1", "cam:2", t0 + 295_000)  # same track — still 1
    agg.observe("entrance", "cam:3", t0 + 296_000)
    snaps = agg.maybe_snapshot(t0 + 301_000)
    by_zone = {s["zone"]: s for s in snaps}
    assert by_zone["shelf_A1"]["occupied_tracks"] == 2
    assert by_zone["shelf_A1"]["ratio"] == 0.5  # 2 / capacity 4
    assert by_zone["entrance"]["occupied_tracks"] == 1
    assert by_zone["entrance"]["ratio"] == 0.5  # 1 / capacity 2


def test_track_moving_between_zones_counts_once() -> None:
    agg = _agg()
    t0 = 1_000_000
    agg.maybe_snapshot(t0)
    agg.observe("shelf_A1", "cam:9", t0 + 294_000)
    agg.observe("entrance", "cam:9", t0 + 296_000)  # moved — removed from shelf
    snaps = {s["zone"]: s for s in agg.maybe_snapshot(t0 + 301_000)}
    assert snaps["shelf_A1"]["occupied_tracks"] == 0
    assert snaps["entrance"]["occupied_tracks"] == 1


def test_idle_tracks_expire() -> None:
    agg = _agg()
    t0 = 1_000_000
    agg.maybe_snapshot(t0)
    agg.observe("shelf_A1", "cam:1", t0 + 1_000)  # last seen early
    agg.observe("shelf_A1", "cam:2", t0 + 295_000)  # fresh
    # At snapshot time, cam:1 is >30 s idle → expired; cam:2 still counted.
    snaps = {s["zone"]: s for s in agg.maybe_snapshot(t0 + 301_000)}
    assert snaps["shelf_A1"]["occupied_tracks"] == 1


def test_ratio_is_capped_at_one() -> None:
    agg = _agg()
    t0 = 1_000_000
    agg.maybe_snapshot(t0)
    for i in range(6):  # 6 tracks in a capacity-2 zone
        agg.observe("entrance", f"cam:{i}", t0 + 300_000)
    snaps = {s["zone"]: s for s in agg.maybe_snapshot(t0 + 301_000)}
    assert snaps["entrance"]["occupied_tracks"] == 6
    assert snaps["entrance"]["ratio"] == 1.0


def test_leaving_all_zones_removes_presence() -> None:
    agg = _agg()
    t0 = 1_000_000
    agg.maybe_snapshot(t0)
    agg.observe("shelf_A1", "cam:1", t0 + 1_000)
    agg.observe(None, "cam:1", t0 + 2_000)  # walked out of every zone
    snaps = {s["zone"]: s for s in agg.maybe_snapshot(t0 + 301_000)}
    assert snaps["shelf_A1"]["occupied_tracks"] == 0
