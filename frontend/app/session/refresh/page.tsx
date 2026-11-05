'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { refreshSession } from '@/lib/api-client'

export default function RefreshSessionPage() {
  const router = useRouter()

  useEffect(() => {
    let active = true
    refreshSession().then(ok => {
      if (active) {
        router.replace(ok ? '/companies' : '/login')
        router.refresh()
      }
    }).catch(() => {
      if (active) router.replace('/login')
    })
    return () => { active = false }
  }, [router])

  return <main className='app-container'>Обновление сессии…</main>
}
