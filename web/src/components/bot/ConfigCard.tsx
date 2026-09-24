import type { BotConfig } from '../../lib/api'
import { money } from '../../lib/bot'
import { Card } from '../ui'
import { Badge } from './Badge'

const VOTING_DETECTORS = 7

/** The rules the bot trades by, in words rather than parameter names. */
export function ConfigCard({ config: c }: { config: BotConfig }) {
  const rows: [string, string][] = [
    ['Universe', `${c.universe_size} tickers · point-in-time S&P 500`],
    ['Pairing', 'Same GICS sub-industry, Engle-Granger on log prices'],
    ['Selection', `p < ${c.max_pvalue}, half-life ${c.half_life_range[0]}–${c.half_life_range[1]} days`],
    ['Book', `top ${c.top_k} pairs, ≤ ${c.max_pairs_per_stock} per stock, 1/${c.top_k} of equity each`],
    ['Formation', `${c.formation_days} trading days, re-selected every ${c.reselect_every}`],
    ['Entry / exit', `|z| > ${c.entry_z} · exit at z = ${c.exit_z}`],
    ['Stop', c.stop_z == null ? 'none (break monitor handles tail risk)' : `|z| > ${c.stop_z}`],
    ['Execution', `next close · ${(c.cost_rate * 1e4).toFixed(0)} bps per side`],
    ['Starting capital', money(c.capital)],
  ]
  return (
    <Card
      title="Configuration"
      action={
        <Badge tone={c.break_monitor ? 'good' : 'warning'}>
          Break monitor {c.break_monitor ? `on · ${c.break_votes}/${VOTING_DETECTORS} votes` : 'off'}
        </Badge>
      }
    >
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[auto_1fr]">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k}</dt>
            <dd className="text-ink">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}
