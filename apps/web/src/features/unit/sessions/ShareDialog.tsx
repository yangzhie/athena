import type { ChatMessage } from '../../../types'
import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../components/ui'

interface Props {
  open: boolean
  messageCount: number
  messages: ChatMessage[]
  onConfirm: () => Promise<void>
  onClose: () => void
}

/** Consent before sharing: exactly what the lecturer will and won't see. */
export function ShareDialog({ open, messageCount, messages, onConfirm, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const d = dialog.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      await onConfirm()
    } catch {
      setError('Couldn’t share the session. Try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      aria-labelledby="share-title"
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded-xl border border-line bg-surface p-0 text-ink backdrop:bg-black/40"
    >
      <div className="space-y-4 p-6">
        <h2 id="share-title" className="text-lg font-semibold">
          Share this session with your lecturer?
        </h2>
        <ul className="space-y-2 text-sm">
          <li>
            👁 Your lecturer will see <strong>the whole session</strong>: all {messageCount} message
            {messageCount === 1 ? '' : 's'} so far, and anything added while it stays shared.
          </li>
          <li>🧪 Saved Playground discussion is included. Canvas snapshots, private grading criteria and internal tool data are excluded.</li>
          <li>💬 They can reply here, and you’ll see their replies in this chat.</li>
          <li>
            🕶 It’s <strong>anonymous</strong>: they won’t see your name. But anything you wrote that identifies you (like
            your name or lab group) will still be visible.
          </li>
          <li>🔒 Only lecturers of this unit can see it. Other students never can.</li>
          <li>↩ You can stop sharing at any time, and their access ends immediately.</li>
        </ul>
        <div aria-label="Shared session preview" className="max-h-64 space-y-3 overflow-y-auto rounded-lg border border-line p-3 text-sm">
          <p className="font-medium">Preview: the saved conversation</p>
          {messages.filter((m) => !m.via && !m.id.startsWith('pending-')).map((message) => <div key={message.id}>
            <p className="text-xs text-muted">{message.role}</p><p className="whitespace-pre-wrap">{message.content}</p>
          </div>)}
        </div>
        {error && (
          <p className="text-sm text-bad" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void confirm()} disabled={busy}>
            {busy ? 'Sharing…' : 'Share anonymously'}
          </Button>
        </div>
      </div>
    </dialog>
  )
}
