import { useState, type FormEvent } from 'react'
import type { BankVariant } from '../../../api/srsBank'
import { Button } from '../../../components/ui'

const field = 'w-full rounded-md border border-line bg-surface px-2 py-1.5 text-sm outline-none focus:border-accent'

/** Edit a wording's text and answer. The server validates (e.g. one correct option, distinct options). */
export function VariantEditor({
  variant,
  onSave,
  onCancel,
}: {
  variant: BankVariant
  onSave: (changes: Record<string, unknown>) => Promise<string | null>
  onCancel: () => void
}) {
  const [stem, setStem] = useState(variant.stem)
  const [explanation, setExplanation] = useState(variant.explanation)
  const [options, setOptions] = useState(variant.kind === 'mcq' ? variant.options : [])
  const [answerIndex, setAnswerIndex] = useState(variant.kind === 'mcq' ? variant.answer_index : 0)
  const [answer, setAnswer] = useState(variant.kind === 'numeric' ? String(variant.answer) : '')
  const [modelAnswer, setModelAnswer] = useState(variant.kind === 'short' ? variant.model_answer : '')
  const [rubric, setRubric] = useState(variant.kind === 'short' ? variant.rubric.join('\n') : '')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const changes: Record<string, unknown> = { stem: stem.trim(), explanation: explanation.trim() }
    if (variant.kind === 'mcq') Object.assign(changes, { options: options.map((o) => o.trim()), answer_index: answerIndex })
    if (variant.kind === 'numeric') {
      if (Number.isNaN(Number(answer))) return setError('The answer must be a number.')
      changes.answer = Number(answer)
    }
    if (variant.kind === 'short') {
      Object.assign(changes, { model_answer: modelAnswer.trim(), rubric: rubric.split('\n').map((r) => r.trim()).filter(Boolean) })
    }
    setSaving(true)
    setError(await onSave(changes))
    setSaving(false)
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="space-y-3">
      <label className="block text-xs text-muted">
        Question
        <textarea value={stem} onChange={(e) => setStem(e.target.value)} rows={2} className={`${field} mt-1`} />
      </label>

      {variant.kind === 'mcq' && (
        <fieldset className="space-y-1.5">
          <legend className="text-xs text-muted">Options (select the correct one)</legend>
          {options.map((o, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="radio"
                name={`correct-${variant.id}`}
                checked={answerIndex === i}
                onChange={() => setAnswerIndex(i)}
                aria-label={`Option ${i + 1} is correct`}
              />
              <input
                value={o}
                onChange={(e) => setOptions(options.map((x, j) => (j === i ? e.target.value : x)))}
                aria-label={`Option ${i + 1}`}
                className={field}
              />
            </div>
          ))}
        </fieldset>
      )}
      {variant.kind === 'numeric' && (
        <label className="block text-xs text-muted">
          Answer
          <input value={answer} onChange={(e) => setAnswer(e.target.value)} inputMode="decimal" className={`${field} mt-1 max-w-40`} />
        </label>
      )}
      {variant.kind === 'short' && (
        <>
          <label className="block text-xs text-muted">
            Model answer
            <textarea value={modelAnswer} onChange={(e) => setModelAnswer(e.target.value)} rows={2} className={`${field} mt-1`} />
          </label>
          <label className="block text-xs text-muted">
            Rubric (one point per line)
            <textarea value={rubric} onChange={(e) => setRubric(e.target.value)} rows={2} className={`${field} mt-1`} />
          </label>
        </>
      )}

      <label className="block text-xs text-muted">
        Explanation (shown after answering)
        <textarea value={explanation} onChange={(e) => setExplanation(e.target.value)} rows={2} className={`${field} mt-1`} />
      </label>

      {error && (
        <p className="text-sm text-bad" role="alert">
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
        <Button variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  )
}
