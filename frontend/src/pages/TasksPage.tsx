import { useState, useEffect } from 'react'
import { 
  MoreHorizontal, 
  Plus, 
  Clock, 
  MapPin, 
  AlertCircle,
  GripVertical
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

  return (
    <div className="h-full flex flex-col space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t('myTasks')}</h1>
          <p className="text-sm text-muted-foreground">Manage your daily warehouse assignments</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-electric text-white text-sm font-semibold hover:bg-electric/90 transition-all shadow-lg shadow-electric/20">
          <Plus className="h-4 w-4" />
          New Task
        </button>
      </div>

      <div className="flex-1 flex gap-6 overflow-x-auto pb-4">
        {columns.map(col => (
          <div key={col} className="flex-1 min-w-[300px] flex flex-col bg-card/20 border border-border/30 rounded-xl">
            <div className="p-4 border-b border-border/30 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold">{col}</h3>
                <span className="px-2 py-0.5 rounded-full bg-foreground/5 text-[10px] font-bold text-muted-foreground">
                  {tasks.filter(t => t.column === col).length}
                </span>
              </div>
              <button className="p-1 rounded-md hover:bg-foreground/5 text-muted-foreground">
                <MoreHorizontal className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 p-3 space-y-3 overflow-y-auto">
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
                  className="group bg-card border border-border/50 rounded-lg p-4 shadow-sm hover:border-electric/50 transition-all cursor-grab active:cursor-grabbing"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className={cn("h-2 w-2 rounded-full", getPriorityColor(task.priority))} />
                      <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                        {task.priority} Priority
                      </span>
                    </div>
                    <GripVertical className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-muted-foreground transition-colors" />
                  </div>
                  
                  <h4 className="text-sm font-semibold mb-3">{task.title}</h4>
                  
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <MapPin className="h-3 w-3" />
                      {task.zone}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Clock className="h-3 w-3" />
                      {task.dueTime}
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
                className="h-20 border-2 border-dashed border-border/20 rounded-lg flex items-center justify-center text-muted-foreground/20"
              >
                <Plus className="h-6 w-6" />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
