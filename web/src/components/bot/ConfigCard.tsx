import type { BotConfig } from '../../lib/api'
import { useI18n } from '../../i18n/context'
import { Card } from '../ui'
import { Badge } from './Badge'

const VOTING_DETECTORS = 7

/** The rules the bot trades by, in words rather than parameter names. */
export function ConfigCard({ config: c }: { config: BotConfig }) {
  const { t, f } = useI18n()
  const k = t.bot.config
  const rows: [string, string][] = [
    [k.universe, k.universeValue(c.universe_size)],
    [k.pairing, k.pairingValue],
    [k.selection, k.selectionValue(f.plain(c.max_pvalue), c.half_life_range[0], c.half_life_range[1])],
    [k.book, k.bookValue(c.top_k, c.max_pairs_per_stock)],
    [k.formation, k.formationValue(c.formation_days, c.reselect_every)],
    [k.entryExit, k.entryExitValue(f.plain(c.entry_z), f.plain(c.exit_z))],
    [k.stop, c.stop_z == null ? k.stopNone : k.stopValue(f.plain(c.stop_z))],
    [k.execution, k.executionValue(Math.round(c.cost_rate * 1e4))],
    [k.capital, f.money(c.capital)],
  ]
  return (
    <Card
      title={k.title}
      action={
        <Badge tone={c.break_monitor ? 'good' : 'warning'}>
          {c.break_monitor ? k.breakMonitorOn(c.break_votes, VOTING_DETECTORS) : k.breakMonitorOff}
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
