// Typed client for the FastAPI backend.

const BASE = import.meta.env.VITE_API_URL ?? '/api'

export type ParamValue = number | string | boolean | null

export interface StrategyInfo {
  name: string
  description: string
  params: Record<string, ParamValue>
  min_tickers: number
}

export interface Point {
  date: string
  equity: number
  drawdown: number
}

export type Metrics = Record<string, number | null>

export interface BacktestSummary {
  id: number
  strategy: string
  params: Record<string, ParamValue>
  tickers: string[]
  start_date: string
  end_date: string
  cost_rate: number
  metrics: Metrics
  created_at: string | null
}

export interface BacktestDetail extends BacktestSummary {
  points: Point[]
  benchmark: Point[] | null
  benchmark_metrics: Metrics | null
}

export interface BacktestRequest {
  strategy: string
  tickers: string[]
  start: string
  end: string
  params: Record<string, ParamValue>
  cost_rate: number
  risk_free_rate: number
  benchmark: string | null
}

export interface PairRow {
  pair: string
  asset_a: string
  asset_b: string
  correlation: number
  coint_pvalue: number
  hedge_ratio: number
  half_life: number | null
}

export interface PairScanResult {
  pairs: PairRow[]
  skipped: string[]
}

// ---------------------------------------------------------- paper bots

export interface BotSummary {
  name: string
  last_date: string | null
  equity: number | null
  open_pairs: number | null
  updated_at: string | null
}

export interface BotEquityPoint {
  date: string
  equity: number
  cash: number
  gross_exposure: number
  open_pairs: number
}

export interface BotFill {
  order_date: string
  fill_date: string
  ticker: string
  qty: number
  price: number
  cost: number
}

export interface BotEvent {
  date: string
  pair: string
  event: string
  z: number | null
  detail: string | null
}

export interface BotOpenPair {
  pair: string
  /** +1 = long spread (long A, short B), -1 = short spread */
  pos: 1 | -1
  shares_a: number
  shares_b: number
  entry_date: string | null
}

export interface BotPendingOrder {
  ticker: string
  qty: number
  order_date: string
}

export interface BotStatus {
  name: string
  last_date: string | null
  updated_at: string | null
  cash: number
  positions: Record<string, number>
  pending_orders: BotPendingOrder[]
  days_in_period: number
  pairs: string[]
  open_pairs: BotOpenPair[]
  config: BotConfig
}

/** Mirrors quantlab.bot.BotConfig (ticker maps replaced by universe_size). */
export interface BotConfig {
  universe_size: number
  capital: number
  cost_rate: number
  formation_days: number
  reselect_every: number
  top_k: number
  max_pvalue: number
  half_life_range: [number, number]
  max_pairs_per_stock: number
  entry_z: number
  exit_z: number
  stop_z: number | null
  break_monitor: boolean
  monitor_thresholds: Record<string, number> | null
  break_votes: number
  min_order_value: number
}

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError('Cannot reach the API. Is the backend running?')
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(message)
  }
  return res.json() as Promise<T>
}

export const api = {
  strategies: () => request<StrategyInfo[]>('/strategies'),
  runBacktest: (body: BacktestRequest) =>
    request<BacktestDetail>('/backtests', { method: 'POST', body: JSON.stringify(body) }),
  backtests: () => request<BacktestSummary[]>('/backtests'),
  backtest: (id: number) => request<BacktestDetail>(`/backtests/${id}`),
  scanPairs: (tickers: string[], start: string, end: string) =>
    request<PairScanResult>('/research/pairs', {
      method: 'POST',
      body: JSON.stringify({ tickers, start, end }),
    }),
  bots: () => request<BotSummary[]>('/bots'),
  bot: (name: string) => request<BotStatus>(botPath(name)),
  botEquity: (name: string) => request<BotEquityPoint[]>(botPath(name, '/equity')),
  botFills: (name: string, limit = 500) => request<BotFill[]>(botPath(name, `/fills?limit=${limit}`)),
  botEvents: (name: string, limit = 500) => request<BotEvent[]>(botPath(name, `/events?limit=${limit}`)),
}

function botPath(name: string, suffix = '') {
  return `/bots/${encodeURIComponent(name)}${suffix}`
}
