import { useRegistry, useRuns } from '@/lib/api'
import { cn } from '@/lib/utils'

const STAGE_STYLES: Record<string, string> = {
  Production: 'bg-emerald/15 text-emerald ring-emerald/30',
  Staging:    'bg-amber/15 text-amber ring-amber/30',
  None:       'bg-muted text-muted-foreground ring-border',
  Archived:   'bg-muted/50 text-muted-foreground line-through ring-border',
}

export function SystemPage() {
  const reg = useRegistry()
  const runs = useRuns(20)

  return (
    <div className="space-y-5">
      <div className="glass-card rounded-2xl shadow-soft overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold">Model Registry</h2>
          <p className="text-[11px] text-muted-foreground">Modèles enregistrés dans MLflow et leurs versions</p>
        </div>
        {reg.isLoading ? <div className="p-4 text-xs text-muted-foreground">Chargement…</div>
          : reg.error ? <div className="p-4 text-xs text-coral">MLflow injoignable — démarrez-le avec <code className="font-mono">make bootstrap</code>.</div>
          : (reg.data?.models?.length ?? 0) === 0 ? <div className="p-4 text-xs text-muted-foreground italic">Aucun modèle enregistré.</div>
          : (
            <ul className="divide-y divide-border">
              {reg.data!.models.map((m) => (
                <li key={m.name} className="px-4 py-3">
                  <div className="text-sm font-semibold">{m.name}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    {m.versions.map((v) => (
                      <span
                        key={v.version}
                        className={cn(
                          'text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded ring-1',
                          STAGE_STYLES[v.stage] ?? STAGE_STYLES.None,
                        )}
                      >
                        v{v.version} · {v.stage}
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
      </div>

      <div className="glass-card rounded-2xl shadow-soft overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <h2 className="text-sm font-semibold">Derniers runs MLflow</h2>
          <p className="text-[11px] text-muted-foreground">Triés par recency</p>
        </div>
        {runs.isLoading ? <div className="p-4 text-xs text-muted-foreground">Chargement…</div>
          : runs.error ? <div className="p-4 text-xs text-coral">MLflow injoignable.</div>
          : (runs.data?.runs?.length ?? 0) === 0 ? <div className="p-4 text-xs text-muted-foreground italic">Aucun run trouvé.</div>
          : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  <th className="text-left px-4 py-2">Run</th>
                  <th className="text-left px-4 py-2">Exp.</th>
                  <th className="text-left px-4 py-2">Statut</th>
                  <th className="text-left px-4 py-2 font-mono">map50</th>
                  <th className="text-left px-4 py-2 font-mono">map50_95</th>
                </tr>
              </thead>
              <tbody>
                {runs.data!.runs.map((r) => (
                  <tr key={r.run_id} className="border-t border-border">
                    <td className="px-4 py-2 font-mono text-xs">{r.run_id.slice(0, 8)}</td>
                    <td className="px-4 py-2 text-xs">{r.experiment}</td>
                    <td className="px-4 py-2 text-xs">{r.status}</td>
                    <td className="px-4 py-2 font-mono text-xs tabular-nums">{r.metrics?.val_map50?.toFixed(3) ?? '—'}</td>
                    <td className="px-4 py-2 font-mono text-xs tabular-nums">{r.metrics?.val_map50_95?.toFixed(3) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </div>
  )
}
