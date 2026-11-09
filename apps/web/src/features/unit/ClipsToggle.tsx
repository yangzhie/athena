import { Link, useMatch } from 'react-router'
import type { SidebarActionProps } from '../../app/feature'
import { useRole } from '../../app/role'
import { buttonStyles } from '../../components/ui'

/**
 * Bottom-left switch between the open unit's chat and its lecture clips
 * (students) or the clip review screen (lecturers). Hidden when no unit is open.
 */
export function ClipsToggle({ onNavigate }: SidebarActionProps) {
  const role = useRole()
  const unit = useMatch('/units/:offeringId/*')
  const id = unit?.params.offeringId
  if (!id) return null

  const view = unit.params['*']
  const onClips = view === 'clips' || view === 'review'
  const target = role === 'lecturer' ? 'review' : 'clips'
  return (
    <Link
      to={onClips ? `/units/${id}` : `/units/${id}/${target}`}
      onClick={onNavigate}
      className={buttonStyles('ghost', 'sm', 'w-full justify-start')}
    >
      <span aria-hidden>{onClips ? '💬' : '🎬'}</span>
      {onClips ? 'Back to chat' : role === 'lecturer' ? 'Review clips' : 'Lecture clips'}
    </Link>
  )
}
