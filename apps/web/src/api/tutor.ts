import type { ChatMessage, Offering } from '../types'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * Streams the tutor's reply as text chunks.
 * Mock for now: yields a canned reply word by word. The real version will
 * POST to the API and read a server-sent event stream; keep this signature.
 */
export async function* streamTutorReply(
  offering: Offering,
  history: ChatMessage[],
  signal?: AbortSignal,
): AsyncGenerator<string> {
  const question = history.at(-1)?.content ?? ''
  const reply =
    `This is a placeholder reply, because the tutor isn't connected yet.\n\n` +
    `You asked: “${question}”\n\n` +
    `Once the backend is running, I'll answer using ${offering.unit.code} ${offering.unit.title} ` +
    `course material, cite the slides and lecture clips I used, and check your understanding with a quick question.`

  await sleep(400) // "thinking"
  for (const word of reply.split(/(\s+)/)) {
    if (signal?.aborted) return
    yield word
    await sleep(word.trim() ? 25 : 0)
  }
}
