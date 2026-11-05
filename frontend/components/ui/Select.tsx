'use client'

import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentProps,
  type KeyboardEvent,
} from 'react'

type Option = { value: string; label: string; disabled: boolean; group: string }
type SelectProps = Omit<ComponentProps<'select'>, 'multiple' | 'size' | 'ref'>

export default function Select({
  className = '',
  style,
  children,
  onChange,
  onFocus,
  onInvalid,
  ...props
}: SelectProps) {
  const native = useRef<HTMLSelectElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const menu = useRef<HTMLDivElement>(null)
  const root = useRef<HTMLDivElement>(null)
  const listId = useId()
  const search = useRef({ text: '', time: 0 })
  const [enhanced, setEnhanced] = useState(false)
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState<Option[]>([])
  const [selected, setSelected] = useState('')
  const [label, setLabel] = useState('')
  const [active, setActive] = useState(-1)

  useEffect(() => {
    const element = native.current
    if (!element || !('showPopover' in HTMLElement.prototype)) return
    const sync = () => {
      setOptions(
        Array.from(element.options, option => ({
          value: option.value,
          label: option.label,
          disabled:
            option.disabled ||
            (option.parentElement instanceof HTMLOptGroupElement &&
              option.parentElement.disabled),
          group:
            option.parentElement instanceof HTMLOptGroupElement
              ? option.parentElement.label
              : '',
        })),
      )
      setSelected(element.value)
      setLabel(
        Array.from(
          element.labels ?? [],
          item => item.textContent?.trim() ?? '',
        ).join(' '),
      )
    }
    sync()
    setEnhanced(true)
    const reset = () => {
      requestAnimationFrame(sync)
      setOpen(false)
    }
    const form = element.form
    form?.addEventListener('reset', reset)
    return () => form?.removeEventListener('reset', reset)
  }, [children, props.value, props.defaultValue])

  useLayoutEffect(() => {
    if (!open || props.disabled) return
    const popup = menu.current
    const button = trigger.current
    if (!popup || !button) return
    const position = () => {
      const rect = button.getBoundingClientRect()
      const below = window.innerHeight - rect.bottom - 12
      const above = rect.top - 12
      const upwards = below < 200 && above > below
      const height = Math.max(80, Math.min(288, upwards ? above : below))
      const width = Math.min(Math.max(rect.width, 220), window.innerWidth - 24)
      popup.style.width = `${width}px`
      popup.style.maxHeight = `${height}px`
      popup.style.left = `${Math.max(12, Math.min(rect.left, window.innerWidth - width - 12))}px`
      popup.style.top = upwards ? 'auto' : `${rect.bottom + 6}px`
      popup.style.bottom = upwards
        ? `${window.innerHeight - rect.top + 6}px`
        : 'auto'
      popup.dataset.side = upwards ? 'top' : 'bottom'
    }
    position()
    popup.showPopover()
    const dismiss = (event: Event) => {
      if (event.target instanceof Node && !root.current?.contains(event.target))
        setOpen(false)
    }
    const scroll = (event: Event) => {
      if (event.target !== popup) position()
    }
    document.addEventListener('pointerdown', dismiss)
    document.addEventListener('focusin', dismiss)
    window.addEventListener('resize', position)
    document.addEventListener('scroll', scroll, true)
    return () => {
      popup.hidePopover()
      document.removeEventListener('pointerdown', dismiss)
      document.removeEventListener('focusin', dismiss)
      window.removeEventListener('resize', position)
      document.removeEventListener('scroll', scroll, true)
    }
  }, [open, props.disabled])

  useEffect(() => {
    if (open)
      menu.current
        ?.querySelector(`[data-index="${active}"]`)
        ?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  const currentValue =
    props.value === undefined ? selected : String(props.value)
  const current = options.find(option => option.value === currentValue)
  const expanded = open && !props.disabled

  function show(edge?: 'first' | 'last') {
    const index = options.findIndex(
      option => option.value === currentValue && !option.disabled,
    )
    setActive(
      edge === 'last'
        ? options.findLastIndex(option => !option.disabled)
        : edge === 'first' || index < 0
          ? options.findIndex(option => !option.disabled)
          : index,
    )
    search.current = { text: '', time: 0 }
    setOpen(true)
  }

  function choose(index: number) {
    const option = options[index]
    const element = native.current
    if (!option || option.disabled || !element) return
    element.value = option.value
    setSelected(option.value)
    element.dispatchEvent(new Event('change', { bubbles: true }))
    setOpen(false)
    trigger.current?.focus()
  }

  function keyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const enabled = options.flatMap((option, index) =>
      option.disabled ? [] : [index],
    )
    if (event.key === 'Tab') {
      setOpen(false)
      return
    }
    if (event.key === 'Escape' && open) {
      event.preventDefault()
      event.stopPropagation()
      setOpen(false)
      return
    }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault()
      if (!open) {
        show(
          event.key === 'End'
            ? 'last'
            : event.key === 'Home'
              ? 'first'
              : undefined,
        )
        return
      }
      const position = enabled.indexOf(active)
      const next =
        event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? enabled.length - 1
            : Math.max(
                0,
                Math.min(
                  enabled.length - 1,
                  position + (event.key === 'ArrowDown' ? 1 : -1),
                ),
              )
      setActive(enabled[next] ?? -1)
    } else if (
      event.key === 'Enter' ||
      (event.key === ' ' && !search.current.text)
    ) {
      event.preventDefault()
      if (open) choose(active)
      else show()
    } else if (
      event.key.length === 1 &&
      !event.ctrlKey &&
      !event.metaKey &&
      !event.altKey
    ) {
      event.preventDefault()
      const now = Date.now()
      const text =
        (now - search.current.time < 700 ? search.current.text : '') +
        event.key.toLocaleLowerCase('ru')
      search.current = { text, time: now }
      const start = open ? active + 1 : 0
      const ordered = [
        ...enabled.filter(index => index >= start),
        ...enabled.filter(index => index < start),
      ]
      const index = ordered.find(index =>
        options[index].label.toLocaleLowerCase('ru').startsWith(text),
      )
      setOpen(true)
      if (index !== undefined) setActive(index)
    }
  }

  return (
    <div
      className={`select-field ${enhanced ? 'select-enhanced' : ''}`}
      ref={root}
    >
      <select
        {...props}
        ref={native}
        style={style}
        className={`form-select ${className}`}
        tabIndex={enhanced ? -1 : props.tabIndex}
        aria-hidden={enhanced ? true : undefined}
        onChange={event => {
          setSelected(event.target.value)
          onChange?.(event)
        }}
        onFocus={event => {
          if (enhanced) trigger.current?.focus()
          onFocus?.(event)
        }}
        onInvalid={event => {
          onInvalid?.(event)
          if (enhanced) {
            event.preventDefault()
            trigger.current?.focus()
            show()
          }
        }}
      >
        {children}
      </select>
      {enhanced && (
        <>
          <button
            ref={trigger}
            type='button'
            role='combobox'
            className={`form-select select-trigger ${className}`}
            style={style}
            disabled={props.disabled}
            tabIndex={props.tabIndex}
            aria-label={props['aria-label'] ?? label}
            aria-labelledby={props['aria-labelledby']}
            aria-describedby={props['aria-describedby']}
            aria-invalid={props['aria-invalid']}
            aria-required={props.required}
            aria-expanded={expanded}
            aria-controls={expanded ? listId : undefined}
            aria-haspopup='listbox'
            aria-activedescendant={
              expanded && active >= 0 ? `${listId}-${active}` : undefined
            }
            onClick={() => {
              search.current = { text: '', time: 0 }
              if (open) setOpen(false)
              else show()
            }}
            onKeyDown={keyDown}
          >
            <span className='select-value'>{current?.label ?? ''}</span>
            <svg
              className='select-chevron'
              width='18'
              height='18'
              viewBox='0 0 24 24'
              fill='none'
              stroke='currentColor'
              strokeWidth='1.7'
              aria-hidden='true'
            >
              <path d='m7 10 5 5 5-5' />
            </svg>
          </button>
          {expanded && (
            <div
              ref={menu}
              id={listId}
              role='listbox'
              aria-label={props['aria-label'] ?? label}
              aria-labelledby={props['aria-labelledby']}
              className='select-menu'
              popover='manual'
            >
              {options.map((option, index) => (
                <div key={`${option.value}-${index}`}>
                  {option.group &&
                    option.group !== options[index - 1]?.group && (
                      <div className='select-group'>{option.group}</div>
                    )}
                  <div
                    id={`${listId}-${index}`}
                    role='option'
                    aria-selected={option.value === currentValue}
                    aria-disabled={option.disabled || undefined}
                    data-index={index}
                    data-active={index === active}
                    className='select-option'
                    onPointerMove={() => {
                      if (!option.disabled) setActive(index)
                    }}
                    onPointerDown={event => event.preventDefault()}
                    onClick={() => choose(index)}
                  >
                    <span>{option.label}</span>
                    {option.value === currentValue && (
                      <svg
                        width='16'
                        height='16'
                        viewBox='0 0 24 24'
                        fill='none'
                        stroke='currentColor'
                        strokeWidth='2'
                        aria-hidden='true'
                      >
                        <path d='m5 12 4 4L19 6' />
                      </svg>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
