import { UnitChat } from './chat/UnitChat'
import { UnitHeader } from './UnitHeader'
import { useOffering } from './useOffering'

export default function ChatView() {
  const offering = useOffering()

  return (
    <div className="flex flex-1 flex-col">
      <div className="mx-auto w-full max-w-3xl">
        <UnitHeader offering={offering} />
      </div>
      <UnitChat key={offering.id} offering={offering} />
    </div>
  )
}
