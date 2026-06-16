import { useState, useEffect, useRef } from 'react'
import { Bell, RefreshCw, Search, Globe, Check, AlertCircle, AlertTriangle, Info, X, Command, User, Settings as SettingsIcon, LogOut } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useAppStore, type ViewType } from '@/lib/store'
import { cn } from '@/lib/utils'
import { useTranslation, type Language } from '@/lib/i18n'

const TITLES: Record<ViewType, { titleKey: string; subKey: string }> = {
  overview:  { titleKey: "overview",  subKey: 'overviewSub' },
  entries:   { titleKey: 'entries', subKey: 'entriesSub' },
  zones:     { titleKey: 'zones',           subKey: 'zonesSub' },
  anomalies: { titleKey: 'alerts',       subKey: 'anomaliesSub' },
  cameras:   { titleKey: 'cameras',         subKey: 'camerasSub' },
  system:    { titleKey: 'system',         subKey: 'systemSub' },
  'ml-monitoring': { titleKey: 'mlMonitoring', subKey: 'mlMonitoringSub' },
  analytics: { titleKey: 'analytics',        subKey: 'analyticsSub' },
  inventory: { titleKey: 'inventory',      subKey: 'inventorySub' },
  workforce: { titleKey: 'workforce',       subKey: 'workforceSub' },
  settings:  { titleKey: 'settings', subKey: 'settingsSub' },
  profile:   { titleKey: 'profile',   subKey: 'profileSub' },
  'activity-log': { titleKey: 'activityLog', subKey: 'activityLogSub' },
  tasks: { titleKey: 'myTasks', subKey: 'myTasksSub' },
}

// Mock search data
const SEARCH_RESULTS = [
  { id: 'ORD-5521', name: 'Order #5521', category: 'Orders', zone: 'Zone A-1' },
  { id: 'ORD-5522', name: 'Order #5522', category: 'Orders', zone: 'Zone B-2' },
  { id: 'FL-004', name: 'Forklift FL-004', category: 'Alerts', zone: 'Zone C-3' },
  { id: 'AL-99', name: 'Critical Obstruction', category: 'Alerts', zone: 'Zone A-2' },
  { id: 'WK-12', name: 'John Doe', category: 'Workforce', zone: 'Zone B-4' },
  { id: 'WK-15', name: 'Sarah Smith', category: 'Workforce', zone: 'Zone A-1' },
]

export function Header() {
  const { t, lang, setLang } = useTranslation()
  const view = useAppStore((s) => s.currentView)
  const setView = useAppStore((s) => s.setView)
  const events = useAppStore((s) => s.live.events)
  const qc = useQueryClient()
  const userRole = useAppStore((s) => s.userRole)
  const role = userRole ?? 'worker'
  
  const [now, setNow] = useState(new Date())
  const [langOpen, setLangOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  
  // Search state
  const [searchExpanded, setSearchExpanded] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const searchInputRef = useRef<HTMLInputElement>(null)
  const searchContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])

  // Keyboard shortcut Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setSearchExpanded(true)
        setTimeout(() => searchInputRef.current?.focus(), 100)
      }
      if (e.key === 'Escape') {
        setSearchExpanded(false)
        setSearchQuery('')
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Click outside to close search
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setSearchExpanded(false)
        setSearchQuery('')
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (searchQuery.trim().length > 1) {
      const filtered = SEARCH_RESULTS.filter(item => 
        item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.zone.toLowerCase().includes(searchQuery.toLowerCase())
      ).slice(0, 6)
      setSearchResults(filtered)
    } else {
      setSearchResults([])
    }
  }, [searchQuery])

  const dateStr = now.toLocaleDateString(lang === 'ar' ? 'ar-SA' : lang === 'fr' ? 'fr-FR' : 'en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  const timeStr = now.toLocaleTimeString(lang === 'ar' ? 'ar-SA' : lang === 'fr' ? 'fr-FR' : 'en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

  const languages = [
    { code: 'en' as Language, label: 'English', flag: '🇬🇧' },
    { code: 'fr' as Language, label: 'Français', flag: '🇫🇷' },
    { code: 'ar' as Language, label: 'العربية', flag: '🇸🇦' },
  ]

  const handleRefresh = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    setRefreshing(true)
    qc.invalidateQueries()
    setTimeout(() => setRefreshing(false), 1000)
  }

  const groupedResults = searchResults.reduce((acc: any, item) => {
    if (!acc[item.category]) acc[item.category] = []
    acc[item.category].push(item)
    return acc
  }, {})

  const logout = useAppStore((s) => s.logout)

  return (
    <header className="sticky top-0 z-20 glass border-b border-border/50">
      <div className="px-6 py-4 flex items-center justify-between gap-4">
        {/* Left: Warehouse selector and date/time */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <button className="flex items-center gap-2 px-3 py-2 rounded-lg bg-card/40 hover:bg-card/60 transition-colors text-sm font-medium">
              <span>{t('warehouse')}</span>
              <span className="text-xs text-muted-foreground">Alpha-01</span>
            </button>
          </div>
          <div className="hidden lg:flex items-center gap-4 text-xs text-muted-foreground font-mono">
            <div>
              <span className="text-muted-foreground">{t('date')}</span>
              <div className="text-foreground font-semibold">{dateStr}</div>
            </div>
            <div>
              <span className="text-muted-foreground">{t('time')}</span>
              <div className="text-foreground font-semibold">{timeStr}</div>
            </div>
          </div>
        </div>

        {/* Right: System status, search, and controls */}
        <div className="flex items-center gap-3">
          {/* System Status */}
          <div className="hidden md:flex items-center gap-2 px-3 py-2 rounded-lg bg-emerald/10 border border-emerald/30">
            <div className="h-2 w-2 rounded-full bg-emerald animate-pulse" />
            <span className="text-xs font-semibold text-emerald">{t('systemStatus')}</span>
          </div>

          {/* Search Functional */}
          <div ref={searchContainerRef} className="relative flex items-center">
            <div className={cn(
              "flex items-center bg-card/40 border border-border/50 rounded-lg transition-all duration-300 overflow-hidden",
              searchExpanded ? "w-[280px] px-3" : "w-10 px-0 justify-center border-transparent hover:bg-card/60"
            )}>
              <Search 
                className={cn("h-4 w-4 text-muted-foreground cursor-pointer shrink-0", !searchExpanded && "hover:text-foreground")} 
                onClick={() => {
                  setSearchExpanded(true)
                  setTimeout(() => searchInputRef.current?.focus(), 100)
                }}
              />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t('searchPlaceholder')}
                className={cn(
                  "bg-transparent border-none outline-none text-xs ml-2 w-full transition-opacity duration-200",
                  searchExpanded ? "opacity-100" : "opacity-0 pointer-events-none"
                )}
              />
              {searchExpanded && (
                <div className="flex items-center gap-1 shrink-0 ml-1">
                  <kbd className="hidden sm:inline-flex h-4 items-center gap-1 rounded border border-border/50 bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
                    <span className="text-xs">⌘</span>K
                  </kbd>
                  <X 
                    className="h-3 w-3 text-muted-foreground cursor-pointer hover:text-foreground" 
                    onClick={() => {
                      setSearchExpanded(false)
                      setSearchQuery('')
                    }}
                  />
                </div>
              )}
            </div>

            {/* Search Results Dropdown */}
            {searchExpanded && searchResults.length > 0 && (
              <div className="absolute top-full right-0 mt-2 w-[320px] bg-card border border-border/50 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2">
                <div className="max-h-[400px] overflow-y-auto p-2">
                  {Object.entries(groupedResults).map(([category, items]: [string, any]) => (
                    <div key={category} className="mb-2 last:mb-0">
                      <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                        {category}
                      </div>
                      {items.map((item: any) => (
                        <button
                          key={item.id}
                          onClick={() => {
                            setSearchExpanded(false)
                            setSearchQuery('')
                            // Navigation logic would go here
                          }}
                          className="w-full flex flex-col gap-0.5 px-3 py-2 rounded-lg hover:bg-foreground/5 transition-colors text-left"
                        >
                          <span className="text-xs font-medium">{item.name}</span>
                          <span className="text-[10px] text-muted-foreground">{item.id} • {item.zone}</span>
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Language Selector */}
          <div className="relative">
            <button 
              onClick={() => setLangOpen(!langOpen)}
              className="p-2 rounded-lg hover:bg-card/60 transition-colors text-muted-foreground hover:text-foreground"
            >
              <Globe className="h-4 w-4" />
            </button>
            {langOpen && (
              <div className={cn(
                "absolute mt-2 w-40 bg-card border border-border/50 rounded-lg shadow-lg overflow-hidden z-50",
                lang === 'ar' ? "left-0" : "right-0"
              )}>
                <ul className="py-1">
                  {languages.map((l) => (
                    <li key={l.code}>
                      <button 
                        onClick={() => {
                          setLang(l.code)
                          setLangOpen(false)
                        }}
                        className="w-full px-3 py-2 text-left text-xs hover:bg-foreground/5 transition-colors flex items-center justify-between"
                      >
                        <div className="flex items-center gap-2">
                          <span>{l.flag}</span>
                          <span>{l.label}</span>
                        </div>
                        {lang === l.code && <Check className="h-3 w-3 text-electric" />}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Refresh */}
          <button 
            type="button"
            onClick={handleRefresh}
            className="p-2 rounded-lg hover:bg-card/60 transition-colors text-muted-foreground hover:text-foreground"
          >
            <RefreshCw className={cn("h-4 w-4", refreshing && "animate-spin")} />
          </button>

          {/* Notifications */}
          <div className="relative">
            <button 
              type="button"
              onClick={() => setNotificationsOpen(!notificationsOpen)}
              className="relative p-2 rounded-lg hover:bg-card/60 transition-colors text-muted-foreground hover:text-foreground"
            >
              <Bell className="h-4 w-4" />
              {events.length > 0 && (
                <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-coral border-2 border-background" />
              )}
            </button>

            {notificationsOpen && (
              <div className={cn(
                "absolute mt-2 w-80 bg-card border border-border/50 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2",
                lang === 'ar' ? "left-0" : "right-0"
              )}>
                <div className="p-4 border-b border-border/30 flex items-center justify-between bg-foreground/[0.02]">
                  <h3 className="text-xs font-bold uppercase tracking-wider">{t('notifications')}</h3>
                  <button className="text-[10px] text-electric font-bold hover:underline">{t('markAllAsRead')}</button>
                </div>
                <div className="max-h-[350px] overflow-y-auto">
                  {events.length > 0 ? (
                    <div className="divide-y divide-border/30">
                      {events.slice(0, 10).map((event, i) => (
                        <div key={i} className="p-4 hover:bg-foreground/[0.02] transition-colors cursor-pointer group">
                          <div className="flex gap-3">
                            <div className={cn(
                              "mt-1 h-2 w-2 rounded-full shrink-0",
                              event.severity === 'critical' ? "bg-coral shadow-[0_0_8px_rgba(244,63,94,0.4)]" : 
                              event.severity === 'warning' ? "bg-amber" : "bg-electric"
                            )} />
                            <div className="space-y-1">
                              <p className="text-xs font-medium leading-tight group-hover:text-electric transition-colors">
                                {event.event_type.replace(/_/g, ' ')} in {event.zone}
                              </p>
                              <p className="text-[10px] text-muted-foreground">
                                {new Date(event.timestamp_ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-12 px-4 text-center">
                      <div className="h-12 w-12 rounded-full bg-muted/20 flex items-center justify-center mx-auto mb-3">
                        <Bell className="h-6 w-6 text-muted-foreground/40" />
                      </div>
                      <p className="text-xs text-muted-foreground">{t('noAlerts')}</p>
                    </div>
                  )}
                </div>
                <div className="p-3 border-t border-border/30 text-center bg-foreground/[0.01]">
                  <button 
                    onClick={() => { setView('anomalies'); setNotificationsOpen(false); }}
                    className="text-[10px] font-bold text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {t('viewAllAlerts')}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* User Profile Menu */}
          <div className="relative ml-2 border-l border-border/30 pl-3">
            <button 
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-2 p-1 rounded-full hover:bg-card/60 transition-colors border border-transparent hover:border-border/50"
            >
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-electric/20 to-teal/20 flex items-center justify-center text-electric border border-electric/30">
                <User className="h-4 w-4" />
              </div>
            </button>
            
            {userMenuOpen && (
              <div className={cn(
                "absolute mt-2 w-56 bg-card border border-border/50 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2",
                lang === 'ar' ? "left-0" : "right-0"
              )}>
                <div className="p-3 border-b border-border/30 bg-foreground/[0.02]">
                  <p className="text-xs font-bold">{role === 'admin' ? 'Administrator' : 'Operator'}</p>
                  <p className="text-[10px] text-muted-foreground truncate">operator@logivision.ai</p>
                </div>
                <div className="p-1.5">
                  <button 
                    onClick={() => { setView('profile'); setUserMenuOpen(false); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs hover:bg-foreground/5 transition-colors"
                  >
                    <User className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>{t('myProfile')}</span>
                  </button>
                  <button 
                    onClick={() => { setView('settings'); setUserMenuOpen(false); }}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs hover:bg-foreground/5 transition-colors"
                  >
                    <SettingsIcon className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>{t('accountSettings')}</span>
                  </button>
                </div>
                <div className="p-1.5 border-t border-border/30">
                  <button 
                    onClick={() => logout()}
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs text-coral hover:bg-coral/10 transition-colors"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    <span>{t('logout')}</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
