import { useState } from 'react'
import { 
  BarChart3, 
  Database, 
  ExternalLink, 
  Activity, 
  CheckCircle2, 
  Clock, 
  Filter,
  MoreVertical,
  ChevronRight,
  TrendingUp,
  Target,
  Cpu,
  X
} from 'lucide-react'
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts'
import { cn } from '@/lib/utils'

// Mock Data
const MOCK_MODELS = [
  { id: '1', name: 'Object Detection YOLOv8', version: 'v2.4.1', status: 'Production', accuracy: 98.2, f1: 0.97, date: '2024-05-12', precision: 0.98, recall: 0.96 },
  { id: '2', name: 'Path Prediction LSTM', version: 'v1.2.0', status: 'Production', accuracy: 94.5, f1: 0.92, date: '2024-06-01', precision: 0.93, recall: 0.91 },
  { id: '3', name: 'Anomaly Detection', version: 'v3.0.2', status: 'Staging', accuracy: 96.8, f1: 0.95, date: '2024-06-10', precision: 0.95, recall: 0.94 },
  { id: '4', name: 'Pose Estimation', version: 'v1.0.5', status: 'Archived', accuracy: 89.2, f1: 0.88, date: '2024-04-20', precision: 0.89, recall: 0.87 },
  { id: '5', name: 'Crowd Density', version: 'v2.1.0', status: 'Staging', accuracy: 92.4, f1: 0.91, date: '2024-06-14', precision: 0.92, recall: 0.90 },
]

const ACCURACY_HISTORY = [
  { run: 'Run #101', accuracy: 92.1 },
  { run: 'Run #102', accuracy: 93.4 },
  { run: 'Run #103', accuracy: 92.8 },
  { run: 'Run #104', accuracy: 94.5 },
  { run: 'Run #105', accuracy: 95.2 },
  { run: 'Run #106', accuracy: 96.8 },
  { run: 'Run #107', accuracy: 97.5 },
  { run: 'Run #108', accuracy: 98.2 },
]

const MLFLOW_URL = import.meta.env.VITE_MLFLOW_URL || 'https://mlflow.logivision.ai'

export function MlMonitoringPage() {
  const [selectedModel, setSelectedModel] = useState(MOCK_MODELS[0])
  const [drawerOpen, setDrawerOpen] = useState(false)

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Production': return 'bg-emerald/10 text-emerald border-emerald/30'
      case 'Staging': return 'bg-amber/10 text-amber border-amber/30'
      case 'Archived': return 'bg-slate-500/10 text-slate-400 border-slate-500/30'
      default: return 'bg-slate-500/10 text-slate-400 border-slate-500/30'
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Bar with Metrics and MLflow Link */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 flex-1">
          <div className="glass-card p-4 rounded-xl border border-border/50 flex items-center gap-4">
            <div className="h-10 w-10 rounded-lg bg-electric/10 border border-electric/30 flex items-center justify-center">
              <Target className="h-5 w-5 text-electric" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Best Model Accuracy</p>
              <p className="text-xl font-bold text-gradient">98.2%</p>
            </div>
          </div>
          <div className="glass-card p-4 rounded-xl border border-border/50 flex items-center gap-4">
            <div className="h-10 w-10 rounded-lg bg-teal/10 border border-teal/30 flex items-center justify-center">
              <Cpu className="h-5 w-5 text-teal" />
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">Models in Production</p>
              <p className="text-xl font-bold text-gradient">2 Active</p>
            </div>
          </div>
        </div>
        <a 
          href={MLFLOW_URL} 
          target="_blank" 
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-card border border-border/50 text-xs font-medium hover:bg-card/80 transition-all self-start md:self-center"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Open in MLflow
        </a>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Model Table */}
        <div className="lg:col-span-2 glass-card rounded-2xl border border-border/50 overflow-hidden flex flex-col">
          <div className="px-6 py-4 border-b border-border/30 flex items-center justify-between bg-card/30">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-electric" />
              <h3 className="text-sm font-semibold">Model Registry</h3>
            </div>
            <button className="p-1.5 rounded-md hover:bg-foreground/5 text-muted-foreground transition-colors">
              <Filter className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="overflow-x-auto flex-1">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground border-b border-border/30">
                  <th className="px-6 py-4">Model Name</th>
                  <th className="px-4 py-4">Version</th>
                  <th className="px-4 py-4">Status</th>
                  <th className="px-4 py-4 text-right">Accuracy</th>
                  <th className="px-4 py-4 text-right">F1 Score</th>
                  <th className="px-4 py-4">Date</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/20">
                {MOCK_MODELS.map((model) => (
                  <tr 
                    key={model.id} 
                    className={cn(
                      "group hover:bg-foreground/5 transition-colors cursor-pointer",
                      selectedModel.id === model.id && "bg-electric/5"
                    )}
                    onClick={() => setSelectedModel(model)}
                  >
                    <td className="px-6 py-4">
                      <div className="text-xs font-medium">{model.name}</div>
                    </td>
                    <td className="px-4 py-4">
                      <code className="text-[10px] px-1.5 py-0.5 rounded bg-card border border-border/50 text-muted-foreground">{model.version}</code>
                    </td>
                    <td className="px-4 py-4">
                      <span className={cn("text-[10px] px-2 py-0.5 rounded-full border font-medium", getStatusColor(model.status))}>
                        {model.status}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <span className="text-xs font-mono">{model.accuracy}%</span>
                    </td>
                    <td className="px-4 py-4 text-right">
                      <span className="text-xs font-mono">{model.f1}</span>
                    </td>
                    <td className="px-4 py-4">
                      <span className="text-[10px] text-muted-foreground">{model.date}</span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button 
                          className="p-1.5 rounded-md hover:bg-emerald/10 text-muted-foreground hover:text-emerald transition-colors"
                          title="Set as Production"
                          onClick={(e) => { e.stopPropagation(); alert(`Set ${model.name} to Production`); }}
                        >
                          <CheckCircle2 className="h-3.5 w-3.5" />
                        </button>
                        <button 
                          className="p-1.5 rounded-md hover:bg-electric/10 text-muted-foreground hover:text-electric transition-colors"
                          title="View Details"
                          onClick={(e) => { e.stopPropagation(); setSelectedModel(model); setDrawerOpen(true); }}
                        >
                          <ChevronRight className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Accuracy Chart */}
        <div className="glass-card rounded-2xl border border-border/50 p-6 flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-teal" />
              <h3 className="text-sm font-semibold">Training Accuracy</h3>
            </div>
            <div className="text-[10px] text-muted-foreground bg-card px-2 py-1 rounded border border-border/50">
              {selectedModel.name}
            </div>
          </div>
          
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ACCURACY_HISTORY}>
                <defs>
                  <linearGradient id="colorAcc" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00f2ff" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#00f2ff" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" vertical={false} />
                <XAxis 
                  dataKey="run" 
                  stroke="#94a3b8" 
                  fontSize={10} 
                  tickLine={false} 
                  axisLine={false}
                  tickFormatter={(val) => val.split(' ')[1]}
                />
                <YAxis 
                  stroke="#94a3b8" 
                  fontSize={10} 
                  tickLine={false} 
                  axisLine={false}
                  domain={[90, 100]}
                />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', fontSize: '10px' }}
                  itemStyle={{ color: '#00f2ff' }}
                />
                <Area 
                  type="monotone" 
                  dataKey="accuracy" 
                  stroke="#00f2ff" 
                  strokeWidth={2}
                  fillOpacity={1} 
                  fill="url(#colorAcc)" 
                  animationDuration={1500}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="space-y-4">
            <div className="p-3 rounded-xl bg-card/50 border border-border/30 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-muted-foreground uppercase">Current Accuracy</span>
                <span className="text-xs font-bold text-emerald">{selectedModel.accuracy}%</span>
              </div>
              <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-electric to-teal transition-all duration-1000" 
                  style={{ width: `${selectedModel.accuracy}%` }}
                />
              </div>
            </div>
            <p className="text-[10px] text-muted-foreground leading-relaxed italic">
              "The model shows high stability across recent training runs. Convergence achieved at epoch 45."
            </p>
          </div>
        </div>
      </div>

      {/* Side Drawer for Details */}
      {drawerOpen && (
        <>
          <div 
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-[100]"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="fixed right-0 top-0 h-screen w-full max-w-md bg-slate-900 border-l border-border/50 shadow-2xl z-[101] flex flex-col animate-in slide-in-from-right duration-300">
            <div className="px-6 py-6 border-b border-border/30 flex items-center justify-between bg-card/50">
              <div>
                <h3 className="text-lg font-bold">{selectedModel.name}</h3>
                <p className="text-xs text-muted-foreground">Version {selectedModel.version} · {selectedModel.status}</p>
              </div>
              <button 
                onClick={() => setDrawerOpen(false)}
                className="p-2 rounded-lg hover:bg-foreground/10 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-8">
              {/* Metrics Grid */}
              <section className="space-y-4">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Core Metrics</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-card/30 border border-border/30">
                    <p className="text-[10px] text-muted-foreground mb-1">Precision</p>
                    <p className="text-xl font-mono font-bold text-electric">{selectedModel.precision}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-card/30 border border-border/30">
                    <p className="text-[10px] text-muted-foreground mb-1">Recall</p>
                    <p className="text-xl font-mono font-bold text-teal">{selectedModel.recall}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-card/30 border border-border/30">
                    <p className="text-[10px] text-muted-foreground mb-1">F1 Score</p>
                    <p className="text-xl font-mono font-bold text-purple-400">{selectedModel.f1}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-card/30 border border-border/30">
                    <p className="text-[10px] text-muted-foreground mb-1">Accuracy</p>
                    <p className="text-xl font-mono font-bold text-emerald">{selectedModel.accuracy}%</p>
                  </div>
                </div>
              </section>

              {/* Confusion Matrix Summary */}
              <section className="space-y-4">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Confusion Matrix Summary</h4>
                <div className="p-4 rounded-xl bg-card/30 border border-border/30 space-y-3">
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">True Positives</span>
                    <span className="font-bold text-emerald">1,240</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">True Negatives</span>
                    <span className="font-bold text-emerald">8,520</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">False Positives</span>
                    <span className="font-bold text-coral">24</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">False Negatives</span>
                    <span className="font-bold text-coral">16</span>
                  </div>
                </div>
              </section>

              {/* Hyperparameters */}
              <section className="space-y-4">
                <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Hyperparameters</h4>
                <div className="grid grid-cols-1 gap-2">
                  {[
                    { label: 'Learning Rate', value: '0.001' },
                    { label: 'Batch Size', value: '32' },
                    { label: 'Optimizer', value: 'AdamW' },
                    { label: 'Loss Function', value: 'CrossEntropy' },
                    { label: 'Epochs', value: '100' },
                  ].map((param, i) => (
                    <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-foreground/5 border border-border/10">
                      <span className="text-xs text-muted-foreground">{param.label}</span>
                      <span className="text-xs font-mono font-medium">{param.value}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>

            <div className="p-6 border-t border-border/30 bg-card/50">
              <button 
                className="w-full py-3 rounded-xl bg-gradient-to-r from-electric to-teal text-sm font-bold text-white shadow-lg shadow-electric/20 hover:shadow-electric/40 transition-all"
                onClick={() => { alert(`Setting ${selectedModel.name} ${selectedModel.version} as Production`); setDrawerOpen(false); }}
              >
                Set as Production Model
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
