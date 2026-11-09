import { useRouteLoaderData } from 'react-router'
import type { Offering } from '../../types'
import { UNIT_ROUTE_ID, type unitLoader } from './loader'

/** The current offering, for views rendered inside UnitLayout (which handles "not found"). */
export function useOffering(): Offering {
  const data = useRouteLoaderData<typeof unitLoader>(UNIT_ROUTE_ID)
  if (!data?.offering) throw new Error('useOffering must be used inside a found unit')
  return data.offering
}
