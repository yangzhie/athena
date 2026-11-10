import { useEffect, useRef, useState } from 'react'
import { Button } from '../../../components/ui'

interface Props {
  open: boolean
  messageCount: number
  onConfirm: () => Promise<void>
  onClose: () => void
}

/** Consent before sharing: exactly what the lecturer will and won't see. */
export function ShareDialog({ open, messageCount, onConfirm, onClose }: Props) {
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
          <li>💬 They can reply here, and you’ll see their replies in this chat.</li>
          <li>
            🕶 It’s <strong>anonymous</strong>: they won’t see your name. But anything you wrote that identifies you (like
            your name or lab group) will still be visible.
          </li>
          <li>🔒 Only lecturers of this unit can see it. Other students never can.</li>
          <li>↩ You can stop sharing at any time, and their access ends immediately.</li>
        </ul>
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
