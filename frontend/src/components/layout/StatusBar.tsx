import { useAppStore } from '@/lib/store'
import { cn } from '@/lib/utils'
import { Wifi, Cpu, Database, Globe } from 'lucide-react'
import { useTranslation } from '@/lib/i18n'
import { useKpis } from '@/lib/api'

export function StatusBar() {
  const { lang } = useTranslation()
  const { data } = useKpis()
  const wsState = useAppStore((s) => s.live.wsState)
  const userRole = useAppStore((s) => s.userRole)
  const role = userRole ?? 'worker'
  
  const sys = data?.systemStatus ?? 'offline'

  return (
    <footer className="h-8 shrink-0 bg-card border-t border-border flex items-center justify-between px-4 text-[10px] text-muted-foreground">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <div className={cn(
            'h-1.5 w-1.5 rounded-full',
            wsState === 'live' || sys === 'operational' ? 'bg-emerald shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-coral'
          )} />
          <span className="font-medium uppercase tracking-wider">
            {wsState === 'live' ? 'Live Stream' : sys === 'operational' ? 'Operational' : 'Offline'}
          </span>
        </div>
        <div className="h-3 w-[1px] bg-border/50" />
        <div className="flex items-center gap-1.5">
          <Cpu className="h-3 w-3" />
          <span>Inference: <span className="text-foreground font-semibold">{data?.avgProcessingTime ?? 0}ms</span></span>
        </div>
        <div className="h-3 w-[1px] bg-border/50" />
        <div className="flex items-center gap-1.5">
          <Database className="h-3 w-3" />
          <span>Cameras: <span className="text-foreground font-semibold">{data?.camerasOnline ?? 0}/{data?.totalCameras ?? 0}</span></span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <Globe className="h-3 w-3" />
          <span className="uppercase font-bold text-electric">{lang}</span>
        </div>
        <div className="h-3 w-[1px] bg-border/50" />
        <div className="flex items-center gap-1.5">
          <span className="uppercase font-bold px-1.5 py-0.5 rounded bg-foreground/10 text-foreground">
            {role}
          </span>
        </div>
        <div className="h-3 w-[1px] bg-border/50" />
        <div className="flex items-center gap-1.5">
          <Wifi className="h-3 w-3 text-emerald" />
          <span>v2.4.0-stable</span>
        </div>
      </div>
    </footer>
  )
}
