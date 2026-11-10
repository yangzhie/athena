import { useEffect, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'
import { useRole } from '../../../app/role'
import { ApiUnavailable } from '../../../components/ApiUnavailable'
import { Card } from '../../../components/ui'
import type { LearningSession } from '../../../types'
import { loadThread, suggestPlayground, useThread } from '../chat/chatStore'
import { useOffering } from '../useOffering'
import { markSeen } from './seenStore'

/** Both chat and Playground must load the same server-authorised learning session. */
export function SessionGate({ children }: { children: (session: LearningSession) => ReactNode }) {
  const offering = useOffering()
  const role = useRole()
  const { sessionId = '' } = useParams()
  const thread = useThread(sessionId)
  const session = thread.session
  const ownsRoute = session?.id === sessionId && session?.offeringId === offering.id
  const lastReply = session?.lastLecturerReplyAt

  useEffect(() => {
    if (role === 'student' && ownsRoute && thread.status === 'ready') markSeen(sessionId)
  }, [role, ownsRoute, sessionId, thread.status, lastReply, thread.messages.length])

  useEffect(() => {
    if (role !== 'student' || !sessionId) return
    void loadThread(offering.id, sessionId, { refresh: true })
    const onFocus = () => void loadThread(offering.id, sessionId, { refresh: true })
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
  }, [offering.id, sessionId, role])

  const goal = session?.goal
  useEffect(() => {
    if (role === 'student' && ownsRoute && thread.status === 'ready' && goal) {
      void suggestPlayground(offering, sessionId, goal)
    }
  }, [offering, sessionId, goal, ownsRoute, role, thread.status])

  if (role !== 'student') {
    return (
      <Card className="mx-auto w-full max-w-3xl" title="Learning sessions are private">
        <Link to={`/units/${offering.id}/shared`} className="text-sm text-accent hover:underline">
          View sessions students have shared with you
        </Link>
      </Card>
    )
  }
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
  if (thread.status === 'missing' || !session || !ownsRoute) {
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
  return children(session)
}
