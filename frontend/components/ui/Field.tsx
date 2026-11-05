import type { ReactNode } from 'react'

export default function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string
  label: string
  hint?: ReactNode
  error?: string
  children: ReactNode
}) {
  return (
    <div className='form-group'>
      <label className='form-label' htmlFor={id}>
        {label}
      </label>
      {children}
      {error ? (
        <span id={`${id}-error`} className='form-error' role='alert'>
          {error}
        </span>
      ) : null}
      {hint ? (
        <span id={`${id}-hint`} className='form-hint'>
          {hint}
        </span>
      ) : null}
    </div>
  )
}
