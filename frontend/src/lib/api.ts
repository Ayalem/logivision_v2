/**
 * Thin fetch wrapper + TanStack Query hooks against the FastAPI backend.
 * Endpoints live in services/api/routers/client.py — see types.ts for shapes.
 */
import { useQuery } from '@tanstack/react-query'
import type {
  Anomaly,
  Camera,
  EntryExitItem,
  Kpis,
  Me,
  Zone,
} from './types'

async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(path, { credentials: 'same-origin' })
  if (!r.ok) throw new Error(`${path} → ${r.status}`)
  return (await r.json()) as T
}

// ---------- queries ----------

export const useMe = () =>
  useQuery<Me>({
    queryKey: ['me'],
    queryFn: () => getJson<Me>('/api/me'),
    staleTime: 60_000,
  })

export const useKpis = () =>
  useQuery<Kpis>({
    queryKey: ['kpis'],
    queryFn: () => getJson<Kpis>('/api/kpis'),
    refetchInterval: 10_000,
  })

export const useZones = () =>
  useQuery<{ zones: Zone[] }>({
    queryKey: ['zones'],
    queryFn: () => getJson<{ zones: Zone[] }>('/api/zones'),
    refetchInterval: 30_000,
  })

export const useCameras = () =>
  useQuery<{ cameras: Camera[]; degraded: boolean }>({
    queryKey: ['cameras'],
    queryFn: () => getJson<{ cameras: Camera[]; degraded: boolean }>('/api/cameras'),
    refetchInterval: 10_000,
  })

export const useAnomalies = (n = 50) =>
  useQuery<{ anomalies: Anomaly[]; degraded: boolean }>({
    queryKey: ['anomalies', n],
    queryFn: () => getJson<{ anomalies: Anomaly[]; degraded: boolean }>(`/api/anomalies?n=${n}`),
    refetchInterval: 5_000,
  })

export const useEntriesExits = (n = 50) =>
  useQuery<{ items: EntryExitItem[]; degraded: boolean }>({
    queryKey: ['entries-exits', n],
    queryFn: () => getJson<{ items: EntryExitItem[]; degraded: boolean }>(`/api/entries-exits?n=${n}`),
    refetchInterval: 10_000,
  })

// ---------- admin-only (kept for the System tab) ----------

export interface MlRun {
  run_id: string
  experiment: string
  status: string
  start_time: number
  metrics: Record<string, number>
  tags: Record<string, string>
}

export const useRuns = (limit = 10) =>
  useQuery<{ runs: MlRun[] }>({
    queryKey: ['runs', limit],
    queryFn: () => getJson<{ runs: MlRun[] }>(`/api/registry/runs?limit=${limit}`),
    refetchInterval: 30_000,
    retry: false,
  })

export const useRegistry = () =>
  useQuery<{ models: Array<{ name: string; versions: Array<{ version: string; stage: string; run_id: string }> }> }>({
    queryKey: ['registry'],
    queryFn: () =>
      getJson('/api/registry/models'),
    refetchInterval: 30_000,
    retry: false,
  })


// ---------- predictions / heatmap / insights (Phase A.3) ----------

export interface CongestionForecast {
  event_id: string
  event_type: 'congestion_forecast'
  severity: 'warning'
  zone: string
  eta_seconds: number
  confidence: number
  density: number
  timestamp_ms: number
  /** Identifies whether the trained LSTM (lstm-prsa-v1) produced this
   * forecast or the rule-based fallback (rule-v0). The UI uses this to
   * flip the panel badge between the green LSTM tag and the amber rule tag. */
  forecast_source?: 'lstm-prsa-v1' | 'rule-v0'
}
export interface CollisionRisk {
  event_id: string
  event_type: 'collision_risk'
  severity: 'critical'
  track_a: string
  track_b: string
  zone: string
  eta_seconds: number
  point_x: number
  point_y: number
  timestamp_ms: number
}
export interface TrajectoryHint {
  event_id: string
  event_type: 'trajectory_hint'
  severity: 'info'
  track_id: string
  points: Array<{ t: number; x: number; y: number }>
  predicted_point: { x: number; y: number }
  horizon_seconds: number
  speed_units_per_s: number
  timestamp_ms: number
}

export interface PredictionsResponse {
  predictions: Array<CongestionForecast | CollisionRisk | TrajectoryHint>
  buckets: {
    congestion: CongestionForecast[]
    collision: CollisionRisk[]
    trajectories: TrajectoryHint[]
  }
  degraded: boolean
}

export const usePredictions = () =>
  useQuery<PredictionsResponse>({
    queryKey: ['predictions'],
    queryFn: () => getJson<PredictionsResponse>('/api/predictions?n=40'),
    refetchInterval: 5_000,
  })

// Trained-model metadata for the AI MODEL STATUS panel.
export const useModelInfo = () =>
  useQuery<import('./types').ModelInfo>({
    queryKey: ['model-info'],
    queryFn: () => getJson<import('./types').ModelInfo>('/api/model-info'),
    refetchInterval: 60_000,  // doesn't change often
    staleTime: 30_000,
  })

// ─── Admin / Système MLOps hooks ───
// Lightweight wrappers around the existing /api/topics, /api/drift, /api/benchmarks
// endpoints so the Système page can render them in one place without hitting
// the FastAPI gateway four times on render.

export interface TopicMessages {
  messages: Array<Record<string, unknown>>
  degraded: boolean
}
export const useTopicMessages = (topic: string, n = 10) =>
  useQuery<TopicMessages>({
    queryKey: ['topic', topic, n],
    queryFn: () => getJson<TopicMessages>(`/api/topics/${topic}/messages?n=${n}`),
    refetchInterval: 5_000,
  })

export interface ReportListing {
  reports: Array<{ name: string; size_bytes: number; modified: number }>
}
export const useDriftReports = () =>
  useQuery<ReportListing>({
    queryKey: ['drift'],
    queryFn: () => getJson<ReportListing>('/api/drift/reports'),
    refetchInterval: 60_000,
  })
export const useBenchmarks = () =>
  useQuery<ReportListing>({
    queryKey: ['benchmarks'],
    queryFn: () => getJson<ReportListing>('/api/benchmarks'),
    refetchInterval: 60_000,
  })

export interface HeatmapResponse {
  layer: string
  grid: number
  cell_size: number
  cells: Array<{ x: number; y: number; value: number }>
  degraded: boolean
}
export const useHeatmap = (layer: string, enabled = true) =>
  useQuery<HeatmapResponse>({
    queryKey: ['heatmap', layer],
    queryFn: () => getJson<HeatmapResponse>(`/api/heatmap?layer=${layer}&grid=20`),
    refetchInterval: 8_000,
    enabled: enabled && layer !== 'off',
  })

export interface InsightChain {
  id: string
  title: string
  outcome: string
  severity: 'info' | 'warning' | 'critical'
  timestamp_ms: number
  steps: Array<{ label: string; status: 'done' | 'pending' | 'failed'; ts_ms: number | null }>
}
export const useInsights = () =>
  useQuery<{ insights: InsightChain[]; degraded: boolean }>({
    queryKey: ['insights'],
    queryFn: () => getJson<{ insights: InsightChain[]; degraded: boolean }>('/api/insights'),
    refetchInterval: 10_000,
  })


// ---------- Kafka detection peek — drives the SVG overlay on camera tiles ----------
// Reads the real `detections` topic so the bounding boxes we draw on top of
// the input video are the actual model output that flowed through Kafka.
export interface DetectionBox {
  class_id: number
  class_name: string
  confidence: number
  x1: number; y1: number; x2: number; y2: number
}
export interface DetectionMessage {
  partition: number
  offset: number
  key: string | null
  value: {
    frame_id: string
    camera_id: string
    timestamp_ms: number
    model_version: string
    inference_ms: number
    frame_uri: string
    width?: number
    height?: number
    detections: DetectionBox[]
  }
}
export const useDetections = (n = 20) =>
  useQuery<{ topic: string; messages: DetectionMessage[] }>({
    queryKey: ['detections', n],
    queryFn: () =>
      getJson<{ topic: string; messages: DetectionMessage[] }>(
        `/api/topics/detections/messages?n=${n}`,
      ),
    refetchInterval: 1_500,        // ~10x faster than zones — boxes feel live
    retry: false,
  })
