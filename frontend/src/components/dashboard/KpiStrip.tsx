/**
 * Top-of-overview KPI tiles — 5 cards matching the operator mockup.
 *
 * No fake data: tiles render an em-dash and a "waiting for pipeline"
 * banner appears beneath when pipelineActive is false.
 */
import {
  AlertTriangle, ArrowDownRight, ArrowUpRight, Package, RadioTower, Gauge,
} from 'lucide-react'
import { useKpis } from '@/lib/api'
import { cn, formatNumber } from '@/lib/utils'

interface Tile {
  label: string
  value: string
  icon: typeof Package
  accent: string
  hint?: string
}

export function KpiStrip() {
  const { data, isLoading } = useKpis()
  const live = !!data?.pipelineActive
  const placeholder = '—'

  // Efficiency score = 100 − (anomalies / max(1, today_events) × 100).
  // Operator-friendly proxy: 100% when no anomalies, drops as anomaly rate rises.
  let efficiency = placeholder
  if (live) {
    const total = data!.todayEntries + data!.todayExits + data!.activeAnomalies
    const eff = 100 - (data!.activeAnomalies / Math.max(1, total)) * 100
    efficiency = `${Math.max(0, Math.round(eff))}%`
  }

  const tiles: Tile[] = [
    {
      label: 'Cartons en stock',
      value: live ? formatNumber(data!.totalBoxes) : placeholder,
      icon: Package,
      accent: 'bg-electric',
      hint: live ? `Stock ${data!.stockLevel}%` : 'entries − exits',
    },
    {
      label: "Entrées Aujourd'hui",
      value: live ? formatNumber(data!.todayEntries) : placeholder,
      icon: ArrowDownRight,
      accent: 'bg-emerald',
    },
    {
      label: "Sorties Aujourd'hui",
      value: live ? formatNumber(data!.todayExits) : placeholder,
      icon: ArrowUpRight,
      accent: 'bg-amber',
    },
    {
      label: 'Anomalies Actives',
      value: live ? formatNumber(data!.activeAnomalies) : placeholder,
      icon: AlertTriangle,
      accent: 'bg-coral',
      hint: live ? (data!.activeAnomalies > 0 ? 'à surveiller' : 'tout est calme') : undefined,
    },
    {
      label: 'Efficacité',
      value: efficiency,
      icon: Gauge,
      accent: 'bg-purple',
      hint: live ? '100 − taux d\'anomalies' : 'proxy temps réel',
    },
  ]

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {tiles.map((t) => {
          const Icon = t.icon
          return (
            <div key={t.label} className="glass-card rounded-2xl p-4 relative overflow-hidden shadow-soft">
              <div className={cn('absolute left-0 top-3 bottom-3 w-[2px] rounded-full opacity-70', t.accent)} />
              <div className="pl-3">
                <div className="flex items-center gap-2 mb-1.5 text-xs font-medium text-muted-foreground">
                  <Icon className="h-4 w-4" />
                  <span className="truncate">{t.label}</span>
                </div>
                <div className={cn('text-2xl font-bold tabular-nums', !live && 'text-muted-foreground/60', isLoading && 'opacity-50')}>
                  {t.value}
                </div>
                {t.hint && (
                  <div className="mt-1 text-[11px] text-muted-foreground truncate">{t.hint}</div>
                )}
              </div>
            </div>
          )
        })}
      </div>
      {data && !live && (
        <div className="rounded-xl border border-amber/40 bg-amber/10 text-amber px-3 py-1.5 text-[11px] inline-flex items-center gap-2">
          <RadioTower className="h-3.5 w-3.5" />
          waiting for pipeline — start <code className="font-mono">make frame-grabber</code> + <code className="font-mono">make inference-worker</code> + <code className="font-mono">make cep</code> to fill these tiles
        </div>
      )}
    </div>
  )
}
