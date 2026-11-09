import { useRef, useState, type DragEvent } from 'react'
import { Button } from '../../../components/ui'
import { cn } from '../../../lib/cn'

const ACCEPT = '.pdf,.pptx,.docx,.txt,.md,.mp4,.mov,.mp3,.m4a,.wav'

/**
 * Picks files but doesn't upload them yet. The ingestion branch replaces
 * `queued` handling with a real upload + processing status.
 */
export function UploadDropzone() {
  const input = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [queued, setQueued] = useState<string[]>([])

  function add(files: FileList | null) {
    if (files) setQueued((prev) => [...prev, ...Array.from(files, (f) => f.name)])
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    add(e.dataTransfer.files)
  }

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition',
          dragging ? 'border-accent bg-accent-soft' : 'border-line bg-surface',
        )}
      >
        <p className="font-medium">Drop files here to add them to your library</p>
        <p className="text-sm text-muted">Slides, PDFs, documents or lecture recordings</p>
        <Button variant="secondary" size="sm" onClick={() => input.current?.click()}>
          Choose files
        </Button>
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            add(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {queued.length > 0 && (
        <ul className="mt-3 space-y-1 text-sm text-muted">
          {queued.map((name, i) => (
            <li key={`${name}-${i}`}>
              {name} · <span className="text-warn">not uploaded (backend not connected)</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
