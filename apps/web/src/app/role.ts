import { useServerIdentity } from './identity'
import { createPersistedStore } from '../lib/persistedStore'

/** A display preference. Server-issued lecturer authority is required for lecturer mode. */
export type Role = 'student' | 'lecturer'

const store = createPersistedStore<Role>('athena.role', 'student')

export const useRole = (): Role => {
  const preference = store.use()
  const identity = useServerIdentity()
  return identity.role === 'lecturer' ? preference : 'student'
}
export const setRole = (role: Role) => store.set(role)
