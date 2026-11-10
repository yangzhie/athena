import { useEffect } from 'react'
import { Link, useParams } from 'react-router'
import { ApiUnavailable } from '../../../components/ApiUnavailable'
import { Card } from '../../../components/ui'
import { loadThread, useThread } from '../chat/chatStore'
import { UnitChat } from '../chat/UnitChat'
import { useOffering } from '../useOffering'
import { SessionHeader } from './SessionHeader'

/** One learning session: its header and chat, loaded from apps/api. */
export default function SessionView() {
  const offering = useOffering()
  const { sessionId = '' } = useParams()
  const thread = useThread(sessionId)

  useEffect(() => {
    void loadThread(offering.id, sessionId)
  }, [offering.id, sessionId])

  if (thread.status === 'loading') {
    return <Card className="mx-auto w-full max-w-3xl">Loading…</Card>
  }
  if (thread.status === 'error' && thread.error) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <ApiUnavailable error={thread.error} what="Your sessions" onRetry={() => void loadThread(offering.id, sessionId)} />
      </div>
    )
  }
  if (thread.status === 'missing' || !thread.session) {
    return (
      <section className="mx-auto w-full max-w-3xl pb-10">
        <h1 className="text-xl font-semibold">Session not found</h1>
        <p className="mt-1 text-muted">It may have been deleted.</p>
        <Link to={`/units/${offering.id}`} className="mt-2 inline-block text-accent hover:underline">
          Start a new session
        </Link>
      </section>
    )
  }

  return (
    <div className="flex flex-1 flex-col">
      <div className="mx-auto w-full max-w-3xl">
        <SessionHeader offering={offering} session={thread.session} />
      </div>
      <UnitChat key={thread.session.id} offering={offering} session={thread.session} />
    </div>
  )
}
