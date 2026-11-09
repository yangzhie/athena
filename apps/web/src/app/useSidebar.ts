import { useCallback, useEffect, useState } from 'react'
import { readStored, writeStored } from '../lib/storage'
import { useMediaQuery } from '../lib/useMediaQuery'

const KEY = 'athena.sidebarOpen'

/**
 * Desktop: the sidebar is docked and its open/closed choice is remembered.
 * Phone: it's a drawer over the page, closed by default, closed again after navigating.
 */
export function useSidebar() {
  const isDesktop = useMediaQuery('(min-width: 48rem)')
  const [desktopOpen, setDesktopOpen] = useState(() => readStored(KEY) !== 'false')
  const [mobileOpen, setMobileOpen] = useState(false)
  const open = isDesktop ? desktopOpen : mobileOpen

  const toggle = useCallback(() => {
    if (isDesktop) {
      setDesktopOpen((o) => {
        writeStored(KEY, String(!o))
        return !o
      })
    } else {
      setMobileOpen((o) => !o)
    }
  }, [isDesktop])

  const closeDrawer = useCallback(() => setMobileOpen(false), [])

  // Esc closes the phone drawer.
  useEffect(() => {
    if (isDesktop || !mobileOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setMobileOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isDesktop, mobileOpen])

  return { open, isDesktop, toggle, closeDrawer }
}
