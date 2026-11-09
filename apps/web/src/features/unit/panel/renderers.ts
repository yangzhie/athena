import type { ComponentType } from 'react'
import { ClipRenderer } from './renderers/ClipRenderer'
import { SandboxRenderer } from './renderers/SandboxRenderer'
import { SourceRenderer } from './renderers/SourceRenderer'
import type { PanelContent, PanelKind } from './types'

type Renderer<K extends PanelKind> = ComponentType<{ content: Extract<PanelContent, { kind: K }> }>

/** Kind → component, title and label. A new kind won't compile until it's added here. */
export const renderers: { [K in PanelKind]: { label: string; title: (c: Extract<PanelContent, { kind: K }>) => string; Component: Renderer<K> } } = {
  sandbox: { label: 'Sandbox', title: (c) => c.session.title, Component: SandboxRenderer },
  clip: { label: 'Lecture clip', title: (c) => c.clip.title, Component: ClipRenderer },
  source: { label: 'Source', title: (c) => c.source.title, Component: SourceRenderer },
}
