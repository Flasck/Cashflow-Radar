'use client'

import { useEffect, useRef, useState, type ComponentProps } from 'react'
import Input from './Input'

export default function PasswordInput({
  className = '',
  ...props
}: Omit<ComponentProps<'input'>, 'type'>) {
  const [visible, setVisible] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const [filled, setFilled] = useState(
    Boolean(props.value ?? props.defaultValue),
  )
  const hasValue =
    props.value === undefined ? filled : String(props.value).length > 0
  useEffect(() => {
    if (props.value !== undefined && String(props.value).length === 0)
      setVisible(false)
  }, [props.value])
  useEffect(() => {
    const element = input.current
    if (!element) return
    const sync = () => {
      setFilled(element.value.length > 0)
      if (!element.value) setVisible(false)
    }
    sync()
    const reset = () => {
      setVisible(false)
      requestAnimationFrame(sync)
    }
    const form = element.form
    form?.addEventListener('reset', reset)
    return () => form?.removeEventListener('reset', reset)
  }, [])
  return (
    <div className='password-field'>
      <Input
        {...props}
        ref={input}
        type={visible && hasValue ? 'text' : 'password'}
        className={className}
        onChange={event => {
          setFilled(event.target.value.length > 0)
          if (!event.target.value) setVisible(false)
          props.onChange?.(event)
        }}
        onFocus={event => {
          setFilled(event.target.value.length > 0)
          props.onFocus?.(event)
        }}
        onInput={event => {
          setFilled(event.currentTarget.value.length > 0)
          props.onInput?.(event)
        }}
        onAnimationStart={event => {
          if (event.animationName === 'input-autofill')
            setFilled(event.currentTarget.value.length > 0)
          props.onAnimationStart?.(event)
        }}
      />
      {hasValue && (
        <button
          className='password-toggle'
          type='button'
          aria-label={visible ? 'Скрыть пароль' : 'Показать пароль'}
          aria-controls={props.id}
          aria-pressed={visible}
          disabled={props.disabled}
          onClick={() => setVisible(value => !value)}
        >
          <svg
            width='20'
            height='20'
            viewBox='0 0 24 24'
            fill='none'
            stroke='currentColor'
            strokeWidth='1.6'
            strokeLinecap='round'
            strokeLinejoin='round'
            aria-hidden='true'
          >
            <path d='M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z' />
            <circle cx='12' cy='12' r='3' />
            {visible ? <path d='m3 3 18 18' /> : null}
          </svg>
        </button>
      )}
    </div>
  )
}
