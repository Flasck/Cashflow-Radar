import { serverFetch } from '@/lib/api-server'
import type { Company, PersonalInvitation, User } from '@/lib/types'
import AppShell from './AppShell'
import { cookies } from 'next/headers'

export default async function AppFrame({
  children,
  currentCompany,
}: {
  children: React.ReactNode
  currentCompany?: Company
}) {
  const [user, companies, invitations] = await Promise.all([
    serverFetch<User>('/api/auth/me'),
    serverFetch<Company[]>('/api/companies'),
    serverFetch<PersonalInvitation[]>('/api/invitations'),
  ])
  const pendingCount = invitations.filter(
    inv => inv.status === 'pending' && !inv.is_member,
  ).length
  const lastCompanyId = (await cookies()).get(`radar_company_${user.id}`)?.value
  const selectedCompany =
    currentCompany ??
    companies.find(company => String(company.id) === lastCompanyId)
  return (
    <AppShell
      user={user}
      companies={companies}
      currentCompany={selectedCompany}
      pendingCount={pendingCount}
    >
      {children}
    </AppShell>
  )
}
