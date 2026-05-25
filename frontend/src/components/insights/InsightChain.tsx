/**
 * Narrative AI insight cards — each insight is a vertical chain of steps
 * connected by dashed arrows. Pillar 6 of the design.
 */
import { CheckCircle2, Clock, AlertTriangle, Sparkles } from 'lucide-react'
import { useInsights, type InsightChain as Chain } from '@/lib/api'
import { cn, formatRelativeFR } from '@/lib/utils'

function severityStyles(s: Chain['severity']): { ring: string; badge: string; icon: string } {
  if (s === 'critical') return { ring: 'ring-coral/30', badge: 'bg-coral/15 text-coral', icon: 'text-coral' }
  if (s === 'warning')  return { ring: 'ring-amber/30', badge: 'bg-amber/15 text-amber', icon: 'text-amber' }
  return { ring: 'ring-electric/30', badge: 'bg-electric/15 text-electric', icon: 'text-electric' }
}

function StepIcon({ status }: { status: 'done' | 'pending' | 'failed' }) {
  if (status === 'done') return <CheckCircle2 className="h-3.5 w-3.5 text-emerald" />
  if (status === 'failed') return <AlertTriangle className="h-3.5 w-3.5 text-coral" />
  return <Clock className="h-3.5 w-3.5 text-muted-foreground animate-pulse" />
}

function InsightCard({ chain }: { chain: Chain }) {
  const s = severityStyles(chain.severity)
  return (
    <div className={cn('glass-card rounded-2xl p-4 shadow-soft ring-1', s.ring)}>
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className={cn('h-4 w-4', s.icon)} />
        <span className={cn('text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded', s.badge)}>
          {chain.severity}
        </span>
        <span className="ml-auto text-[10px] text-muted-foreground">
          {formatRelativeFR(chain.timestamp_ms)}
        </span>
      </div>
      <h3 className="text-sm font-semibold mb-3">{chain.title}</h3>
      <ol className="space-y-0">
        {chain.steps.map((step, i) => (
          <li key={i}>
            <div className="flex items-start gap-2">
              <div className="mt-0.5 shrink-0"><StepIcon status={step.status} /></div>
              <div className="text-xs leading-snug">
                <span className={step.status === 'pending' ? 'text-muted-foreground italic' : ''}>
                  {step.label}
                </span>
                {step.ts_ms && (
                  <span className="ml-2 text-[10px] font-mono text-muted-foreground">
                    {new Date(step.ts_ms).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                )}
              </div>
            </div>
            {i < chain.steps.length - 1 && <div className="insight-connector" />}
          </li>
        ))}
      </ol>
      <div className={cn('mt-3 pt-3 border-t border-border/60 text-xs font-medium', s.icon)}>
        → {chain.outcome}
      </div>
    </div>
  )
}

export function InsightRail() {
  const { data, isLoading } = useInsights()
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">AI Insights</h3>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {data?.insights.length ?? 0} actifs
        </span>
      </div>
      {isLoading && <div className="text-xs text-muted-foreground">Analyse en cours…</div>}
      {data?.insights.map((chain) => <InsightCard key={chain.id} chain={chain} />)}
    </div>
  )
}
