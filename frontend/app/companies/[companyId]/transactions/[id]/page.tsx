import { redirect } from 'next/navigation'
import { serverFetch } from '@/lib/api-server'
import type { Company, Category, Transaction } from '@/lib/types'
import EditTransactionForm from './EditTransactionForm'

export const dynamic = 'force-dynamic'

interface EditTransactionPageProps {
  params: Promise<{ companyId: string; id: string }>
}

export default async function EditTransactionPage({
  params,
}: EditTransactionPageProps) {
  const { companyId, id } = await params

  const [company, transaction, categories] = await Promise.all([
    serverFetch<Company>(`/api/companies/${companyId}`),
    serverFetch<Transaction>(`/api/companies/${companyId}/transactions/${id}`),
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
      <EditTransactionForm
        companyId={Number(companyId)}
        transaction={transaction}
        categories={categories}
        todayMoscow={todayMoscow}
      />
    </main>
  )
}
