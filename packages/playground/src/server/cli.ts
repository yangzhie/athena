// One bounded JSON request per process. stdout is protocol only; no private logging.
import { transition } from './adapter'
import { contract } from './contract'
declare const process: { stdin: AsyncIterable<Uint8Array>; stdout: { write(s: string): void }; exitCode: number }
let input = ''
try {
  const decoder = new TextDecoder()
  for await (const chunk of process.stdin) {
    input += decoder.decode(chunk, { stream: true })
    if (input.length > 2 * 1024 * 1024) throw new Error('Playground request too large')
  }
  const body = JSON.parse(input)
  const result = body.kind === 'contract' ? contract() : await transition(body.checkpoint ?? null, body.command)
  process.stdout.write(JSON.stringify({ ok: true, data: result }))
} catch (e) {
  process.stdout.write(JSON.stringify({ ok: false, error: e instanceof Error ? e.message : 'Invalid Playground request' }))
}
