import { Link } from 'react-router'
import { UnitChat } from './chat/UnitChat'
import { UnitHeader } from './UnitHeader'
import { useOffering } from './useOffering'

export default function ChatView() {
  const offering = useOffering()

  return (
    <div className="flex flex-1 flex-col">
      <div className="mx-auto flex w-full max-w-3xl items-end justify-between gap-4">
        <UnitHeader offering={offering} />
        <Link to={`/units/${offering.id}/playground`} className="shrink-0 text-sm text-accent hover:underline">
          🧪 Playground
        </Link>
      </div>
      <UnitChat key={offering.id} offering={offering} />
    </div>
  )
}
