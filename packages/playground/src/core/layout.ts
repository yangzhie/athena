import type { Rect, Viewport } from '../contracts'

const GAP = 56
const ORIGIN = { x: 0, y: 0 }
export const DEFAULT_HEIGHT = 320

const overlaps = (a: Rect, b: Rect) =>
  a.x < b.x + b.w + GAP / 2 && b.x < a.x + a.w + GAP / 2 && a.y < b.y + b.h + GAP / 2 && b.y < a.y + a.h + GAP / 2

/**
 * Place a new object without moving anything the student arranged: to the
 * right of its anchor if there is one, otherwise after the last object, then
 * down until it no longer overlaps.
 */
export function place(w: number, existing: Rect[], anchor: Rect | null, side: 'right' | 'below' = 'right', h = DEFAULT_HEIGHT): Rect {
  const ref = anchor ?? existing[existing.length - 1] ?? null
  const rect: Rect = !ref
    ? { ...ORIGIN, w, h }
    : side === 'below' && anchor
      ? { x: ref.x, y: ref.y + ref.h + GAP, w, h }
      : { x: ref.x + ref.w + GAP, y: ref.y, w, h }
  for (let i = 0; i < 50 && existing.some((r) => overlaps(r, rect)); i++) {
    const blocker = existing.find((r) => overlaps(r, rect))!
    rect.y = blocker.y + blocker.h + GAP
  }
  return rect
}

export function bounds(rects: Rect[]): Rect | null {
  if (!rects.length) return null
  const x = Math.min(...rects.map((r) => r.x))
  const y = Math.min(...rects.map((r) => r.y))
  const x2 = Math.max(...rects.map((r) => r.x + r.w))
  const y2 = Math.max(...rects.map((r) => r.y + r.h))
  return { x, y, w: x2 - x, h: y2 - y }
}

export const MIN_ZOOM = 0.25
export const MAX_ZOOM = 2

export const clampZoom = (z: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z))

/** A viewport that shows `rect` inside a container of the given size. */
export function fit(rect: Rect, size: { w: number; h: number }, pad = 48, maxZoom = 1): Viewport {
  const zoom = clampZoom(Math.min(maxZoom, (size.w - pad * 2) / rect.w, (size.h - pad * 2) / rect.h))
  return {
    zoom,
    x: (size.w - rect.w * zoom) / 2 - rect.x * zoom,
    y: Math.max(pad, (size.h - rect.h * zoom) / 2) - rect.y * zoom,
  }
}

/** Zoom around a screen point so the world point under it stays put. */
export function zoomAt(v: Viewport, zoom: number, cx: number, cy: number): Viewport {
  const z = clampZoom(zoom)
  const wx = (cx - v.x) / v.zoom
  const wy = (cy - v.y) / v.zoom
  return { zoom: z, x: cx - wx * z, y: cy - wy * z }
}
