export default function Placeholder({ title }: { title: string }) {
  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 text-muted">Coming soon.</p>
    </section>
  )
}
