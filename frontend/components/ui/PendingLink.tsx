'use client'

import Link, { useLinkStatus } from 'next/link'
import type { ComponentProps } from 'react'
import Spinner from './Spinner'

function LinkStatus() {
  const { pending } = useLinkStatus()
  return pending ? (
    <span
      className='link-pending'
      role='status'
      aria-label='Открываем страницу'
    >
      <Spinner />
    </span>
  ) : null
}

export default function PendingLink({
  children,
  ...props
}: ComponentProps<typeof Link>) {
  return (
    <Link {...props}>
      {children}
      <LinkStatus />
    </Link>
  )
}
