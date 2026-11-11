import type { ObjectId, PortKind, PortRef } from '../contracts'
import type { AnyModule, CanvasObject, PortSpec } from '../objects/types'

type Point = { x: number; y: number }
type Objects = Record<ObjectId, CanvasObject>
type ModuleOf = (o: CanvasObject) => AnyModule

/** World position of a point given relative to an object's top-left corner. */
export const worldPoint = (o: CanvasObject, p: Point): Point => ({ x: o.rect.x + p.x, y: o.rect.y + p.y })

export function portSpec(objects: Objects, moduleOf: ModuleOf, ref: PortRef): PortSpec | undefined {
  const o = objects[ref.objectId]
  return o && moduleOf(o).ports?.[ref.port]
}

/** World position of a port's attachment point. */
export function portPoint(objects: Objects, moduleOf: ModuleOf, ref: PortRef): Point | null {
  const spec = portSpec(objects, moduleOf, ref)
  return spec ? worldPoint(objects[ref.objectId], spec.at) : null
}

/** Where a plug's tip is: being dragged, attached to a socket, or resting. */
export function plugTip(objects: Objects, moduleOf: ModuleOf, o: CanvasObject, plug: string): Point {
  if (o.plugDrag?.plug === plug) return o.plugDrag
  const to = o.plugs[plug]
  const attached = to && portPoint(objects, moduleOf, to)
  if (attached) return attached
  const spec = moduleOf(o).ports![plug]
  return worldPoint(o, spec.rest ?? spec.at)
}

/** Sockets of one kind on other objects, with their world positions. */
export function socketsOfKind(objects: Objects, order: ObjectId[], moduleOf: ModuleOf, kind: PortKind, exclude: ObjectId) {
  return order.flatMap((id) => {
    const o = objects[id]
    if (id === exclude) return []
    return Object.entries(moduleOf(o).ports ?? {})
      .filter(([, spec]) => spec.role === 'socket' && spec.kind === kind)
      .map(([port, spec]) => ({ ref: { objectId: id, port }, ...worldPoint(o, spec.at) }))
  })
}

/** The closest compatible socket within `radius` world pixels of a point. */
export function nearestSocket(
  objects: Objects,
  order: ObjectId[],
  moduleOf: ModuleOf,
  kind: PortKind,
  exclude: ObjectId,
  p: Point,
  radius = 48,
): PortRef | null {
  let best: { ref: PortRef; d: number } | null = null
  for (const s of socketsOfKind(objects, order, moduleOf, kind, exclude)) {
    const d = Math.hypot(s.x - p.x, s.y - p.y)
    if (d <= radius && (!best || d < best.d)) best = { ref: s.ref, d }
  }
  return best?.ref ?? null
}
