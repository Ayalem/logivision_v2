/**
 * Système — admin-only MLOps view.
 *
 * Surfaces every backend system the operator dashboard hides:
 *   - Trained model card  (the LSTM + its held-out metrics)
 *   - MLflow Model Registry (versions per stage)
 *   - MLflow Runs (last 20)
 *   - Kafka topic browser (latest N messages from key topics)
 *   - Drift reports + benchmarks (from docs/mlops/)
 *
 * Mount controlled by App.tsx via useMe() — only role='admin' sees it.
 */
import type { ReactNode } from 'react'
import { Cpu, GitBranch, Database, AlertCircle, Activity, FileText } from 'lucide-react'
import {
  useRegistry, useRuns, useModelInfo,
  useTopicMessages, useDriftReports, useBenchmarks,
} from '@/lib/api'
import { cn } from '@/lib/utils'

const STAGE_STYLES: Record<string, string> = {
  Production: 'bg-emerald/15 text-emerald ring-emerald/30',
  Staging:    'bg-amber/15 text-amber ring-amber/30',
  None:       'bg-muted text-muted-foreground ring-border',
  Archived:   'bg-muted/50 text-muted-foreground line-through ring-border',
}

export function SystemPage() {
  return (
    <div className="space-y-5">
      <TrainedModelCard />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <RegistryCard />
        <RunsCard />
      </div>

      <KafkaTopicsCard />

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <DriftCard />
        <BenchmarksCard />
      </div>
    </div>
  )
}

// ───────── Trained model card ─────────

function TrainedModelCard() {
  const info = useModelInfo()
  const m = info.data
  const lstm = m?.metrics?.lstm
  return (
    <SectionCard
      icon={<Cpu className="h-4 w-4 text-emerald" />}
      title="Trained Model · Congestion LSTM"
      subtitle={m?.training_dataset ?? '—'}
    >
      {info.isLoading ? <Loading />
        : !m?.loaded ? <NoData hint="Model artifact not loaded." />
        : (
          <div className="px-4 py-3 space-y-2">
            <div className="flex flex-wrap gap-2 text-[11px]">
              <Badge className="bg-emerald/15 text-emerald ring-emerald/30">{m.version}</Badge>
              <Badge className="bg-electric/15 text-electric ring-electric/30">{m.architecture}</Badge>
            </div>
            {lstm && (
              <table className="w-full text-xs font-mono tabular-nums">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    <th className="text-left py-1.5">horizon</th>
                    <th className="text-right py-1.5">RMSE</th>
                    <th className="text-right py-1.5">MAE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/40">
                  {Object.entries(lstm).map(([h, v]) => (
                    <tr key={h}>
                      <td className="py-1">{h}</td>
                      <td className="text-right">{v.rmse.toFixed(4)}</td>
                      <td className="text-right">{v.mae.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
    </SectionCard>
  )
}

// ───────── Model Registry ─────────

function RegistryCard() {
  const reg = useRegistry()
  return (
    <SectionCard
      icon={<GitBranch className="h-4 w-4 text-electric" />}
      title="Model Registry"
      subtitle="MLflow versions par stage"
    >
      {reg.isLoading ? <Loading />
        : reg.error ? <ErrorState>MLflow injoignable. <code className="font-mono">make bootstrap</code>.</ErrorState>
        : !reg.data?.models?.length ? <NoData />
        : (
          <ul className="divide-y divide-border">
            {reg.data.models.map((m) => (
              <li key={m.name} className="px-4 py-3">
                <div className="text-sm font-semibold">{m.name}</div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {m.versions.map((v) => (
                    <Badge
                      key={v.version}
                      className={cn('text-[10px] uppercase tracking-wider', STAGE_STYLES[v.stage] ?? STAGE_STYLES.None)}
                    >
                      v{v.version} · {v.stage}
                    </Badge>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
    </SectionCard>
  )
}

// ───────── MLflow Runs ─────────

function RunsCard() {
  const runs = useRuns(20)
  return (
    <SectionCard
      icon={<Activity className="h-4 w-4 text-amber" />}
      title="MLflow Runs"
      subtitle="20 derniers runs"
    >
      {runs.isLoading ? <Loading />
        : runs.error ? <ErrorState>MLflow injoignable.</ErrorState>
        : !runs.data?.runs?.length ? <NoData />
        : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-[10px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="text-left px-4 py-2">Run</th>
                  <th className="text-left px-4 py-2">Exp.</th>
                  <th className="text-left px-4 py-2">Statut</th>
                  <th className="text-right px-4 py-2 font-mono">mAP50</th>
                  <th className="text-right px-4 py-2 font-mono">mAP50_95</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.runs.map((r) => (
                  <tr key={r.run_id} className="border-t border-border">
                    <td className="px-4 py-2 font-mono text-xs">{r.run_id.slice(0, 8)}</td>
                    <td className="px-4 py-2 text-xs truncate max-w-[12ch]">{r.experiment}</td>
                    <td className="px-4 py-2 text-xs">
                      <Badge className={cn(
                        'text-[10px]',
                        r.status === 'FINISHED'  && 'bg-emerald/15 text-emerald ring-emerald/30',
                        r.status === 'FAILED'    && 'bg-coral/15 text-coral ring-coral/30',
                        r.status === 'RUNNING'   && 'bg-electric/15 text-electric ring-electric/30',
                      )}>{r.status}</Badge>
                    </td>
                    <td className="px-4 py-2 font-mono text-xs tabular-nums text-right">{r.metrics?.val_map50?.toFixed(3) ?? '—'}</td>
                    <td className="px-4 py-2 font-mono text-xs tabular-nums text-right">{r.metrics?.val_map50_95?.toFixed(3) ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </SectionCard>
  )
}

// ───────── Kafka topics ─────────

function KafkaTopicsCard() {
  const topics = ['events', 'detections', 'raw-frames']
  return (
    <SectionCard
      icon={<Database className="h-4 w-4 text-coral" />}
      title="Kafka Topics"
      subtitle="3 derniers messages par topic — rafraîchi toutes les 5 s"
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 p-4">
        {topics.map((t) => <KafkaTopicTile key={t} topic={t} />)}
      </div>
    </SectionCard>
  )
}

function KafkaTopicTile({ topic }: { topic: string }) {
  const q = useTopicMessages(topic, 3)
  return (
    <div className="rounded-xl bg-muted/30 ring-1 ring-border p-3 space-y-2">
      <div className="flex items-center justify-between">
        <code className="text-xs font-mono font-semibold">{topic}</code>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {q.data?.degraded ? 'kafka offline' : `${q.data?.messages?.length ?? 0} msg`}
        </span>
      </div>
      {q.isLoading ? <div className="text-[11px] text-muted-foreground italic">Chargement…</div>
        : q.error || q.data?.degraded ? <div className="text-[11px] text-amber italic">Kafka injoignable.</div>
        : !q.data?.messages?.length ? <div className="text-[11px] text-muted-foreground italic">Topic vide — démarrez le pipeline.</div>
        : (
          <ul className="space-y-1.5">
            {q.data.messages.slice(0, 3).map((msg, i) => (
              <li key={i} className="text-[10px] font-mono leading-snug text-muted-foreground rounded bg-background/60 px-2 py-1 truncate">
                {JSON.stringify(msg).slice(0, 110)}…
              </li>
            ))}
          </ul>
        )}
    </div>
  )
}

// ───────── Drift / Benchmarks ─────────

function DriftCard() {
  const q = useDriftReports()
  return (
    <SectionCard
      icon={<AlertCircle className="h-4 w-4 text-amber" />}
      title="Drift Reports"
      subtitle="docs/mlops/drift/"
    >
      <ReportList state={q} kind="drift" />
    </SectionCard>
  )
}

function BenchmarksCard() {
  const q = useBenchmarks()
  return (
    <SectionCard
      icon={<FileText className="h-4 w-4 text-electric" />}
      title="Benchmarks"
      subtitle="docs/mlops/benchmarks/"
    >
      <ReportList state={q} kind="benchmark" />
    </SectionCard>
  )
}

function ReportList({ state, kind }: { state: ReturnType<typeof useDriftReports>; kind: 'drift' | 'benchmark' }) {
  if (state.isLoading) return <Loading />
  if (state.error)     return <ErrorState>Erreur de chargement.</ErrorState>
  const reports = state.data?.reports ?? []
  if (!reports.length) return <NoData hint={`Aucun rapport ${kind} pour l'instant.`} />
  return (
    <ul className="divide-y divide-border">
      {reports.map((r) => (
        <li key={r.name} className="px-4 py-2.5 flex items-center justify-between text-xs">
          <span className="font-mono truncate">{r.name}</span>
          <span className="text-muted-foreground tabular-nums shrink-0">{Math.round(r.size_bytes / 1024)} KB</span>
        </li>
      ))}
    </ul>
  )
}

// ───────── Primitives ─────────

function SectionCard({
  icon, title, subtitle, children,
}: { icon: ReactNode; title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="glass-card rounded-2xl shadow-soft overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center gap-2">
        {icon}
        <div>
          <h2 className="text-sm font-semibold leading-tight">{title}</h2>
          {subtitle && <p className="text-[11px] text-muted-foreground">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

function Badge({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span className={cn('inline-block px-1.5 py-0.5 rounded ring-1', className)}>{children}</span>
  )
}

function Loading() { return <div className="p-4 text-xs text-muted-foreground italic">Chargement…</div> }
function NoData({ hint }: { hint?: string }) { return <div className="p-4 text-xs text-muted-foreground italic">{hint ?? 'Aucune donnée pour le moment.'}</div> }
function ErrorState({ children }: { children: ReactNode }) { return <div className="p-4 text-xs text-coral">{children}</div> }
