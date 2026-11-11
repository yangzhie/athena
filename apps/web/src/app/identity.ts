import { createContext, useContext } from 'react'
import type { ServerIdentity } from '../api/spaces'

/** Server authority; deliberately separate from the persisted view preference. */
export const IdentityContext = createContext<ServerIdentity>({ anonymous: true, role: 'student' })
export const useServerIdentity = () => useContext(IdentityContext)
