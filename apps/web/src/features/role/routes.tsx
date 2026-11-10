import type { Feature } from '../../app/feature'
import { RoleSwitch } from './RoleSwitch'

/** Demo role switch. Remove once SSO provides real roles. */
export const roleFeature: Feature = {
  id: 'role',
  routes: [],
  sidebarAction: RoleSwitch,
}
