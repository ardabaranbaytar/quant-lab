import { useEffect, useId, useRef, useState } from 'react'
import { useI18n } from '../i18n/context'
import { api, type SecurityHit } from '../lib/api'

// The shape the API accepts (api/schemas.py): letters, digits and . - = ^, up to 16 characters.
const SYMBOL = /^[A-Z0-9^][A-Z0-9.\-=]{0,15}$/

const fold = (s: string) => s.normalize('NFD').replace(/\p{M}/gu, '').replace(/ı/g, 'i').toLowerCase()

/** The top suggestion is only taken for Enter when it plainly is what was typed. */
function confident(hit: SecurityHit, query: string) {
  const q = fold(query.trim()).replace(/^\^/, '')
  return fold(hit.symbol).replace(/^\^/, '').startsWith(q) || fold(hit.name).startsWith(q)
}

/**
 * Ticker entry with search: type a company name or a symbol, pick from the list (arrow keys + Enter, or click).
 * Anything typed that is not picked is checked with the server before it is added, so a typo is refused
 * here instead of failing a run later.
 */
export function TickerInput({ value, onChange, max = 100 }: {
  value: string[]
  onChange: (tickers: string[]) => void
  max?: number
}) {
  const { t } = useI18n()
  const listId = useId()
  const [draft, setDraft] = useState('')
  const [checking, setChecking] = useState(0) // existence lookups in flight
  const [problem, setProblem] = useState<string | null>(null)
  const [hits, setHits] = useState<SecurityHit[]>([])
  const [hitsFor, setHitsFor] = useState('') // the query `hits` answers
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  // The current list, for lookups that finish after the visitor has already changed it.
  const latest = useRef(value)
  useEffect(() => {
    latest.current = value
  }, [value])

  const clearHits = () => {
    setHits([])
    setHitsFor('')
    setActive(-1)
  }

  // Suggestions follow the text, a moment after typing pauses.
  useEffect(() => {
    const query = draft.trim()
    if (!query) return
    let stale = false
    const timer = setTimeout(() => {
      api.searchTickers(query).then(
        (found) => {
          if (stale) return
          setHits(found)
          setHitsFor(query)
          setActive(found.length > 0 && confident(found[0], query) ? 0 : -1)
        },
        () => {
          if (stale) return
          setHits([])
          setHitsFor(query)
          setActive(-1)
        },
      )
    }, 180)
    return () => {
      stale = true
      clearTimeout(timer)
    }
  }, [draft])

  const pick = (hit: SecurityHit) => {
    setDraft('')
    clearHits()
    setProblem(null)
    setOpen(false)
    if (!latest.current.includes(hit.symbol)) onChange([...latest.current, hit.symbol].slice(0, max))
  }

  /** Add what was typed as symbols (several may be separated by spaces or commas), after checking them. */
  const commit = async (raw: string) => {
    const typed = [...new Set(raw.toUpperCase().split(/[\s,;]+/).filter(Boolean))]
    if (!typed.length) return
    setDraft('')
    clearHits()
    setProblem(null)
    setOpen(false)

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

  const enter = async () => {
    const query = draft.trim()
    if (!query) return
    if (hitsFor === query) {
      if (active >= 0) pick(hits[active])
      else void commit(draft)
      return
    }
    // Enter came before the search answered: ask now rather than treat half a name as a symbol.
    let found: SecurityHit[] = []
    try {
      found = await api.searchTickers(query)
    } catch {
      /* fall through: the text is checked as typed */
    }
    if (found.length > 0 && confident(found[0], query)) pick(found[0])
    else void commit(query)
  }

  const showList = open && hits.length > 0
  const label = (hit: SecurityHit) =>
    [
      hit.kind === 'etf' ? t.common.kindEtf : hit.kind === 'index' ? t.common.kindIndex : '',
      t.common.groups[hit.group] ?? hit.group,
    ]
      .filter(Boolean)
      .join(' · ')

  return (
    <div>
      <div className="relative">
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
              if (!e.target.value.trim()) clearHits()
              setProblem(null)
              setOpen(true)
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => {
              setOpen(false)
              // Clicking away right after typing a full symbol still adds it; half-typed text stays put.
              const top = hitsFor === draft.trim() && active >= 0 ? hits[active] : undefined
              if (top && top.symbol.toLowerCase() === draft.trim().toLowerCase()) pick(top)
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                if (!hits.length) return
                e.preventDefault()
                setOpen(true)
                const down = e.key === 'ArrowDown'
                setActive((a) => (a < 0 ? (down ? 0 : hits.length - 1) : (a + (down ? 1 : -1) + hits.length) % hits.length))
              } else if (e.key === 'Escape') {
                setOpen(false)
              } else if (e.key === 'Enter') {
                e.preventDefault()
                void enter()
              } else if (e.key === ',') {
                e.preventDefault()
                void commit(draft)
              } else if (e.key === 'Backspace' && !draft && value.length) {
                onChange(value.slice(0, -1))
              }
            }}
            onPaste={(e) => {
              // A pasted list (commas, lines) is added at once; a single name is left in the box to search.
              const text = e.clipboardData.getData('text')
              if (/[,;\n\t]/.test(text.trim())) {
                e.preventDefault()
                void commit(text)
              }
            }}
            placeholder={value.length ? '' : t.common.tickerExample}
            className="!w-auto min-w-24 flex-1 !border-0 !bg-transparent !p-1 !outline-none"
            role="combobox"
            aria-label={t.common.addTicker}
            aria-autocomplete="list"
            aria-expanded={showList}
            aria-controls={listId}
            aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
            autoComplete="off"
            spellCheck={false}
          />
        </div>

        {showList && (
          <ul
            id={listId}
            role="listbox"
            className="absolute inset-x-0 z-20 mt-1 max-h-80 max-w-2xl overflow-auto rounded-lg border border-line bg-surface p-1 shadow-lg"
          >
            {hits.map((hit, i) => {
              const added = value.includes(hit.symbol)
              return (
                <li
                  key={hit.symbol}
                  id={`${listId}-${i}`}
                  role="option"
                  aria-selected={i === active}
                  aria-disabled={added}
                  // mousedown, not click: the input would lose focus (and close the list) before a click lands.
                  onMouseDown={(e) => {
                    e.preventDefault()
                    if (!added) pick(hit)
                  }}
                  onMouseEnter={() => setActive(i)}
                  className={`flex items-baseline gap-3 rounded-md px-2.5 py-1.5 text-sm ${
                    i === active ? 'bg-surface-2' : ''
                  } ${added ? 'opacity-50' : 'cursor-pointer'}`}
                >
                  <span className="w-24 shrink-0 font-semibold text-ink">{hit.symbol}</span>
                  <span className="min-w-0 flex-1 truncate text-ink-2">{hit.name}</span>
                  <span className="hidden shrink-0 text-xs text-muted sm:block">
                    {added && '✓ '}
                    {label(hit)}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {(checking > 0 || problem) && (
        <p role="status" className={`mt-1.5 text-xs ${checking > 0 ? 'text-muted' : 'text-critical'}`}>
          {checking > 0 ? t.common.checkingTicker : problem}
        </p>
      )}
    </div>
  )
}
