import { listTopics } from '../../api/learning'
import { listDueItems } from '../../api/review'

export async function reviewLoader() {
  const [due, topics] = await Promise.all([listDueItems(), listTopics()])
  return {
    due,
    topicTitles: Object.fromEntries(topics.map((t) => [t.id, t.title])),
  }
}
