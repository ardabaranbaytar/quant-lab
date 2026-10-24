import { useState } from 'react'
import type { BotFill } from '../../lib/api'
import { useI18n } from '../../i18n/context'
import { Button, Card } from '../ui'

const PAGE = 20
const TH = 'py-2 pr-4 font-medium'

/** Executed paper trades, newest first (from the paper_fills table). */
export function FillsCard({ fills }: { fills: BotFill[] }) {
  const { t, f: fmt } = useI18n()
  const [shown, setShown] = useState(PAGE)
  const totalCost = fills.reduce((s, f) => s + f.cost, 0)
  const notional = fills.reduce((s, f) => s + Math.abs(f.qty * f.price), 0)

  return (
    <Card
      title={t.bot.fills.title(fills.length)}
      action={
        fills.length > 0 && (
          <span className="text-xs text-muted">
            {t.bot.fills.summary(fmt.money(notional), fmt.money(totalCost, 2))}
          </span>
        )
      }
    >
      {fills.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">{t.bot.fills.none}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className={TH}>{t.bot.fills.filled}</th>
                  <th className={TH}>{t.bot.fills.decided}</th>
                  <th className={TH}>{t.bot.fills.ticker}</th>
                  <th className={TH}>{t.bot.fills.side}</th>
                  <th className={`${TH} text-right`}>{t.bot.fills.shares}</th>
                  <th className={`${TH} text-right`}>{t.bot.fills.price}</th>
                  <th className={`${TH} text-right`}>{t.bot.fills.notional}</th>
                  <th className="py-2 text-right font-medium">{t.bot.fills.cost}</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {fills.slice(0, shown).map((f, i) => (
                  <tr key={`${f.fill_date}-${f.ticker}-${i}`} className="border-b border-line/50 last:border-0">
                    <td className="whitespace-nowrap py-1.5 pr-4 text-ink">{fmt.longDate(f.fill_date)}</td>
                    <td className="whitespace-nowrap py-1.5 pr-4 text-muted">{fmt.longDate(f.order_date)}</td>
                    <td className="py-1.5 pr-4 font-medium text-ink">{f.ticker}</td>
                    <td className={`py-1.5 pr-4 ${f.qty > 0 ? 'text-good' : 'text-critical'}`}>
                      {f.qty > 0 ? t.common.buy : t.common.sell}
                    </td>
                    <td className="py-1.5 pr-4 text-right text-ink-2">{fmt.shares(f.qty)}</td>
                    <td className="py-1.5 pr-4 text-right text-ink-2">{fmt.money(f.price, 2)}</td>
                    <td className="py-1.5 pr-4 text-right text-ink">{fmt.money(Math.abs(f.qty * f.price))}</td>
                    <td className="py-1.5 text-right text-muted">{fmt.money(f.cost, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {shown < fills.length && (
            <div className="mt-3 text-center">
              <Button variant="ghost" onClick={() => setShown(shown + PAGE * 5)}>
                {t.common.showMore(fills.length - shown)}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
