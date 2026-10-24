import type { ReactNode } from 'react'
import { useI18n } from '../i18n/context'
import { ApiError } from '../lib/api'

export function Card({ title, action, children, className = '' }: {
  title?: ReactNode
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-5 ${className}`}>
      {(title || action) && (
        <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
          {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

export function StatTile({ label, value, delta, deltaLabel, higherIsBetter = true }: {
  label: string
  value: string
  delta?: number | null
  deltaLabel?: string
  higherIsBetter?: boolean
}) {
  const good = delta != null && (higherIsBetter ? delta > 0 : delta < 0)
  const bad = delta != null && (higherIsBetter ? delta < 0 : delta > 0)
  return (
    <div className="rounded-xl border border-line bg-surface px-4 py-3.5">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-ink">{value}</div>
      {deltaLabel && (
        <div className={`mt-1 text-xs ${good ? 'text-good' : bad ? 'text-critical' : 'text-muted'}`}>
          {good ? '▲ ' : bad ? '▼ ' : ''}
          {deltaLabel}
        </div>
      )}
    </div>
  )
}

export function Button({ children, variant = 'primary', className = '', ...props }: {
  variant?: 'primary' | 'ghost'
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const styles =
    variant === 'primary'
      ? 'bg-accent text-accent-ink hover:opacity-90 disabled:opacity-50'
      : 'border border-line text-ink-2 hover:bg-surface-2 hover:text-ink'
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed ${styles} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  )
}

/** Shows an API error; the two failures the UI knows by code are translated, anything else is the server's text. */
export function ErrorBanner({ error }: { error: Error }) {
  const { t } = useI18n()
  const message = error instanceof ApiError && error.code ? t.errors[error.code] : error.message
  return (
    <div role="alert" className="rounded-lg border border-critical/40 bg-critical/10 px-4 py-3 text-sm text-ink">
      <span className="font-semibold text-critical">{t.common.error} · </span>
      {message}
    </div>
  )
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useI18n()
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-muted border-t-transparent" />
      {label ?? t.common.loading}
    </span>
  )
}

export function Segmented<T extends string>({ value, options, onChange }: {
  value: T
  options: { value: T; label: string }[]
  onChange: (v: T) => void
}) {
  return (
    <div className="inline-flex rounded-lg border border-line p-0.5 text-xs" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={`rounded-md px-2.5 py-1 transition ${
            value === o.value ? 'bg-surface-2 text-ink' : 'text-muted hover:text-ink'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}
