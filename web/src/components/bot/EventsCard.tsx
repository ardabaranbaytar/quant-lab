import { useMemo, useState } from 'react'
import type { BotEvent } from '../../lib/api'
import { eventMeta, type EventGroup } from '../../lib/bot'
import { longDate, num } from '../../lib/format'
import { Button, Card, Segmented } from '../ui'
import { Badge } from './Badge'

type Filter = 'all' | EventGroup
const PAGE = 25

/** Pair-level decisions, with BreakMonitor forced exits highlighted. */
export function EventsCard({ events }: { events: BotEvent[] }) {
  const [filter, setFilter] = useState<Filter>('all')
  const [shown, setShown] = useState(PAGE)

  const counts = useMemo(() => {
    const c: Record<Filter, number> = { all: events.length, risk: 0, trade: 0, selection: 0 }
    for (const e of events) c[eventMeta(e.event).group]++
    return c
  }, [events])
  const visible = filter === 'all' ? events : events.filter((e) => eventMeta(e.event).group === filter)

  const label = (f: Filter, text: string) => `${text} (${counts[f]})`
  return (
    <Card
      title="Events"
      action={
        <Segmented
          value={filter}
          onChange={(f) => {
            setFilter(f)
            setShown(PAGE)
          }}
          options={[
            { value: 'all', label: label('all', 'All') },
            { value: 'risk', label: label('risk', 'Risk') },
            { value: 'trade', label: label('trade', 'Trades') },
            { value: 'selection', label: label('selection', 'Selection') },
          ]}
        />
      }
    >
      {filter === 'risk' && (
        <p className="mb-3 text-xs text-muted">
          Forced exits come from the BreakMonitor: seven causal detectors, a pair is closed when enough of them agree
          on 8 of the last 10 days. A z-stop or a delisted leg also counts as a risk exit.
        </p>
      )}
      {visible.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">
          {filter === 'risk' ? 'No risk exits so far — no pair has broken.' : 'No events.'}
        </p>
      ) : (
        <>
          <ul className="divide-y divide-line/50">
            {visible.slice(0, shown).map((e, i) => {
              const meta = eventMeta(e.event)
              const risky = meta.group === 'risk'
              return (
                <li
                  key={`${e.date}-${e.pair}-${e.event}-${i}`}
                  className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md px-2 py-2 text-sm ${risky ? 'bg-critical/10' : ''}`}
                >
                  <span className="tabular w-28 shrink-0 text-ink-2">{longDate(e.date)}</span>
                  <span className="w-32 shrink-0">
                    <Badge tone={meta.tone} title={meta.hint}>{meta.label}</Badge>
                  </span>
                  <span className="font-medium text-ink">{e.pair === '*' ? 'All pairs' : e.pair}</span>
                  {e.z != null && <span className="tabular text-xs text-muted">z = {num(e.z)}</span>}
                  {e.detail && (
                    <span className="min-w-0 flex-1 truncate text-xs text-muted" title={e.detail}>
                      {e.detail}
                    </span>
                  )}
                </li>
              )
            })}
          </ul>
          {shown < visible.length && (
            <div className="mt-3 text-center">
              <Button variant="ghost" onClick={() => setShown(shown + PAGE * 4)}>
                Show more ({visible.length - shown} left)
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
