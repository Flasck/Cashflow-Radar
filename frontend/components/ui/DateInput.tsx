'use client'

import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentProps,
} from 'react'
import { boundDate, monthDays, shiftDate, shiftMonth } from '@/lib/calendar'
import Select from './Select'

type DateInputProps = Omit<ComponentProps<'input'>, 'ref'>
const monthFormat = new Intl.DateTimeFormat('ru-RU', {
  month: 'long',
  timeZone: 'UTC',
})
const dayFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})
const months = Array.from({ length: 12 }, (_, index) =>
  monthFormat.format(new Date(Date.UTC(2026, index, 1))),
)
const todayMoscow = () =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Moscow',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())

export default function DateInput({
  className = '',
  onChange,
  onClick,
  onKeyDown,
  ...props
}: DateInputProps) {
  const native = useRef<HTMLInputElement>(null)
  const popup = useRef<HTMLDivElement>(null)
  const root = useRef<HTMLDivElement>(null)
  const [enhanced, setEnhanced] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState('2026-01-01')
  const [today, setToday] = useState('')
  const id = useId()
  const min = typeof props.min === 'string' ? props.min : undefined
  const max = typeof props.max === 'string' ? props.max : undefined
  const disabled = (date: string) =>
    !!((min && date < min) || (max && date > max))

  useEffect(() => {
    setEnhanced('showPopover' in HTMLElement.prototype)
    const form = native.current?.form
    const reset = () => setOpen(false)
    form?.addEventListener('reset', reset)
    return () => form?.removeEventListener('reset', reset)
  }, [])

  useLayoutEffect(() => {
    const element = popup.current
    if (!open || props.disabled || !element) return
    const position = () => {
      const rect = native.current!.getBoundingClientRect()
      const width = Math.min(304, window.innerWidth - 24)
      element.style.width = `${width}px`
      element.style.left = `${Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))}px`
      const above =
        window.innerHeight - rect.bottom < 370 &&
        rect.top > window.innerHeight - rect.bottom
      element.style.top = above ? 'auto' : `${rect.bottom + 6}px`
      element.style.bottom = above
        ? `${window.innerHeight - rect.top + 6}px`
        : 'auto'
      element.style.maxHeight = `${Math.max(180, (above ? rect.top : window.innerHeight - rect.bottom) - 18)}px`
    }
    position()
    element.showPopover()
    const dismiss = (event: Event) => {
      if (event.target instanceof Node && !root.current?.contains(event.target))
        setOpen(false)
    }
    window.addEventListener('resize', position)
    document.addEventListener('scroll', position, true)
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('focusin', dismiss)
    return () => {
      element.hidePopover()
      window.removeEventListener('resize', position)
      document.removeEventListener('scroll', position, true)
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('focusin', dismiss)
    }
  }, [open, props.disabled])

  useEffect(() => {
    if (open)
      popup.current
        ?.querySelector<HTMLButtonElement>(`[data-date="${active}"]`)
        ?.focus({ preventScroll: true })
  }, [open, active])

  function show() {
    if (props.disabled || props.readOnly) return
    const today = todayMoscow()
    setToday(today)
    setActive(boundDate(native.current?.value || today, min, max))
    setOpen(true)
  }

  function choose(value: string) {
    const element = native.current
    if (!element || (value && disabled(value))) return
    Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      'value',
    )?.set?.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
    setOpen(false)
    element.focus()
  }

  const year = Number(active.slice(0, 4))
  const month = Number(active.slice(5, 7)) - 1
  const firstYear = min ? Number(min.slice(0, 4)) : Math.min(1900, year)
  const lastYear = max ? Number(max.slice(0, 4)) : Math.max(2100, year)

  return (
    <div className={`date-field ${enhanced ? 'date-enhanced' : ''}`} ref={root}>
      <input
        {...props}
        type='date'
        ref={native}
        className={`form-input ${className}`}
        onChange={onChange}
        aria-controls={open ? id : undefined}
        aria-haspopup={enhanced ? 'dialog' : undefined}
        onClick={event => {
          onClick?.(event)
          if (enhanced && !event.defaultPrevented) {
            event.preventDefault()
            show()
          }
        }}
        onKeyDown={event => {
          onKeyDown?.(event)
          if (
            enhanced &&
            !event.defaultPrevented &&
            event.key === 'ArrowDown' &&
            event.altKey
          ) {
            event.preventDefault()
            show()
          }
        }}
      />
      {enhanced && (
        <button
          type='button'
          className='date-toggle'
          disabled={props.disabled || props.readOnly}
          aria-label='Открыть календарь'
          aria-expanded={open}
          aria-controls={open ? id : undefined}
          onClick={() => (open ? setOpen(false) : show())}
        >
          <svg
            width='18'
            height='18'
            viewBox='0 0 24 24'
            fill='none'
            stroke='currentColor'
            strokeWidth='1.6'
            aria-hidden='true'
          >
            <rect x='3' y='5' width='18' height='16' rx='3' />
            <path d='M16 3v4M8 3v4M3 11h18m-13 4h2m4 0h2' />
          </svg>
        </button>
      )}
      {open && !props.disabled && (
        <div
          ref={popup}
          id={id}
          popover='manual'
          role='dialog'
          aria-label='Выбор даты'
          className='date-calendar'
          onKeyDown={event => {
            if (event.key === 'Escape') {
              event.preventDefault()
              event.stopPropagation()
              setOpen(false)
              native.current?.focus()
              return
            }
            if (
              !(event.target instanceof HTMLElement) ||
              !event.target.dataset.date
            )
              return
            let next: string | undefined
            const weekday =
              (new Date(`${active}T00:00:00Z`).getUTCDay() + 6) % 7
            if (event.key === 'ArrowLeft') next = shiftDate(active, -1)
            if (event.key === 'ArrowRight') next = shiftDate(active, 1)
            if (event.key === 'ArrowUp') next = shiftDate(active, -7)
            if (event.key === 'ArrowDown') next = shiftDate(active, 7)
            if (event.key === 'Home') next = shiftDate(active, -weekday)
            if (event.key === 'End') next = shiftDate(active, 6 - weekday)
            if (event.key === 'PageUp')
              next = shiftMonth(active, event.shiftKey ? -12 : -1)
            if (event.key === 'PageDown')
              next = shiftMonth(active, event.shiftKey ? 12 : 1)
            if (next) {
              event.preventDefault()
              setActive(boundDate(next, min, max))
            }
          }}
        >
          <div className='calendar-heading'>
            <button
              type='button'
              className='calendar-arrow'
              aria-label='Предыдущий месяц'
              disabled={!!min && active.slice(0, 7) <= min.slice(0, 7)}
              onClick={() =>
                setActive(boundDate(shiftMonth(active, -1), min, max))
              }
            >
              ‹
            </button>
            <Select
              aria-label='Месяц'
              value={String(month)}
              onChange={event =>
                setActive(
                  boundDate(
                    shiftMonth(active, Number(event.target.value) - month),
                    min,
                    max,
                  ),
                )
              }
            >
              {months.map((name, index) => (
                <option key={name} value={index}>
                  {name}
                </option>
              ))}
            </Select>
            <Select
              aria-label='Год'
              value={String(year)}
              onChange={event =>
                setActive(
                  boundDate(
                    shiftMonth(
                      active,
                      (Number(event.target.value) - year) * 12,
                    ),
                    min,
                    max,
                  ),
                )
              }
            >
              {Array.from({ length: lastYear - firstYear + 1 }, (_, index) => (
                <option key={firstYear + index} value={firstYear + index}>
                  {firstYear + index}
                </option>
              ))}
            </Select>
            <button
              type='button'
              className='calendar-arrow'
              aria-label='Следующий месяц'
              disabled={!!max && active.slice(0, 7) >= max.slice(0, 7)}
              onClick={() =>
                setActive(boundDate(shiftMonth(active, 1), min, max))
              }
            >
              ›
            </button>
          </div>
          <div className='calendar-weekdays' aria-hidden='true'>
            {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map(day => (
              <span key={day}>{day}</span>
            ))}
          </div>
          <div
            className='calendar-days'
            role='group'
            aria-label={`${months[month]} ${year}`}
          >
            {monthDays(active).map(date => (
              <button
                key={date}
                type='button'
                data-date={date}
                data-outside={date.slice(0, 7) !== active.slice(0, 7)}
                data-today={date === today}
                aria-label={dayFormat.format(new Date(`${date}T00:00:00Z`))}
                aria-pressed={date === (props.value ?? native.current?.value)}
                disabled={disabled(date)}
                tabIndex={date === active ? 0 : -1}
                onClick={() => choose(date)}
              >
                {Number(date.slice(8))}
              </button>
            ))}
          </div>
          <div className='calendar-footer'>
            <button
              type='button'
              className='text-button'
              disabled={disabled(today)}
              onClick={() => choose(today)}
            >
              Сегодня
            </button>
            {!props.required && (
              <button
                type='button'
                className='text-button'
                onClick={() => choose('')}
              >
                Очистить
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
