import { useEffect, useState } from 'react'
import { Bell, RefreshCw, Search, Settings, User, ChevronDown, LogOut, UserCircle, Cog } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useAppStore, type ViewType } from '@/lib/store'
import { useMe } from '@/lib/api'
import { cn } from '@/lib/utils'

const TITLES: Record<ViewType, { title: string; sub: string }> = {
  overview:  { title: "Vue d'ensemble",  sub: 'Détection · Prédiction · Réaction en temps réel' },
  entries:   { title: 'Entrées / Sorties', sub: 'Flux quotidien sur les quais' },
  zones:     { title: 'Zones',           sub: 'Occupation, statut, catégories' },
  anomalies: { title: 'Anomalies',       sub: 'Événements warning + critical' },
  cameras:   { title: 'Caméras',         sub: 'Vues analytiques temps réel' },
  system:    { title: 'Système',         sub: 'MLflow runs · drift · benchmarks' },
  analytics: { title: 'Analyses',        sub: 'Indicateurs de performance et statistiques' },
  inventory: { title: 'Inventaire',      sub: 'Gestion des stocks et emplacements' },
  workforce: { title: 'Personnel',       sub: 'Suivi de la productivité et sécurité' },
}

export function Header() {
  const view = useAppStore((s) => s.currentView)
  const wsState = useAppStore((s) => s.live.wsState)
  const events = useAppStore((s) => s.live.events)
  const qc = useQueryClient()
  const meta = TITLES[view]
  const me = useMe()
  const role = me.data?.role ?? 'operator'
  const userName = me.data?.name ?? role
  
  const [now, setNow] = useState(new Date())
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  const dateStr = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

  // Filter events by severity for notifications
  const criticalAlerts = events.filter(e => e.severity === 'critical')
  const warningAlerts = events.filter(e => e.severity === 'warning')
  const infoAlerts = events.filter(e => e.severity === 'info')

  const handleLogout = () => {
    useAppStore.getState().logout()
    setSettingsOpen(false)
  }

  const handleRefresh = () => {
    qc.invalidateQueries()
  }

  return (
    <header className="sticky top-0 z-20 glass border-b border-border/50">
      <div className="px-6 py-4 flex items-center justify-between gap-4">
        {/* Left: Warehouse selector and date/time */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-3 py-2 rounded-lg bg-card/40 hover:bg-card/60 transition-colors text-sm font-medium">
              <span>Warehouse</span>
              <span className="text-xs text-muted-foreground">Alpha-01</span>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </button>
          </div>
          <div className="flex items-center gap-4 text-xs text-muted-foreground font-mono">
            <div>
              <span className="text-muted-foreground">DATE</span>
              <div className="text-foreground font-semibold">{dateStr}</div>
            </div>
            <div>
              <span className="text-muted-foreground">TIME</span>
              <div className="text-foreground font-semibold">{timeStr}</div>
            </div>
          </div>
        </div>

        {/* Right: System status, alerts, and controls */}
        <div className="flex items-center gap-3">
          {/* System Status */}
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald/10 border border-emerald/30">
            <div className="h-2 w-2 rounded-full bg-emerald animate-pulse" />
            <span className="text-xs font-semibold text-emerald">SYSTEM STATUS</span>
            <span className="text-xs text-emerald/80">AI ACTIVE</span>
          </div>

          {/* Search */}
          <button className="p-2 rounded-lg hover:bg-card/60 transition-colors text-muted-foreground hover:text-foreground">
            <Search className="h-4 w-4" />
          </button>

          {/* Refresh */}
          <button 
            onClick={handleRefresh}
            className="p-2 rounded-lg hover:bg-card/60 transition-colors text-muted-foreground hover:text-foreground"
          >
            <RefreshCw className="h-4 w-4" />
          </button>

          {/* Notifications */}
          <div className="relative">
            <button 
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className="relative p-2 rounded-lg hover:bg-card/60 transition-colors text-muted-foreground hover:text-foreground"
            >
              <Bell className="h-4 w-4" />
              {events.length > 0 && (
                <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-coral animate-pulse" />
              )}
            </button>

            {/* Notifications Dropdown */}
            {notificationsOpen && (
              <div className="absolute right-0 mt-2 w-80 bg-card border border-border/50 rounded-lg shadow-lg overflow-hidden z-50">
                <div className="px-4 py-3 border-b border-border/30 bg-card/50">
                  <h3 className="text-sm font-semibold">Notifications d'alertes</h3>
                  <p className="text-xs text-muted-foreground mt-1">{events.length} événements</p>
                </div>

                {events.length === 0 ? (
                  <div className="px-4 py-6 text-center text-xs text-muted-foreground">
                    Aucune alerte pour le moment
                  </div>
                ) : (
                  <div className="max-h-96 overflow-y-auto">
                    {/* Critical Alerts */}
                    {criticalAlerts.length > 0 && (
                      <>
                        <div className="px-4 py-2 bg-coral/5 border-b border-border/30">
                          <p className="text-xs font-semibold text-coral uppercase">Critiques ({criticalAlerts.length})</p>
                        </div>
                        <ul className="divide-y divide-border/30">
                          {criticalAlerts.slice(0, 3).map((evt) => (
                            <li key={evt.event_id} className="px-4 py-2 hover:bg-foreground/5 transition-colors">
                              <div className="flex items-start gap-2">
                                <div className="h-2 w-2 rounded-full bg-coral mt-1 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs font-medium text-coral truncate">{evt.event_type}</p>
                                  <p className="text-[10px] text-muted-foreground mt-0.5">
                                    {new Date(evt.timestamp_ms).toLocaleTimeString('fr-FR')}
                                  </p>
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}

                    {/* Warning Alerts */}
                    {warningAlerts.length > 0 && (
                      <>
                        <div className="px-4 py-2 bg-amber/5 border-b border-border/30">
                          <p className="text-xs font-semibold text-amber uppercase">Avertissements ({warningAlerts.length})</p>
                        </div>
                        <ul className="divide-y divide-border/30">
                          {warningAlerts.slice(0, 3).map((evt) => (
                            <li key={evt.event_id} className="px-4 py-2 hover:bg-foreground/5 transition-colors">
                              <div className="flex items-start gap-2">
                                <div className="h-2 w-2 rounded-full bg-amber mt-1 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs font-medium text-amber truncate">{evt.event_type}</p>
                                  <p className="text-[10px] text-muted-foreground mt-0.5">
                                    {new Date(evt.timestamp_ms).toLocaleTimeString('fr-FR')}
                                  </p>
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}

                    {/* Info Alerts */}
                    {infoAlerts.length > 0 && (
                      <>
                        <div className="px-4 py-2 bg-teal/5 border-b border-border/30">
                          <p className="text-xs font-semibold text-teal uppercase">Informations ({infoAlerts.length})</p>
                        </div>
                        <ul className="divide-y divide-border/30">
                          {infoAlerts.slice(0, 3).map((evt) => (
                            <li key={evt.event_id} className="px-4 py-2 hover:bg-foreground/5 transition-colors">
                              <div className="flex items-start gap-2">
                                <div className="h-2 w-2 rounded-full bg-teal mt-1 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="text-xs font-medium text-teal truncate">{evt.event_type}</p>
                                  <p className="text-[10px] text-muted-foreground mt-0.5">
                                    {new Date(evt.timestamp_ms).toLocaleTimeString('fr-FR')}
                                  </p>
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}

                <div className="px-4 py-2 border-t border-border/30 bg-card/50">
                  <button className="w-full text-xs text-center text-muted-foreground hover:text-foreground transition-colors py-1">
                    Voir toutes les alertes →
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Settings */}
          <div className="relative">
            <button 
              onClick={() => setSettingsOpen(!settingsOpen)}
              className="p-2 rounded-lg hover:bg-card/60 transition-colors text-muted-foreground hover:text-foreground"
            >
              <Settings className="h-4 w-4" />
            </button>

            {/* Settings Dropdown */}
            {settingsOpen && (
              <div className="absolute right-0 mt-2 w-48 bg-card border border-border/50 rounded-lg shadow-lg overflow-hidden z-50">
                <div className="px-4 py-2 border-b border-border/30 bg-card/50">
                  <p className="text-xs font-semibold">Paramètres</p>
                </div>
                <ul className="divide-y divide-border/30">
                  <li>
                    <button className="w-full px-4 py-2 text-left text-xs hover:bg-foreground/5 transition-colors flex items-center gap-2">
                      <Cog className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>Préférences</span>
                    </button>
                  </li>
                  <li>
                    <button className="w-full px-4 py-2 text-left text-xs hover:bg-foreground/5 transition-colors flex items-center gap-2">
                      <UserCircle className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>Compte</span>
                    </button>
                  </li>
                  <li className="border-t border-border/30">
                    <button 
                      onClick={handleLogout}
                      className="w-full px-4 py-2 text-left text-xs hover:bg-coral/10 transition-colors flex items-center gap-2 text-coral"
                    >
                      <LogOut className="h-3.5 w-3.5" />
                      <span>Déconnexion</span>
                    </button>
                  </li>
                </ul>
              </div>
            )}
          </div>

          {/* User profile */}
          <div className="relative">
            <button 
              onClick={() => setProfileOpen(!profileOpen)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-card/60 transition-colors"
            >
              <div className="h-6 w-6 rounded-full bg-gradient-to-br from-electric/20 to-teal/20 border border-electric/30 flex items-center justify-center">
                <User className="h-3.5 w-3.5 text-electric" />
              </div>
              <span className="text-xs font-medium capitalize">{role}</span>
            </button>

            {/* Profile Dropdown */}
            {profileOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-card border border-border/50 rounded-lg shadow-lg overflow-hidden z-50">
                <div className="px-4 py-4 border-b border-border/30 bg-card/50">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-gradient-to-br from-electric/20 to-teal/20 border border-electric/30 flex items-center justify-center">
                      <User className="h-5 w-5 text-electric" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold truncate capitalize">{userName}</p>
                      <p className="text-xs text-muted-foreground capitalize">{role}</p>
                    </div>
                  </div>
                </div>

                <ul className="divide-y divide-border/30">
                  <li>
                    <button className="w-full px-4 py-2 text-left text-xs hover:bg-foreground/5 transition-colors flex items-center gap-2">
                      <UserCircle className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>Mon profil</span>
                    </button>
                  </li>
                  <li>
                    <button className="w-full px-4 py-2 text-left text-xs hover:bg-foreground/5 transition-colors flex items-center gap-2">
                      <Cog className="h-3.5 w-3.5 text-muted-foreground" />
                      <span>Paramètres du compte</span>
                    </button>
                  </li>
                </ul>

                <div className="px-4 py-2 border-t border-border/30 bg-card/50 text-[10px] text-muted-foreground">
                  <p>Connecté depuis</p>
                  <p className="font-mono mt-1">{now.toLocaleString('fr-FR')}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Close dropdowns when clicking outside */}
      {(settingsOpen || profileOpen || notificationsOpen) && (
        <div 
          className="fixed inset-0 z-40"
          onClick={() => {
            setSettingsOpen(false)
            setProfileOpen(false)
            setNotificationsOpen(false)
          }}
        />
      )}
    </header>
  )
}
