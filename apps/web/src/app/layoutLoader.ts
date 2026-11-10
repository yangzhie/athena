import { redirect } from 'react-router'
import { listEnrolledOfferings } from '../api/spaces'

export async function layoutLoader() {
  return { offerings: await listEnrolledOfferings() }
}

/** "/" goes straight to the first enrolled unit, or shows "No units yet". */
export async function indexLoader() {
  const [first] = await listEnrolledOfferings()
  return first ? redirect(first.status === 'draft' ? `/units/${first.id}/manage` : `/units/${first.id}`) : null
}
