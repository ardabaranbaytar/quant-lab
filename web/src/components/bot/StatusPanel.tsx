import type { BotEquityPoint, BotEvent, BotStatus } from '../../lib/api'
import { isRiskEvent, money, timeAgo } from '../../lib/bot'
import { longDate, pct, signedPct } from '../../lib/format'
import { StatTile } from '../ui'

export function StatusPanel({ status, equity, events }: {
  status: BotStatus
  equity: BotEquityPoint[]
  events: BotEvent[]
}) {
  const cfg = status.config
  const last = equity.at(-1)
  const ret = last ? last.equity / cfg.capital - 1 : null
  const forced = events.filter(isRiskEvent).length
  const toReselect = Math.max(0, cfg.reselect_every - status.days_in_period)

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      <StatTile
        label="Equity"
        value={money(last?.equity ?? cfg.capital)}
        delta={ret}
        deltaLabel={ret == null ? undefined : `${signedPct(ret, 2)} since start`}
      />
      <StatTile
        label="Open pairs"
        value={`${status.open_pairs.length} / ${cfg.top_k}`}
        deltaLabel={`${status.pairs.length} pairs in the current book`}
      />
      <StatTile
        label="Gross exposure"
        value={pct(last?.gross_exposure ?? 0)}
        deltaLabel={`cash ${money(status.cash)}`}
      />
      <StatTile
        label="Last bar"
        value={status.last_date ? longDate(status.last_date) : '—'}
        deltaLabel={status.updated_at ? `run ${timeAgo(status.updated_at)}` : undefined}
      />
      <StatTile
        label="Risk exits"
        value={String(forced)}
        deltaLabel={`next re-selection in ${toReselect} trading day${toReselect === 1 ? '' : 's'}`}
      />
    </div>
  )
}
