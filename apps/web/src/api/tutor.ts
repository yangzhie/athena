import type { ChatMessage, KnowledgeOrigin, Offering, SourceReference } from '../types'
import { documentPassages } from '../mocks/documents'
import { lectureRecordings } from '../mocks/lectures'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export type TutorEvent =
  | { type: 'text'; text: string }
  | { type: 'sources'; sources: SourceReference[]; knowledgeOrigin: KnowledgeOrigin }

const STOPWORDS = new Set('the and for are but not you your how why what when who which can does did should would could use over with from into about this that quiz explain tell know model'.split(' '))

const words = (text: string) =>
  new Set(text.toLowerCase().split(/[^a-z0-9()²-]+/).filter((w) => w.length > 2 && !STOPWORDS.has(w)))

/** Mock retrieval: course passages and clips sharing a keyword with the question. */
function findSources(offering: Offering, question: string): SourceReference[] {
  const q = words(question)
  const hit = (text: string) => [...words(text)].some((w) => q.has(w))

  const docs: SourceReference[] = documentPassages
    .filter((p) => p.offeringId === offering.id && p.keywords.some((k) => q.has(k)))
    .map((p) => ({
      kind: 'document' as const,
      sourceId: p.sourceId,
      passageId: p.passageId,
      title: p.title,
      quote: p.quote,
      page: p.page,
      section: p.section,
    }))

  const clips: SourceReference[] = lectureRecordings
    .filter((r) => r.offeringId === offering.id)
    .flatMap((r) =>
      r.clips
        .filter((c) => hit(`${c.topic} ${c.title}`))
        .map((c) => ({
          kind: 'video' as const,
          sourceId: r.id,
          segmentId: c.id,
          title: `Week ${r.week}: ${c.title}`,
          quote: c.summary,
          startS: c.startS,
          endS: c.endS,
        })),
    )

  return [...docs, ...clips].slice(0, 4)
}

/**
 * Streams the tutor's reply: text chunks, then one `sources` event.
 * Mock for now. The real version calls the agent API and maps its
 * `sources` / `knowledge_origin` to these camelCase types; keep this signature.
 */
export async function* streamTutorReply(
  offering: Offering,
  history: ChatMessage[],
  signal?: AbortSignal,
): AsyncGenerator<TutorEvent> {
  const question = history.at(-1)?.content ?? ''
  const sources = findSources(offering, question)
  const grounded = sources.length > 0

  const reply =
    `This is a placeholder reply, because the tutor isn't connected yet.\n\n` +
    `You asked: “${question}”\n\n` +
    (grounded
      ? `I found ${sources.length} relevant part${sources.length === 1 ? '' : 's'} of ${offering.unit.code}'s material, listed below. The real tutor will answer from them.`
      : `I couldn't find this in ${offering.unit.code}'s material, so a real answer would be general knowledge and labelled that way.`)

  await sleep(400) // "thinking"
  for (const word of reply.split(/(\s+)/)) {
    if (signal?.aborted) return
    yield { type: 'text', text: word }
    await sleep(word.trim() ? 25 : 0)
  }
  yield { type: 'sources', sources, knowledgeOrigin: grounded ? 'materials' : 'general' }
}
