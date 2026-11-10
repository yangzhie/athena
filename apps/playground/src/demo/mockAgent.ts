import { TutorRunner, type ObjectId, type Playground } from '@athena/playground'
import { demoScenes, mockAsk, prepareScene } from '@athena/playground/fixtures'

export interface ChatMessage {
  id: number
  role: 'student' | 'agent'
  text: string
  /** Tool calls the agent made for this turn, shown under the message. */
  tools?: string[]
  /** Where the reply came from: written with the scene, or asked of the model now. */
  origin?: 'prepared' | 'model'
  about?: string
}

export interface QuickReply {
  label: string
  text: string
}

type Post = (msg: Omit<ChatMessage, 'id'>) => void

/**
 * The demo's tutor: the shared `TutorRunner` plus mock stand-ins for the model
 * (picking a prepared scene for a prompt, answering free questions).
 */
export class MockAgent {
  private runner: TutorRunner
  private post: Post

  constructor(pg: Playground, post: Post, onBusy: (busy: boolean) => void) {
    this.post = post
    this.runner = new TutorRunner(pg, { post: (m) => post({ role: 'agent', ...m }), busy: onBusy, ask: mockAsk })
  }

  start() {
    return this.runner.start()
  }

  /** Quick replies that make sense for the current canvas. */
  suggestions(): QuickReply[] {
    const scene = this.runner.scene
    const others = demoScenes.filter((d) => d.scene.id !== scene?.id).map((d) => d.prompt)
    return scene?.showMe ? [{ label: 'Show me how', text: 'Can you show me the right way?' }, ...others] : others
  }

  /** A chat message from the student. `about` is the selected object, if any. */
  send(text: string, about: ObjectId | null) {
    const scene = prepareScene(text, this.runner.scene?.id)
    if (scene) {
      void this.runner.open(scene).then((r) => {
        if (!r.ok) this.post({ role: 'agent', origin: 'model', text: `The scene didn't validate, so it would go back to the model to fix:\n${r.error}` })
      })
      return
    }
    if (/show me|demonstrat|right way|演示/i.test(text) && this.runner.showMe()) return
    this.runner.ask(about, text)
  }
}
