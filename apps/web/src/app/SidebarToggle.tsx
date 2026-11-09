export function SidebarToggle({ open, onClick }: { open: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-controls="sidebar"
      aria-expanded={open}
      aria-label={open ? 'Hide sidebar' : 'Show sidebar'}
      title={open ? 'Hide sidebar' : 'Show sidebar'}
      className="grid size-9 place-items-center rounded-lg text-muted transition-colors hover:bg-line/60 hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
    >
      {/* Panel icon: a frame with a left column. */}
      <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth={1.75} aria-hidden>
        <rect x="3" y="4" width="18" height="16" rx="2.5" />
        <path d="M9 4v16" />
        {open && <path d="M5.5 8h1M5.5 11h1" strokeLinecap="round" />}
      </svg>
    </button>
  )
}
