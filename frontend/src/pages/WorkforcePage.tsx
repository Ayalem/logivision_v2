import { useState } from 'react'
import { Users, Activity, AlertTriangle, Clock, TrendingUp, Plus, CheckCircle2, UserPlus, X as XIcon, ShieldCheck, Mail, User } from 'lucide-react'
import { useKpis, useWorkers, createWorker, createTask } from '@/lib/api'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/lib/i18n'

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
  const { t } = useTranslation()
  const { data: kpis } = useKpis()
  
  const [assigningTo, setAssigningTo] = useState<string | null>(null)
  const [showCreateAccount, setShowCreateAccount] = useState(false)
  const [newWorker, setNewWorker] = useState({ name: '', email: '', role: 'Opérateur', zone: 'Zone A' })
  const [createSuccess, setCreateSuccess] = useState(false)

  const { data: workersData, refetch: refetchWorkers } = useWorkers()
  const workers = workersData?.workers ?? WORKFORCE_DATA
  const [taskTitle, setTaskTitle] = useState('')
  const [taskZone, setTaskZone] = useState('Zone A-1')
  const [taskPriority, setTaskPriority] = useState<'High' | 'Medium' | 'Low'>('Medium')
  const [showSuccess, setShowSuccess] = useState(false)

  const activeWorkers = workers.filter((w: any) => w.status === 'active').length
  const totalWorkers = workers.length
  const avgEfficiency = workers.length > 0 
    ? Math.round(workers.reduce((sum: number, w: any) => sum + w.efficiency, 0) / workers.length)
    : 0

  const handleCreateAccount = async () => {
    if (!newWorker.name || !newWorker.email) return
    
    try {
      await createWorker({
        ...newWorker,
        id: Math.random().toString(36).substr(2, 9),
      })
      
      refetchWorkers()
      setCreateSuccess(true)
      setTimeout(() => {
        setCreateSuccess(false)
        setShowCreateAccount(false)
        setNewWorker({ name: '', email: '', role: 'Opérateur', zone: 'Zone A' })
      }, 2000)
    } catch (error) {
      console.error("Failed to create worker:", error)
    }
  }

  const handleAssignTask = async () => {
    if (!taskTitle || !assigningTo) return
    
    try {
      await createTask({
        id: Math.random().toString(36).substr(2, 9),
        title: taskTitle,
        zone: taskZone,
        priority: taskPriority,
        dueTime: 'Today',
        column: 'To Do',
        assignedTo: assigningTo
      })
      
      setShowSuccess(true)
      setTimeout(() => {
        setShowSuccess(false)
        setAssigningTo(null)
        setTaskTitle('')
      }, 2000)
    } catch (error) {
      console.error("Failed to assign task:", error)
    }
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t('workforce')}</h1>
          <p className="text-xs text-muted-foreground mt-1">Gestion des équipes et des performances</p>
        </div>
        <button 
          onClick={() => setShowCreateAccount(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-electric text-white text-xs font-bold hover:bg-electric/90 transition-all shadow-lg shadow-electric/20"
        >
          <UserPlus className="h-4 w-4" />
          CREATE ACCOUNT
        </button>
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
              <p className="text-xs text-muted-foreground mb-1">{t('efficiencyScore')}</p>
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

      {/* Workforce Details */}
      <div className="glass-card rounded-2xl shadow-soft overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold flex items-center gap-2">
            <Users className="h-4 w-4" />
            Détails des travailleurs
          </h2>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            {workers.length} personnes
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b border-border/30 bg-card/50">
              <tr>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Nom</th>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Zone</th>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Statut</th>
                <th className="px-4 py-2 text-left font-semibold text-muted-foreground">Efficacité</th>
                <th className="px-4 py-2 text-right font-semibold text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {workers.map((worker: any) => (
                <tr key={worker.id} className="hover:bg-foreground/[0.02] transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium">{worker.name}</div>
                    <div className="text-[10px] text-muted-foreground uppercase">{worker.role}</div>
                  </td>
                  <td className="px-4 py-3">{worker.zone}</td>
                  <td className="px-4 py-3">
                    <span className={cn(
                      'text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded inline-flex items-center gap-1',
                      worker.status === 'active' ? 'bg-emerald/15 text-emerald' : 'bg-amber/15 text-amber'
                    )}>
                      {worker.status === 'active' ? 'Actif' : 'Inactif'}
                    </span>
                  </td>
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
                  <td className="px-4 py-3 text-right">
                    <button 
                      onClick={() => setAssigningTo(worker.id)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-electric/10 text-electric text-[10px] font-bold hover:bg-electric/20 transition-colors"
                    >
                      <Plus className="h-3 w-3" />
                      ASSIGN TASK
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Assign Task Modal */}
      {assigningTo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md bg-card border border-border shadow-2xl rounded-2xl p-6 animate-in zoom-in-95 duration-200">
            {showSuccess ? (
              <div className="py-8 text-center space-y-4">
                <div className="h-12 w-12 bg-emerald/10 text-emerald rounded-full flex items-center justify-center mx-auto">
                  <CheckCircle2 className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold">Task Assigned!</h3>
                <p className="text-sm text-muted-foreground">The task has been successfully assigned to the worker.</p>
              </div>
            ) : (
              <>
                <h3 className="text-lg font-bold mb-1">Assign Task</h3>
                <p className="text-xs text-muted-foreground mb-6">Assigning to {WORKFORCE_DATA.find(w => w.id === assigningTo)?.name}</p>
                
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Task Title</label>
                    <input 
                      type="text" 
                      placeholder="e.g. Inspect Zone B-4"
                      value={taskTitle}
                      onChange={(e) => setTaskTitle(e.target.value)}
                      className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric/50"
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Zone</label>
                      <select 
                        value={taskZone}
                        onChange={(e) => setTaskZone(e.target.value)}
                        className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none"
                      >
                        <option>Zone A-1</option>
                        <option>Zone B-4</option>
                        <option>Zone C-2</option>
                        <option>Shipping</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Priority</label>
                      <select 
                        value={taskPriority}
                        onChange={(e) => setTaskPriority(e.target.value as any)}
                        className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none"
                      >
                        <option value="High">High</option>
                        <option value="Medium">Medium</option>
                        <option value="Low">Low</option>
                      </select>
                    </div>
                  </div>
                </div>
                
                <div className="flex gap-3 mt-8">
                  <button 
                    onClick={() => setAssigningTo(null)}
                    className="flex-1 py-2.5 rounded-xl text-xs font-bold border border-border/50 hover:bg-foreground/5 transition-colors"
                  >
                    {t('cancel')}
                  </button>
                  <button 
                    onClick={handleAssignTask}
                    disabled={!taskTitle}
                    className="flex-1 py-2.5 rounded-xl text-xs font-bold bg-electric text-white hover:bg-electric/90 disabled:opacity-50 transition-colors"
                  >
                    {t('confirm')}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Create Account Modal */}
      {showCreateAccount && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="w-full max-w-md bg-card border border-border shadow-2xl rounded-2xl p-6 animate-in zoom-in-95 duration-200 relative overflow-hidden">
            {createSuccess ? (
              <div className="py-8 text-center space-y-4">
                <div className="h-16 w-16 bg-emerald/10 text-emerald rounded-full flex items-center justify-center mx-auto">
                  <ShieldCheck className="h-8 w-8" />
                </div>
                <h3 className="text-xl font-bold">Account Created!</h3>
                <p className="text-sm text-muted-foreground">Worker account for {newWorker.name} has been successfully registered.</p>
              </div>
            ) : (
              <>
                <button 
                  onClick={() => setShowCreateAccount(false)}
                  className="absolute top-4 right-4 p-2 rounded-full hover:bg-foreground/5 transition-colors"
                >
                  <XIcon className="h-4 w-4 text-muted-foreground" />
                </button>

                <div className="flex items-center gap-3 mb-6">
                  <div className="h-10 w-10 rounded-xl bg-electric/10 text-electric flex items-center justify-center">
                    <UserPlus className="h-5 w-5" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold">Create Worker Account</h3>
                    <p className="text-xs text-muted-foreground">Register a new operator in the system</p>
                  </div>
                </div>
                
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <User className="h-3 w-3" /> Full Name
                    </label>
                    <input 
                      type="text" 
                      placeholder="e.g. Robert Wilson"
                      value={newWorker.name}
                      onChange={(e) => setNewWorker({...newWorker, name: e.target.value})}
                      className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric/50"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                      <Mail className="h-3 w-3" /> Email Address
                    </label>
                    <input 
                      type="email" 
                      placeholder="robert.w@logivision.ai"
                      value={newWorker.email}
                      onChange={(e) => setNewWorker({...newWorker, email: e.target.value})}
                      className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric/50"
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Role</label>
                      <select 
                        value={newWorker.role}
                        onChange={(e) => setNewWorker({...newWorker, role: e.target.value})}
                        className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none"
                      >
                        <option>Opérateur</option>
                        <option>Chef d'équipe</option>
                        <option>Superviseur</option>
                        <option>Maintenance</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Primary Zone</label>
                      <select 
                        value={newWorker.zone}
                        onChange={(e) => setNewWorker({...newWorker, zone: e.target.value})}
                        className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none"
                      >
                        <option>Zone A</option>
                        <option>Zone B</option>
                        <option>Zone C</option>
                        <option>Shipping</option>
                        <option>Receiving</option>
                      </select>
                    </div>
                  </div>
                </div>
                
                <div className="flex gap-3 mt-8">
                  <button 
                    onClick={() => setShowCreateAccount(false)}
                    className="flex-1 py-2.5 rounded-xl text-xs font-bold border border-border/50 hover:bg-foreground/5 transition-colors"
                  >
                    {t('cancel')}
                  </button>
                  <button 
                    onClick={handleCreateAccount}
                    disabled={!newWorker.name || !newWorker.email}
                    className="flex-1 py-2.5 rounded-xl text-xs font-bold bg-electric text-white hover:bg-electric/90 disabled:opacity-50 transition-colors shadow-lg shadow-electric/20"
                  >
                    REGISTER WORKER
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
