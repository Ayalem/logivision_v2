import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { useEntriesExits, useKpis } from '@/lib/api'
import { cn, formatRelativeFR } from '@/lib/utils'

export function EntriesPage() {
  const { data: kpis } = useKpis()
  const { data, isLoading } = useEntriesExits(80)
  const items = data?.items ?? []

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3">
        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="text-xs text-muted-foreground mb-1">Entrées aujourd'hui</div>
          <div className="text-3xl font-bold text-emerald tabular-nums">{kpis?.todayEntries ?? '—'}</div>
        </div>
        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="text-xs text-muted-foreground mb-1">Sorties aujourd'hui</div>
          <div className="text-3xl font-bold text-amber tabular-nums">{kpis?.todayExits ?? '—'}</div>
        </div>
      </div>

      <div className="glass-card rounded-2xl shadow-soft overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold">Journal des mouvements</h2>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {items.length} événements
          </span>
        </div>
        {isLoading ? (
          <div className="p-6 text-xs text-muted-foreground">Chargement…</div>
        ) : items.length === 0 ? (
          <div className="p-6 text-xs text-muted-foreground italic">
            Aucun mouvement détecté. Lancez <code className="font-mono">make cep</code> avec une vidéo en entrée pour générer des événements.
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((it) => (
              <li key={it.id} className="px-4 py-2.5 flex items-center gap-3 hover:bg-foreground/[0.02]">
                <div className={cn(
                  'h-8 w-8 rounded-lg flex items-center justify-center',
                  it.type === 'entry' ? 'bg-emerald/15 text-emerald' : 'bg-amber/15 text-amber',
                )}>
                  {it.type === 'entry' ? <ArrowDownRight className="h-4 w-4" /> : <ArrowUpRight className="h-4 w-4" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate">{it.message}</div>
                  <div className="text-[10px] font-mono text-muted-foreground">
                    {it.cameraId} · {it.zone}
                  </div>
                </div>
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                  {formatRelativeFR(it.timestamp)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
