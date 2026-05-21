CREATE TABLE IF NOT EXISTS kpi_detections (
    label String,
    count UInt64,
    window_start DateTime64(3),
    window_end DateTime64(3),
    window_sec UInt32
) ENGINE = MergeTree()
ORDER BY (window_start, label);
