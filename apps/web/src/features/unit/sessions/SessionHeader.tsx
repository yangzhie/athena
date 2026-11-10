import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { Button } from '../../../components/ui'
import type { LearningSession, Offering } from '../../../types'
import { deleteSession, renameSession } from './sessionStore'

/** Session title with rename and delete, and a privacy note. */
export function SessionHeader({ offering, session }: { offering: Offering; session: LearningSession }) {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'view' | 'rename' | 'confirm-delete'>('view')

  function rename(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    renameSession(offering.id, session.id, String(new FormData(e.currentTarget).get('title')))
    setMode('view')
  }

  return (
    <header className="space-y-1">
      <p className="text-sm text-muted">{offering.unit.code} · learning session</p>
      {mode === 'rename' ? (
        <form onSubmit={rename} className="flex flex-wrap items-center gap-2">
          <input
            name="title"
            defaultValue={session.title}
            autoFocus
            maxLength={80}
            aria-label="Session name"
            className="h-9 min-w-0 flex-1 rounded-lg border border-line bg-surface px-3 text-base font-semibold outline-none focus:border-accent"
          />
          <Button type="submit" size="sm">Save</Button>
          <Button variant="ghost" size="sm" onClick={() => setMode('view')}>Cancel</Button>
        </form>
      ) : (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="min-w-0 truncate text-xl font-semibold tracking-tight">{session.title}</h1>
          {mode === 'confirm-delete' ? (
            <span className="flex items-center gap-2 text-sm">
              Delete this session and its chat?
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  deleteSession(offering.id, session.id)
                  navigate(`/units/${offering.id}`)
                }}
              >
                Delete
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setMode('view')}>Cancel</Button>
            </span>
          ) : (
            <span className="flex gap-1">
              <Button variant="ghost" size="sm" onClick={() => setMode('rename')}>Rename</Button>
              <Button variant="ghost" size="sm" onClick={() => setMode('confirm-delete')}>Delete</Button>
            </span>
          )}
        </div>
      )}
      <p className="text-xs text-muted">🔒 Private: only you can see this session.</p>
    </header>
  )
}
