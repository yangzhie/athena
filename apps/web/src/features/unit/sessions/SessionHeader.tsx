import { Link, useNavigate } from 'react-router'
import { useState, type CSSProperties, type FormEvent } from 'react'
import { Button, Icon } from '../../../components/ui'
import { unitColor } from '../../../lib/unitColor'
import { lessonProgress } from '../chat/lessonProgress'
import { StepRail } from './StepRail'
import type { LearningSession, Offering } from '../../../types'
import { formatDate } from '../../../lib/format'
import { loadThread, updateThreadSession, useThread } from '../chat/chatStore'
import { ShareDialog } from './ShareDialog'
import { playgroundPath } from './paths'
import { deleteSession, renameSession, setSharing } from './sessionStore'

/** Session title with rename and delete, and a privacy note. */
export function SessionHeader({ offering, session }: { offering: Offering; session: LearningSession }) {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'view' | 'rename' | 'confirm-delete'>('view')
  const [error, setError] = useState<string | null>(null)
  const [sharing, setSharingOpen] = useState(false)
  const { messages } = useThread(session.id)

  async function share() {
    updateThreadSession(await setSharing(offering.id, session.id, true))
    setSharingOpen(false)
  }

  async function stopSharing() {
    try {
      updateThreadSession(await setSharing(offering.id, session.id, false))
    } catch {
      setError('Couldn’t stop sharing. Try again.')
    }
  }

  async function rename(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const title = String(new FormData(e.currentTarget).get('title')).trim()
    if (!title) return
    try {
      updateThreadSession(await renameSession(offering.id, session.id, title))
      setMode('view')
      setError(null)
    } catch {
      setError('Couldn’t rename the session.')
    }
  }

  async function remove() {
    try {
      await deleteSession(offering.id, session.id)
      navigate(`/units/${offering.id}`)
    } catch {
      setError('Couldn’t delete the session.')
    }
  }

  const progress = lessonProgress(messages)
  const tool = 'inline-flex items-center gap-1 text-sm text-muted transition-colors hover:text-ink'

  return (
    <header className="space-y-3 border-b border-line pb-5" style={{ '--unit': unitColor(offering.unit.code) } as CSSProperties}>
      <p className="text-xs font-semibold tracking-[0.14em] text-(--unit) uppercase">{offering.unit.code} · Lesson</p>
      {mode === 'rename' ? (
        <form onSubmit={(e) => void rename(e)} className="flex flex-wrap items-center gap-2">
          <input
            name="title"
            defaultValue={session.title}
            autoFocus
            maxLength={80}
            aria-label="Session name"
            className="h-11 min-w-0 flex-1 rounded-md border border-line bg-surface px-3 font-serif text-2xl font-semibold outline-none focus:border-accent"
          />
          <Button type="submit" size="sm">Save</Button>
          <Button variant="ghost" size="sm" onClick={() => setMode('view')}>Cancel</Button>
        </form>
      ) : (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="min-w-0 text-3xl leading-tight font-semibold">{session.title}</h1>
          {mode === 'confirm-delete' ? (
            <span className="flex items-center gap-2 text-sm">
              Delete this session and its chat?
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void remove()}
              >
                Delete
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setMode('view')}>Cancel</Button>
            </span>
          ) : (
            <span className="flex gap-3">
              <button type="button" className={tool} onClick={() => setMode('rename')}>Rename</button>
              <button type="button" className={tool} onClick={() => setMode('confirm-delete')}>Delete</button>
            </span>
          )}
        </div>
      )}
      <StepRail progress={progress} />
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1">
        <Link to={playgroundPath(offering.id, session.id)} className="inline-flex items-center gap-1.5 text-sm font-semibold text-accent hover:underline">
          <Icon name="flask" className="size-4" /> Open Playground
        </Link>
      {session.shared ? (
        <p className="flex flex-wrap items-center gap-x-2 text-xs">
          <span className="font-medium text-accent">
            Shared anonymously with your lecturer{session.sharedAt && ` since ${formatDate(session.sharedAt)}`}
          </span>
          <button type="button" onClick={() => void stopSharing()} className="text-muted underline hover:text-ink">
            Stop sharing
          </button>
        </p>
      ) : (
        <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
          Private: only you can see this session.
          <button type="button" onClick={() => { void loadThread(offering.id, session.id, { refresh: true }).then(() => setSharingOpen(true)) }} className="underline hover:text-ink">
            Share with lecturer…
          </button>
        </p>
      )}
      </div>
      {error && (
        <p className="text-sm text-bad" role="alert">
          {error}
        </p>
      )}
      <ShareDialog
        open={sharing}
        messages={messages}
        messageCount={messages.filter((m) => !m.via && !m.id.startsWith('pending-')).length}
        onConfirm={share}
        onClose={() => setSharingOpen(false)}
      />
    </header>
  )
}
