// The delete key for the History page. It lives only in this browser; the server decides what it may do.

const STORAGE_KEY = 'admin-key'

export function loadAdminKey(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function saveAdminKey(key: string | null) {
  try {
    if (key) localStorage.setItem(STORAGE_KEY, key)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* storage unavailable: the key then only lasts until the page is closed */
  }
}
