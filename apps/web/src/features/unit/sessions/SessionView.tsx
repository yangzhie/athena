import { Link, useParams } from 'react-router'
import { UnitChat } from '../chat/UnitChat'
import { useOffering } from '../useOffering'
import { SessionHeader } from './SessionHeader'
import { useSession } from './sessionStore'

/** One learning session: its header and chat. */
export default function SessionView() {
  const offering = useOffering()
  const { sessionId = '' } = useParams()
  const session = useSession(offering.id, sessionId)

  if (!session) {
    return (
      <section className="mx-auto w-full max-w-3xl pb-10">
        <h1 className="text-xl font-semibold">Session not found</h1>
        <p className="mt-1 text-muted">It may have been deleted, or it was started in another browser.</p>
        <Link to={`/units/${offering.id}`} className="mt-2 inline-block text-accent hover:underline">
          Start a new session
        </Link>
      </section>
    )
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="mx-auto w-full max-w-3xl">
        <SessionHeader offering={offering} session={session} />
      </div>
      <UnitChat key={session.id} offering={offering} session={session} />
    </div>
  )
}
