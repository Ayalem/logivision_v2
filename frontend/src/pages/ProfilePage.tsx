import { useState, useEffect } from 'react'
import { User, Mail, Phone, Calendar, Shield, Edit2, Check, X, AlertCircle, Loader2 } from 'lucide-react'
import { useAppStore } from '@/lib/store'
import { cn } from '@/lib/utils'

export function ProfilePage() {
  const user = useAppStore((s) => s.user)
  const authToken = useAppStore((s) => s.authToken)
  const setUser = useAppStore((s) => s.setUser)
  
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  
  const [formData, setFormData] = useState({
    name: user?.name ?? 'Operator',
    email: user?.email ?? 'operator@logivision.ai',
    phone: user?.phone ?? '+33 1 23 45 67 89',
    zone: user?.zone ?? 'General'
  })

  // Update form data when user changes
  useEffect(() => {
    if (user) {
      setFormData({
        name: user.name ?? 'Operator',
        email: user.email ?? 'operator@logivision.ai',
        phone: user.phone ?? '+33 1 23 45 67 89',
        zone: user.zone ?? 'General'
      })
    }
  }, [user])

  const handleSave = async () => {
    if (!user?.id || !authToken) {
      setError('User information not available')
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
        body: JSON.stringify({
          name: formData.name,
          email: formData.email,
          phone: formData.phone,
          zone: formData.zone
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to save profile')
      }

      const updatedUser = await response.json()
      setUser(updatedUser)
      setIsEditing(false)
      setSuccessMessage('Profile updated successfully!')
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to save changes'
      setError(errorMsg)
    } finally {
      setIsSaving(false)
    }
  }

  const handleCancel = () => {
    setIsEditing(false)
    setError(null)
    // Reset form to current user data
    if (user) {
      setFormData({
        name: user.name ?? 'Operator',
        email: user.email ?? 'operator@logivision.ai',
        phone: user.phone ?? '+33 1 23 45 67 89',
        zone: user.zone ?? 'General'
      })
    }
  }

  if (!user) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="glass-card rounded-2xl p-8 shadow-soft flex items-center gap-4 border-l-4 border-coral">
          <AlertCircle className="h-6 w-6 text-coral flex-shrink-0" />
          <div>
            <h3 className="font-bold text-coral">Could not load profile data</h3>
            <p className="text-sm text-muted-foreground">Please log in again to view your profile.</p>
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
          <button
            onClick={() => setError(null)}
            className="ml-auto text-coral hover:text-coral/80"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Success Banner */}
      {successMessage && (
        <div className="glass-card rounded-2xl p-4 shadow-soft flex items-center gap-3 border-l-4 border-emerald bg-emerald/5">
          <Check className="h-5 w-5 text-emerald flex-shrink-0" />
          <p className="text-sm font-semibold text-emerald">{successMessage}</p>
        </div>
      )}

      {/* Profile Header Card */}
      <div className="glass-card rounded-2xl overflow-hidden shadow-soft">
        <div className="h-32 bg-gradient-to-r from-electric/40 via-teal/40 to-indigo/40 relative">
          <div className="absolute -bottom-12 left-8">
            <div className="h-24 w-24 rounded-2xl bg-card border-4 border-background flex items-center justify-center shadow-xl">
              <div className="h-20 w-20 rounded-xl bg-gradient-to-br from-electric/20 to-teal/20 flex items-center justify-center text-electric text-3xl font-bold">
                {formData.name.charAt(0).toUpperCase()}
              </div>
            </div>
          </div>
        </div>
        <div className="pt-16 pb-6 px-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold">{formData.name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-electric/10 text-electric border border-electric/20">
                {user.role ?? 'operator'}
              </span>
              <span className="text-xs text-muted-foreground">ID: {user.id}</span>
            </div>
          </div>
          <button 
            onClick={() => isEditing ? handleSave() : setIsEditing(true)}
            disabled={isSaving}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all disabled:opacity-50",
              isEditing 
                ? "bg-emerald text-white hover:bg-emerald/90" 
                : "bg-foreground/5 hover:bg-foreground/10 text-foreground border border-border/50"
            )}
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : isEditing ? (
              <>
                <Check className="h-4 w-4" />
                Sauvegarder
              </>
            ) : (
              <>
                <Edit2 className="h-4 w-4" />
                Modifier le profil
              </>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: Details */}
        <div className="md:col-span-2 space-y-6">
          <div className="glass-card rounded-2xl p-6 shadow-soft space-y-6">
            <div className="flex items-center justify-between border-b border-border/30 pb-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Informations Personnelles</h3>
              {isEditing && (
                <button onClick={handleCancel} className="text-xs text-muted-foreground hover:text-coral flex items-center gap-1">
                  <X className="h-3 w-3" /> Annuler
                </button>
              )}
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="space-y-1.5">
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold flex items-center gap-1.5">
                  <User className="h-3 w-3" /> Nom Complet
                </label>
                {isEditing ? (
                  <input 
                    type="text" 
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
                  />
                ) : (
                  <p className="text-sm font-medium">{formData.name}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold flex items-center gap-1.5">
                  <Mail className="h-3 w-3" /> Email
                </label>
                {isEditing ? (
                  <input 
                    type="email" 
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
                  />
                ) : (
                  <p className="text-sm font-medium">{formData.email}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold flex items-center gap-1.5">
                  <Phone className="h-3 w-3" /> Téléphone
                </label>
                {isEditing ? (
                  <input 
                    type="text" 
                    value={formData.phone}
                    onChange={(e) => setFormData({...formData, phone: e.target.value})}
                    className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
                  />
                ) : (
                  <p className="text-sm font-medium">{formData.phone}</p>
                )}
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold flex items-center gap-1.5">
                  <Calendar className="h-3 w-3" /> Zone
                </label>
                {isEditing ? (
                  <input 
                    type="text" 
                    value={formData.zone}
                    onChange={(e) => setFormData({...formData, zone: e.target.value})}
                    className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
                  />
                ) : (
                  <p className="text-sm font-medium">{formData.zone}</p>
                )}
              </div>
            </div>
          </div>

          <div className="glass-card rounded-2xl p-6 shadow-soft">
            <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground border-b border-border/30 pb-4 mb-4">
              Activité Récente
            </h3>
            <div className="space-y-4">
              {[
                { action: 'Connexion réussie', time: 'Il y a 2 heures', location: 'Paris, FR · Chrome' },
                { action: 'Modification de zone', time: 'Hier, 14:20', location: 'Zone Alpha-01' },
                { action: 'Alerte résolue', time: '12 Juin, 09:15', location: 'Caméra #04' },
              ].map((item, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="h-2 w-2 rounded-full bg-electric mt-1.5" />
                  <div>
                    <p className="text-xs font-semibold">{item.action}</p>
                    <p className="text-[10px] text-muted-foreground">{item.time} · {item.location}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Stats/Badge */}
        <div className="space-y-6">
          <div className="glass-card rounded-2xl p-6 shadow-soft text-center">
            <div className="h-16 w-16 rounded-full bg-emerald/10 text-emerald flex items-center justify-center mx-auto mb-4">
              <Shield className="h-8 w-8" />
            </div>
            <h4 className="text-sm font-bold">Compte Vérifié</h4>
            <p className="text-[10px] text-muted-foreground mt-1">Niveau de sécurité : Élevé</p>
            <div className="mt-4 pt-4 border-t border-border/30 grid grid-cols-2 gap-2">
              <div>
                <p className="text-lg font-bold text-electric">124</p>
                <p className="text-[8px] uppercase tracking-wider text-muted-foreground">Alertes gérées</p>
              </div>
              <div>
                <p className="text-lg font-bold text-teal">99.2%</p>
                <p className="text-[8px] uppercase tracking-wider text-muted-foreground">Précision</p>
              </div>
            </div>
          </div>

          <div className="glass-card rounded-2xl p-6 shadow-soft">
            <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-4">Rôles & Permissions</h4>
            <div className="space-y-2">
              {['Accès aux caméras', 'Gestion des zones', 'Rapports analytiques', 'Alertes temps réel'].map((p) => (
                <div key={p} className="flex items-center gap-2 text-xs">
                  <Check className="h-3 w-3 text-emerald" />
                  <span>{p}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Account Management Footer */}
      <div className="glass-card rounded-2xl p-6 shadow-soft flex items-center justify-between border-t border-border/30">
        <div className="flex items-center gap-4">
          <div className="h-10 w-10 rounded-full bg-foreground/5 flex items-center justify-center text-muted-foreground">
            <User className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-bold">Gestion du compte</p>
            <p className="text-[10px] text-muted-foreground">Modifier vos accès ou quitter la session</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={() => useAppStore.getState().setView('settings')}
            className="px-4 py-2 rounded-lg text-xs font-bold bg-foreground/5 hover:bg-foreground/10 transition-colors"
          >
            Paramètres
          </button>
          <button 
            onClick={() => useAppStore.getState().logout()}
            className="px-4 py-2 rounded-lg text-xs font-bold bg-coral/10 text-coral hover:bg-coral/20 transition-colors"
          >
            Déconnexion
          </button>
        </div>
      </div>
    </div>
  )
}
