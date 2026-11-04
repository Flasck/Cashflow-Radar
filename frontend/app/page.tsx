import { redirect } from 'next/navigation'
import { serverFetch } from '@/lib/api-server'
import type { User } from '@/lib/types'

export const dynamic = 'force-dynamic'

export default async function HomePage() {
  await serverFetch<User>('/api/auth/me')
  redirect('/companies')
}
