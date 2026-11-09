import { useState, type FormEvent } from 'react'
import { Button } from '../../../components/ui'

export function ReplyBox({ onSend }: { onSend: (text: string) => void }) {
  const [text, setText] = useState('')

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!text.trim()) return
    onSend(text.trim())
    setText('')
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type your answer or ask a question"
        aria-label="Reply to Athena"
        className="h-10 flex-1 rounded-lg border border-line bg-surface px-3 text-sm outline-none focus:border-accent"
      />
      <Button variant="secondary" disabled title="Voice input coming soon" aria-label="Voice input (coming soon)">
        🎤
      </Button>
      <Button type="submit" disabled={!text.trim()}>
        Send
      </Button>
    </form>
  )
}
