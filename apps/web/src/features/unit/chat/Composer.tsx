import { useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

interface ComposerProps {
  placeholder: string
  streaming: boolean
  /** A Playground operation is busy; committed changes finish through the session API. */
  disabled?: boolean
  onSend: (text: string) => void
  onStop: () => void
}

const MAX_HEIGHT = 200

export function Composer({ placeholder, streaming, disabled = false, onSend, onStop }: ComposerProps) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)
  const canSend = text.trim() !== '' && !streaming && !disabled

  // Grow with the content up to MAX_HEIGHT, then scroll inside.
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`
  }, [text])

  function submit(e?: FormEvent) {
    e?.preventDefault()
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter is a new line; ignore Enter while an IME is composing.
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form
      onSubmit={submit}
      // A ruled line to write on, not a chat box.
      className="flex items-end gap-2 rounded-md border-b-2 border-line bg-surface/80 px-1 pt-1 pb-1.5 backdrop-blur transition-colors focus-within:border-accent"
    >
      <textarea
        ref={ref}
        value={text}
        disabled={disabled}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKeyDown}
        rows={1}
        placeholder={placeholder}
        aria-label="Message Athena"
        className="max-h-[200px] min-h-10 flex-1 resize-none bg-transparent px-2 py-2 outline-none placeholder:text-muted placeholder:italic"
      />
      {streaming ? (
        <button
          type="button"
          onClick={onStop}
          aria-label="Stop generating"
          title="Stop generating"
          className="grid size-9 shrink-0 place-items-center rounded-md bg-ink text-bg transition hover:opacity-85"
        >
          <span className="size-3 rounded-sm bg-current" />
        </button>
      ) : (
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send message"
          title="Send (Enter)"
          className="h-9 shrink-0 rounded-md px-3 text-sm font-semibold text-accent transition hover:bg-accent-soft disabled:opacity-40"
        >
          Ask ↵
        </button>
      )}
    </form>
  )
}
