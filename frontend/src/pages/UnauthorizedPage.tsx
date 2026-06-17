import { ShieldAlert } from 'lucide-react'
import { useAppStore } from '@/lib/store'

export function UnauthorizedPage() {
  const setView = useAppStore((s) => s.setView)

  return (
    <div className="h-full flex flex-col items-center justify-center text-center p-6">
      <div className="h-16 w-16 rounded-2xl bg-coral/10 border border-coral/30 flex items-center justify-center mb-6">
        <ShieldAlert className="h-8 w-8 text-coral" />
      </div>
      <h1 className="text-2xl font-bold mb-2">Access Denied</h1>
      <p className="text-muted-foreground mb-8 max-w-md">
        You do not have the required permissions to view this page. Please contact your administrator if you believe this is an error.
      </p>
      <button
        onClick={() => setView('overview')}
        className="px-6 py-2 rounded-lg bg-gradient-to-r from-electric to-teal text-sm font-medium text-white hover:shadow-lg hover:shadow-electric/30 transition-all"
      >
        Back to Overview
      </button>
    </div>
  )
}
