import { useEffect, useState } from 'react'
import { Bell, RefreshCw } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useAppStore, type ViewType } from '@/lib/store'

const TITLES: Record<ViewType, { title: string; sub: string }> = {
  overview:  { title: "Vue d'ensemble",  sub: 'Détection · Prédiction · Réaction en temps réel' },
  entries:   { title: 'Entrées / Sorties', sub: 'Flux quotidien sur les quais' },
  zones:     { title: 'Zones',           sub: 'Occupation, statut, catégories' },
  anomalies: { title: 'Anomalies',       sub: 'Événements warning + critical' },
  cameras:   { title: 'Caméras',         sub: 'Vues analytiques temps réel' },
  system:    { title: 'Système',         sub: 'MLflow runs · drift · benchmarks' },
}

export function Header() {
  const view = useAppStore((s) => s.currentView)
  const wsState = useAppStore((s) => s.live.wsState)
  const eventsCount = useAppStore((s) => s.live.events.length)
  const qc = useQueryClient()
  const meta = TITLES[view]

  const [now, setNow] = useState(new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="sticky top-0 z-20 glass border-b border-border">
      <div className="px-6 py-3 flex items-center gap-4">
        <div className="min-w-0">
          <h1 className="text-[15px] font-semibold">{meta.title}</h1>
          <p className="text-[11px] text-muted-foreground truncate">{meta.sub}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="hidden sm:inline-flex font-mono text-xs text-muted-foreground tabular-nums">
            {now.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
          <span className="inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1.5 rounded-lg bg-card ring-1 ring-border">
            <Bell className="h-3.5 w-3.5 text-coral" />
            <span className="font-mono">{eventsCount}</span>
            <span className="text-muted-foreground">events</span>
          </span>
          <span className="text-[11px] px-2.5 py-1.5 rounded-lg bg-card ring-1 ring-border font-mono uppercase tracking-wider">
            ws · {wsState}
          </span>
          <button
            onClick={() => qc.invalidateQueries()}
            className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1.5 rounded-lg bg-card hover:bg-foreground/5 ring-1 ring-border"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Rafraîchir
          </button>
        </div>
      </div>
    </header>
  )
}
