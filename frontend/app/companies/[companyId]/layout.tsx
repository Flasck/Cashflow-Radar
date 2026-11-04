import { serverFetch } from '@/lib/api-server'
import type { Company, User } from '@/lib/types'
import CompanyHeader from '@/components/CompanyHeader'

export const dynamic = 'force-dynamic'

export default async function CompanyLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ companyId: string }>
}) {
  const { companyId } = await params

  const [currentCompany, allCompanies, user] = await Promise.all([
    serverFetch<Company>(`/api/companies/${companyId}`),
    serverFetch<Company[]>('/api/companies'),
    serverFetch<User>('/api/auth/me'),
  ])

  return (
    <div
      style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}
    >
      <CompanyHeader
        currentCompany={currentCompany}
        allCompanies={allCompanies}
        user={user}
      />
      <div style={{ flex: 1, paddingBottom: 'var(--space-6)' }}>{children}</div>
    </div>
  )
}
