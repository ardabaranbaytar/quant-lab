import { useMemo, useState } from 'react'
import type { BotEvent } from '../../lib/api'
import { useI18n } from '../../i18n/context'
import { eventMeta, type EventGroup } from '../../lib/bot'
import { Button, Card, Segmented } from '../ui'
import { Badge } from './Badge'

type Filter = 'all' | EventGroup
const PAGE = 25

/** Pair-level decisions, with BreakMonitor forced exits highlighted. */
export function EventsCard({ events }: { events: BotEvent[] }) {
  const { t, f } = useI18n()
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
      title={t.bot.events.title}
      action={
        <Segmented
          value={filter}
          onChange={(f) => {
            setFilter(f)
            setShown(PAGE)
          }}
          options={[
            { value: 'all', label: label('all', t.bot.events.all) },
            { value: 'risk', label: label('risk', t.bot.events.risk) },
            { value: 'trade', label: label('trade', t.bot.events.trade) },
            { value: 'selection', label: label('selection', t.bot.events.selection) },
          ]}
        />
      }
    >
      {filter === 'risk' && (
        <p className="mb-3 text-xs text-muted">{t.bot.events.riskNote}</p>
      )}
      {visible.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">
          {filter === 'risk' ? t.bot.events.noRisk : t.bot.events.none}
        </p>
      ) : (
        <>
          <ul className="divide-y divide-line/50">
            {visible.slice(0, shown).map((e, i) => {
              const meta = eventMeta(e.event)
              const risky = meta.group === 'risk'
              const kind = t.bot.events.kinds[e.event]
              return (
                <li
                  key={`${e.date}-${e.pair}-${e.event}-${i}`}
                  className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md px-2 py-2 text-sm ${risky ? 'bg-critical/10' : ''}`}
                >
                  <span className="tabular w-28 shrink-0 text-ink-2">{f.longDate(e.date)}</span>
                  <span className="w-44 shrink-0">
                    <Badge tone={meta.tone} title={kind?.hint}>{kind?.label ?? e.event}</Badge>
                  </span>
                  <span className="font-medium text-ink">{e.pair === '*' ? t.bot.events.allPairs : e.pair}</span>
                  {e.z != null && <span className="tabular text-xs text-muted">z = {f.num(e.z)}</span>}
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
                {t.common.showMore(visible.length - shown)}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
