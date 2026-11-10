import { useSyncExternalStore } from 'react'
import { readStored, writeStored } from './storage'

/**
 * A single global value kept in localStorage, readable from any component.
 * For per-viewer PoC state that a backend will own later.
 */
export function createPersistedStore<T>(key: string, initial: T) {
  let value: T = initial
  const stored = readStored(key)
  if (stored !== null) {
    try {
      value = JSON.parse(stored) as T
    } catch {
      // Corrupt or old format: start fresh.
    }
  }
  const listeners = new Set<() => void>()

  const get = () => value
  const set = (next: T | ((prev: T) => T)) => {
    value = typeof next === 'function' ? (next as (prev: T) => T)(value) : next
    writeStored(key, JSON.stringify(value))
    listeners.forEach((l) => l())
  }
  const subscribe = (l: () => void) => {
    listeners.add(l)
    return () => listeners.delete(l)
  }
  const use = () => useSyncExternalStore(subscribe, get)

  return { get, set, use }
}
