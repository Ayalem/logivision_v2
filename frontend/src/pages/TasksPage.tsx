import { useState, useEffect } from 'react'
import { 
  MoreHorizontal, 
  Plus, 
  Clock, 
  MapPin, 
  AlertCircle,
  GripVertical,
  X
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/lib/i18n'

type Priority = 'High' | 'Medium' | 'Low'
type Column = 'To Do' | 'In Progress' | 'Done'

interface Task {
  id: string
  title: string
  zone: string
  priority: Priority
  dueTime: string
  column: Column
}

const INITIAL_TASKS: Task[] = [
  { id: '1', title: 'Restock Shelf A-42', zone: 'Zone A-1', priority: 'High', dueTime: '10:30 AM', column: 'To Do' },
  { id: '2', title: 'Inspect Forklift FL-04', zone: 'Maintenance', priority: 'Medium', dueTime: '11:15 AM', column: 'To Do' },
  { id: '3', title: 'Clear Obstruction', zone: 'Zone B-2', priority: 'High', dueTime: '09:45 AM', column: 'In Progress' },
  { id: '4', title: 'Inventory Count', zone: 'Zone C-3', priority: 'Low', dueTime: '02:00 PM', column: 'In Progress' },
  { id: '5', title: 'Package Labeling', zone: 'Shipping', priority: 'Medium', dueTime: '08:30 AM', column: 'Done' },
]

export function TasksPage() {
  const { t } = useTranslation()
  const [tasks, setTasks] = useState<Task[]>(() => {
    const saved = localStorage.getItem('logivision_tasks')
    return saved ? JSON.parse(saved) : INITIAL_TASKS
  })
  const [showNewTaskForm, setShowNewTaskForm] = useState(false)
  const [newTask, setNewTask] = useState({ title: '', zone: '', priority: 'Medium' as Priority, dueTime: '' })

  useEffect(() => {
    localStorage.setItem('logivision_tasks', JSON.stringify(tasks))
  }, [tasks])

  const columns: Column[] = ['To Do', 'In Progress', 'Done']

  const moveTask = (taskId: string, newColumn: Column) => {
    setTasks(prev => prev.map(t => t.id === taskId ? { ...t, column: newColumn } : t))
  }

  const getPriorityColor = (p: Priority) => {
    switch (p) {
      case 'High': return 'bg-coral'
      case 'Medium': return 'bg-amber'
      case 'Low': return 'bg-teal'
    }
  }

  const handleAddTask = () => {
    if (newTask.title && newTask.zone && newTask.dueTime) {
      const task: Task = {
        id: `${Date.now()}`,
        title: newTask.title,
        zone: newTask.zone,
        priority: newTask.priority,
        dueTime: newTask.dueTime,
        column: 'To Do'
      }
      setTasks([...tasks, task])
      setNewTask({ title: '', zone: '', priority: 'Medium', dueTime: '' })
      setShowNewTaskForm(false)
    }
  }

  return (
    <div className="h-full flex flex-col space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('myTasks')}</h1>
          <p className="text-sm text-muted-foreground">Manage your daily warehouse assignments</p>
        </div>
        <button 
          onClick={() => setShowNewTaskForm(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-electric text-white text-xs font-bold hover:bg-electric/90 transition-all shadow-lg shadow-electric/20"
        >
          <Plus className="h-4 w-4" />
          New Task
        </button>
      </div>

      {/* New Task Modal */}
      {showNewTaskForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="glass-card rounded-2xl p-6 border border-border/80 shadow-2xl max-w-md w-full mx-4 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border/40">
              <h2 className="text-sm font-black uppercase tracking-wider">Create New Task</h2>
              <button 
                onClick={() => setShowNewTaskForm(false)}
                className="p-1 rounded-lg hover:bg-secondary text-muted-foreground transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">Task Title</label>
                <input 
                  type="text" 
                  value={newTask.title}
                  onChange={(e) => setNewTask({...newTask, title: e.target.value})}
                  placeholder="Restock Shelf A-42..."
                  className="w-full px-3.5 py-2.5 rounded-lg bg-secondary border border-border/50 text-sm text-foreground focus:outline-none focus:border-electric/50 search-glow"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">Zone</label>
                <input 
                  type="text" 
                  value={newTask.zone}
                  onChange={(e) => setNewTask({...newTask, zone: e.target.value})}
                  placeholder="e.g., Zone A-1"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-secondary border border-border/50 text-sm text-foreground focus:outline-none focus:border-electric/50 search-glow"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">Priority</label>
                <select 
                  value={newTask.priority}
                  onChange={(e) => setNewTask({...newTask, priority: e.target.value as Priority})}
                  className="w-full px-3.5 py-2.5 rounded-lg bg-secondary border border-border/50 text-sm text-foreground focus:outline-none focus:border-electric/50 search-glow"
                >
                  <option value="Low">Low</option>
                  <option value="Medium">Medium</option>
                  <option value="High">High</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-black uppercase tracking-wider text-muted-foreground">Due Time</label>
                <input 
                  type="text" 
                  value={newTask.dueTime}
                  onChange={(e) => setNewTask({...newTask, dueTime: e.target.value})}
                  placeholder="e.g., 10:30 AM"
                  className="w-full px-3.5 py-2.5 rounded-lg bg-secondary border border-border/50 text-sm text-foreground focus:outline-none focus:border-electric/50 search-glow"
                />
              </div>
            </div>

            <div className="flex gap-3 pt-4 border-t border-border/40">
              <button 
                onClick={() => setShowNewTaskForm(false)}
                className="flex-1 px-4 py-2.5 rounded-lg border border-border text-foreground text-xs font-bold hover:bg-secondary transition-all"
              >
                Cancel
              </button>
              <button 
                onClick={handleAddTask}
                disabled={!newTask.title || !newTask.zone || !newTask.dueTime}
                className="flex-1 px-4 py-2.5 rounded-lg bg-electric text-white text-xs font-bold hover:bg-electric/90 shadow-lg shadow-electric/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Create Task
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex-1 flex gap-6 overflow-x-auto pb-4">
        {columns.map(col => (
          <div key={col} className="flex-1 min-w-[320px] flex flex-col bg-secondary/30 border border-border/60 rounded-2xl">
            <div className="p-4 border-b border-border/50 flex items-center justify-between bg-foreground/[0.01]">
              <div className="flex items-center gap-2.5">
                <h3 className="text-xs font-black uppercase tracking-wider text-foreground">{col}</h3>
                <span className="px-2.5 py-0.5 rounded-full bg-secondary text-[10px] font-bold text-muted-foreground border border-border/50">
                  {tasks.filter(t => t.column === col).length}
                </span>
              </div>
              <button className="p-1 rounded-lg hover:bg-foreground/5 text-muted-foreground transition-colors">
                <MoreHorizontal className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 p-3.5 space-y-3.5 overflow-y-auto">
              {tasks.filter(t => t.column === col).map(task => (
                <div 
                  key={task.id}
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData('taskId', task.id)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    const id = e.dataTransfer.getData('taskId')
                    moveTask(id, col)
                  }}
                  className="group bg-card border border-border/60 rounded-xl p-4 shadow-soft interactive-card transition-all cursor-grab active:cursor-grabbing hover:border-electric/30"
                >
                  <div className="flex items-start justify-between mb-3.5">
                    <span className={cn(
                      "status-badge",
                      task.priority === 'High' ? "status-badge-critical" :
                      task.priority === 'Medium' ? "status-badge-warning" :
                      "status-badge-success"
                    )}>
                      {task.priority}
                    </span>
                    <GripVertical className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-muted-foreground/80 transition-colors" />
                  </div>
                  
                  <h4 className="text-sm font-black text-foreground mb-3">{task.title}</h4>
                  
                  <div className="flex items-center justify-between text-[10px] font-bold text-muted-foreground border-t border-border/40 pt-2.5">
                    <div className="flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5 text-electric/70" />
                      <span>{task.zone}</span>
                    </div>
                    <div className="flex items-center gap-1 bg-secondary px-2 py-0.5 rounded border border-border/40">
                      <Clock className="h-3 w-3 text-electric/70" />
                      <span className="font-mono">{task.dueTime}</span>
                    </div>
                  </div>
                </div>
              ))}
              
              {/* Drop target for empty columns */}
              <div 
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  const id = e.dataTransfer.getData('taskId')
                  moveTask(id, col)
                }}
                className="h-16 border-2 border-dashed border-border/30 hover:border-electric/30 hover:bg-electric/[0.02] rounded-xl flex items-center justify-center text-muted-foreground/30 hover:text-electric transition-all"
              >
                <Plus className="h-5 w-5" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
