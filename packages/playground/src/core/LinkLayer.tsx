import type { Link, Rect, Relation } from '../contracts'

const RELATION_LABEL: Record<Relation, string> = {
  from: 'from',
  contrast: 'contrast',
  explains: 'explains',
}

const RELATION_STROKE: Record<Relation, string> = {
  from: 'stroke-muted',
  contrast: 'stroke-warn',
  explains: 'stroke-accent',
}

/** Where the segment from the centre of `r` towards (tx, ty) leaves the rectangle. */
function edgePoint(r: Rect, tx: number, ty: number) {
  const cx = r.x + r.w / 2
  const cy = r.y + r.h / 2
  const dx = tx - cx
  const dy = ty - cy
  if (!dx && !dy) return { x: cx, y: cy }
  const s = Math.min(Math.abs(r.w / 2 / (dx || 1e-9)), Math.abs(r.h / 2 / (dy || 1e-9)))
  return { x: cx + dx * s, y: cy + dy * s }
}

/** Typed links, drawn in world coordinates behind the cards. */
export function LinkLayer({ links, rects }: { links: Link[]; rects: Record<string, Rect> }) {
  return (
    <svg className="pointer-events-none absolute top-0 left-0 overflow-visible" width={1} height={1}>
      <defs>
        <marker id="pg-link-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
          <path d="M0,0 L10,5 L0,10 z" className="fill-muted" />
        </marker>
      </defs>
      {links.map((l) => {
        const a = rects[l.from]
        const b = rects[l.to]
        if (!a || !b) return null
        const p1 = edgePoint(a, b.x + b.w / 2, b.y + b.h / 2)
        const p2 = edgePoint(b, a.x + a.w / 2, a.y + a.h / 2)
        const mx = (p1.x + p2.x) / 2
        const my = (p1.y + p2.y) / 2
        return (
          <g key={l.id}>
            <line
              x1={p1.x}
              y1={p1.y}
              x2={p2.x}
              y2={p2.y}
              strokeWidth={2}
              strokeDasharray={l.relation === 'contrast' ? '6 5' : undefined}
              className={RELATION_STROKE[l.relation]}
              markerEnd="url(#pg-link-arrow)"
            />
            <foreignObject x={mx - 30} y={my - 12} width={60} height={24}>
              <div className="flex h-full items-center justify-center">
                <span className="rounded-full border border-line bg-surface px-2 py-0.5 text-[11px] text-muted shadow-sm">
                  {RELATION_LABEL[l.relation]}
                </span>
              </div>
            </foreignObject>
          </g>
        )
      })}
    </svg>
  )
}
