import type { ComponentProps } from 'react'
import DateInput from './DateInput'

export default function Input({
  className = '',
  ...props
}: ComponentProps<'input'>) {
  if (props.type === 'date')
    return <DateInput {...props} className={className} />
  return <input {...props} className={`form-input ${className}`} />
}
