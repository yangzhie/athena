import { UnitChat } from './chat/UnitChat'
import { SandboxPanel } from './sandbox/SandboxPanel'
import { UnitHeader } from './UnitHeader'
import { useOffering } from './useOffering'

export default function ChatView() {
  const offering = useOffering()

  return (
    // Chat on the left, sandbox on the right (1280px and wider for now).
    <div className="flex flex-1 gap-8">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mx-auto w-full max-w-3xl">
          <UnitHeader offering={offering} />
        </div>
        <UnitChat key={offering.id} offering={offering} />
      </div>

      {/* Stays in view while the chat scrolls; sits below the top bar when it's shown. */}
      <aside className="hidden w-[24rem] shrink-0 xl:sticky xl:top-[calc(var(--topbar-h)+1.5rem)] xl:block xl:h-[calc(100svh-var(--topbar-h)-3rem)] 2xl:w-[28rem]">
        <SandboxPanel key={offering.id} />
      </aside>
    </div>
  )
}
