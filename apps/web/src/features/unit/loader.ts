import type { LoaderFunctionArgs } from 'react-router'
import { listLectures } from '../../api/lectures'
import { getEnrolledOffering } from '../../api/spaces'

/** Route id, so child views can read the offering with useRouteLoaderData. */
export const UNIT_ROUTE_ID = 'unit'

export async function unitLoader({ params }: LoaderFunctionArgs) {
  return { offering: (await getEnrolledOffering(params.offeringId ?? '')) ?? null }
}

export async function clipsLoader({ params }: LoaderFunctionArgs) {
  return { lectures: await listLectures(params.offeringId ?? '') }
}
