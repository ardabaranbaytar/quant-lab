import type { BotStatus } from '../../lib/api'
import { useI18n } from '../../i18n/context'
import { Card } from '../ui'
import { Badge } from './Badge'

const TH = 'py-2 pr-4 font-medium'

/** Open pair trades and the orders waiting for the next close. */
export function OpenBookCard({ status }: { status: BotStatus }) {
  const { t, f } = useI18n()
  return (
    <Card title={t.bot.book.title}>
      <div className="space-y-6">
        {status.open_pairs.length === 0 ? (
          <p className="text-sm text-muted">{t.bot.book.empty}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className={TH}>{t.common.pair}</th>
                  <th className={TH}>{t.bot.book.spread}</th>
                  <th className={`${TH} text-right`}>{t.bot.book.legA}</th>
                  <th className={`${TH} text-right`}>{t.bot.book.legB}</th>
                  <th className="py-2 font-medium">{t.bot.book.since}</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {status.open_pairs.map((p) => {
                  const [a, b] = p.pair.split('/')
                  return (
                    <tr key={p.pair} className="border-b border-line/50 last:border-0">
                      <td className="py-2 pr-4 font-medium text-ink">{p.pair}</td>
                      <td className="py-2 pr-4">
                        <Badge tone={p.pos === 1 ? 'good' : 'critical'}>{p.pos === 1 ? t.common.long : t.common.short}</Badge>
                      </td>
                      <td className="py-2 pr-4 text-right text-ink-2">
                        {p.shares_a >= 0 ? '+' : '−'}{f.shares(p.shares_a)} {a}
                      </td>
                      <td className="py-2 pr-4 text-right text-ink-2">
                        {p.shares_b >= 0 ? '+' : '−'}{f.shares(p.shares_b)} {b}
                      </td>
                      <td className="py-2 text-ink-2">{p.entry_date ? f.longDate(p.entry_date) : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <div>
          <h3 className="mb-2 text-xs font-medium text-ink-2">
            {t.bot.book.pending} <span className="text-muted">{t.bot.book.pendingNote}</span>
          </h3>
          {status.pending_orders.length === 0 ? (
            <p className="text-sm text-muted">{t.common.none}</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {status.pending_orders.map((o, i) => (
                <Badge key={`${o.ticker}-${i}`} tone={o.qty > 0 ? 'good' : 'critical'}>
                  {o.qty > 0 ? t.common.buy : t.common.sell} {f.shares(o.qty)} {o.ticker}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}
