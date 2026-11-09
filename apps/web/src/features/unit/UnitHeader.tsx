import type { ReactNode } from 'react'
import type { Offering } from '../../types'

export function UnitHeader({ offering, title }: { offering: Offering; title?: ReactNode }) {
  return (
    <header>
      <p className="text-sm text-muted">
        {offering.unit.code} · {offering.semester} {offering.year}
      </p>
      <h1 className="mt-0.5 text-xl font-semibold tracking-tight">{title ?? offering.unit.title}</h1>
    </header>
  )
}
