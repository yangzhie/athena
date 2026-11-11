import { useRole } from '../app/role'

export default function NoUnits() {
  const role = useRole()
  return (
    <section className="pb-10">
      <h1 className="text-2xl font-semibold tracking-tight">No units yet</h1>
      <p className="mt-2 text-muted">{role === 'lecturer' ? 'Create a study space using the sidebar, upload material, and publish the Offering for students.' : 'Published Offerings will appear here when a lecturer makes them available. You can then start your own private learning sessions.'}</p>
    </section>
  )
}
