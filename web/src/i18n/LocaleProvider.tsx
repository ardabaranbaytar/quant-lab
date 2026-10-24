import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { createFormat, humanize } from '../lib/format'
import { I18nContext, type I18n } from './context'
import { de } from './de'
import { en, type Messages } from './en'
import { LOCALES, STORAGE_KEY, detectLocale, type Locale } from './locales'
import { tr } from './tr'

const MESSAGES: Record<Locale, Messages> = { en, tr, de }

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(detectLocale)

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* storage unavailable */
    }
  }, [])

  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])

  const value = useMemo<I18n>(() => {
    const t = MESSAGES[locale]
    const tag = LOCALES.find((l) => l.code === locale)!.tag
    return {
      locale,
      setLocale,
      t,
      f: createFormat(tag),
      names: {
        strategy: (name) => t.strategies[name]?.name ?? humanize(name),
        strategyDescription: (name, fallback) => t.strategies[name]?.description ?? fallback,
        param: (name) => t.params[name]?.label ?? humanize(name),
        paramHint: (name) => t.params[name]?.hint,
      },
    }
  }, [locale, setLocale])

  return <I18nContext value={value}>{children}</I18nContext>
}
