import { useState } from 'react'
import { Link, useLoaderData } from 'react-router'
import { Card, MasteryBar } from '../../components/ui'
import type { ChatMessage } from '../../types'
import { MessageBubble } from './components/MessageBubble'
import { QuestionCard } from '../../components/quiz'
import { ReplyBox } from './components/ReplyBox'
import type { learnSessionLoader } from './loader'

type SessionData = Extract<Awaited<ReturnType<typeof learnSessionLoader>>, { topic: object }>

export default function LearnPage() {
  const data = useLoaderData<typeof learnSessionLoader>()

  if (!data.topic) {
    return (
      <div className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight">Topic not found</h1>
        <Link to="/learn" className="mt-2 inline-block text-accent hover:underline">
          Pick another topic
        </Link>
      </div>
    )
  }

  // Keyed so local state resets when switching topics (the route component is reused).
  return <LearnSession key={data.topic.id} data={data as SessionData} />
}

function LearnSession({ data }: { data: SessionData }) {
  // Replies are kept locally until the tutor API exists.
  const [sent, setSent] = useState<ChatMessage[]>([])
  const { topic, concepts, question, materialTitles } = data
  const messages = [...data.messages, ...sent]

  return (
    <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[1fr_18rem]">
      <section className="flex min-w-0 flex-col gap-4">
        <header>
          <p className="text-sm text-muted">Learning</p>
          <h1 className="text-2xl font-semibold tracking-tight">{topic.title}</h1>
        </header>

        {messages.length === 0 && (
          <MessageBubble
            materialTitles={materialTitles}
            message={{
              id: 'intro',
              role: 'tutor',
              content: `Let's see what you already know about ${topic.title}. Try this one.`,
              createdAt: '',
            }}
          />
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} materialTitles={materialTitles} />
        ))}

        {question && <QuestionCard key={question.id} item={question} allowRetry />}

        <ReplyBox
          onSend={(text) =>
            setSent((prev) => [
              ...prev,
              { id: `local-${prev.length}`, role: 'learner', content: text, createdAt: new Date().toISOString() },
            ])
          }
        />
      </section>

      <aside>
        <Card title="Concepts in this topic">
          <div className="space-y-3">
            {concepts.map((c) => (
              <MasteryBar key={c.id} label={c.name} value={c.mastery} />
            ))}
          </div>
        </Card>
      </aside>
    </div>
  )
}
