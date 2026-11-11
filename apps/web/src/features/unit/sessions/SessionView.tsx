import { UnitChat } from '../chat/UnitChat'
import { useOffering } from '../useOffering'
import { SessionGate } from './SessionGate'
import { SessionHeader } from './SessionHeader'

/** One learning session: its header and chat, loaded from apps/api. */
export default function SessionView() {
  const offering = useOffering()
  return (
    <SessionGate>
      {(session) => (
        <div className="@container mx-auto flex w-full max-w-4xl flex-1 flex-col">
          <div className="w-full pt-2">
            <SessionHeader key={session.id} offering={offering} session={session} />
          </div>
          <UnitChat key={session.id} offering={offering} session={session} />
        </div>
      )}
    </SessionGate>
  )
}
