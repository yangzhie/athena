import { useEffect, type ComponentType } from 'react'
import { Badge } from '../../../components/ui'
import { cn } from '../../../lib/cn'
import type { Offering } from '../../../types'
import { closePanel, usePanel } from './panelStore'
import { renderers } from './renderers'
import type { PanelContent } from './types'

function Body({ content }: { content: PanelContent }) {
  // TS can't correlate the kind across the lookup, so narrow through a loose type.
  const { Component } = renderers[content.kind] as { Component: ComponentType<{ content: PanelContent }> }
  return <Component content={content} />
}

function title(content: PanelContent) {
  return (renderers[content.kind].title as (c: PanelContent) => string)(content)
}

/**
 * The unit's right-hand panel. Shows one item the tutor or the learner opened:
 * a sandbox, a lecture clip, and later slides or other sources.
 * Hidden until something opens. Then 1280px+: docked beside the page; narrower: a sheet over the page.
 */
export function SidePanel({ offering }: { offering: Offering }) {
  const content = usePanel(offering.id)
  const close = () => closePanel(offering.id)

  // Esc closes the panel when it's a sheet over the page (narrow screens).
  useEffect(() => {
    if (!content) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !window.matchMedia('(min-width: 80rem)').matches) closePanel(offering.id)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [content, offering.id])

  return (
    <>
      {content && <div className="fixed inset-0 z-30 bg-black/40 xl:hidden" onClick={close} aria-hidden />}

      <aside
        aria-label="Side panel"
        className={cn(
          'shrink-0',
          // Narrow screens: slide-over sheet, only when something is open.
          content ? 'fixed inset-y-0 right-0 z-40 w-full max-w-md p-3' : 'hidden',
          // Wide screens: docked beside the page while something is open, sticky below the top bar.
          content && 'xl:static xl:z-auto xl:block xl:w-[24rem] xl:max-w-none xl:p-0 2xl:w-[28rem]',
        )}
      >
        <section className="flex h-full flex-col overflow-hidden rounded-lg border border-line bg-surface shadow-[0_12px_32px_-22px_color-mix(in_oklab,var(--color-ink)_50%,transparent)] xl:sticky xl:top-[calc(var(--topbar-h)+1.5rem)] xl:h-[calc(100svh-var(--topbar-h)-3rem)]">
          <header className="flex items-center gap-3 border-b border-line px-5 py-3">
            <h2 className="min-w-0 flex-1 truncate font-semibold">{content ? title(content) : ''}</h2>
            {content && <Badge>{renderers[content.kind].label}</Badge>}
            {content && (
              <button
                type="button"
                onClick={close}
                aria-label="Close panel"
                title="Close"
                className="grid size-8 place-items-center rounded-lg text-muted hover:bg-line/60 hover:text-ink"
              >
                ✕
              </button>
            )}
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {content && <Body key={JSON.stringify(content)} content={content} />}
          </div>
        </section>
      </aside>
    </>
  )
}
