import { Users, Activity, AlertTriangle, Clock, TrendingUp } from 'lucide-react'
import { useKpis } from '@/lib/api'
import { cn } from '@/lib/utils'

// Mock data for workforce
const WORKFORCE_DATA = [
  { id: '1', name: 'Jean Dupont', role: 'Opérateur', zone: 'Zone A', status: 'active', lastSeen: '2 min', efficiency: 92 },
  { id: '2', name: 'Marie Martin', role: 'Chef d\'équipe', zone: 'Zone B', status: 'active', lastSeen: '1 min', efficiency: 88 },
  { id: '3', name: 'Pierre Bernard', role: 'Opérateur', zone: 'Zone C', status: 'idle', lastSeen: '15 min', efficiency: 85 },
  { id: '4', name: 'Sophie Leclerc', role: 'Opérateur', zone: 'Zone A', status: 'active', lastSeen: '3 min', efficiency: 91 },
  { id: '5', name: 'Marc Rousseau', role: 'Superviseur', zone: 'Supervision', status: 'active', lastSeen: '1 min', efficiency: 95 },
]

const SHIFTS = [
  { id: '1', name: 'Matin', start: '06:00', end: '14:00', workers: 8, status: 'active' },
  { id: '2', name: 'Après-midi', start: '14:00', end: '22:00', workers: 7, status: 'active' },
  { id: '3', name: 'Nuit', start: '22:00', end: '06:00', workers: 5, status: 'upcoming' },
]

export function WorkforcePage() {
  const { data: kpis } = useKpis()

  const activeWorkers = WORKFORCE_DATA.filter(w => w.status === 'active').length
  const totalWorkers = WORKFORCE_DATA.length
  const avgEfficiency = Math.round(WORKFORCE_DATA.reduce((sum, w) => sum + w.efficiency, 0) / WORKFORCE_DATA.length)

  return (
    <div className="space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Workforce</h1>
        <p className="text-xs text-muted-foreground mt-1">Gestion des équipes et des performances</p>
      </div>

      {/* Workforce Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Travailleurs actifs</p>
              <p className="text-2xl font-bold text-emerald">{activeWorkers}/{totalWorkers}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-emerald/10 flex items-center justify-center">
              <Activity className="h-5 w-5 text-emerald" />
            </div>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Efficacité moyenne</p>
              <p className="text-2xl font-bold text-electric">{avgEfficiency}%</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-electric/10 flex items-center justify-center">
              <TrendingUp className="h-5 w-5 text-electric" />
            </div>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-4 shadow-soft">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Équipes en service</p>
              <p className="text-2xl font-bold text-teal">{SHIFTS.filter(s => s.status === 'active').length}</p>
            </div>
            <div className="h-10 w-10 rounded-lg bg-teal/10 flex items-center justify-center">
              <Clock className="h-5 w-5 text-teal" />
            </div>
          </div>
        </div>
      </div>

      {/* Current Shifts */}
      <div className="glass-card rounded-2xl shadow-soft overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Équipes actuelles
          </h2>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {SHIFTS.length} équipes
          </span>
        </div>

        <div className="divide-y divide-border/30">
          {SHIFTS.map((shift) => (
            <div key={shift.id} className="px-4 py-3 hover:bg-foreground/[0.02] transition-colors">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="text-sm font-medium">{shift.name}</p>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {shift.start} - {shift.end}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-electric">{shift.workers} travailleurs</p>
                  <span className={cn(
                    'text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded inline-block mt-1',
                    shift.status === 'active' ? 'bg-emerald/15 text-emerald' : 'bg-amber/15 text-amber'
                  )}>
                    {shift.status === 'active' ? 'En cours' : 'À venir'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Workforce Details */}
      <div className="glass-card rounded-2xl shadow-soft overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Users className="h-4 w-4" />
            Détails des travailleurs
          </h2>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {WORKFORCE_DATA.length} personnes
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b border-border/30 bg-card/50">
              <tr>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Nom</th>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Rôle</th>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Zone</th>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Statut</th>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Vu</th>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Efficacité</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {WORKFORCE_DATA.map((worker) => (
                <tr key={worker.id} className="hover:bg-foreground/[0.02] transition-colors">
                  <td className="px-4 py-3 font-medium">{worker.name}</td>
                  <td className="px-4 py-3">
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground px-2 py-1 rounded bg-card/50">
                      {worker.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">{worker.zone}</td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded inline-flex items-center gap-1',
                      worker.status === 'active' ? 'bg-emerald/15 text-emerald' : 'bg-amber/15 text-amber'
                    )}>
                      <span className={cn(
                        'h-1.5 w-1.5 rounded-full',
                        worker.status === 'active' ? 'bg-emerald' : 'bg-amber'
                      )} />
                      {worker.status === 'active' ? 'Actif' : 'Inactif'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{worker.lastSeen}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-1.5 w-16 bg-card rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-emerald to-teal rounded-full"
                          style={{ width: `${worker.efficiency}%` }}
                        />
                      </div>
                      <span className="font-semibold text-emerald">{worker.efficiency}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Performance Insights */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Top Performers */}
        <div className="glass-card rounded-2xl p-5 shadow-soft">
          <h2 className="text-sm font-semibold mb-4">Meilleurs performants</h2>
          <div className="space-y-2">
            {[...WORKFORCE_DATA]
              .sort((a, b) => b.efficiency - a.efficiency)
              .slice(0, 3)
              .map((worker) => (
                <div key={worker.id} className="p-3 rounded-lg bg-card/50 border border-border/30">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium">{worker.name}</p>
                      <p className="text-[10px] text-muted-foreground mt-1">{worker.role}</p>
                    </div>
                    <span className="text-sm font-semibold text-emerald">{worker.efficiency}%</span>
                  </div>
                </div>
              ))}
          </div>
        </div>

        {/* Needs Attention */}
        <div className="glass-card rounded-2xl p-5 shadow-soft">
          <h2 className="text-sm font-semibold mb-4 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber" />
            Nécessite attention
          </h2>
          <div className="space-y-2">
            {WORKFORCE_DATA
              .filter(w => w.efficiency < 90 || w.status === 'idle')
              .slice(0, 3)
              .map((worker) => (
                <div key={worker.id} className="p-3 rounded-lg bg-card/50 border border-border/30">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium">{worker.name}</p>
                      <p className="text-[10px] text-muted-foreground mt-1">
                        {worker.status === 'idle' ? 'Inactif depuis ' + worker.lastSeen : 'Efficacité faible'}
                      </p>
                    </div>
                    <span className={cn(
                      'text-sm font-semibold',
                      worker.efficiency < 90 ? 'text-amber' : 'text-coral'
                    )}>
                      {worker.efficiency}%
                    </span>
                  </div>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}

