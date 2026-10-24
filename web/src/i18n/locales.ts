export const LOCALES = [
  { code: 'en', tag: 'en-US', short: 'EN', name: 'English' },
  { code: 'tr', tag: 'tr-TR', short: 'TR', name: 'Türkçe' },
  { code: 'de', tag: 'de-DE', short: 'DE', name: 'Deutsch' },
] as const

export type Locale = (typeof LOCALES)[number]['code']

export const STORAGE_KEY = 'lang'

const isLocale = (v: unknown): v is Locale => LOCALES.some((l) => l.code === v)

/**
 * A `?lang=` link (the portfolio site passes its own language) first, then the saved choice,
 * then the browser's language list, then English.
 */
export function detectLocale(): Locale {
  const linked = new URLSearchParams(location.search).get('lang')
  if (isLocale(linked)) {
    try {
      localStorage.setItem(STORAGE_KEY, linked)
    } catch {
      /* storage unavailable */
    }
    return linked
  }
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (isLocale(saved)) return saved
  } catch {
    /* storage unavailable */
  }
  for (const lang of navigator.languages ?? [navigator.language]) {
    const code = lang.slice(0, 2).toLowerCase()
    if (isLocale(code)) return code
  }
  return 'en'
}
