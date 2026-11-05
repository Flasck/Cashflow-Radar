'use client'

import { useEffect, useId, useRef } from 'react'

export default function Modal({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    const element = dialog.current
    element?.showModal()
    return () => element?.close()
  }, [])

  return (
    <dialog
      ref={dialog}
      className='modal'
      aria-labelledby={titleId}
      onCancel={event => {
        event.preventDefault()
        onClose()
      }}
      onClick={event => {
        if (event.target === event.currentTarget) {
          const rect = event.currentTarget.getBoundingClientRect()
          if (
            event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom
          )
            onClose()
        }
      }}
    >
      <div className='modal-heading'>
        <h2 id={titleId}>{title}</h2>
        <button
          type='button'
          className='icon-button'
          aria-label='Закрыть'
          onClick={onClose}
        >
          ×
        </button>
      </div>
      {children}
    </dialog>
  )
}
