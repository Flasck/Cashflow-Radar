import { redirect } from 'next/navigation'
import { serverFetch } from '@/lib/api-server'
import type { Company } from '@/lib/types'
import ImportFlow from './ImportFlow'

export const dynamic = 'force-dynamic'

interface ImportPageProps {
  params: Promise<{ companyId: string }>
}

export default async function ImportPage({ params }: ImportPageProps) {
  const { companyId } = await params

  const company = await serverFetch<Company>(`/api/companies/${companyId}`)

  if (company.role === 'viewer') {
    redirect(`/companies/${companyId}/transactions`)
  }

  return (
    <main className='app-container' style={{ paddingTop: 'var(--space-4)' }}>
      <ImportFlow companyId={Number(companyId)} />
    </main>
  )
}
