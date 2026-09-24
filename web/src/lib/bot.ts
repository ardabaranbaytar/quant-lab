// Presentation helpers for the paper-trading bot page (pure, no React).

import type { BotEquityPoint, BotEvent } from './api'

export type Tone = 'critical' | 'warning' | 'good' | 'neutral' | 'info'

export type EventGroup = 'risk' | 'trade' | 'selection'

/** What each bot event means. Keys match `event` values written by quantlab.bot. */
export const EVENT_META: Record<string, { label: string; tone: Tone; group: EventGroup; hint: string }> = {
  risk_exit: {
    label: 'Forced exit',
    tone: 'critical',
    group: 'risk',
    hint: 'BreakMonitor flagged the pair BROKEN: position closed, pair blocked until the detectors go quiet.',
  },
  delisted: {
    label: 'Delisted leg',
    tone: 'critical',
    group: 'risk',
    hint: 'A leg stopped trading; the pair was closed at its last close.',
  },
  stop: {
    label: 'Stop-loss',
    tone: 'warning',
    group: 'risk',
    hint: '|z| exceeded the stop level; no re-entry until z is back inside the entry band.',
  },
  entry: { label: 'Entry', tone: 'info', group: 'trade', hint: '|z| crossed the entry threshold.' },
  exit: { label: 'Exit', tone: 'good', group: 'trade', hint: 'The spread reverted to the exit level.' },
  vetoed: { label: 'Vetoed', tone: 'neutral', group: 'trade', hint: 'An entry filter rejected the signal.' },
  period_close: {
    label: 'Period close',
    tone: 'neutral',
    group: 'selection',
    hint: 'Closed because the quarterly pair re-selection started a new period.',
  },
  reselect: {
    label: 'Re-selection',
    tone: 'neutral',
    group: 'selection',
    hint: 'New formation window: pairs re-tested for cointegration and re-ranked.',
  },
}

export const eventMeta = (event: string) =>
  EVENT_META[event] ?? { label: event, tone: 'neutral' as Tone, group: 'trade' as EventGroup, hint: '' }

export const isRiskEvent = (e: BotEvent) => eventMeta(e.event).group === 'risk'

export const money = (v: number | null | undefined, digits = 0) =>
  v == null
    ? '—'
    : v.toLocaleString('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })

export const shares = (v: number) =>
  Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: Math.abs(v) < 10 ? 3 : 1 })

/** "3 min ago", "5 h ago", "2 d ago" — for the last run time. */
export function timeAgo(iso: string, now: Date = new Date()) {
  // FastAPI sends naive UTC timestamps from the DB; treat them as UTC.
  const t = new Date(/[Z+]/.test(iso.slice(10)) ? iso : `${iso}Z`)
  const mins = Math.round((now.getTime() - t.getTime()) / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hours = Math.round(mins / 60)
  if (hours < 48) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
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
