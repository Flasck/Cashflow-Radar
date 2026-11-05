'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'

type Toast = { id: number; message: string }
const ToastContext = createContext<((message: string) => void) | null>(null)

function ToastItem({
  toast,
  dismiss,
}: {
  toast: Toast
  dismiss: (id: number) => void
}) {
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [hidden, setHidden] = useState(false)
  const remaining = useRef(6000)
  useEffect(() => {
    const update = () => setHidden(document.hidden)
    update()
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  useEffect(() => {
    if (hovered || focused || hidden) return
    const started = Date.now()
    const timer = window.setTimeout(() => dismiss(toast.id), remaining.current)
    return () => {
      window.clearTimeout(timer)
      remaining.current = Math.max(
        0,
        remaining.current - (Date.now() - started),
      )
    }
  }, [hovered, focused, hidden, dismiss, toast.id])
  return (
    <div
      className='toast'
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={event => {
        if (!event.currentTarget.contains(event.relatedTarget))
          setFocused(false)
      }}
    >
      <span className='toast-icon' aria-hidden='true'>
        ✓
      </span>
      <p role='status' aria-atomic='true'>
        {toast.message}
      </p>
      <button
        className='toast-close'
        type='button'
        aria-label='Закрыть уведомление'
        onClick={() => dismiss(toast.id)}
      >
        ×
      </button>
    </div>
  )
}

export default function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const sequence = useRef(0)
  const dismiss = useCallback(
    (id: number) => setToasts(items => items.filter(item => item.id !== id)),
    [],
  )
  const notify = useCallback((message: string) => {
    const id = ++sequence.current
    setToasts(items =>
      [
        ...items.filter(item => item.message !== message),
        { id, message },
      ].slice(-3),
    )
  }, [])
  return (
    <ToastContext.Provider value={notify}>
      {children}
      <section className='toast-viewport' aria-label='Уведомления'>
        {toasts.map(toast => (
          <ToastItem key={toast.id} toast={toast} dismiss={dismiss} />
        ))}
      </section>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const notify = useContext(ToastContext)
  if (!notify) throw new Error('useToast must be used within ToastProvider')
  return notify
}
