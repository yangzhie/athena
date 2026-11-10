import { useEffect, useRef, useState } from 'react'
import { formatTimestamp } from '../../../../lib/format'

interface Props {
  src: string
  startS: number
  endS: number
  title: string
}

/**
 * Plays one clip: a time range of the full recording. Starts at `startS`,
 * stops at `endS`, and the progress bar only spans the clip.
 */
export function ClipPlayer({ src, startS, endS, title }: Props) {
  const video = useRef<HTMLVideoElement>(null)
  const [time, setTime] = useState(startS)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState(false)
  const length = endS - startS

  // Jump to the clip's start once the recording's metadata is known.
  useEffect(() => {
    const v = video.current
    if (!v) return
    const toStart = () => {
      v.currentTime = startS
    }
    if (v.readyState >= 1) toStart()
    else v.addEventListener('loadedmetadata', toStart, { once: true })
    return () => v.removeEventListener('loadedmetadata', toStart)
  }, [startS])

  function onTimeUpdate() {
    const v = video.current
    if (!v) return
    if (v.currentTime >= endS) {
      v.pause()
      v.currentTime = endS
    }
    setTime(v.currentTime)
  }

  function toggle() {
    const v = video.current
    if (!v) return
    if (v.paused) {
      if (v.currentTime >= endS - 0.25 || v.currentTime < startS) v.currentTime = startS
      void v.play()
    } else {
      v.pause()
    }
  }

  function seek(offset: number) {
    const v = video.current
    if (v) v.currentTime = startS + offset
  }

  const offset = Math.min(Math.max(time - startS, 0), length)

  return (
    <div className="overflow-hidden rounded-xl bg-black">
      <video
        ref={video}
        src={`${src}#t=${startS},${endS}`}
        preload="metadata"
        playsInline
        onClick={toggle}
        onTimeUpdate={onTimeUpdate}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onError={() => setError(true)}
        aria-label={`Lecture clip: ${title}`}
        className="aspect-video w-full cursor-pointer bg-black"
      />
      {error ? (
        <p className="px-4 py-3 text-sm text-white/80">
          The recording couldn’t be loaded. It only plays in the dev server (npm run dev) on the machine that indexed it.
        </p>
      ) : (
        <div className="flex items-center gap-3 px-3 py-2 text-white">
          <button
            type="button"
            onClick={toggle}
            aria-label={playing ? 'Pause' : 'Play'}
            className="grid size-8 shrink-0 place-items-center rounded-full bg-white/15 text-sm hover:bg-white/25"
          >
            {playing ? '❚❚' : '▶'}
          </button>
          <input
            type="range"
            min={0}
            max={length}
            step={0.5}
            value={offset}
            onChange={(e) => seek(Number(e.target.value))}
            aria-label="Position in clip"
            aria-valuetext={`${formatTimestamp(offset)} of ${formatTimestamp(length)}`}
            className="h-1 min-w-0 flex-1 cursor-pointer accent-white"
          />
          <span className="shrink-0 text-xs tabular-nums text-white/80">
            {formatTimestamp(offset)} / {formatTimestamp(length)}
          </span>
        </div>
      )}
    </div>
  )
}
