import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Backtest', end: true },
  { to: '/history', label: 'History', end: false },
  { to: '/pairs', label: 'Pair scanner', end: false },
  { to: '/bots', label: 'Paper bot', end: false },
]

function ThemeToggle() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() =>
    document.documentElement.dataset.theme === 'light' ? 'light' : 'dark',
  )
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('theme', theme)
    } catch {
      /* storage unavailable */
    }
  }, [theme])
  return (
    <button
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
      className="rounded-lg border border-line px-2.5 py-1.5 text-xs text-ink-2 hover:text-ink"
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
    >
      {theme === 'dark' ? '☀ Light' : '☾ Dark'}
    </button>
  )
}

export function Layout() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-page/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3 sm:px-6">
          <NavLink to="/" className="flex items-center gap-2 font-semibold text-ink">
            <img src="/favicon.svg" alt="" className="h-6 w-6" />
            quant-lab
          </NavLink>
          <nav className="flex gap-1 overflow-x-auto text-sm">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-md px-3 py-1.5 transition ${
                    isActive ? 'bg-surface-2 text-ink' : 'text-muted hover:text-ink'
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <a
              href="https://github.com/ardabaranbaytar/quant-lab"
              target="_blank"
              rel="noreferrer"
              className="hidden text-xs text-muted hover:text-ink sm:block"
            >
              GitHub
            </a>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-muted sm:px-6">
        Research and education only — not investment advice. Data: Yahoo Finance.
      </footer>
    </div>
  )
}
