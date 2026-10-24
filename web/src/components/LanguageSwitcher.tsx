import { useI18n } from '../i18n/context'
import { LOCALES } from '../i18n/locales'

/** EN / TR / DE. Each button is labelled with the language's own name for screen readers. */
export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n()
  return (
    <div className="inline-flex rounded-lg border border-line p-0.5 text-xs" role="group" aria-label={t.language}>
      {LOCALES.map((l) => (
        <button
          key={l.code}
          type="button"
          lang={l.code}
          aria-label={l.name}
          aria-pressed={locale === l.code}
          onClick={() => setLocale(l.code)}
          className={`rounded-md px-2 py-1 font-medium transition ${
            locale === l.code ? 'bg-surface-2 text-ink' : 'text-muted hover:text-ink'
          }`}
        >
          {l.short}
        </button>
      ))}
    </div>
  )
}
