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
        <div className="glass-card rounded-2xl p-4 shadow-soft interactive-card">
          <div className="text-xs font-bold text-muted-foreground mb-1.5 uppercase tracking-wider">Entrées aujourd'hui</div>
          <div className="text-3xl font-black text-emerald tabular-nums">{kpis?.todayEntries ?? '—'}</div>
        </div>
        <div className="glass-card rounded-2xl p-4 shadow-soft interactive-card">
          <div className="text-xs font-bold text-muted-foreground mb-1.5 uppercase tracking-wider">Sorties aujourd'hui</div>
          <div className="text-3xl font-black text-amber tabular-nums">{kpis?.todayExits ?? '—'}</div>
        </div>
      </div>

      <div className="glass-card rounded-2xl shadow-soft overflow-hidden interactive-card">
        <div className="px-5 py-4 border-b border-border/60 flex items-center justify-between bg-foreground/[0.01]">
          <h2 className="text-sm font-black uppercase tracking-wider">Journal des mouvements</h2>
          <span className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground bg-secondary px-2.5 py-1 rounded-lg border border-border/50">
            {items.length} événements
          </span>
        </div>
        {isLoading ? (
          <div className="p-12 text-center text-xs text-muted-foreground">Chargement…</div>
        ) : items.length === 0 ? (
          <div className="p-12 text-center text-xs text-muted-foreground italic">
            Aucun mouvement détecté. Lancez <code className="font-mono">make cep</code> avec une vidéo en entrée pour générer des événements.
          </div>
        ) : (
          <ul className="divide-y divide-border/60">
            {items.map((it) => (
              <li key={it.id} className="px-5 py-3.5 flex items-center gap-4 hover:bg-foreground/[0.015] transition-colors">
                <div className={cn(
                  'h-9 w-9 rounded-xl flex items-center justify-center border shrink-0',
                  it.type === 'entry' ? 'bg-emerald/10 border-emerald/20 text-emerald glow-emerald' : 'bg-amber/10 border-amber/20 text-amber glow-amber',
                )}>
                  {it.type === 'entry' ? <ArrowDownRight className="h-4 w-4" /> : <ArrowUpRight className="h-4 w-4" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-foreground truncate">{it.message}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] font-mono font-bold text-muted-foreground/80 bg-secondary px-2 py-0.5 rounded border border-border/40">
                      {it.cameraId}
                    </span>
                    <span className="text-[10px] font-bold text-muted-foreground/80 bg-secondary px-2 py-0.5 rounded border border-border/40">
                      {it.zone}
                    </span>
                  </div>
                </div>
                <span className="text-[10px] font-bold text-muted-foreground/60 whitespace-nowrap bg-secondary px-2 py-1 rounded-lg">
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
