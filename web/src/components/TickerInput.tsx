import { useState } from 'react'
import { useI18n } from '../i18n/context'

/** Chip-style ticker entry: type and press Enter, comma or space. */
export function TickerInput({ value, onChange, max = 100 }: {
  value: string[]
  onChange: (tickers: string[]) => void
  max?: number
}) {
  const { t } = useI18n()
  const [draft, setDraft] = useState('')

  const commit = (raw: string) => {
    const incoming = raw.toUpperCase().split(/[\s,;]+/).filter(Boolean)
    if (!incoming.length) return
    onChange([...new Set([...value, ...incoming])].slice(0, max))
    setDraft('')
  }

  return (
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
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (['Enter', ',', ' '].includes(e.key)) {
            e.preventDefault()
            commit(draft)
          } else if (e.key === 'Backspace' && !draft && value.length) {
            onChange(value.slice(0, -1))
          }
        }}
        onBlur={() => commit(draft)}
        onPaste={(e) => {
          e.preventDefault()
          commit(e.clipboardData.getData('text'))
        }}
        placeholder={value.length ? '' : t.common.tickerExample}
        className="!w-auto min-w-24 flex-1 !border-0 !bg-transparent !p-1 !outline-none"
        aria-label={t.common.addTicker}
      />
    </div>
  )
}
