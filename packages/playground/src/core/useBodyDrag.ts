import { useRef, type PointerEvent } from 'react'
import type { Rect } from '../contracts'

/**
 * Drag a frameless object by its body (e.g. a beaker). Buttons inside keep
 * working; the canvas zoom is read from the object's on-screen size.
 */
export function useBodyDrag(rect: Rect, moveTo: (x: number, y: number) => void, disabled = false) {
  const drag = useRef<{ x: number; y: number; ox: number; oy: number; scale: number } | null>(null)
  return {
    onPointerDown(e: PointerEvent<Element>) {
      if (disabled || (e.target as Element).closest('button')) return
      const frame = (e.currentTarget as Element).closest('[data-object]')
      const scale = frame ? frame.getBoundingClientRect().width / rect.w : 1
      e.currentTarget.setPointerCapture(e.pointerId)
      drag.current = { x: e.clientX, y: e.clientY, ox: rect.x, oy: rect.y, scale }
    },
    onPointerMove(e: PointerEvent<Element>) {
      const d = drag.current
      if (d) moveTo(d.ox + (e.clientX - d.x) / d.scale, d.oy + (e.clientY - d.y) / d.scale)
    },
    onPointerUp() {
      drag.current = null
    },
    onPointerCancel() {
      drag.current = null
    },
  }
}
