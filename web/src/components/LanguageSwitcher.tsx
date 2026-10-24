import { useI18n } from '../i18n/context'
import { LOCALES } from '../i18n/locales'
import { FlagDE, FlagGB, FlagTR } from './Flags'

const FLAGS = { en: FlagGB, tr: FlagTR, de: FlagDE } as const

/** Flag + code per language. Each button is labelled with the language's own name for screen readers. */
export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n()
  return (
    <div className="inline-flex rounded-lg border border-line p-0.5 text-xs" role="group" aria-label={t.language}>
      {LOCALES.map((l) => {
        const Flag = FLAGS[l.code]
        const active = locale === l.code
        return (
          <button
            key={l.code}
            type="button"
            lang={l.code}
            aria-label={l.name}
            aria-pressed={active}
            title={l.name}
            onClick={() => setLocale(l.code)}
            className={`flex items-center gap-1.5 rounded-md px-2 py-1 font-medium transition ${
              active ? 'bg-surface-2 text-ink' : 'text-muted hover:text-ink'
            }`}
          >
            <span className={active ? '' : 'opacity-60'}>
              <Flag />
            </span>
            <span className="hidden sm:inline">{l.short}</span>
          </button>
        )
      })}
    </div>
  )
}
