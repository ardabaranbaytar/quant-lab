import type { ReactNode } from 'react'
import type { Tone } from '../../lib/bot'

const DOT: Record<Tone, string> = {
  critical: 'bg-critical',
  warning: 'bg-warning',
  good: 'bg-good',
  info: 'bg-accent',
  neutral: 'bg-muted',
}

/** Status pill: the colour is carried by the dot, the text stays high-contrast. */
export function Badge({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-line px-2 py-0.5 text-xs text-ink-2"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[tone]}`} />
      {children}
    </span>
  )
}
