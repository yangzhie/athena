import { useRef, useState, type PointerEvent } from 'react'
import { cn } from '../../core/cn'
import type { ObjectViewProps } from '../types'
import { canStop, isSorted, type SortBenchState, type SortItem } from './module'

const BAR_AREA = 150
const BUTTONS = 44

/** Equal values get a letter in their starting order, so a swap that breaks stability shows. */
function tags(items: SortItem[]) {
  const byStart = [...items].sort((a, b) => a.id - b.id)
  const seen = new Map<number, number>()
  const out = new Map<number, string>()
  for (const it of byStart) {
    const n = seen.get(it.value) ?? 0
    seen.set(it.value, n + 1)
    if (byStart.filter((x) => x.value === it.value).length > 1) out.set(it.id, String.fromCharCode(97 + n))
  }
  return out
}

type Drag = { kind: 'bar'; id: number; side: 1 | -1; x0: number; dx: number } | { kind: 'next'; x0: number; dx: number }

/**
 * Bubble sort by hand: in the highlighted pair, drag one bar past the other to
 * swap them, or slide the arrow under the pair on to keep them; pass after
 * pass, then say when the algorithm can stop.
 */
export function SortBenchView({ object, state, dispatch, demonstrating, highlight }: ObjectViewProps<'sort-bench', SortBenchState>) {
  const area = useRef<HTMLDivElement>(null)
  const [drag, setDrag] = useState<Drag | null>(null)
  const n = state.items.length
  const slot = Math.min(64, Math.floor(520 / n))
  const max = Math.max(...state.items.map((i) => i.value))
  const letters = tags(state.items)
  const deciding = !state.finished && state.sortedFrom > 1
  const pair = deciding ? [state.cursor, state.cursor + 1] : []
  const flagged = highlight?.part === 'last-pair' && state.last ? [state.last.index, state.last.index + 1] : []
  // Bars are placed by their current index, so a swap slides them past each other.
  const at = new Map(state.items.map((it, i) => [it.id, i]))
  const byId = [...state.items].sort((a, b) => a.id - b.id)
  const held = drag?.kind === 'bar' ? drag : null
  /** How far a bar is pushed while the other one in the pair is dragged past it. */
  const offset = (i: number, id: number) => {
    if (!held) return 0
    if (id === held.id) return held.dx
    return pair.includes(i) ? -held.dx : 0
  }

  /** Pointer x in the bar area's own pixels, whatever the canvas zoom. */
  const localX = (e: PointerEvent) => {
    const box = area.current!.getBoundingClientRect()
    return ((e.clientX - box.left) * area.current!.offsetWidth) / box.width
  }
  const grab = (e: PointerEvent<HTMLDivElement>) => {
    if (demonstrating || !deciding) return
    const { bar } = e.currentTarget.dataset
    const i = bar === undefined ? -1 : at.get(Number(bar))!
    if (bar !== undefined && !pair.includes(i)) return
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    const x0 = localX(e)
    setDrag(bar === undefined ? { kind: 'next', x0, dx: 0 } : { kind: 'bar', id: Number(bar), side: i === state.cursor ? 1 : -1, x0, dx: 0 })
  }
  const pull = (e: PointerEvent<HTMLDivElement>) => {
    if (!drag) return
    const dx = localX(e) - drag.x0
    // The left bar only goes right, the right one only left, and the arrow only on.
    const limit = drag.kind === 'bar' ? drag.side : 1
    setDrag({ ...drag, dx: limit > 0 ? Math.min(slot, Math.max(0, dx)) : Math.max(-slot, Math.min(0, dx)) })
  }
  const release = () => {
    if (!drag) return
    setDrag(null)
    if (drag.kind === 'bar' && Math.abs(drag.dx) > slot / 2) dispatch({ type: 'swap', index: state.cursor })
    // The arrow moves on when slid more than halfway, or tapped.
    if (drag.kind === 'next' && (drag.dx > slot / 2 || drag.dx < 3)) dispatch({ type: 'keep', index: state.cursor })
  }
  const handlers = { onPointerDown: grab, onPointerMove: pull, onPointerUp: release, onPointerCancel: release }

  return (
    <div className="space-y-3 p-3 text-sm">
      <div className="flex items-baseline gap-3">
        <p className="min-w-0 flex-1">
          {state.finished ? (
            <span className="font-medium text-good">Sorted, and the algorithm knows it.</span>
          ) : deciding ? (
            <>
              Pass {state.pass}: compare positions{' '}
              <span className="font-mono">
                {state.cursor} and {state.cursor + 1}
              </span>
            </>
          ) : (
            <span className="text-muted">Every pass has run.</span>
          )}
        </p>
        <span className="shrink-0 text-xs text-muted">
          {state.comparisons} comparisons · {state.swaps} swaps
        </span>
      </div>

      <div ref={area} data-anchor={`${object.id}/bars`} className="relative mx-auto select-none" style={{ width: n * slot, height: BAR_AREA + BUTTONS }}>
        {byId.map((it) => {
          const i = at.get(it.id)!
          const movable = pair.includes(i) && !demonstrating
          return (
            <div
              key={it.id}
              {...handlers}
              data-bar={it.id}
              data-anchor={i === state.cursor && deciding ? `${object.id}/pair` : undefined}
              className={cn('absolute bottom-[44px] touch-none', held ? '' : 'transition-[left] duration-500 ease-in-out', movable && 'cursor-grab active:cursor-grabbing')}
              style={{ left: i * slot + offset(i, it.id), width: slot, zIndex: held?.id === it.id ? 2 : 1 }}
            >
              <div
                className={cn(
                  'mx-1 flex items-end justify-center rounded-t-md border pb-1 font-mono text-xs font-semibold',
                  i >= state.sortedFrom || state.finished
                    ? 'border-good/40 bg-good/15 text-good'
                    : pair.includes(i)
                      ? 'border-accent bg-accent-soft text-accent'
                      : 'border-line bg-bg',
                  flagged.includes(i) && 'ring-4 ring-warn/70',
                  held?.id === it.id && 'shadow-lg',
                )}
                style={{ height: 24 + (it.value / max) * (BAR_AREA - 30) }}
              >
                {it.value}
                {letters.has(it.id) && <sub className="ml-px text-[9px] font-normal">{letters.get(it.id)}</sub>}
              </div>
            </div>
          )
        })}
        {deciding && (
          <div
            {...handlers}
            data-anchor={`${object.id}/next`}
            title="Keep this pair and move on"
            className={cn(
              'absolute bottom-1 flex h-7 touch-none items-center justify-center rounded-full border border-accent/40 bg-accent-soft font-mono text-sm text-accent',
              drag?.kind === 'next' ? '' : 'transition-[left] duration-300',
              !demonstrating && 'cursor-grab active:cursor-grabbing',
            )}
            style={{ left: state.cursor * slot + slot / 2 + (drag?.kind === 'next' ? drag.dx : 0), width: slot }}
          >
            ⟶
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <p className="min-w-0 flex-1 text-xs text-muted">Drag a bar past its neighbour to swap them, or slide ⟶ on to keep them. Green bars are in their final place.</p>
        <button
          type="button"
          data-anchor={`${object.id}/reset`}
          disabled={demonstrating || state.comparisons === 0}
          onClick={() => dispatch({ type: 'resetSort' })}
          className="shrink-0 rounded-lg border border-line px-3 py-1.5 text-xs hover:bg-line/50 disabled:opacity-40"
        >
          Start over
        </button>
        <button
          type="button"
          data-anchor={`${object.id}/finish`}
          disabled={demonstrating || state.finished}
          onClick={() => dispatch({ type: 'finish' })}
          className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-40"
        >
          Done: it can stop
        </button>
      </div>

      <table className="w-full text-xs">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className="py-1 font-normal">Pass</th>
            <th className="py-1 font-normal">After the pass</th>
            <th className="py-1 text-right font-normal">Comparisons</th>
            <th className="py-1 text-right font-normal">Swaps</th>
          </tr>
        </thead>
        <tbody>
          {state.history.map((p) => (
            <tr key={p.pass} className="border-b border-line/60">
              <td className="py-1 text-muted">{p.pass}</td>
              <td className="py-1 font-mono">[{p.values.join(', ')}]</td>
              <td className="py-1 text-right font-mono">{p.comparisons}</td>
              <td className={cn('py-1 text-right font-mono', p.swaps === 0 && 'font-semibold text-good')}>{p.swaps}</td>
            </tr>
          ))}
          {!state.history.length && (
            <tr>
              <td colSpan={4} className="py-2 text-center text-muted">
                No pass finished yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {!state.finished && isSorted(state.items) && !canStop(state) && state.comparisons > 0 && (
        <p className="text-xs text-muted">You can see it's in order. Can the algorithm?</p>
      )}
    </div>
  )
}
