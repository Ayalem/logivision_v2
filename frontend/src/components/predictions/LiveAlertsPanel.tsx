/**
 * LIVE ALERTS panel — right-rail card showing the most recent CEP events.
 *
 * Severity → colour:
 *   critical  → coral (zone_violation, box_falling, collision_risk)
 *   warning   → amber (stationary_object, congestion_forecast)
 *   info      → electric (entry, exit — usually filtered out here)
 *
 * Reads /api/anomalies (the Anomalies feed) so events appear here AND on
 * the Anomalies page consistently. No fake fallback: empty list when the
 * pipeline isn't running.
 */
import { AlertTriangle, ShieldAlert, Clock } from 'lucide-react'
import { useAnomalies } from '@/lib/api'
import { cn, formatRelativeFR } from '@/lib/utils'

const SEV_STYLE: Record<string, { dot: string; tag: string }> = {
  critical: { dot: 'bg-coral',    tag: 'text-coral border-coral/40 bg-coral/10' },
  warning:  { dot: 'bg-amber',    tag: 'text-amber border-amber/40 bg-amber/10' },
  info:     { dot: 'bg-electric', tag: 'text-electric border-electric/40 bg-electric/10' },
}

export function LiveAlertsPanel() {
  const { data, isLoading } = useAnomalies(8)
  const items = (data?.anomalies ?? []).filter((a) => a.severity !== 'info').slice(0, 6)

  return (
    <div className="glass-card rounded-2xl p-4 shadow-soft space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold inline-flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-coral" /> Live Alerts
        </h3>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {items.length === 0 ? 'aucune' : `${items.length} actives`}
        </span>
      </div>
      {isLoading ? (
        <p className="text-xs text-muted-foreground italic">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">
          Aucune alerte — pipeline silencieux ou tout est calme.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((a) => {
            const sev = SEV_STYLE[a.severity] ?? SEV_STYLE.info
            return (
              <li key={a.id} className="rounded-xl bg-muted/30 ring-1 ring-border px-3 py-2">
                <div className="flex items-start gap-2">
                  <span className={cn('mt-1.5 h-1.5 w-1.5 rounded-full shrink-0 animate-pulse-live', sev.dot)} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={cn('text-[9px] uppercase tracking-wider px-1.5 py-px rounded border', sev.tag)}>
                        {a.severity}
                      </span>
                      <span className="text-xs font-medium truncate">{a.type.replace(/_/g, ' ')}</span>
                    </div>
                    <div className="text-[11px] text-muted-foreground truncate mt-0.5">
                      <AlertTriangle className="h-3 w-3 inline-block mr-1 -mt-0.5 opacity-50" />
                      {a.cameraId ?? '—'} · {a.zone ?? '—'}
                    </div>
                    <div className="text-[10px] text-muted-foreground/80 mt-0.5 inline-flex items-center gap-1">
                      <Clock className="h-2.5 w-2.5" />
                      {formatRelativeFR(a.timestamp)}
                    </div>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
