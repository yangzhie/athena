/** 312 → "05:12", 3725 → "1:02:05". */
export function formatTimestamp(totalSeconds: number) {
  const s = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(sec).padStart(2, '0')
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

/** "9 Nov 2026" in the viewer's locale. */
export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}
