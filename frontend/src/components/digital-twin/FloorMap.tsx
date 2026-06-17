/**
 * FloorMap — top-down 2D plan of the warehouse, driven by the real zone
 * geometry from GET /api/zones (normalised 0..1 polygons). Click a zone to
 * open a detail side-panel (occupancy, kind, capacity, live status). Light,
 * clean styling inspired by the AGV fleet-management reference UI.
 *
 * This complements the 3D R3F DigitalTwin with a flat, readable plan view —
 * the same real zone data, projected to a top-down SVG.
 */
import { useState } from 'react'
import { MapPin, Layers, ArrowRightLeft, Ban, Boxes } from 'lucide-react'
import { useZones } from '@/lib/api'

const KIND_META: Record<string, { color: string; label: string; Icon: typeof Layers }> = {
  entry: { color: '#10B981', label: 'Entrée', Icon: ArrowRightLeft },
  exit: { color: '#F59E0B', label: 'Sortie', Icon: ArrowRightLeft },
  forbidden: { color: '#EF4444', label: 'Interdite', Icon: Ban },
  shelf: { color: '#0EA5E9', label: 'Stockage', Icon: Boxes },
}

function occColor(pct: number | null | undefined): string {
  if (pct == null) return '#94A3B8'
  if (pct >= 90) return '#EF4444'
  if (pct >= 70) return '#F59E0B'
  if (pct >= 50) return '#06B6D4'
  return '#10B981'
}

function centroid(poly: { x: number; y: number }[]): { x: number; y: number } {
  if (!poly.length) return { x: 0.5, y: 0.5 }
  const sx = poly.reduce((a, p) => a + p.x, 0) / poly.length
  const sy = poly.reduce((a, p) => a + p.y, 0) / poly.length
  return { x: sx, y: sy }
}

export function FloorMap() {
  const { data, isLoading } = useZones()
  const zones = data?.zones ?? []
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const selected = zones.find((z) => z.id === selectedId) ?? null

  return (
    <div className="rounded-xl border border-border/60 bg-card/60 backdrop-blur-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/50">
        <div className="flex items-center gap-2">
          <MapPin className="h-4 w-4 text-electric" />
          <h3 className="text-sm font-semibold">Plan de l'entrepôt — vue de dessus</h3>
        </div>
        <span className="text-[11px] text-muted-foreground">{zones.length} zones · cliquez pour les détails</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3">
        {/* ── Map ─────────────────────────────────────────────── */}
        <div className="lg:col-span-2 p-4">
          <svg
            viewBox="0 0 100 100"
            className="w-full rounded-lg ring-1 ring-border/50"
            style={{ aspectRatio: '1 / 1', background: '#F8FAFC' }}
          >
            <defs>
              <pattern id="grid" width="5" height="5" patternUnits="userSpaceOnUse">
                <path d="M 5 0 L 0 0 0 5" fill="none" stroke="#E2E8F0" strokeWidth="0.3" />
              </pattern>
            </defs>
            <rect width="100" height="100" fill="url(#grid)" />
            <rect width="100" height="100" fill="none" stroke="#CBD5E1" strokeWidth="0.6" />

            {zones.map((z) => {
              const poly = z.polygon ?? []
              if (!poly.length) return null
              const pts = poly.map((p) => `${p.x * 100},${p.y * 100}`).join(' ')
              const c = centroid(poly)
              const isSel = z.id === selectedId
              const fill = z.occupancy != null ? occColor(z.occupancy) : KIND_META[z.kind]?.color ?? '#94A3B8'
              return (
                <g
                  key={z.id}
                  onClick={() => setSelectedId(z.id)}
                  style={{ cursor: 'pointer' }}
                >
                  <polygon
                    points={pts}
                    fill={fill}
                    fillOpacity={isSel ? 0.55 : 0.28}
                    stroke={fill}
                    strokeWidth={isSel ? 1.4 : 0.8}
                  />
                  <text
                    x={c.x * 100}
                    y={c.y * 100}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="3"
                    fontWeight="600"
                    fill="#0F172A"
                  >
                    {z.name}
                  </text>
                  {z.live && (
                    <circle cx={c.x * 100 + 9} cy={c.y * 100 - 4} r="1" fill="#10B981">
                      <animate attributeName="opacity" values="1;0.3;1" dur="1.6s" repeatCount="indefinite" />
                    </circle>
                  )}
                </g>
              )
            })}
          </svg>
          {isLoading && <p className="text-xs text-muted-foreground mt-2">Chargement des zones…</p>}
          <div className="flex flex-wrap gap-3 mt-3">
            {Object.entries(KIND_META).map(([k, m]) => (
              <span key={k} className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: m.color }} /> {m.label}
              </span>
            ))}
          </div>
        </div>

        {/* ── Side detail panel ───────────────────────────────── */}
        <div className="border-t lg:border-t-0 lg:border-l border-border/50 p-4 bg-card/40">
          {selected ? (
            <ZoneDetail zone={selected} />
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-center text-muted-foreground py-10">
              <Layers className="h-8 w-8 mb-2 opacity-40" />
              <p className="text-xs">Sélectionnez une zone sur le plan<br />pour voir ses détails</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function ZoneDetail({ zone }: { zone: NonNullable<ReturnType<typeof useZones>['data']>['zones'][number] }) {
  const meta = KIND_META[zone.kind] ?? KIND_META.shelf
  const occ = zone.occupancy
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-sm font-semibold">{zone.name}</h4>
          <p className="text-[11px] text-muted-foreground">{zone.category || '—'}</p>
        </div>
        <span
          className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded-md"
          style={{ background: `${meta.color}22`, color: meta.color }}
        >
          <meta.Icon className="h-3 w-3" /> {meta.label}
        </span>
      </div>

      <div>
        <div className="flex items-center justify-between text-[11px] mb-1">
          <span className="text-muted-foreground">Occupation</span>
          <span className="font-mono font-semibold" style={{ color: occColor(occ) }}>
            {occ != null ? `${occ}%` : '—'}
          </span>
        </div>
        <div className="h-2 rounded-full bg-foreground/10 overflow-hidden">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${occ ?? 0}%`, background: occColor(occ) }}
          />
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-2 text-[11px]">
        <Cell label="Capacité" value={String(zone.capacity ?? '—')} />
        <Cell label="Articles" value={zone.currentItems != null ? String(zone.currentItems) : '—'} />
        <Cell label="Statut" value={zone.status || 'inconnu'} />
        <Cell label="Flux live" value={zone.live ? 'actif' : 'inactif'} />
      </dl>

      {!zone.live && (
        <p className="text-[10px] text-muted-foreground border-t border-border/50 pt-2">
          Aucun flux temps-réel sur cette zone — démarrez le pipeline pour des données live.
        </p>
      )}
    </div>
  )
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-foreground/[0.03] ring-1 ring-border/40 px-2.5 py-1.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium capitalize">{value}</dd>
    </div>
  )
}
