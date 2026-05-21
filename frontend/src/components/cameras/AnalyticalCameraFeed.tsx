/**
 * Camera tile — strictly honest version.
 *
 * Shows:
 *   1. Live MJPEG video for `camera.id` (always — the input feed).
 *   2. SVG bounding boxes EXCLUSIVELY from the real Kafka `detections`
 *      topic. Each box is annotated with the real model output: class
 *      name + confidence. Nothing else.
 *
 * Does NOT show:
 *   - Fake track IDs (we have no ByteTrack tracking yet).
 *   - Fake destinations (no zone-classification model).
 *   - Fake speeds (would require frame-to-frame tracking).
 *   - Fake ETAs (would require speed + path planning).
 *   - Predicted-path arrows (no trajectory model).
 *
 * When zero real detections exist for a camera the overlay is empty
 * and the bottom-right badge says "0 detections" — never a simulation.
 */
import { Cctv } from 'lucide-react'
import { useDetections, type DetectionBox } from '@/lib/api'
import type { Camera } from '@/lib/types'
import { cn } from '@/lib/utils'

interface DrawableBox {
  /** Position in % of the tile (matches SVG viewBox 0..100). */
  x: number
  y: number
  w: number
  h: number
  className: string
  confidence: number
  color: string
}

// Project a model bbox (image pixels) onto the 0..100 SVG viewBox space.
// Detection messages don't always carry width/height — fall back to the
// most common output of `frame_grabber --resize 640`.
function bboxToPercent(d: DetectionBox, w: number | undefined, h: number | undefined): DrawableBox {
  const W = w ?? 1280
  const H = h ?? 720
  const x = Math.max(0, Math.min(100, (d.x1 / W) * 100))
  const y = Math.max(0, Math.min(100, (d.y1 / H) * 100))
  const x2 = Math.max(0, Math.min(100, (d.x2 / W) * 100))
  const y2 = Math.max(0, Math.min(100, (d.y2 / H) * 100))
  const palette = ['#06B6D4', '#10B981', '#F59E0B', '#8B5CF6', '#EF4444']
  return {
    x,
    y,
    w: Math.max(2, x2 - x),
    h: Math.max(2, y2 - y),
    className: d.class_name,
    confidence: d.confidence,
    color: palette[d.class_id % palette.length],
  }
}

function statusDot(camera: Camera): { color: string; label: string } {
  if (camera.status === 'maintenance') return { color: 'bg-amber animate-pulse-live', label: 'maint.' }
  if (camera.status === 'offline')     return { color: 'bg-coral', label: 'offline' }
  if (camera.kafkaLive) return { color: 'bg-emerald animate-pulse-live', label: 'live · kafka' }
  return { color: 'bg-electric animate-pulse-live', label: 'feed only' }
}

export function AnalyticalCameraFeed({ camera }: { camera: Camera }) {
  const { data: detData } = useDetections(20)

  // The most recent Kafka `detections` message for THIS camera. We do
  // not mock anything when none exists.
  const msgs = detData?.messages ?? []
  const latest = msgs
    .filter((m) => m.value?.camera_id === camera.id)
    .sort((a, b) => (b.value?.timestamp_ms ?? 0) - (a.value?.timestamp_ms ?? 0))[0]
  const detections: DrawableBox[] =
    latest?.value.detections?.slice(0, 8).map((d) =>
      bboxToPercent(d, latest.value.width, latest.value.height),
    ) ?? []
  const inferenceMs = latest?.value.inference_ms

  const stat = statusDot(camera)

  return (
    <div className="glass-card rounded-2xl overflow-hidden shadow-soft ring-1 ring-border">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 text-xs border-b border-border/60">
        <Cctv className="h-3.5 w-3.5 text-electric" />
        <span className="font-semibold truncate">{camera.name}</span>
        <span className="font-mono text-[10px] text-muted-foreground">{camera.id}</span>
        <span className="ml-auto inline-flex items-center gap-1 text-[10px] uppercase tracking-wider">
          <span className={cn('h-1.5 w-1.5 rounded-full', stat.color)} />
          {stat.label}
        </span>
      </div>

      {/* Feed canvas */}
      <div className="relative aspect-video bg-[#0B1120] overflow-hidden">
        {/* Live MJPEG video. Hidden via onError if the stream URL 404s
            (e.g. camera not configured yet) — gradient fallback below. */}
        <img
          src={`/api/cameras/${camera.id}/stream.mjpg`}
          alt={`${camera.name} live feed`}
          className="absolute inset-0 w-full h-full object-cover"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = 'none'
          }}
        />
        <div
          className="absolute inset-0 -z-10"
          style={{
            backgroundImage:
              'radial-gradient(ellipse at 50% 60%, rgba(37,99,235,0.18), transparent 60%), linear-gradient(180deg, #0B1120 0%, #050912 100%)',
          }}
        />

        {/* "INPUT" badge — this video is what the inference worker consumes. */}
        <div className="absolute top-2 left-2 text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-electric/80 text-white pointer-events-none">
          input · /raw-frames
        </div>

        {/* SVG overlay — REAL Kafka detections only.  Each box gets just
            class_name + confidence%.  No IDs, speeds, destinations, ETAs. */}
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full pointer-events-none">
          {detections.map((b, i) => (
            <g key={i}>
              <rect
                x={b.x}
                y={b.y}
                width={b.w}
                height={b.h}
                fill="none"
                stroke={b.color}
                strokeWidth="0.45"
                opacity="0.95"
              />
              {[[b.x, b.y], [b.x + b.w, b.y], [b.x, b.y + b.h], [b.x + b.w, b.y + b.h]].map(
                (p, j) => (
                  <circle key={j} cx={p[0]} cy={p[1]} r="0.4" fill={b.color} />
                ),
              )}
            </g>
          ))}
        </svg>

        {/* HTML labels positioned above each box — class + confidence ONLY. */}
        <div className="absolute inset-0 pointer-events-none">
          {detections.map((b, i) => (
            <div
              key={`${i}-label`}
              className="absolute"
              style={{ left: `${b.x}%`, top: `${Math.max(0, b.y - 6)}%`, color: b.color }}
            >
              <div className="text-[9px] font-mono bg-background/85 backdrop-blur px-1.5 py-0.5 rounded ring-1 ring-border/60 whitespace-nowrap">
                <span className="font-semibold">{b.className}</span>
                <span className="text-muted-foreground"> · {(b.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
        </div>

        {/* Empty-state hint when no Kafka detections received yet. */}
        {detections.length === 0 && (
          <div className="absolute top-2 right-2 text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-background/75 text-muted-foreground pointer-events-none">
            0 detections · awaiting worker
          </div>
        )}

        {/* Bottom HUD — strictly real numbers. */}
        <div className="absolute bottom-2 left-2 right-2 flex items-end justify-between text-[10px] pointer-events-none">
          <div className="font-mono text-muted-foreground bg-background/70 backdrop-blur px-1.5 py-0.5 rounded">
            {camera.resolution} · {camera.fps} fps
          </div>
          <div
            className={cn(
              'font-mono backdrop-blur px-1.5 py-0.5 rounded',
              detections.length > 0
                ? 'bg-emerald/20 text-emerald'
                : 'bg-background/70 text-muted-foreground',
            )}
          >
            {detections.length === 0
              ? 'no detections'
              : `${detections.length} det · ${inferenceMs ? `${inferenceMs.toFixed(0)} ms` : ''}`}
          </div>
        </div>
      </div>

      {/* Footer — config metadata only, no fabricated values. */}
      <div className="px-3 py-2 text-[10px] text-muted-foreground flex items-center justify-between">
        <span>{camera.location || '—'}</span>
        <span className="font-mono">{camera.zone}</span>
      </div>
    </div>
  )
}
