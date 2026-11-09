/** localStorage that never throws (private windows, blocked storage). */
export function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeStored(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Not persisted; fine for a UI preference.
  }
}
