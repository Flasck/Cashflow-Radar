import type { ComponentProps } from 'react'
import Spinner from './Spinner'

export default function Button({
  children,
  pending = false,
  pendingLabel,
  variant = 'primary',
  disabled,
  className = '',
  ...props
}: ComponentProps<'button'> & {
  pending?: boolean
  pendingLabel?: string
  variant?: 'primary' | 'secondary' | 'danger' | 'accent'
}) {
  return (
    <button
      {...props}
      className={`btn btn-${variant} ${className}`}
      disabled={disabled || pending}
      aria-busy={pending || undefined}
    >
      {pending ? <Spinner /> : null}
      {pending && pendingLabel ? pendingLabel : children}
    </button>
  )
}
