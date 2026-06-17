import { useState, useMemo } from 'react'
import { 
  Search, 
  Filter, 
  Calendar, 
  User, 
  Tag, 
  ArrowUpDown, 
  Download,
  ShieldCheck,
  ShieldAlert,
  Settings,
  Package,
  AlertTriangle,
  LogIn
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/lib/i18n'

interface LogEntry {
  id: string
  timestamp: string
  user: string
  role: 'admin' | 'worker'
  action: string
  entity: string
  type: 'login' | 'model' | 'alert' | 'inventory' | 'system'
}

const MOCK_LOGS: LogEntry[] = [
  { id: '1', timestamp: '2024-06-16 10:45:22', user: 'Admin User', role: 'admin', action: 'Model ResNet-v3 set to Production', entity: 'ResNet-v3', type: 'model' },
  { id: '2', timestamp: '2024-06-16 10:30:15', user: 'Worker John', role: 'worker', action: 'Alert acknowledged: Forklift Speeding', entity: 'Alert #882', type: 'alert' },
  { id: '3', timestamp: '2024-06-16 09:15:00', user: 'Admin User', role: 'admin', action: 'User login', entity: 'System', type: 'login' },
  { id: '4', timestamp: '2024-06-16 08:45:10', user: 'Worker Sarah', role: 'worker', action: 'Inventory change: Zone A-1 capacity updated', entity: 'Zone A-1', type: 'inventory' },
  { id: '5', timestamp: '2024-06-15 17:20:44', user: 'Admin User', role: 'admin', action: 'System configuration updated', entity: 'Settings', type: 'system' },
  { id: '6', timestamp: '2024-06-15 16:10:12', user: 'Worker John', role: 'worker', action: 'Alert snoozed: Obstruction in Zone B-2', entity: 'Alert #875', type: 'alert' },
  { id: '7', timestamp: '2024-06-15 14:30:00', user: 'Admin User', role: 'admin', action: 'Model YoloV8-Nano promoted to Staging', entity: 'YoloV8-Nano', type: 'model' },
  { id: '8', timestamp: '2024-06-15 09:00:00', user: 'Worker Sarah', role: 'worker', action: 'User login', entity: 'System', type: 'login' },
]

export function ActivityLogPage() {
  const { t } = useTranslation()
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')

  const filteredLogs = useMemo(() => {
    return MOCK_LOGS.filter(log => {
      const matchesSearch = log.user.toLowerCase().includes(search.toLowerCase()) || 
                           log.action.toLowerCase().includes(search.toLowerCase()) ||
                           log.entity.toLowerCase().includes(search.toLowerCase())
      const matchesType = typeFilter === 'all' || log.type === typeFilter
      return matchesSearch && matchesType
    })
  }, [search, typeFilter])

  const getTypeIcon = (type: LogEntry['type']) => {
    switch (type) {
      case 'login': return <LogIn className="h-3.5 w-3.5" />
      case 'model': return <Settings className="h-3.5 w-3.5" />
      case 'alert': return <AlertTriangle className="h-3.5 w-3.5" />
      case 'inventory': return <Package className="h-3.5 w-3.5" />
      default: return <Tag className="h-3.5 w-3.5" />
    }
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('activityLog')}</h1>
          <p className="text-sm text-muted-foreground">Chronological audit trail of all platform actions</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-2 px-3 py-2 rounded-lg bg-card/40 border border-border/50 text-xs font-medium hover:bg-card/60 transition-colors">
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="md:col-span-2 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input 
            type="text" 
            placeholder="Search logs..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-card/40 border border-border/50 rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric/50"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <select 
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="w-full bg-card/40 border border-border/50 rounded-lg pl-10 pr-4 py-2 text-sm appearance-none focus:outline-none"
          >
            <option value="all">All Types</option>
            <option value="login">Logins</option>
            <option value="model">Models</option>
            <option value="alert">Alerts</option>
            <option value="inventory">Inventory</option>
          </select>
        </div>
        <div className="relative">
          <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <button className="w-full bg-card/40 border border-border/50 rounded-lg pl-10 pr-4 py-2 text-sm text-left text-muted-foreground">
            Date Range
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-card/30 border border-border/50 rounded-xl overflow-hidden backdrop-blur-sm">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border/30 bg-card/50">
              <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Timestamp</th>
              <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">User</th>
              <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Action</th>
              <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground">Entity</th>
              <th className="px-6 py-4 text-xs font-bold uppercase tracking-wider text-muted-foreground text-right">Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/20">
            {filteredLogs.map((log) => (
              <tr key={log.id} className="hover:bg-foreground/5 transition-colors group">
                <td className="px-6 py-4 text-xs font-mono text-muted-foreground">{log.timestamp}</td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <div className={cn(
                      "h-6 w-6 rounded-full flex items-center justify-center",
                      log.role === 'admin' ? "bg-electric/10 text-electric" : "bg-teal/10 text-teal"
                    )}>
                      {log.role === 'admin' ? <ShieldCheck className="h-3 w-3" /> : <User className="h-3 w-3" />}
                    </div>
                    <div className="flex flex-col">
                      <span className="text-xs font-medium">{log.user}</span>
                      <span className="text-[10px] text-muted-foreground uppercase">{log.role}</span>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 text-xs">{log.action}</td>
                <td className="px-6 py-4">
                  <span className="px-2 py-0.5 rounded-full bg-foreground/5 border border-border/30 text-[10px] font-medium">
                    {log.entity}
                  </span>
                </td>
                <td className="px-6 py-4 text-right">
                  <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-card border border-border/50 text-[10px] font-semibold uppercase tracking-wider">
                    {getTypeIcon(log.type)}
                    {log.type}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredLogs.length === 0 && (
          <div className="px-6 py-12 text-center">
            <p className="text-sm text-muted-foreground">No log entries found matching your filters.</p>
          </div>
        )}
      </div>
    </div>
  )
}
