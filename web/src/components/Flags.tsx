import { useId } from 'react'

// Small inline flags: emoji flags show up as plain letters on Windows, so they are drawn as SVG.
const flagClass = 'h-3.5 w-[21px] shrink-0 rounded-[2px] ring-1 ring-ink/20'

// Five-pointed star as an SVG points string; the first tip points along rotation (degrees, 0 = right).
function starPoints(cx: number, cy: number, outer: number, rotation: number) {
  const inner = outer * 0.382
  return Array.from({ length: 10 }, (_, i) => {
    const angle = ((rotation + i * 36) * Math.PI) / 180
    const radius = i % 2 === 0 ? outer : inner
    return `${(cx + radius * Math.cos(angle)).toFixed(2)},${(cy - radius * Math.sin(angle)).toFixed(2)}`
  }).join(' ')
}

export function FlagGB() {
  const clipId = useId()
  return (
    <svg viewBox="0 0 60 30" aria-hidden className={flagClass}>
      <clipPath id={clipId}>
        <path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z" />
      </clipPath>
      <path d="M0,0 v30 h60 v-30 z" fill="#012169" />
      <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
      <path d="M0,0 L60,30 M60,0 L0,30" clipPath={`url(#${clipId})`} stroke="#C8102E" strokeWidth="4" />
      <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10" />
      <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
    </svg>
  )
}

export function FlagTR() {
  return (
    <svg viewBox="0 0 30 20" aria-hidden className={flagClass}>
      <rect width="30" height="20" fill="#E30A17" />
      <circle cx="10.5" cy="10" r="5" fill="#fff" />
      <circle cx="11.9" cy="10" r="4" fill="#E30A17" />
      <polygon points={starPoints(15.6, 10, 2.6, 180)} fill="#fff" />
    </svg>
  )
}

export function FlagDE() {
  return (
    <svg viewBox="0 0 5 3" aria-hidden className={flagClass}>
      <rect width="5" height="1" fill="#000" />
      <rect width="5" height="1" y="1" fill="#DD0000" />
      <rect width="5" height="1" y="2" fill="#FFCE00" />
    </svg>
  )
}
