import { Link, useMatch } from 'react-router'
import type { SidebarActionProps } from '../../app/feature'
import { buttonStyles } from '../../components/ui'

/** Bottom-left switch between the open unit's chat and its lecture clips. Hidden when no unit is open. */
export function ClipsToggle({ onNavigate }: SidebarActionProps) {
  const unit = useMatch('/units/:offeringId/*')
  const id = unit?.params.offeringId
  if (!id) return null

  const onClips = unit.params['*'] === 'clips'
  return (
    <Link
      to={onClips ? `/units/${id}` : `/units/${id}/clips`}
      onClick={onNavigate}
      className={buttonStyles('ghost', 'sm', 'w-full justify-start')}
    >
      <span aria-hidden>{onClips ? '💬' : '🎬'}</span>
      {onClips ? 'Back to chat' : 'Lecture clips'}
    </Link>
  )
}
