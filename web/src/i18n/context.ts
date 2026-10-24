import { createContext, useContext } from 'react'
import type { Formatters } from '../lib/format'
import type { Messages } from './en'
import type { Locale } from './locales'

export interface I18n {
  locale: Locale
  setLocale: (locale: Locale) => void
  /** All UI text for the current language. */
  t: Messages
  /** Number, percent, money and date formatting for the current language. */
  f: Formatters
  /** Names the API sends as identifiers (strategies, parameters), in the current language. */
  names: {
    strategy: (name: string) => string
    strategyDescription: (name: string, fallback: string) => string
    param: (name: string) => string
    paramHint: (name: string) => string | undefined
  }
}

export const I18nContext = createContext<I18n | null>(null)

export function useI18n(): I18n {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used inside <LocaleProvider>')
  return ctx
}
