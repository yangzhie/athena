import { useEffect, useState } from 'react'
import { getInsights, type OfferingInsights } from '../../../api/progress'
import { Badge, Card, IntervalBar } from '../../../components/ui'
import { useOffering } from '../useOffering'
import { demoInsights, demoStudents } from './demoData'

export default function InsightsView() {
  const offering = useOffering()
  // Demo units always show hard-coded sample aggregates, whoever is viewing.
  const demo = demoInsights(offering.unit.code)
  const [fetched, setInsights] = useState<OfferingInsights | null>(null)
  const [fetchError, setError] = useState<string | null>(null)
  const insights = demo ?? fetched
  const students = demoStudents(offering.unit.code)
  const error = demo ? null : fetchError
  useEffect(() => {
    let active = true
    if (demoInsights(offering.unit.code)) return
    getInsights(offering.id).then(result => { if (active) setInsights(result) }).catch(e => { if (active) setError(e instanceof Error ? e.message : 'Insights unavailable.') })
    return () => { active = false }
  }, [offering.id, offering.unit.code])
  return <section className="mx-auto w-full max-w-3xl space-y-5 pb-10">
    <h1 className="text-2xl font-semibold">Offering insights</h1>
    <p className="text-sm text-muted">Class-level aggregates for {offering.unit.code}. Private chats, individual answers, notes and cross-unit profiles are excluded.</p>
    {error && <p className="text-bad" role="alert">{error}</p>}
    {!insights && !error && <p>Loading aggregates…</p>}
    {insights && !insights.sufficient_data && <Card title="Not enough contributions yet"><p className="text-sm text-muted">Metrics are suppressed until at least {insights.minimum_environments} independent Environments contribute. No sample data is mixed with real results.</p></Card>}
    {insights?.sample_data && <p className="rounded-lg bg-warn/15 px-3 py-2 text-sm text-warn">Sample data: these aggregates include an invented demo cohort, not real students.</p>}
    {insights?.sufficient_data && <>
      <Card title="Learning activity"><p className="text-sm">{insights.contributing_environments} Environments · {insights.sessions} sessions · {insights.completed_sessions} completed · {insights.practice_reviews} Practice reviews</p><p className="mt-2 text-xs text-muted">{insights.population_label}</p></Card>
      {[...insights.concepts].sort((a, b) => b.difficulty_rate - a.difficulty_rate).map(concept => <Card key={concept.id} title={concept.name}>
        <IntervalBar label="Assessments needing more work" value={concept.difficulty_rate} low={concept.ci_low} high={concept.ci_high} tone="bg-warn" />
        <p className="mt-3 text-sm text-muted">{concept.assessments} decisive assessments · {concept.environments} contributing Environments</p>
      </Card>)}
      <p className="text-xs text-muted">Ranges are 95% confidence intervals. They treat each assessment as independent, so when one Environment answers several times they are somewhat too narrow.</p>
      <Card title="Common knowledge gaps"><ul className="space-y-2 text-sm">{insights.gaps.map(gap => <li key={gap.category}>{gap.category.replaceAll('_', ' ')} · {gap.environments} Environments</li>)}</ul><p className="mt-3 text-xs text-muted">Breakdowns with fewer than five contributing Environments are suppressed.</p></Card>
    </>}
    {students && <section className="space-y-3">
      <h2 className="pt-4 text-lg font-semibold">Individual progress</h2>
      <p className="text-sm text-muted">Only students who opted in to individual insight for {offering.unit.code} appear, under a pseudonym. They can withdraw at any time. You see their per-topic results for this unit only: never their chats, individual answers or other units.</p>
      {students.map(student => {
        const weakest = student.topics.filter(t => t.accuracy !== null).sort((a, b) => a.accuracy! - b.accuracy!)[0]
        return <details key={student.label} className="group rounded-xl border border-line bg-surface p-5">
          <summary className="cursor-pointer list-none space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold">{student.label}</span>
              <span className="flex items-center gap-2 text-xs text-muted">
                <Badge tone="warn">Sample data</Badge>{student.sessions} sessions · active {student.lastActive}
                <span aria-hidden className="transition-transform group-open:rotate-90">›</span>
              </span>
            </div>
            <IntervalBar label="Overall, answered correctly" value={student.overall.accuracy} low={student.overall.ci_low} high={student.overall.ci_high}
              tone={student.overall.accuracy < 0.55 ? 'bg-warn' : 'bg-accent'} />
            {weakest && <p className="text-sm text-muted">Weakest topic: {weakest.name} ({Math.round(weakest.accuracy! * 100)}%, {weakest.assessed} answers)</p>}
          </summary>
          <div className="mt-4 space-y-4 border-t border-line pt-4">
            {student.topics.map(topic => topic.accuracy !== null && topic.ci_low !== null && topic.ci_high !== null
              ? <div key={topic.name}>
                  <IntervalBar label={topic.name} value={topic.accuracy} low={topic.ci_low} high={topic.ci_high} tone={topic.accuracy < 0.55 ? 'bg-warn' : 'bg-accent'} />
                  <p className="mt-1 text-xs text-muted">{topic.assessed} assessed answers</p>
                </div>
              : <p key={topic.name} className="text-sm text-muted">{topic.name}: not assessed yet</p>)}
          </div>
        </details>
      })}
      <p className="text-xs text-muted">Ranges are 95% confidence intervals for each student's share of correct answers. With few answers they are wide, so read them as a guide, not a grade.</p>
    </section>}
  </section>
}
