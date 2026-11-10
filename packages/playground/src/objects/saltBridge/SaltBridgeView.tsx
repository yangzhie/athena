import { useBodyDrag } from '../../core/useBodyDrag'
import type { ObjectViewProps } from '../types'
import { SALT_BRIDGE } from './module'

/** The bridge's clamp. Its two ends are tubes the student dips into beakers. */
export function SaltBridgeView({ object, demonstrating, moveTo }: ObjectViewProps<'salt-bridge', null>) {
  const drag = useBodyDrag(object.rect, moveTo, demonstrating)
  return (
    <svg width={SALT_BRIDGE.w} height={SALT_BRIDGE.h} className="overflow-visible">
      <g className={demonstrating ? 'pointer-events-auto' : 'pointer-events-auto cursor-grab active:cursor-grabbing'} {...drag}>
        <rect x={4} y={22} width={142} height={24} rx={12} fill="#e0f2fe" stroke="#94a3b8" strokeWidth={2} />
        <text x={75} y={38} textAnchor="middle" className="pointer-events-none fill-ink text-[11px] font-semibold">
          Salt bridge
        </text>
        <text x={75} y={14} textAnchor="middle" className="pointer-events-none fill-muted text-[10px]">
          {object.config.electrolyte}(aq) in agar
        </text>
      </g>
    </svg>
  )
}
