import { createPersistedStore } from '../lib/persistedStore'

/**
 * Who's using the app. A mock switch for the PoC; real roles come from
 * university SSO, and the server must enforce them, never this value.
 */
export type Role = 'student' | 'lecturer'

const store = createPersistedStore<Role>('athena.role', 'student')

export const useRole = store.use
export const setRole = (role: Role) => store.set(role)
