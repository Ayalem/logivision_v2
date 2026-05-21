/**
 * Camera tile that goes beyond CCTV — Pillar 4 of the design.
 *
 * Renders a placeholder "live frame" (scan-line texture + zone gradient)
 * with an SVG overlay carrying:
 *   - persistent track bbox + ID
 *   - speed badge
 *   - destination + ETA label
 *   - predicted-path arrow
 *
 * Until the inference worker exposes frame thumbnails, the tracked
 * objects animate deterministically from a per-camera seed so the
 * tile feels alive during the demo.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, Cctv } from 'lucide-react'
import { useDetections, type DetectionBox } from '@/lib/api'
import type { Camera } from '@/lib/types'
import { cn } from '@/lib/utils'

interface MockTrack {
  id: string
  x: number          // bbox top-left in % (0..100)
  y: number
  w: number          // bbox size in %
  h: number
  speed: number      // m/s
  destination: string
  eta: number        // seconds
  vx: number
  vy: number
  color: string
  load: string
}

function seededRandom(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return (s & 0xffffff) / 0xffffff
  }
}

function mockTracks(cameraId: string): MockTrack[] {
  const rand = seededRandom(cameraId.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0))
  const palette = ['#06B6D4', '#10B981', '#F59E0B', '#8B5CF6']
  const destinations = ['Zone A1', 'Zone A3', 'Quai B', 'Stockage C', 'Quai expé.']
  const loads = ['Chargé', 'Vide', '~12 cartons', '4 palettes']
  return Array.from({ length: 2 + Math.floor(rand() * 2) }, (_, i) => ({
    id: `#${Math.floor(10 + rand() * 90)}`,
    x: 10 + rand() * 60,
    y: 25 + rand() * 40,
    w: 12 + rand() * 8,
    h: 16 + rand() * 8,
    speed: 0.5 + rand() * 2.5,
    destination: destinations[Math.floor(rand() * destinations.length)],
    eta: 6 + Math.floor(rand() * 20),
    vx: (rand() - 0.5) * 0.4,
    vy: (rand() - 0.5) * 0.25,
    color: palette[i % palette.length],
    load: loads[Math.floor(rand() * loads.length)],
  }))
}

function statusDot(camera: Camera): { color: string; label: string } {
  if (camera.status === 'maintenance') return { color: 'bg-amber animate-pulse-live', label: 'maint.' }
  if (camera.status === 'offline')     return { color: 'bg-coral', label: 'offline' }
  // online: distinguish "pipeline ingesting now" vs "configured but quiet".
  if (camera.kafkaLive) return { color: 'bg-emerald animate-pulse-live', label: 'live · kafka' }
  return { color: 'bg-electric animate-pulse-live', label: 'live · feed only' }
}

// Project a model bbox (pixel coords) onto the 0..100 SVG viewBox space.
// Detection messages don't always carry width/height — fall back to a 1280x720
// reference frame, the most common output of `frame_grabber --resize 640`.
function bboxToPercent(d: DetectionBox, w: number | undefined, h: number | undefined): MockTrack {
  const W = w ?? 1280
  const H = h ?? 720
  const x = Math.max(0, Math.min(100, (d.x1 / W) * 100))
  const y = Math.max(0, Math.min(100, (d.y1 / H) * 100))
  const x2 = Math.max(0, Math.min(100, (d.x2 / W) * 100))
  const y2 = Math.max(0, Math.min(100, (d.y2 / H) * 100))
  const palette = ['#06B6D4', '#10B981', '#F59E0B', '#8B5CF6']
  return {
    id: `#${d.class_id.toString().padStart(2, '0')}`,
    x, y, w: Math.max(2, x2 - x), h: Math.max(2, y2 - y),
    speed: 0,                          // real speed needs ByteTrack; omitted for now
    destination: d.class_name,
    eta: 0,
    vx: 0, vy: 0,
    color: palette[d.class_id % palette.length],
    load: `${(d.confidence * 100).toFixed(0)}%`,
  }
}

export function AnalyticalCameraFeed({ camera }: { camera: Camera }) {
  // Real detections from Kafka for this camera.
  const { data: detData } = useDetections(20)
  const liveTracks = useMemo<MockTrack[]>(() => {
    const msgs = detData?.messages ?? []
    // The most recent message for THIS camera; render its boxes.
    const latest = msgs
      .filter((m) => m.value?.camera_id === camera.id)
      .sort((a, b) => (b.value?.timestamp_ms ?? 0) - (a.value?.timestamp_ms ?? 0))[0]
    if (!latest) return []
    return (latest.value.detections || []).slice(0, 8).map((d) =>
      bboxToPercent(d, latest.value.width, latest.value.height),
    )
  }, [detData, camera.id])

  // Synthetic fallback so the tile never looks dead before the pipeline runs.
  const initialMock = useMemo(() => mockTracks(camera.id), [camera.id])
  const [mock, setMock] = useState<MockTrack[]>(initialMock)
  const rafRef = useRef<number | null>(null)

  const usingRealDetections = liveTracks.length > 0
  const tracks = usingRealDetections ? liveTracks : mock

  // Drift the mock tracks only when we're in fallback mode.
  useEffect(() => {
    if (usingRealDetections) return
    let last = performance.now()
    const tick = (t: number) => {
      const dt = Math.min(0.05, (t - last) / 1000)
      last = t
      setMock((cur) =>
        cur.map((tr) => {
          let nx = tr.x + tr.vx * dt * 18
          let ny = tr.y + tr.vy * dt * 18
          let { vx, vy } = tr
          if (nx < 4 || nx > 100 - tr.w - 4) { vx = -vx; nx = Math.max(4, Math.min(100 - tr.w - 4, nx)) }
          if (ny < 18 || ny > 100 - tr.h - 4) { vy = -vy; ny = Math.max(18, Math.min(100 - tr.h - 4, ny)) }
          return { ...tr, x: nx, y: ny, vx, vy }
        }),
      )
      rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }
  }, [usingRealDetections])

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
        {/* Live MJPEG video — this is the *input* feed the inference pipeline
            consumes. We render it for every camera regardless of pipeline
            health so the operator can always see what the model is watching.
            The status pill above tells them whether Kafka is currently
            consuming this feed.  If the stream URL 404s the onError handler
            hides the <img> and the gradient fallback below shows through. */}
        <img
          src={`/api/cameras/${camera.id}/stream.mjpg`}
          alt={`${camera.name} live feed`}
          className="absolute inset-0 w-full h-full object-cover"
          onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
        />
        {/* Tiny "INPUT" badge so the jury sees this is the source feed, not a
            decorative thumbnail. Sits above the overlay, below the live boxes. */}
        <div className="absolute top-2 left-2 text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-electric/80 text-white pointer-events-none">
          input · /raw-frames
        </div>
        {/* Fallback gradient — only visible when the <img> above failed or is offline. */}
        <div
          className="absolute inset-0 -z-10"
          style={{
            backgroundImage:
              'radial-gradient(ellipse at 50% 60%, rgba(37,99,235,0.18), transparent 60%), linear-gradient(180deg, #0B1120 0%, #050912 100%)',
          }}
        />
        <div className="absolute inset-x-0 h-px bg-electric/40 animate-scan pointer-events-none" />

        {/* Analytical overlay */}
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 w-full h-full">
          {tracks.map((t) => {
            const cx = t.x + t.w / 2
            const cy = t.y + t.h / 2
            const arrowLen = Math.min(20, t.speed * 6)
            const ax = cx + t.vx * arrowLen
            const ay = cy + t.vy * arrowLen
            return (
              <g key={t.id}>
                {/* Predicted path */}
                <line
                  x1={cx} y1={cy} x2={ax} y2={ay}
                  stroke={t.color}
                  strokeWidth="0.45"
                  strokeDasharray="1.2 0.6"
                  opacity="0.85"
                />
                {/* Arrow head */}
                <circle cx={ax} cy={ay} r="0.7" fill={t.color} />
                {/* Bbox */}
                <rect
                  x={t.x} y={t.y} width={t.w} height={t.h}
                  fill="none"
                  stroke={t.color}
                  strokeWidth="0.4"
                  opacity="0.95"
                />
                {/* Corner ticks */}
                {[[t.x, t.y], [t.x + t.w, t.y], [t.x, t.y + t.h], [t.x + t.w, t.y + t.h]].map((p, i) => (
                  <circle key={i} cx={p[0]} cy={p[1]} r="0.45" fill={t.color} />
                ))}
              </g>
            )
          })}
        </svg>

        {/* HTML overlays — labels positioned in % */}
        <div className="absolute inset-0">
          {tracks.map((t) => (
            <div
              key={t.id + '-label'}
              className="absolute pointer-events-none"
              style={{ left: `${t.x}%`, top: `${Math.max(0, t.y - 10)}%`, color: t.color }}
            >
              <div className="text-[9px] font-mono bg-background/80 backdrop-blur px-1.5 py-0.5 rounded ring-1 ring-border/60 whitespace-nowrap">
                <span className="font-semibold">{t.id}</span>
                <span className="text-muted-foreground"> · {t.speed.toFixed(1)} m/s</span>
              </div>
              <div className="mt-0.5 text-[9px] font-mono bg-background/60 backdrop-blur px-1.5 py-0.5 rounded text-foreground/80 whitespace-nowrap">
                → {t.destination} · ETA {t.eta}s
              </div>
            </div>
          ))}
        </div>

        {/* Bottom HUD — labels the source of the boxes (real Kafka vs sim). */}
        <div className="absolute bottom-2 left-2 right-2 flex items-end justify-between text-[10px]">
          <div className="font-mono text-muted-foreground bg-background/60 backdrop-blur px-1.5 py-0.5 rounded">
            {camera.resolution} · {camera.fps} fps
          </div>
          <div className={cn(
            'font-mono backdrop-blur px-1.5 py-0.5 rounded inline-flex items-center gap-1',
            usingRealDetections
              ? 'bg-emerald/20 text-emerald'
              : 'bg-background/60 text-muted-foreground',
          )}>
            <Activity className="h-3 w-3" />
            {tracks.length} {usingRealDetections ? '⟵ Kafka detections' : 'pistes (sim)'}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 py-2 text-[10px] text-muted-foreground flex items-center justify-between">
        <span>{camera.location || '—'}</span>
        <span className="font-mono">{camera.zone}</span>
      </div>
    </div>
  )
}
