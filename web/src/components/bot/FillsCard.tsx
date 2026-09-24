import { useState } from 'react'
import type { BotFill } from '../../lib/api'
import { money, shares } from '../../lib/bot'
import { longDate } from '../../lib/format'
import { Button, Card } from '../ui'

const PAGE = 20
const TH = 'py-2 pr-4 font-medium'

/** Executed paper trades, newest first (from the paper_fills table). */
export function FillsCard({ fills }: { fills: BotFill[] }) {
  const [shown, setShown] = useState(PAGE)
  const totalCost = fills.reduce((s, f) => s + f.cost, 0)
  const notional = fills.reduce((s, f) => s + Math.abs(f.qty * f.price), 0)

  return (
    <Card
      title={`Fills (${fills.length})`}
      action={
        fills.length > 0 && (
          <span className="text-xs text-muted">
            traded {money(notional)} · costs {money(totalCost, 2)}
          </span>
        )
      }
    >
      {fills.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">No fills yet.</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className={TH}>Filled</th>
                  <th className={TH}>Decided</th>
                  <th className={TH}>Ticker</th>
                  <th className={TH}>Side</th>
                  <th className={`${TH} text-right`}>Shares</th>
                  <th className={`${TH} text-right`}>Price</th>
                  <th className={`${TH} text-right`}>Notional</th>
                  <th className="py-2 text-right font-medium">Cost</th>
                </tr>
              </thead>
              <tbody className="tabular">
                {fills.slice(0, shown).map((f, i) => (
                  <tr key={`${f.fill_date}-${f.ticker}-${i}`} className="border-b border-line/50 last:border-0">
                    <td className="whitespace-nowrap py-1.5 pr-4 text-ink">{longDate(f.fill_date)}</td>
                    <td className="whitespace-nowrap py-1.5 pr-4 text-muted">{longDate(f.order_date)}</td>
                    <td className="py-1.5 pr-4 font-medium text-ink">{f.ticker}</td>
                    <td className={`py-1.5 pr-4 ${f.qty > 0 ? 'text-good' : 'text-critical'}`}>
                      {f.qty > 0 ? 'Buy' : 'Sell'}
                    </td>
                    <td className="py-1.5 pr-4 text-right text-ink-2">{shares(f.qty)}</td>
                    <td className="py-1.5 pr-4 text-right text-ink-2">{money(f.price, 2)}</td>
                    <td className="py-1.5 pr-4 text-right text-ink">{money(Math.abs(f.qty * f.price))}</td>
                    <td className="py-1.5 text-right text-muted">{money(f.cost, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {shown < fills.length && (
            <div className="mt-3 text-center">
              <Button variant="ghost" onClick={() => setShown(shown + PAGE * 5)}>
                Show more ({fills.length - shown} left)
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
