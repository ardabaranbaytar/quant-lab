import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useI18n } from '../i18n/context'
import { LanguageSwitcher } from './LanguageSwitcher'

function ThemeToggle() {
  const { t } = useI18n()
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
      className="whitespace-nowrap rounded-lg border border-line px-2.5 py-1.5 text-xs text-ink-2 hover:text-ink"
      aria-label={theme === 'dark' ? t.theme.toLight : t.theme.toDark}
    >
      {theme === 'dark' ? t.theme.light : t.theme.dark}
    </button>
  )
}

export function Layout() {
  const { t } = useI18n()
  const nav = [
    { to: '/', label: t.nav.backtest, end: true },
    { to: '/history', label: t.nav.history, end: false },
    { to: '/pairs', label: t.nav.pairs, end: false },
    { to: '/bots', label: t.nav.bot, end: false },
  ]

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-line bg-page/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <NavLink to="/" className="flex shrink-0 items-center gap-2 font-semibold whitespace-nowrap text-ink">
            <img src="/favicon.svg" alt="" className="h-6 w-6" />
            quant-lab
          </NavLink>
          {/* Own row on phones so the three language buttons and the theme toggle never squeeze it. */}
          <nav className="order-last flex w-full gap-1 overflow-x-auto text-sm sm:order-none sm:w-auto">
            {nav.map((n) => (
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
            <LanguageSwitcher />
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-muted sm:px-6">{t.footer}</footer>
    </div>
  )
}
