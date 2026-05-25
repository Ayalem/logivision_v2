/**
 * Predicted congestion rail — Google-Maps style ETAs.
 */
import { TrendingUp } from 'lucide-react'
import { usePredictions } from '@/lib/api'
import { cn } from '@/lib/utils'

function severityColor(eta: number): string {
  if (eta <= 60)  return 'text-coral'
  if (eta <= 180) return 'text-amber'
  return 'text-electric'
}

export function CongestionPanel() {
  const { data } = usePredictions()
  const items = data?.buckets.congestion ?? []
  // Show the LSTM badge as soon as ANY congestion event is tagged with
  // the trained-model source. Falls back to "rule v0" otherwise.
  const usesLstm = items.some((c) => c.forecast_source === 'lstm-prsa-v1')
  const badgeLabel = usesLstm ? 'LSTM · PRSA · v1' : 'rule v0'
  const badgeClass = usesLstm
    ? 'bg-emerald/20 text-emerald border-emerald/40'
    : 'bg-amber/15 text-amber border-amber/30'
  return (
    <div className="glass-card rounded-2xl p-4 shadow-soft space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold inline-flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-amber" /> Congestion prévue
          <span className={cn('inline-block rounded border px-1.5 py-px text-[9px] uppercase tracking-wider', badgeClass)}>
            {badgeLabel}
          </span>
        </h3>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {items.length === 0 ? 'aucune' : `${items.length} alertes`}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">Aucune congestion anticipée — flux fluide.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((c) => {
            const pct = Math.max(0, Math.min(100, (c.eta_seconds / 240) * 100))
            return (
              <li key={c.event_id} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium">{c.zone.replace(/_/g, ' ')}</span>
                  <span className={cn('font-mono font-semibold', severityColor(c.eta_seconds))}>
                    ETA {c.eta_seconds}s
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div
                    className={cn(
                      'h-full rounded-full transition-all duration-500',
                      c.eta_seconds <= 60 ? 'bg-coral'
                        : c.eta_seconds <= 180 ? 'bg-amber' : 'bg-electric',
                    )}
                    style={{ width: `${100 - pct}%` }}
                  />
                </div>
                <div className="text-[10px] text-muted-foreground">
                  Densité {(c.density * 100).toFixed(0)}% · confiance {(c.confidence * 100).toFixed(0)}%
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
