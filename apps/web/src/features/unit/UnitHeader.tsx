import type { CSSProperties, ReactNode } from 'react'
import { unitColor } from '../../lib/unitColor'
import type { Offering } from '../../types'

/** A unit page's heading: the unit code in its index-tab colour over a serif title. */
export function UnitHeader({ offering, title }: { offering: Offering; title?: ReactNode }) {
  return (
    <header style={{ '--unit': unitColor(offering.unit.code) } as CSSProperties}>
      <p className="text-xs font-semibold tracking-[0.14em] uppercase">
        <span className="text-(--unit)">{offering.unit.code}</span>
        <span className="text-muted"> · {offering.semester} {offering.year}</span>
      </p>
      <h1 className="mt-1 text-2xl leading-tight font-semibold">{title ?? offering.unit.title}</h1>
    </header>
  )
}
