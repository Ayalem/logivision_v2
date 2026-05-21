import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'logivision-theme'
type Mode = 'light' | 'dark'

function readInitial(): Mode {
  if (typeof window === 'undefined') return 'light'
  const stored = window.localStorage.getItem(STORAGE_KEY) as Mode | null
  if (stored === 'light' || stored === 'dark') return stored
  // Default to light — the warehouse UI ships in light mode.
  return 'light'
}

function apply(mode: Mode) {
  const root = document.documentElement
  root.classList.toggle('dark', mode === 'dark')
}

export function useTheme() {
  const [mode, setMode] = useState<Mode>(readInitial)

  useEffect(() => {
    apply(mode)
    window.localStorage.setItem(STORAGE_KEY, mode)
  }, [mode])

  const toggle = useCallback(() => setMode((m) => (m === 'dark' ? 'light' : 'dark')), [])
  const set = useCallback((m: Mode) => setMode(m), [])
  return { mode, isDark: mode === 'dark', toggle, set }
}
