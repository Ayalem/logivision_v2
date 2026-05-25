import { AlertTriangle, ShieldAlert } from 'lucide-react'
import { useAnomalies } from '@/lib/api'
import { cn, formatRelativeFR } from '@/lib/utils'

export function AnomaliesPage() {
  const { data, isLoading } = useAnomalies(80)
  const anomalies = data?.anomalies ?? []

  return (
    <div className="space-y-4">
      <div className="glass-card rounded-2xl p-4 shadow-soft">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Anomalies détectées</h2>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {anomalies.length} entrées
          </span>
        </div>
      </div>

      {isLoading ? (
        <div className="p-6 text-xs text-muted-foreground">Chargement…</div>
      ) : anomalies.length === 0 ? (
        <div className="glass-card rounded-2xl p-8 text-center text-xs text-muted-foreground italic">
          Aucune anomalie active — bonne nouvelle.
        </div>
      ) : (
        <ul className="space-y-2">
          {anomalies.map((a) => {
            const sev = a.severity === 'critical' ? 'coral' : 'amber'
            return (
              <li key={a.id} className="glass-card rounded-2xl p-3 shadow-soft flex items-start gap-3">
                <div className={cn(
                  'h-9 w-9 rounded-lg flex items-center justify-center shrink-0',
                  sev === 'coral' ? 'bg-coral/15 text-coral' : 'bg-amber/15 text-amber',
                )}>
                  {sev === 'coral' ? <ShieldAlert className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{a.description}</div>
                  <div className="text-[10px] font-mono text-muted-foreground mt-0.5">
                    {a.cameraId} · {a.zone} · {a.eventType}
                  </div>
                </div>
                <div className="text-right">
                  <div className={cn(
                    'text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded inline-block',
                    sev === 'coral' ? 'bg-coral/15 text-coral' : 'bg-amber/15 text-amber',
                  )}>
                    {a.severity}
                  </div>
                  <div className="text-[10px] text-muted-foreground mt-1 whitespace-nowrap">
                    {formatRelativeFR(a.timestamp)}
                  </div>
                  <div className="text-[10px] font-mono text-muted-foreground">
                    {a.confidence}% conf.
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
