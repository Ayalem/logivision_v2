import { useState, useEffect } from 'react'
import { 
  AlertTriangle, 
  Clock, 
  MapPin, 
  Camera, 
  ShieldAlert, 
  CheckCircle2, 
  Timer,
  MessageSquare,
  ChevronRight,
  History
} from 'lucide-react'
import { useAnomalies } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/lib/i18n'
import { useAppStore } from '@/lib/store'

interface SnoozeData {
  alertId: string
  until: number
  reason: string
}

export function AnomaliesPage() {
  const { t } = useTranslation()
  const { data, isLoading } = useAnomalies(80)
  const anomalies = data?.anomalies ?? []
  const userRole = useAppStore(s => s.userRole)
  const isAdmin = userRole === 'admin'
  
  const [activeTab, setActiveTab] = useState<'active' | 'snoozed'>('active')
  const [snoozedAlerts, setSnoozedAlerts] = useState<Record<string, SnoozeData>>(() => {
    const saved = localStorage.getItem('logivision_snoozed')
    return saved ? JSON.parse(saved) : {}
  })
  const [snoozeModal, setSnoozeModal] = useState<string | null>(null)
  const [snoozeDuration, setSnoozeDuration] = useState(15)
  const [snoozeReason, setSnoozeReason] = useState('')

  useEffect(() => {
    localStorage.setItem('logivision_snoozed', JSON.stringify(snoozedAlerts))
  }, [snoozedAlerts])

  // Cleanup expired snoozes
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now()
      let changed = false
      const newSnoozed = { ...snoozedAlerts }
      
      Object.entries(newSnoozed).forEach(([id, data]) => {
        if (now > data.until) {
          delete newSnoozed[id]
          changed = true
        }
      })
      
      if (changed) setSnoozedAlerts(newSnoozed)
    }, 5000)
    return () => clearInterval(interval)
  }, [snoozedAlerts])

  const handleSnooze = (id: string) => {
    const until = Date.now() + snoozeDuration * 60 * 1000
    setSnoozedAlerts(prev => ({
      ...prev,
      [id]: { alertId: id, until, reason: snoozeReason }
    }))
    setSnoozeModal(null)
    setSnoozeReason('')
  }

  const activeAlerts = anomalies.filter(a => !snoozedAlerts[a.id])
  const snoozedItems = anomalies.filter(a => snoozedAlerts[a.id])

  if (isLoading) return <div className="p-12 text-center text-muted-foreground text-xs">Chargement…</div>

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('alerts')}</h1>
          <p className="text-sm text-muted-foreground">Real-time detection of safety and operational violations</p>
        </div>
        
        <div className="flex bg-card/40 p-1 rounded-lg border border-border/50">
          <button 
            onClick={() => setActiveTab('active')}
            className={cn(
              "px-4 py-1.5 text-xs font-semibold rounded-md transition-all",
              activeTab === 'active' ? "bg-electric text-white shadow-lg shadow-electric/20" : "text-muted-foreground hover:text-foreground"
            )}
          >
            Active ({activeAlerts.length})
          </button>
          <button 
            onClick={() => setActiveTab('snoozed')}
            className={cn(
              "px-4 py-1.5 text-xs font-semibold rounded-md transition-all",
              activeTab === 'snoozed' ? "bg-electric text-white shadow-lg shadow-electric/20" : "text-muted-foreground hover:text-foreground"
            )}
          >
            Snoozed ({snoozedItems.length})
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4">
        {(activeTab === 'active' ? activeAlerts : snoozedItems).map((alert) => {
          const snoozeData = snoozedAlerts[alert.id]
          const timeLeft = snoozeData ? Math.max(0, Math.ceil((snoozeData.until - Date.now()) / 60000)) : 0

          return (
            <div 
              key={alert.id}
              className={cn(
                "group relative bg-card border border-border/60 rounded-xl p-5 transition-all interactive-card shadow-soft",
                snoozeData && "opacity-60 grayscale-[0.5]"
              )}
            >
              <div className="flex items-start gap-4">
                <div className={cn(
                  "p-3 rounded-xl border shrink-0",
                  alert.severity === 'critical' ? "bg-coral/10 border-coral/20 text-coral glow-coral" : "bg-amber/10 border-amber/20 text-amber glow-amber"
                )}>
                  <AlertTriangle className="h-5 w-5" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-4 mb-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <h3 className="text-sm font-black text-foreground truncate">{alert.description}</h3>
                      <span className={cn(
                        "status-badge",
                        alert.severity === 'critical' ? "status-badge-critical" : "status-badge-warning"
                      )}>
                        {alert.severity}
                      </span>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-muted-foreground/80 bg-secondary px-2 py-0.5 rounded">
                      {new Date(alert.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </span>
                  </div>
                  
                  <div className="flex flex-wrap items-center gap-2 text-[10px] font-bold text-muted-foreground mb-4">
                    <div className="flex items-center gap-1.5 bg-secondary px-2.5 py-1 rounded-lg border border-border/40">
                      <MapPin className="h-3.5 w-3.5 text-electric/70" />
                      <span>{alert.zone}</span>
                    </div>
                    <div className="flex items-center gap-1.5 bg-secondary px-2.5 py-1 rounded-lg border border-border/40">
                      <Camera className="h-3.5 w-3.5 text-electric/70" />
                      <span className="font-mono">{alert.cameraId}</span>
                    </div>
                    <div className="flex items-center gap-1.5 bg-secondary px-2.5 py-1 rounded-lg border border-border/40">
                      <ShieldAlert className="h-3.5 w-3.5 text-electric/70" />
                      <span>{alert.confidence}% confidence</span>
                    </div>
                  </div>

                  {snoozeData && (
                    <div className="mb-4 p-3 bg-electric/5 border border-electric/20 rounded-lg flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Timer className="h-4 w-4 text-electric" />
                        <span className="text-xs font-semibold text-electric">Snoozed for {timeLeft}m</span>
                        {isAdmin && snoozeData.reason && (
                          <div className="flex items-center gap-1.5 ml-2 pl-3 border-l border-electric/20">
                            <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="text-[10px] text-muted-foreground italic">"{snoozeData.reason}"</span>
                          </div>
                        )}
                      </div>
                      <button 
                        onClick={() => {
                          const newSnoozed = { ...snoozedAlerts }
                          delete newSnoozed[alert.id]
                          setSnoozedAlerts(newSnoozed)
                        }}
                        className="text-[10px] font-bold text-electric hover:underline"
                      >
                        UNSNOOZE
                      </button>
                    </div>
                  )}

                  <div className="flex items-center gap-2 pt-2 border-t border-border/40">
                    {!snoozeData && (
                      <button 
                        onClick={() => setSnoozeModal(alert.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 border border-border/50 text-[10px] font-bold transition-all"
                      >
                        <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                        <span>{t('snooze').toUpperCase()}</span>
                      </button>
                    )}
                    <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-secondary hover:bg-secondary/80 border border-border/50 text-[10px] font-bold transition-all">
                      <CheckCircle2 className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>{t('dismiss').toUpperCase()}</span>
                    </button>
                    <button className="ml-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-electric/10 hover:bg-electric/20 text-[10px] font-bold text-electric transition-all border border-electric/20">
                      <span>{t('viewDetails').toUpperCase()}</span>
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Snooze Modal Popover */}
              {snoozeModal === alert.id && (
                <div className="absolute left-5 bottom-16 w-72 bg-card border border-border shadow-2xl rounded-xl p-4 z-20 animate-in zoom-in-95 backdrop-blur-xl">
                  <h4 className="text-xs font-black uppercase tracking-wider mb-3 text-foreground flex items-center gap-1.5">
                    <Clock className="h-4 w-4 text-electric" /> Snooze Alert
                  </h4>
                  <div className="grid grid-cols-3 gap-2 mb-3">
                    {[15, 30, 60].map(m => (
                      <button 
                        key={m}
                        onClick={() => setSnoozeDuration(m)}
                        className={cn(
                          "py-2 rounded-lg text-[10px] font-bold border transition-all",
                          snoozeDuration === m ? "bg-electric border-electric text-white" : "bg-secondary border-border/50 hover:border-border"
                        )}
                      >
                        {m === 60 ? '1h' : `${m}m`}
                      </button>
                    ))}
                  </div>
                  <textarea 
                    placeholder="Reason (optional)..."
                    value={snoozeReason}
                    onChange={(e) => setSnoozeReason(e.target.value)}
                    className="w-full bg-secondary border border-border/50 rounded-lg p-2.5 text-[11px] mb-3 focus:outline-none focus:border-electric/50 search-glow"
                    rows={2}
                  />
                  <div className="flex gap-2">
                    <button 
                      onClick={() => setSnoozeModal(null)}
                      className="flex-1 py-2 rounded-lg text-[10px] font-bold border border-border/50 hover:bg-secondary transition-all"
                    >
                      {t('cancel')}
                    </button>
                    <button 
                      onClick={() => handleSnooze(alert.id)}
                      className="flex-1 py-2 rounded-lg text-[10px] font-bold bg-electric hover:bg-electric/90 text-white shadow-lg shadow-electric/25 transition-all"
                    >
                      {t('confirm')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
        
        {(activeTab === 'active' ? activeAlerts : snoozedItems).length === 0 && (
          <div className="py-12 text-center border-2 border-dashed border-border/20 rounded-xl">
            <History className="h-8 w-8 text-muted-foreground/20 mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">No {activeTab} alerts found.</p>
          </div>
        )}
      </div>
    </div>
  )
}
