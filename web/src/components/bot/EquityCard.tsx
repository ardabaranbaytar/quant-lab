import { useMemo, useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useI18n } from '../../i18n/context'
import type { BotEquityPoint } from '../../lib/api'
import { equityRows, type EquityRow } from '../../lib/bot'
import { Card, Segmented } from '../ui'

const AXIS = { stroke: 'var(--axis)', fontSize: 11, tickLine: false, tick: { fill: 'var(--muted)' } }

function RowTooltip({ active, row }: { active?: boolean; row?: EquityRow }) {
  const { t, f } = useI18n()
  if (!active || !row) return null
  const items: [string, string][] = [
    [t.bot.equity.equity, f.money(row.equity)],
    [t.bot.equity.return, f.signedPct(row.ret, 2)],
    [t.bot.equity.drawdown, f.pct(row.drawdown, 2)],
    [t.bot.equity.grossExposure, f.pct(row.gross_exposure)],
    [t.bot.equity.openPairs, String(row.open_pairs)],
  ]
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <div className="mb-1.5 font-medium text-ink">{f.longDate(row.date)}</div>
      {items.map(([k, v]) => (
        <div key={k} className="flex justify-between gap-6">
          <span className="text-ink-2">{k}</span>
          <span className="tabular font-medium text-ink">{v}</span>
        </div>
      ))}
    </div>
  )
}

export function EquityCard({ points, capital }: { points: BotEquityPoint[]; capital: number }) {
  const { t, f } = useI18n()
  const [view, setView] = useState<'equity' | 'exposure'>('equity')
  const rows = useMemo(() => equityRows(points, capital), [points, capital])
  const maxDd = rows.reduce((m, r) => Math.min(m, r.drawdown), 0)

  const tooltip = (
    <Tooltip
      cursor={{ stroke: 'var(--muted)', strokeWidth: 1 }}
      isAnimationActive={false}
      content={(p) => <RowTooltip active={p.active} row={p.payload?.[0]?.payload as EquityRow | undefined} />}
    />
  )
  const xAxis = <XAxis dataKey="date" tickFormatter={f.dayLabel} minTickGap={32} {...AXIS} />

  return (
    <Card
      title={t.bot.equity.title}
      action={
        <Segmented
          value={view}
          onChange={setView}
          options={[
            { value: 'equity', label: t.bot.equity.equity },
            { value: 'exposure', label: t.bot.equity.exposure },
          ]}
        />
      }
    >
      {rows.length < 2 ? (
        <p className="py-10 text-center text-sm text-muted">
          {t.bot.equity.needTwoCloses}
        </p>
      ) : (
        <>
          <div className="mb-1 flex flex-wrap justify-between gap-2 text-xs text-muted">
            <span>
              {view === 'equity' ? t.bot.equity.equityCaption : t.bot.equity.exposureCaption}
            </span>
            <span>{t.bot.equity.maxDrawdown(f.pct(maxDd, 2))}</span>
          </div>
          <div className="h-72">
            <ResponsiveContainer>
              {view === 'equity' ? (
                <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 8 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  {xAxis}
                  <YAxis
                    {...AXIS}
                    width={64}
                    domain={['auto', 'auto']}
                    tickFormatter={(v: number) => f.money(v)}
                  />
                  <ReferenceLine y={capital} stroke="var(--axis)" strokeDasharray="4 4" />
                  {tooltip}
                  <Line
                    dataKey="equity"
                    stroke="var(--series-1)"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              ) : (
                <ComposedChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 8 }}>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  {xAxis}
                  <YAxis
                    yAxisId="gross"
                    {...AXIS}
                    width={44}
                    domain={[0, (max: number) => Math.max(1, Math.ceil(max * 10) / 10)]}
                    tickFormatter={(v: number) => f.pct(v, 0)}
                  />
                  <YAxis yAxisId="pairs" orientation="right" {...AXIS} width={28} allowDecimals={false} />
                  {tooltip}
                  <Area
                    yAxisId="gross"
                    dataKey="gross_exposure"
                    stroke="var(--series-1)"
                    fill="var(--series-1)"
                    fillOpacity={0.12}
                    strokeWidth={1.5}
                    isAnimationActive={false}
                  />
                  <Line
                    yAxisId="pairs"
                    dataKey="open_pairs"
                    type="stepAfter"
                    stroke="var(--series-2)"
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              )}
            </ResponsiveContainer>
          </div>
        </>
      )}
    </Card>
  )
}
