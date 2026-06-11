/**
 * Wire types — match the FastAPI response shapes in
 * services/api/routers/client.py.  Keep names ASCII-safe; backend already
 * returns these as camelCase.
 */

export type Role = 'operator' | 'admin'

export interface Me { role: Role; name?: string }

export interface ZonePolygonPoint { x: number; y: number }
export type ZoneKind = 'entry' | 'exit' | 'forbidden' | 'shelf'

export interface Zone {
  id: string
  name: string
  kind: ZoneKind
  category: string
  /** 0-100 from the latest real zone-occupancy snapshot, or null when
   *  the pipeline hasn't produced one yet (UI renders an em-dash). */
  occupancy: number | null
  capacity: number
  currentItems: number | null
  status: 'normal' | 'warning' | 'critical' | 'unknown'
  /** true when occupancy traces to a real CEP snapshot. */
  live: boolean
  x: number; y: number; width: number; height: number  // % bbox
  polygon: ZonePolygonPoint[]                          // 0..1 coords
  lastUpdated: string
}

export interface Camera {
  id: string
  name: string
  location: string
  zone: string
  status: 'online' | 'offline' | 'maintenance' | 'unknown'
  /** True when raw-frames messages flowed in the last 30 s — i.e. the
   *  inference pipeline is currently consuming this feed.  Distinct from
   *  `status`: a camera is `online` whenever it's in the YAML registry, but
   *  `kafkaLive` only flips true when there's actual streaming activity. */
  kafkaLive: boolean
  resolution: string
  fps: number
  detectionCount: number
  lastDetection: string | null
}

export interface Anomaly {
  id: string
  type: 'overflow' | 'unauthorized' | 'misplaced' | 'missing' | 'damaged'
  severity: 'critical' | 'warning' | 'info'
  zone: string
  zoneId: string
  description: string
  timestamp: string
  resolved: boolean
  cameraId: string
  confidence: number
  eventType: string  // raw event_type from CEP — used for filtering
}

export interface EntryExitItem {
  id: string
  type: 'entry' | 'exit'
  message: string
  timestamp: string
  zone: string
  cameraId: string
  className: string
}

export interface Kpis {
  totalBoxes: number
  todayEntries: number
  todayExits: number
  activeAnomalies: number
  systemStatus: 'operational' | 'degraded' | 'offline' | 'waiting'
  camerasOnline: number
  totalCameras: number
  avgProcessingTime: number
  stockLevel: number
  /** True iff a real Kafka event / detection / raw-frame arrived recently.
   * When false the tiles render '—' instead of zeros and a waiting banner appears. */
  pipelineActive: boolean
  degraded: boolean
}

// Live events streamed via /ws/events. The server wraps the payload as
// `{event: ...}` (see services/api/main.py), but we also accept raw forms.
export interface LiveEvent {
  event_id: string
  event_type: string
  severity: 'info' | 'warning' | 'critical'
  timestamp_ms: number
  camera_id?: string | null
  track_id?: string | null
  payload?: Record<string, string>
}

// Prediction event types — backend emits these from /api/predictions.
//
// `forecast_source` tells the UI whether to render the "LSTM · Birmingham" badge
// (model is loaded and produced the number) or the "rule v0" badge (the
// model artifact is missing and the heuristic ran instead).
export type ForecastSource = 'lstm-birmingham-v2' | 'rule-v0'

export interface CongestionForecast {
  event_type: 'congestion_forecast'
  zone: string
  eta_seconds: number
  confidence: number
  density: number
  forecast_source?: ForecastSource
}

// Metadata for the trained congestion-forecast model. Exposed by
// /api/model-info and rendered in the AiModelStatus panel + Système page.
export interface ModelInfo {
  name: string
  version: string | null
  architecture: string
  training_dataset: string
  loaded: boolean
  metrics?: {
    lstm: Record<string, { rmse: number; mae: number }>
    persistence: Record<string, { rmse: number; mae: number }>
    dataset: string
    subset: { n_stations: number; n_weeks: number }
  }
  config?: {
    n_nodes: number
    n_horizons: number
    horizons_hours: number[]
    input_len: number
  }
}

export interface CollisionRisk {
  event_type: 'collision_risk'
  track_a: string
  track_b: string
  eta_seconds: number
  point_x: number
  point_y: number
}
