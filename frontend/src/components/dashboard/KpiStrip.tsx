/**
 * Top-of-overview KPI tiles — Total cartons, Entrées, Sorties, Anomalies.
 */
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Package } from 'lucide-react'
import { useKpis } from '@/lib/api'
import { cn, formatNumber } from '@/lib/utils'

interface Tile {
  label: string
  value: string
  icon: typeof Package
  accent: string  // bg color for the left bar
  hint?: string
}

export function KpiStrip() {
  const { data, isLoading } = useKpis()
  const tiles: Tile[] = [
    {
      label: 'Cartons',
      value: data ? formatNumber(data.totalBoxes) : '—',
      icon: Package,
      accent: 'bg-electric',
      hint: data ? `Stock ${data.stockLevel}%` : undefined,
    },
    {
      label: "Entrées Aujourd'hui",
      value: data ? formatNumber(data.todayEntries) : '—',
      icon: ArrowDownRight,
      accent: 'bg-emerald',
    },
    {
      label: "Sorties Aujourd'hui",
      value: data ? formatNumber(data.todayExits) : '—',
      icon: ArrowUpRight,
      accent: 'bg-amber',
    },
    {
      label: 'Anomalies Actives',
      value: data ? formatNumber(data.activeAnomalies) : '—',
      icon: AlertTriangle,
      accent: 'bg-coral',
      hint: data && data.activeAnomalies > 0 ? 'à surveiller' : 'tout est calme',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {tiles.map((t) => {
        const Icon = t.icon
        return (
          <div key={t.label} className="glass-card rounded-2xl p-4 relative overflow-hidden shadow-soft">
            <div className={cn('absolute left-0 top-3 bottom-3 w-[2px] rounded-full opacity-70', t.accent)} />
            <div className="pl-3">
              <div className="flex items-center gap-2 mb-1.5 text-xs font-medium text-muted-foreground">
                <Icon className="h-4 w-4" />
                {t.label}
              </div>
              <div className={cn('text-2xl font-bold tabular-nums', isLoading && 'opacity-50')}>
                {t.value}
              </div>
              {t.hint && (
                <div className="mt-1 text-[11px] text-muted-foreground">{t.hint}</div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
