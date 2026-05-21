import { useKpis } from '@/lib/api'
import { cn } from '@/lib/utils'

export function StatusBar() {
  const { data } = useKpis()
  const sys = data?.systemStatus ?? 'offline'
  return (
    <footer className="hidden md:flex items-center gap-4 px-6 py-1.5 text-[10px] uppercase tracking-wider font-mono text-muted-foreground border-t border-border bg-card/40">
      <span className="inline-flex items-center gap-1.5">
        <span className={cn(
          'h-1.5 w-1.5 rounded-full',
          sys === 'operational' ? 'bg-emerald animate-pulse-live'
            : sys === 'degraded' ? 'bg-amber' : 'bg-coral',
        )} />
        Système · {sys}
      </span>
      <span>Caméras: {data?.camerasOnline ?? 0}/{data?.totalCameras ?? 0}</span>
      <span>Stock: {data?.stockLevel ?? 0}%</span>
      <span>Inférence: {data?.avgProcessingTime ?? 0} ms</span>
      <span className="ml-auto">LOGIVISION v0.1 · 2026</span>
    </footer>
  )
}
