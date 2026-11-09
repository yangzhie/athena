import { useSyncExternalStore } from 'react'

/**
 * Tiny global store holding one value per key (e.g. per offering id),
 * readable from any component with `use(key)`.
 */
export function createKeyedStore<T>(initial: T) {
  const values = new Map<string, T>()
  const listeners = new Set<() => void>()

  const get = (key: string) => (values.has(key) ? (values.get(key) as T) : initial)
  const set = (key: string, value: T) => {
    values.set(key, value)
    listeners.forEach((l) => l())
  }
  const subscribe = (l: () => void) => {
    listeners.add(l)
    return () => listeners.delete(l)
  }
  const use = (key: string) => useSyncExternalStore(subscribe, () => get(key))

  return { get, set, use }
}
