import { redirect } from 'next/navigation'
import { serverFetch } from '@/lib/api-server'
import type { Company, Category } from '@/lib/types'
import NewTransactionForm from './NewTransactionForm'

export const dynamic = 'force-dynamic'

interface NewTransactionPageProps {
  params: Promise<{ companyId: string }>
}

export default async function NewTransactionPage({
  params,
}: NewTransactionPageProps) {
  const { companyId } = await params

  const [company, categories] = await Promise.all([
    serverFetch<Company>(`/api/companies/${companyId}`),
    serverFetch<Category[]>(`/api/companies/${companyId}/categories`),
  ])

  if (company.role === 'viewer') {
    redirect(`/companies/${companyId}/transactions`)
  }

  const now = new Date()
  const todayMoscow = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Moscow',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)

  return (
    <main
      className='app-container'
      style={{ maxWidth: '640px', paddingTop: 'var(--space-4)' }}
    >
      <NewTransactionForm
        companyId={Number(companyId)}
        categories={categories}
        todayMoscow={todayMoscow}
      />
    </main>
  )
}
