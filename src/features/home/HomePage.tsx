import { Badge, Button, Card, MasteryBar } from '../../components/ui'

// Temporary preview of the UI primitives. Replaced by the real Home page next step.
export default function HomePage() {
  return (
    <section className="max-w-2xl space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Home</h1>

      <Card title="Buttons">
        <div className="flex flex-wrap gap-2">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button size="sm">Small</Button>
          <Button disabled>Disabled</Button>
        </div>
      </Card>

      <Card title="Badges" action={<Badge tone="accent">New</Badge>}>
        <div className="flex flex-wrap gap-2">
          <Badge>neutral</Badge>
          <Badge tone="accent">accent</Badge>
          <Badge tone="good">mastered</Badge>
          <Badge tone="warn">learning</Badge>
          <Badge tone="bad">gap</Badge>
        </div>
      </Card>

      <Card title="Mastery">
        <div className="space-y-3">
          <MasteryBar label="Bubble sort" value={0.92} />
          <MasteryBar label="Big-O notation" value={0.55} />
          <MasteryBar label="Recursion" value={0.18} />
        </div>
      </Card>
    </section>
  )
}
