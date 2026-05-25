/**
 * LoginPage — Futuristic admin login screen with glassmorphism effects.
 * Supports admin and operator roles.
 */
import { useState } from 'react'
import { Lock, Mail, Eye, EyeOff, Warehouse, ArrowRight } from 'lucide-react'
import { useAppStore } from '@/lib/store'
import { cn } from '@/lib/utils'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [role, setRole] = useState<'admin' | 'operator'>('admin')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  const login = useAppStore((s) => s.login)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setIsLoading(true)

    try {
      // Simulate API call — replace with actual authentication
      if (!email || !password) {
        throw new Error('Please enter email and password')
      }

      // Mock authentication (in production, call your backend API)
      if (email === 'admin@logivision.com' && password === 'admin123') {
        // Simulate token generation
        const token = `token_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
        login(token, 'admin')
      } else if (email === 'operator@logivision.com' && password === 'operator123') {
        const token = `token_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
        login(token, 'operator')
      } else {
        throw new Error('Invalid email or password')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Animated background gradients */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-electric/20 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob" />
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-teal/20 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000" />
        <div className="absolute -bottom-8 left-1/2 w-96 h-96 bg-purple/20 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000" />
      </div>

      {/* Content */}
      <div className="relative z-10 w-full max-w-md px-6">
        {/* Logo Section */}
        <div className="text-center mb-12">
          <div className="flex justify-center mb-6">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-electric/30 to-teal/30 border border-electric/50 flex items-center justify-center shadow-2xl shadow-electric/20">
              <Warehouse className="h-8 w-8 text-electric" />
            </div>
          </div>
          <h1 className="text-4xl font-bold text-gradient mb-2">LOGIVISION</h1>
          <p className="text-sm text-muted-foreground">Warehouse Intelligence Platform</p>
        </div>

        {/* Login Card */}
        <div className="glass-card rounded-2xl p-8 border border-electric/20 backdrop-blur-xl shadow-2xl shadow-electric/10">
          <form onSubmit={handleLogin} className="space-y-6">
            {/* Role Selection */}
            <div className="space-y-3">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Login As
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setRole('admin')}
                  className={cn(
                    'py-3 px-4 rounded-lg font-medium text-sm transition-all duration-200 border',
                    role === 'admin'
                      ? 'bg-gradient-to-r from-electric/20 to-teal/10 border-electric/50 text-electric shadow-lg shadow-electric/20'
                      : 'bg-card/40 border-border/50 text-muted-foreground hover:border-electric/30 hover:text-foreground'
                  )}
                >
                  Admin
                </button>
                <button
                  type="button"
                  onClick={() => setRole('operator')}
                  className={cn(
                    'py-3 px-4 rounded-lg font-medium text-sm transition-all duration-200 border',
                    role === 'operator'
                      ? 'bg-gradient-to-r from-electric/20 to-teal/10 border-electric/50 text-electric shadow-lg shadow-electric/20'
                      : 'bg-card/40 border-border/50 text-muted-foreground hover:border-electric/30 hover:text-foreground'
                  )}
                >
                  Operator
                </button>
              </div>
            </div>

            {/* Email Input */}
            <div className="space-y-2">
              <label htmlFor="email" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={role === 'admin' ? 'admin@logivision.com' : 'operator@logivision.com'}
                  className="w-full pl-10 pr-4 py-3 rounded-lg bg-card/50 border border-border/50 text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-electric/50 focus:ring-1 focus:ring-electric/30 transition-all duration-200"
                />
              </div>
            </div>

            {/* Password Input */}
            <div className="space-y-2">
              <label htmlFor="password" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={role === 'admin' ? 'admin123' : 'operator123'}
                  className="w-full pl-10 pr-10 py-3 rounded-lg bg-card/50 border border-border/50 text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-electric/50 focus:ring-1 focus:ring-electric/30 transition-all duration-200"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-3 rounded-lg bg-coral/10 border border-coral/30 text-xs text-coral">
                {error}
              </div>
            )}

            {/* Demo Credentials Info */}
            <div className="p-3 rounded-lg bg-teal/10 border border-teal/30 text-xs text-teal space-y-1">
              <p className="font-semibold">Demo Credentials:</p>
              <p>Admin: admin@logivision.com / admin123</p>
              <p>Operator: operator@logivision.com / operator123</p>
            </div>

            {/* Login Button */}
            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 px-4 rounded-lg bg-gradient-to-r from-electric to-teal font-semibold text-white flex items-center justify-center gap-2 hover:shadow-lg hover:shadow-electric/30 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <div className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  Logging in...
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center text-xs text-muted-foreground">
          <p>Logivision AI Warehouse Intelligence Platform</p>
          <p className="mt-2">© 2024 All rights reserved</p>
        </div>
      </div>
    </div>
  )
}
