import type { ReactNode } from 'react'

export default function Notice({
  children,
  variant = 'error',
}: {
  children: ReactNode
  variant?: 'error' | 'warning' | 'info'
}) {
  return (
    <div
      className={`notice notice-${variant}`}
      role={variant === 'error' ? 'alert' : 'status'}
    >
      {children}
    </div>
  )
}
