import { Link } from 'react-router'

export default function NotFound() {
  return (
    <section>
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <Link to="/" className="mt-2 inline-block text-accent hover:underline">
        Back to Home
      </Link>
    </section>
  )
}
