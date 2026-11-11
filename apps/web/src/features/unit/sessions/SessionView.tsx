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
        <div className="flex flex-1 flex-col">
          <div className="mx-auto w-full max-w-3xl">
            <SessionHeader key={session.id} offering={offering} session={session} />
          </div>
          <UnitChat key={session.id} offering={offering} session={session} />
        </div>
      )}
    </SessionGate>
  )
}
