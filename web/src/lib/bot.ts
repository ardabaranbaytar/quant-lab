// Presentation helpers for the paper-trading bot page (pure, no React).

import type { Messages } from '../i18n/en'
import type { BotEquityPoint, BotEvent } from './api'

export type Tone = 'critical' | 'warning' | 'good' | 'neutral' | 'info'

export type EventGroup = 'risk' | 'trade' | 'selection'

/** How each bot event is grouped and coloured. Keys match `event` values written by quantlab.bot;
 *  the label and hint text live in the message files (`bot.events.kinds`). */
export const EVENT_META: Record<string, { tone: Tone; group: EventGroup }> = {
  risk_exit: { tone: 'critical', group: 'risk' },
  delisted: { tone: 'critical', group: 'risk' },
  stop: { tone: 'warning', group: 'risk' },
  entry: { tone: 'info', group: 'trade' },
  exit: { tone: 'good', group: 'trade' },
  vetoed: { tone: 'neutral', group: 'trade' },
  period_close: { tone: 'neutral', group: 'selection' },
  reselect: { tone: 'neutral', group: 'selection' },
}

export const eventMeta = (event: string) =>
  EVENT_META[event] ?? { tone: 'neutral' as Tone, group: 'trade' as EventGroup }

export const isRiskEvent = (e: BotEvent) => eventMeta(e.event).group === 'risk'

/** "3 min ago", "5 h ago", "2 d ago" — for the last run time. */
export function timeAgo(iso: string, time: Messages['time'], now: Date = new Date()) {
  // FastAPI sends naive UTC timestamps from the DB; treat them as UTC.
  const t = new Date(/[Z+]/.test(iso.slice(10)) ? iso : `${iso}Z`)
  const mins = Math.round((now.getTime() - t.getTime()) / 60_000)
  if (mins < 1) return time.justNow
  if (mins < 60) return time.minAgo(mins)
  const hours = Math.round(mins / 60)
  if (hours < 48) return time.hoursAgo(hours)
  return time.daysAgo(Math.round(hours / 24))
}

export interface EquityRow extends BotEquityPoint {
  drawdown: number
  ret: number // cumulative return vs starting capital
}

export function equityRows(points: BotEquityPoint[], capital: number): EquityRow[] {
  let peak = -Infinity
  return points.map((p) => {
    peak = Math.max(peak, p.equity)
    return { ...p, drawdown: p.equity / peak - 1, ret: p.equity / capital - 1 }
  })
}
