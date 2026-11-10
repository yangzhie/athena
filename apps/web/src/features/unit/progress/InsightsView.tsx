import { useEffect, useState } from 'react'
import { getInsights, type OfferingInsights } from '../../../api/progress'
import { Card } from '../../../components/ui'
import { useOffering } from '../useOffering'

export default function InsightsView() {
  const offering = useOffering()
  const [insights, setInsights] = useState<OfferingInsights | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    getInsights(offering.id).then(result => { if (active) setInsights(result) }).catch(e => { if (active) setError(e instanceof Error ? e.message : 'Insights unavailable.') })
    return () => { active = false }
  }, [offering.id])
  return <section className="mx-auto w-full max-w-3xl space-y-5 pb-10">
    <h1 className="text-2xl font-semibold">Offering insights</h1>
    <p className="text-sm text-muted">Class-level aggregates for {offering.unit.code}. Private chats, individual answers, notes and cross-unit profiles are excluded.</p>
    {error && <p className="text-bad" role="alert">{error}</p>}
    {!insights && !error && <p>Loading aggregates…</p>}
    {insights && !insights.sufficient_data && <Card title="Not enough contributions yet"><p className="text-sm text-muted">Metrics are suppressed until at least {insights.minimum_environments} independent Environments contribute. No sample data is mixed with real results.</p></Card>}
    {insights?.sufficient_data && <>
      <Card title="Learning activity"><p className="text-sm">{insights.contributing_environments} Environments · {insights.sessions} sessions · {insights.completed_sessions} completed · {insights.practice_reviews} Practice reviews</p><p className="mt-2 text-xs text-muted">{insights.population_label}</p></Card>
      {insights.concepts.map(concept => <Card key={concept.id} title={concept.name}><p className="text-sm">{Math.round(concept.difficulty_rate * 100)}% of decisive assessments need more work · {concept.environments} contributing Environments</p></Card>)}
      <Card title="Common knowledge gaps"><ul className="space-y-2 text-sm">{insights.gaps.map(gap => <li key={gap.category}>{gap.category.replaceAll('_', ' ')} · {gap.environments} Environments</li>)}</ul><p className="mt-3 text-xs text-muted">Breakdowns with fewer than five contributing Environments are suppressed.</p></Card>
    </>}
  </section>
}
