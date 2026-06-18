/**
 * Canvas wrapper + HUD overlay (layer toggles, selected zone summary).
 *
 * WebGL fallback: if the user-agent has no WebGL we render a static SVG
 * grid using the same zone polygons, so the demo never shows a blank box.
 */
import { Suspense, useEffect, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import {
  Activity,
  Eye,
  EyeOff,
  Flame,
  Layers,
  Move,
  Shield,
  Sparkles,
} from 'lucide-react'
import { useZones } from '@/lib/api'
import { useAppStore, type HeatmapLayer as HeatmapOption } from '@/lib/store'
import { cn } from '@/lib/utils'
import { Scene } from './Scene'
import { colorForOccupancy, colorForZoneKind } from './twin-config'

const HEATMAP_OPTIONS: Array<{ id: HeatmapOption; label: string; icon: typeof Flame }> = [
  { id: 'off',        label: 'Off',        icon: EyeOff },
  { id: 'traffic',    label: 'Traffic',    icon: Move },
  { id: 'shelf',      label: 'Étagères',   icon: Layers },
  { id: 'idle',       label: 'Inactif',    icon: Eye },
  { id: 'bottleneck', label: 'Goulots',    icon: Flame },
  { id: 'worker',     label: 'Personnel',  icon: Sparkles },
]

function hasWebGL(): boolean {
  if (typeof window === 'undefined') return false
  try {
    const c = document.createElement('canvas')
    return !!(c.getContext('webgl2') || c.getContext('webgl'))
  } catch { return false }
}

function FallbackSvg() {
  const zones = useZones().data?.zones ?? []
  return (
    <div className="flex items-center justify-center h-full">
      <div className="relative w-full max-w-md aspect-square dot-grid rounded-2xl ring-1 ring-border">
        <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full">
          {zones.map((z) => {
            const points = z.polygon.map((p) => `${p.x * 100},${p.y * 100}`).join(' ')
            const fill = z.kind === 'shelf' ? colorForOccupancy(z.occupancy) : colorForZoneKind(z.kind)
            return <polygon key={z.id} points={points} fill={fill} opacity={0.6} stroke={fill} strokeWidth={0.4} />
          })}
        </svg>
        <div className="absolute bottom-2 left-2 text-[10px] font-mono text-muted-foreground bg-background/60 px-2 py-0.5 rounded">
          WebGL fallback
        </div>
      </div>
    </div>
  )
}

export function DigitalTwin() {
  const [hasGL] = useState<boolean>(hasWebGL)
  const heatmap = useAppStore((s) => s.heatmap)
  const setHeatmap = useAppStore((s) => s.setHeatmap)
  const showTraj = useAppStore((s) => s.showTrajectories)
  const showCol  = useAppStore((s) => s.showCollisions)
  const toggleTrajectories = useAppStore((s) => s.toggleTrajectories)
  const toggleCollisions   = useAppStore((s) => s.toggleCollisions)
  const selectedZone       = useAppStore((s) => s.selectedZone)
  const setSelectedZone    = useAppStore((s) => s.setSelectedZone)
  const zonesQ = useZones()
  const selected = zonesQ.data?.zones.find((z) => z.id === selectedZone) ?? null

  // Esc to clear selection.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && selectedZone) setSelectedZone(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selectedZone, setSelectedZone])

  return (
    <div className="relative w-full h-[520px] rounded-2xl overflow-hidden ring-1 ring-border bg-[#0B1120] interactive-card">
      {/* Animated Lidar scanning line */}
      <div className="laser-scanline" />

      {hasGL ? (
        <Canvas
          shadows
          camera={{ position: [12, 14, 14], fov: 45 }}
          dpr={[1, 2]}
          gl={{ antialias: true }}
        >
          <Suspense fallback={null}>
            <Scene />
          </Suspense>
        </Canvas>
      ) : (
        <FallbackSvg />
      )}

      {/* HONESTY BADGE — the twin is an abstract layout driven by the
          7 polygons in infra/zones.example.yaml, NOT a 3D scan of the
          real warehouse. Make this explicit so the jury doesn't think
          we built a Unity digital twin. */}
      <div className="absolute top-2 left-1/2 -translate-x-1/2 text-[10px] font-mono px-2 py-1 rounded bg-background/85 ring-1 ring-border text-muted-foreground pointer-events-none">
        abstract layout · driven by infra/zones.yaml · not a 3D scan
      </div>

      {/* HUD — layer & overlay toggles */}
      <div className="absolute top-3 left-3 flex flex-col gap-2">
        <div className="glass-card rounded-xl px-2 py-1.5 flex items-center gap-1 text-[10px] font-medium">
          <Activity className="h-3 w-3 text-electric" />
          <span className="uppercase tracking-wider text-muted-foreground">Heatmap</span>
        </div>
        <div className="glass-card rounded-xl p-1 flex flex-col gap-0.5">
          {HEATMAP_OPTIONS.map((o) => {
            const Icon = o.icon
            const active = heatmap === o.id
            return (
              <button
                key={o.id}
                onClick={() => setHeatmap(o.id)}
                className={cn(
                  'flex items-center gap-2 px-2 py-1 rounded-lg text-[11px] font-medium transition-colors text-left',
                  active
                    ? 'bg-electric/20 text-electric'
                    : 'text-muted-foreground hover:bg-foreground/5 hover:text-foreground',
                )}
              >
                <Icon className="h-3 w-3" />
                {o.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* HUD — overlay toggles */}
      <div className="absolute top-3 right-3 flex flex-col gap-1.5">
        <button
          onClick={toggleTrajectories}
          className={cn(
            'glass-card rounded-xl px-2.5 py-1.5 text-[11px] font-medium inline-flex items-center gap-1.5',
            showTraj ? 'text-electric' : 'text-muted-foreground',
          )}
        >
          <Move className="h-3.5 w-3.5" /> Trajectoires
        </button>
        <button
          onClick={toggleCollisions}
          className={cn(
            'glass-card rounded-xl px-2.5 py-1.5 text-[11px] font-medium inline-flex items-center gap-1.5',
            showCol ? 'text-coral' : 'text-muted-foreground',
          )}
        >
          <Shield className="h-3.5 w-3.5" /> Collisions
        </button>
      </div>

      {/* Selected zone side panel */}
      {selected && (
        <div className="absolute bottom-3 left-3 right-3 md:right-auto md:max-w-xs glass-card rounded-xl p-3 space-y-1.5 shadow-soft">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                Zone
              </div>
              <div className="text-sm font-semibold">{selected.name}</div>
            </div>
            <button
              onClick={() => setSelectedZone(null)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              ✕
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <Cell label="Catégorie" value={selected.category} />
            <Cell label="Type" value={selected.kind} />
            <Cell label="Occupation" value={`${selected.occupancy}%`} accent={colorForOccupancy(selected.occupancy)} />
            <Cell label="Capacité" value={String(selected.capacity)} />
            <Cell label="Articles" value={String(selected.currentItems)} />
            <Cell label="Statut" value={selected.status} />
          </div>
        </div>
      )}
    </div>
  )
}

function Cell({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="font-semibold tabular-nums" style={accent ? { color: accent } : undefined}>{value}</div>
    </div>
  )
}
