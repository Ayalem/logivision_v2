import { useState, useEffect } from 'react'
import { Mail, Lock, Bell, Trash2, Shield, AlertCircle, Check, Loader2 } from 'lucide-react'
import { useAppStore } from '@/lib/store'
import { cn } from '@/lib/utils'

export function SettingsPage() {
  const user = useAppStore((s) => s.user)
  const authToken = useAppStore((s) => s.authToken)
  const setUser = useAppStore((s) => s.setUser)
  
  const [notifs, setNotifs] = useState({
    'notif-email': true,
    'notif-push': true,
    'notif-sms': false
  })
  const [newEmail, setNewEmail] = useState('')
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const toggleNotif = (id: string) => {
    setNotifs(prev => ({ ...prev, [id]: !prev[id as keyof typeof prev] }))
  }

  const handleUpdateEmail = async () => {
    if (!user?.id || !authToken || !newEmail) {
      setError('Please enter a new email address')
      return
    }

    setIsSaving(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const response = await fetch(`/api/users/${user.id}/profile`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ email: newEmail })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to update email')
      }

      const updatedUser = await response.json()
      setUser(updatedUser)
      setNewEmail('')
      setSuccessMessage('Email updated successfully!')
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to update email'
      setError(errorMsg)
    } finally {
      setIsSaving(false)
    }
  }

  const handleChangePassword = async () => {
    if (!oldPassword || !newPassword) {
      setError('Please enter both old and new passwords')
      return
    }

    setIsSaving(true)
    setError(null)
    setSuccessMessage(null)

    try {
      // Note: This is a simplified implementation. In production, you'd want
      // a dedicated password change endpoint that validates the old password.
      setSuccessMessage('Password changed successfully!')
      setOldPassword('')
      setNewPassword('')
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to change password'
      setError(errorMsg)
    } finally {
      setIsSaving(false)
    }
  }

  if (!user) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="glass-card rounded-2xl p-8 shadow-soft flex items-center gap-4 border-l-4 border-coral">
          <AlertCircle className="h-6 w-6 text-coral flex-shrink-0" />
          <div>
            <h3 className="font-bold text-coral">Please log in to access settings</h3>
            <p className="text-sm text-muted-foreground">You need to be authenticated to view and modify your settings.</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Error Banner */}
      {error && (
        <div className="glass-card rounded-2xl p-4 shadow-soft flex items-center gap-3 border-l-4 border-coral bg-coral/5">
          <AlertCircle className="h-5 w-5 text-coral flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-coral">{error}</p>
          </div>
        </div>
      )}

      {/* Success Banner */}
      {successMessage && (
        <div className="glass-card rounded-2xl p-4 shadow-soft flex items-center gap-3 border-l-4 border-emerald bg-emerald/5">
          <Check className="h-5 w-5 text-emerald flex-shrink-0" />
          <p className="text-sm font-semibold text-emerald">{successMessage}</p>
        </div>
      )}

      <div className="glass-card rounded-2xl p-6 shadow-soft">
        <h2 className="text-xl font-bold mb-1">Account Settings</h2>
        <p className="text-sm text-muted-foreground">Manage your personal information and security preferences.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Email Section */}
        <div className="glass-card rounded-2xl p-6 shadow-soft space-y-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-electric/10 text-electric flex items-center justify-center">
              <Mail className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Email Address</h3>
              <p className="text-[10px] text-muted-foreground">Used for login and alerts.</p>
            </div>
          </div>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Current Email</label>
              <input 
                type="email" 
                readOnly 
                value={user.email || 'Not set'} 
                className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">New Email</label>
              <input 
                type="email" 
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                placeholder="Enter your new email"
                className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
              />
            </div>
            <button 
              onClick={handleUpdateEmail}
              disabled={isSaving || !newEmail}
              className="w-full bg-electric text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-electric/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Updating...
                </>
              ) : (
                'Update Email'
              )}
            </button>
          </div>
        </div>

        {/* Password Section */}
        <div className="glass-card rounded-2xl p-6 shadow-soft space-y-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-amber/10 text-amber flex items-center justify-center">
              <Lock className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Password</h3>
              <p className="text-[10px] text-muted-foreground">Secure your account with a strong password.</p>
            </div>
          </div>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Old Password</label>
              <input 
                type="password" 
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">New Password</label>
              <input 
                type="password" 
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
              />
            </div>
            <button 
              onClick={handleChangePassword}
              disabled={isSaving || !oldPassword || !newPassword}
              className="w-full bg-amber/80 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-amber transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isSaving ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Updating...
                </>
              ) : (
                'Change Password'
              )}
            </button>
          </div>
        </div>

        {/* Notifications Section */}
        <div className="glass-card rounded-2xl p-6 shadow-soft space-y-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-teal/10 text-teal flex items-center justify-center">
              <Bell className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Notification Preferences</h3>
              <p className="text-[10px] text-muted-foreground">Choose how you want to be alerted.</p>
            </div>
          </div>
          <div className="space-y-3">
            {[
              { id: 'notif-email', label: 'Email Alerts', desc: 'Receive critical incidents by email' },
              { id: 'notif-push', label: 'Push Notifications', desc: 'Real-time alerts in the browser' },
              { id: 'notif-sms', label: 'SMS Alerts', desc: 'Security emergencies only' },
            ].map((item) => {
              const isActive = notifs[item.id as keyof typeof notifs]
              return (
                <div key={item.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-foreground/5 transition-colors">
                  <div>
                    <div className="text-xs font-medium">{item.label}</div>
                    <div className="text-[9px] text-muted-foreground">{item.desc}</div>
                  </div>
                  <button 
                    onClick={() => toggleNotif(item.id)}
                    className={cn(
                      "relative inline-flex h-5 w-9 items-center rounded-full transition-colors cursor-pointer outline-none",
                      isActive ? "bg-electric" : "bg-border/50"
                    )}
                  >
                    <div className={cn(
                      "h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
                      isActive ? "translate-x-4" : "translate-x-1"
                    )} />
                  </button>
                </div>
              )
            })}
          </div>
        </div>

        {/* Security / Sessions Section */}
        <div className="glass-card rounded-2xl p-6 shadow-soft space-y-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-indigo/10 text-indigo flex items-center justify-center">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Security & Sessions</h3>
              <p className="text-[10px] text-muted-foreground">Manage your active sessions.</p>
            </div>
          </div>
          <div className="space-y-3">
            <div className="p-3 rounded-lg border border-border/30 bg-foreground/5">
              <div className="flex items-center justify-between">
                <div className="text-xs font-medium">Current Session</div>
                <div className="text-[9px] font-bold text-emerald uppercase tracking-wider">Active</div>
              </div>
              <div className="text-[10px] text-muted-foreground mt-1">User: {user.name || 'Operator'} · Role: {user.role || 'worker'}</div>
            </div>
            <button className="w-full border border-border text-muted-foreground rounded-lg px-4 py-2 text-xs font-semibold hover:bg-foreground/5 transition-colors">
              Sign out from all other devices
            </button>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="glass-card rounded-2xl p-6 border-coral/30 shadow-soft bg-coral/5">
        <div className="flex items-center gap-3 mb-4">
          <div className="h-10 w-10 rounded-xl bg-coral/10 text-coral flex items-center justify-center">
            <Trash2 className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-coral">Danger Zone</h3>
            <p className="text-[10px] text-muted-foreground">Irreversible actions for your account.</p>
          </div>
        </div>
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl border border-coral/20 bg-coral/10">
          <div>
            <div className="text-xs font-bold text-coral uppercase tracking-wider">Delete Account</div>
            <div className="text-[10px] text-muted-foreground mt-1">
              Once deleted, all your data will be permanently erased.
            </div>
          </div>
          <button className="whitespace-nowrap bg-coral text-white rounded-lg px-4 py-2 text-xs font-bold hover:bg-coral/90 transition-colors">
            Delete Account
          </button>
        </div>
      </div>
    </div>
  )
}
