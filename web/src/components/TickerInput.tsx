import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n/context'
import { api } from '../lib/api'

// The shape the API accepts (api/schemas.py): letters, digits and . - = ^, up to 16 characters.
const SYMBOL = /^[A-Z0-9^][A-Z0-9.\-=]{0,15}$/

/**
 * Chip-style ticker entry: type and press Enter, comma or space.
 * New symbols are checked with the server first, so a typo is refused here instead of failing a run later.
 */
export function TickerInput({ value, onChange, max = 100 }: {
  value: string[]
  onChange: (tickers: string[]) => void
  max?: number
}) {
  const { t } = useI18n()
  const [draft, setDraft] = useState('')
  const [checking, setChecking] = useState(0) // lookups in flight
  const [problem, setProblem] = useState<string | null>(null)
  // The current list, for lookups that finish after the visitor has already changed it.
  const latest = useRef(value)
  useEffect(() => {
    latest.current = value
  }, [value])

  const commit = async (raw: string) => {
    const typed = [...new Set(raw.toUpperCase().split(/[\s,;]+/).filter(Boolean))]
    if (!typed.length) return
    setDraft('')
    setProblem(null)

    const fresh = typed.filter((s) => !latest.current.includes(s))
    const badFormat = fresh.filter((s) => !SYMBOL.test(s))
    const candidates = fresh.filter((s) => SYMBOL.test(s))
    let missing: string[] = []
    if (candidates.length) {
      setChecking((n) => n + 1)
      try {
        const { results } = await api.checkTickers(candidates)
        missing = candidates.filter((s) => results[s] === false)
      } catch {
        /* could not check (server or Yahoo down): let it in, a run still reports symbols without data */
      } finally {
        setChecking((n) => n - 1)
      }
    }

    const accepted = candidates.filter((s) => !missing.includes(s))
    if (accepted.length) onChange([...new Set([...latest.current, ...accepted])].slice(0, max))
    const notes = [
      badFormat.length ? t.common.tickerBadFormat(badFormat.join(', ')) : '',
      missing.length ? t.common.tickerNotFound(missing.join(', ')) : '',
    ].filter(Boolean)
    if (notes.length) setProblem(notes.join(' · '))
  }

  return (
    <div>
      <div className="flex flex-wrap gap-1.5 rounded-lg border border-line bg-surface-2 p-1.5">
        {value.map((ticker) => (
          <span key={ticker} className="inline-flex items-center gap-1 rounded-md bg-surface px-2 py-0.5 text-xs font-medium text-ink">
            {ticker}
            <button
              type="button"
              aria-label={t.common.removeTicker(ticker)}
              className="text-muted hover:text-critical"
              onClick={() => onChange(value.filter((x) => x !== ticker))}
            >
              ×
            </button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value)
            setProblem(null)
          }}
          onKeyDown={(e) => {
            if (['Enter', ',', ' '].includes(e.key)) {
              e.preventDefault()
              void commit(draft)
            } else if (e.key === 'Backspace' && !draft && value.length) {
              onChange(value.slice(0, -1))
            }
          }}
          onBlur={() => void commit(draft)}
          onPaste={(e) => {
            e.preventDefault()
            void commit(e.clipboardData.getData('text'))
          }}
          placeholder={value.length ? '' : t.common.tickerExample}
          className="!w-auto min-w-24 flex-1 !border-0 !bg-transparent !p-1 !outline-none"
          aria-label={t.common.addTicker}
        />
      </div>
      {(checking > 0 || problem) && (
        <p role="status" className={`mt-1.5 text-xs ${checking > 0 ? 'text-muted' : 'text-critical'}`}>
          {checking > 0 ? t.common.checkingTicker : problem}
        </p>
      )}
    </div>
  )
}
