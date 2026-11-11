import { useSyncExternalStore } from 'react'
import type { Playground, PlaygroundEvent } from '@athena/playground'

function line(e: PlaygroundEvent): string {
  switch (e.kind) {
    case 'action': {
      const { objectId, type, ...rest } = e.action
      const payload = type === 'runCompleted' ? `average=${(rest as { result: { values: Record<string, string> } }).result.values.average ?? '—'}` : JSON.stringify(rest)
      return `${e.actor}${e.demonstration ? ' (demo)' : ''} ${objectId}.${type} ${payload === '{}' ? '' : payload}`
    }
    case 'check':
      return `check ${e.checkId} → ${e.verdict}`
    case 'unmatched':
      return `unmatched ${e.objectId} ${JSON.stringify(e.observation)}`
    case 'proposal':
      return `proposal ${e.proposalId} ${e.status}`
    case 'demonstration':
      return `demonstration ${e.objectId} ${e.status}`
    case 'discuss':
      return `discuss ${e.objectId ?? 'canvas'} "${e.text}"`
    case 'selected':
      return `selected ${e.objectId ?? 'none'}`
    case 'linked':
      return `linked ${e.link.from} → ${e.link.to} (${e.link.relation})`
    case 'object-added':
    case 'object-removed':
      return `${e.kind} ${e.objectId} by ${e.actor}`
    case 'scene-opened':
      return `scene-opened ${e.sceneId}`
    case 'goal-reached':
      return `goal-reached via ${e.checkId}`
  }
}

const COLOR: Partial<Record<PlaygroundEvent['kind'], string>> = {
  check: 'text-warn',
  'goal-reached': 'text-good',
  unmatched: 'text-bad',
  proposal: 'text-accent',
  demonstration: 'text-accent',
}

/** The Canvas event stream, newest first. The tutor would subscribe to the same stream. */
export function EventLog({ playground }: { playground: Playground }) {
  const events = useSyncExternalStore(playground.onEvent, playground.getEvents)
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3 font-mono text-[11px] leading-5">
      {events.length === 0 && <p className="text-muted">No events yet.</p>}
      {[...events].reverse().map((e) => (
        <div key={e.seq} className={COLOR[e.kind] ?? 'text-ink'}>
          <span className="mr-2 text-muted/60">{String(e.seq).padStart(3, '0')}</span>
          {line(e)}
        </div>
      ))}
    </div>
  )
}
