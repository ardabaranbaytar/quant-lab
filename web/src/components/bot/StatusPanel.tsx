import type { BotEquityPoint, BotEvent, BotStatus } from '../../lib/api'
import { useI18n } from '../../i18n/context'
import { isRiskEvent, timeAgo } from '../../lib/bot'
import { StatTile } from '../ui'

export function StatusPanel({ status, equity, events }: {
  status: BotStatus
  equity: BotEquityPoint[]
  events: BotEvent[]
}) {
  const { t, f } = useI18n()
  const s = t.bot.status
  const cfg = status.config
  const last = equity.at(-1)
  const ret = last ? last.equity / cfg.capital - 1 : null
  const forced = events.filter(isRiskEvent).length
  const toReselect = Math.max(0, cfg.reselect_every - status.days_in_period)

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <StatTile
        label={s.equity}
        value={f.money(last?.equity ?? cfg.capital)}
        delta={ret}
        deltaLabel={ret == null ? undefined : s.sinceStart(f.signedPct(ret, 2))}
      />
      <StatTile
        label={s.openPairs}
        value={`${status.open_pairs.length} / ${cfg.top_k}`}
        deltaLabel={s.pairsInBook(status.pairs.length)}
      />
      <StatTile
        label={s.grossExposure}
        value={f.pct(last?.gross_exposure ?? 0)}
        deltaLabel={s.cash(f.money(status.cash))}
      />
      <StatTile
        label={s.lastBar}
        value={status.last_date ? f.longDate(status.last_date) : '—'}
        deltaLabel={status.updated_at ? s.ran(timeAgo(status.updated_at, t.time)) : undefined}
      />
      <StatTile
        label={s.riskExits}
        value={String(forced)}
        deltaLabel={s.nextReselect(toReselect)}
      />
    </div>
  )
}
