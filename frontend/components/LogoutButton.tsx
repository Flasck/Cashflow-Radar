'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { clientPost } from '@/lib/api-client'
import Button from './ui/Button'

export default function LogoutButton() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)

  const handleLogout = async () => {
    setLoading(true)
    try {
      await clientPost('/api/auth/logout')
    } catch {
      // Proceed to login even if logout API had an issue
    } finally {
      router.push('/login')
      router.refresh()
    }
  }

  return (
    <Button
      type='button'
      onClick={handleLogout}
      variant='secondary'
      style={{ padding: '6px 12px', minHeight: '32px', fontSize: '0.8125rem' }}
      pending={loading}
      pendingLabel='Выход…'
    >
      Выйти
    </Button>
  )
}
