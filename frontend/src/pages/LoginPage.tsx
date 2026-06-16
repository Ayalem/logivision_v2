/**
 * LoginPage — Futuristic admin login screen with glassmorphism effects.
 * Supports admin and operator roles with enhanced features.
 */
import { useState } from 'react'
import { Lock, Mail, Eye, EyeOff, Warehouse, CheckCircle2 } from 'lucide-react'
import { useAppStore } from '@/lib/store'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/lib/i18n'

export function LoginPage() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberMe, setRememberMe] = useState(false)
  const [role, setRole] = useState<'admin' | 'worker'>('admin')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [showForgotPassword, setShowForgotPassword] = useState(false)
  const [showRequestAccess, setShowRequestAccess] = useState(false)

  const login = useAppStore((s) => s.login)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      if (!email || !password) {
        throw new Error(t('pleaseEnterEmailPassword'))
      }

      if (email === 'admin@logivision.com' && password === 'admin123') {
        const token = `token_${Date.now()}`
        login(token, 'admin')
      } else if (email === 'worker@logivision.com' && password === 'worker123') {
        const token = `token_${Date.now()}`
        login(token, 'worker')
      } else {
        throw new Error(t('invalidCredentials'))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : t('loginFailed'))
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-slate-900">
      <div className="absolute inset-0 opacity-10">
        <svg className="w-full h-full" preserveAspectRatio="none">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      <div className="relative z-10 w-full max-w-md px-6">
        <div className="text-center mb-10">
          <div className="flex justify-center mb-6">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-electric/30 to-teal/30 border border-electric/50 flex items-center justify-center shadow-2xl">
              <Warehouse className="h-8 w-8 text-electric" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-white mb-2">{t('logivision')}</h1>
          <p className="text-sm text-muted-foreground">{t('warehouseIntelligence')}</p>
        </div>

        <div className="glass-card rounded-2xl p-8 border border-white/10 backdrop-blur-xl shadow-2xl">
          <form onSubmit={handleLogin} className="space-y-6">
            <div className="space-y-3">
              <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                {t('loginAs')}
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setRole('admin')}
                  className={cn(
                    'py-2.5 rounded-lg font-bold text-xs transition-all border',
                    role === 'admin' ? 'bg-electric/20 border-electric text-electric' : 'bg-white/5 border-white/10 text-muted-foreground'
                  )}
                >
                  {t('admin')}
                </button>
                <button
                  type="button"
                  onClick={() => setRole('worker')}
                  className={cn(
                    'py-2.5 rounded-lg font-bold text-xs transition-all border',
                    role === 'worker' ? 'bg-electric/20 border-electric text-electric' : 'bg-white/5 border-white/10 text-muted-foreground'
                  )}
                >
                  {t('worker')}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{t('email')}</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={role === 'admin' ? 'admin@logivision.com' : 'worker@logivision.com'}
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:border-electric/50"
                />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">{t('password')}</label>
                <button type="button" className="text-[10px] text-electric hover:underline">{t('forgotPassword')}</button>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-10 py-2.5 rounded-lg bg-white/5 border border-white/10 text-sm focus:outline-none focus:border-electric/50"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <input type="checkbox" className="rounded border-white/10 bg-white/5 text-electric" />
              <label className="text-xs text-muted-foreground">{t('rememberMe')}</label>
            </div>

            {error && <div className="p-3 rounded-lg bg-coral/10 border border-coral/30 text-[10px] text-coral font-bold">{error}</div>}

            <div className="p-3 rounded-lg bg-teal/10 border border-teal/30 text-[10px] text-teal space-y-1">
              <p className="font-bold">{t('demoCredentials')}</p>
              <p>{t('adminDemo')}</p>
              <p>{t('workerDemo')}</p>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 rounded-xl bg-electric text-white font-bold text-sm shadow-lg shadow-electric/20 hover:bg-electric/90 transition-all disabled:opacity-50"
            >
              {isLoading ? t('loggingIn') : t('signIn')}
            </button>
          </form>

          <div className="mt-8 text-center">
            <p className="text-xs text-muted-foreground">
              {t('dontHaveAccount')}{' '}
              <button className="text-electric font-bold hover:underline">{t('requestAccess')}</button>
            </p>
          </div>
        </div>
        
        <p className="mt-8 text-center text-[10px] text-muted-foreground uppercase tracking-widest">
          {t('allRightsReserved')}
        </p>
      </div>
    </div>
  )
}
