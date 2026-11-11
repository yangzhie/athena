import { useEffect, useRef, useState } from 'react'
import { Button } from '../ui'

interface Props {
  value: string
  onChange: (text: string) => void
  disabled?: boolean
  transcribe?: (audio: Blob, signal: AbortSignal) => Promise<string>
  onBusyChange?: (busy: boolean) => void
}

/** Dictation is an editable draft, never a submission. Audio stays out of storage. */
export function VoiceAnswerInput({ value, onChange, disabled = false, transcribe, onBusyChange }: Props) {
  const [state, setState] = useState<'idle' | 'requesting' | 'recording' | 'transcribing'>('idle')
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const recorder = useRef<MediaRecorder | null>(null)
  const stream = useRef<MediaStream | null>(null)
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined)
  const request = useRef<AbortController | null>(null)
  const generation = useRef(0)
  const container = useRef<HTMLDivElement>(null)
  const supported = typeof window !== 'undefined' && window.isSecureContext &&
    typeof MediaRecorder !== 'undefined' && !!navigator.mediaDevices?.getUserMedia

  useEffect(() => { onBusyChange?.(state !== 'idle') }, [state, onBusyChange])
  useEffect(() => {
    if (notice) container.current?.closest('form')?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [notice])

  function release() {
    clearInterval(timer.current)
    stream.current?.getTracks().forEach(track => track.stop())
    stream.current = null
  }

  function cancel() {
    generation.current++
    request.current?.abort()
    if (recorder.current?.state === 'recording') recorder.current.stop()
    release()
    setState('idle')
  }

  useEffect(() => () => {
    generation.current++
    request.current?.abort()
    if (recorder.current?.state === 'recording') recorder.current.stop()
    clearInterval(timer.current)
    stream.current?.getTracks().forEach(track => track.stop())
  }, [])

  useEffect(() => {
    const hide = () => {
      if (!document.hidden || recorder.current?.state !== 'recording') return
      generation.current++
      recorder.current.stop()
      clearInterval(timer.current)
      stream.current?.getTracks().forEach(track => track.stop())
      setState('idle')
      setNotice('Recording cancelled when you left the tab. No audio was sent; your draft is safe.')
    }
    document.addEventListener('visibilitychange', hide)
    return () => document.removeEventListener('visibilitychange', hide)
  }, [])

  async function start() {
    if (!supported || !transcribe || disabled || state !== 'idle') return
    const id = ++generation.current
    setError(null)
    setNotice('')
    setState('requesting')
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (generation.current !== id) { media.getTracks().forEach(track => track.stop()); return }
      stream.current = media
      const mime = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus']
        .find(type => MediaRecorder.isTypeSupported(type))
      if (!mime) throw new Error('This browser cannot record a supported audio format. Please type your answer.')
      const recording = new MediaRecorder(media, { mimeType: mime })
      recorder.current = recording
      const chunks: Blob[] = []
      let bytes = 0
      recording.ondataavailable = event => {
        if (id !== generation.current) return
        bytes += event.data.size
        if (bytes > 2 * 1024 * 1024) {
          cancel()
          setError('The recording is too large. Please record a shorter answer.')
        } else if (event.data.size) chunks.push(event.data)
      }
      recording.onerror = () => {
        if (id !== generation.current) return
        cancel()
        setError('Recording stopped unexpectedly. Your typed answer is safe; please try again.')
      }
      recording.onstop = async () => {
        if (id !== generation.current) return
        release()
        setState('transcribing')
        const abort = new AbortController()
        request.current = abort
        try {
          const audio = new Blob(chunks, { type: mime })
          if (!audio.size) throw new Error('No audio was recorded. Please try again or type your answer.')
          const text = (await transcribe(audio, abort.signal)).trim()
          if (id !== generation.current) return
          const combined = [value.trimEnd(), text].filter(Boolean).join(' ')
          if (!text) throw new Error('No speech was detected. Please try again.')
          if (combined.length > 4000) throw new Error('The combined answer is too long. Shorten your draft before recording again.')
          onChange(combined)
          setNotice('Transcript added. Review or edit your answer, then submit it.')
        } catch (e) {
          if (id === generation.current) setError(e instanceof Error ? e.message : 'Voice typing failed. Please type your answer.')
        } finally {
          if (id === generation.current) setState('idle')
        }
      }
      setSeconds(0)
      recording.start(1000)
      setState('recording')
      const started = Date.now()
      timer.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - started) / 1000)
        setSeconds(Math.min(elapsed, 60))
        if (elapsed >= 60 && recording.state === 'recording') recording.stop()
      }, 1000)
    } catch (e) {
      if (id !== generation.current) return
      release()
      setState('idle')
      setError(e instanceof DOMException && e.name === 'NotAllowedError'
        ? 'Microphone access was denied. Allow it in your browser settings, or type your answer.'
        : e instanceof Error ? e.message : 'The microphone is unavailable. You can still type your answer.')
    }
  }

  const working = state !== 'idle'
  return <div ref={container} className="space-y-2">
    <textarea value={value} onChange={event => onChange(event.target.value)} rows={3} maxLength={4000}
      aria-label="Your answer" placeholder="Explain your reasoning in a sentence or two"
      disabled={disabled || working}
      className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent disabled:opacity-70" />
    {transcribe && <>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="secondary" size="sm" disabled={disabled || !supported || state === 'requesting' || state === 'transcribing'}
          onClick={() => state === 'recording' ? recorder.current?.stop() : void start()}>
          {state === 'recording' ? `Stop recording · ${seconds}s` : state === 'transcribing' ? 'Transcribing…' : state === 'requesting' ? 'Opening microphone…' : '🎙 Speak answer'}
        </Button>
        {working && <Button type="button" variant="ghost" size="sm" onClick={cancel}>Cancel voice typing</Button>}
      </div>
      <p className="text-xs text-muted">{supported
        ? 'Up to 60 seconds. Audio is sent for transcription, not saved by Athena. Review before submitting.'
        : 'Voice typing needs a supported browser on HTTPS or localhost. You can still type your answer.'}</p>
      {notice && <p role="status" className="text-xs text-muted">{notice}</p>}
      {error && <p role="alert" className="text-sm text-bad">{error}</p>}
    </>}
  </div>
}
