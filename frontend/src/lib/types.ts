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
  occupancy: number       // 0-100
  capacity: number
  currentItems: number
  status: 'normal' | 'warning' | 'critical'
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
  systemStatus: 'operational' | 'degraded' | 'offline'
  camerasOnline: number
  totalCameras: number
  avgProcessingTime: number
  stockLevel: number
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

// Prediction event types (Phase A.3) — shape proposal; the backend will
// emit these once the predictions module ships.
export interface CongestionForecast {
  event_type: 'congestion_forecast'
  zone: string
  eta_seconds: number
  confidence: number
  density: number
}

export interface CollisionRisk {
  event_type: 'collision_risk'
  track_a: string
  track_b: string
  eta_seconds: number
  point_x: number
  point_y: number
}
