import { Mail, Lock, Bell, Trash2, Shield } from 'lucide-react'
import { cn } from '@/lib/utils'

export function SettingsPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="glass-card rounded-2xl p-6 shadow-soft">
        <h2 className="text-xl font-bold mb-1">Paramètres du compte</h2>
        <p className="text-sm text-muted-foreground">Gérez vos informations personnelles et vos préférences de sécurité.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Email Section */}
        <div className="glass-card rounded-2xl p-6 shadow-soft space-y-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-electric/10 text-electric flex items-center justify-center">
              <Mail className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Adresse Email</h3>
              <p className="text-[10px] text-muted-foreground">Utilisée pour la connexion et les alertes.</p>
            </div>
          </div>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Email actuel</label>
              <input 
                type="email" 
                readOnly 
                value="operator@logivision.ai" 
                className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Nouvel email</label>
              <input 
                type="email" 
                placeholder="Entrez votre nouvel email"
                className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
              />
            </div>
            <button className="w-full bg-electric text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-electric/90 transition-colors">
              Mettre à jour l'email
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
              <h3 className="text-sm font-semibold">Mot de passe</h3>
              <p className="text-[10px] text-muted-foreground">Sécurisez votre compte avec un mot de passe fort.</p>
            </div>
          </div>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Ancien mot de passe</label>
              <input 
                type="password" 
                className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground font-bold">Nouveau mot de passe</label>
              <input 
                type="password" 
                className="w-full bg-foreground/5 border border-border/50 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-electric"
              />
            </div>
            <button className="w-full bg-amber/80 text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-amber transition-colors">
              Changer le mot de passe
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
              <h3 className="text-sm font-semibold">Préférences de notification</h3>
              <p className="text-[10px] text-muted-foreground">Choisissez comment vous souhaitez être alerté.</p>
            </div>
          </div>
          <div className="space-y-3">
            {[
              { id: 'notif-email', label: 'Alertes par email', desc: 'Recevoir les incidents critiques par email' },
              { id: 'notif-push', label: 'Notifications push', desc: 'Alertes en temps réel sur le navigateur' },
              { id: 'notif-sms', label: 'Alertes SMS', desc: 'Urgences de sécurité uniquement' },
            ].map((item) => (
              <div key={item.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-foreground/5 transition-colors">
                <div>
                  <div className="text-xs font-medium">{item.label}</div>
                  <div className="text-[9px] text-muted-foreground">{item.desc}</div>
                </div>
                <div className="relative inline-flex h-5 w-9 items-center rounded-full bg-border/50 cursor-pointer">
                  <div className="h-4 w-4 translate-x-1 rounded-full bg-white shadow-sm" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Security / Sessions Section */}
        <div className="glass-card rounded-2xl p-6 shadow-soft space-y-4">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-10 w-10 rounded-xl bg-indigo/10 text-indigo flex items-center justify-center">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold">Sécurité & Sessions</h3>
              <p className="text-[10px] text-muted-foreground">Gérez vos sessions actives.</p>
            </div>
          </div>
          <div className="space-y-3">
            <div className="p-3 rounded-lg border border-border/30 bg-foreground/5">
              <div className="flex items-center justify-between">
                <div className="text-xs font-medium">Session actuelle</div>
                <div className="text-[9px] font-bold text-emerald uppercase tracking-wider">Actif</div>
              </div>
              <div className="text-[10px] text-muted-foreground mt-1">Chrome sur Windows · Paris, FR</div>
            </div>
            <button className="w-full border border-border text-muted-foreground rounded-lg px-4 py-2 text-xs font-semibold hover:bg-foreground/5 transition-colors">
              Déconnexion de tous les autres appareils
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
            <h3 className="text-sm font-semibold text-coral">Zone de danger</h3>
            <p className="text-[10px] text-muted-foreground">Actions irréversibles pour votre compte.</p>
          </div>
        </div>
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl border border-coral/20 bg-coral/10">
          <div>
            <div className="text-xs font-bold text-coral uppercase tracking-wider">Supprimer le compte</div>
            <div className="text-[10px] text-muted-foreground mt-1">
              Une fois supprimé, toutes vos données seront définitivement effacées.
            </div>
          </div>
          <button className="whitespace-nowrap bg-coral text-white rounded-lg px-4 py-2 text-xs font-bold hover:bg-coral/90 transition-colors">
            Supprimer le compte
          </button>
        </div>
      </div>
    </div>
  )
}
