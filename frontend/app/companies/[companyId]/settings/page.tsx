import { unstable_rethrow } from 'next/navigation'
import { serverFetch } from '@/lib/api-server'
import type { Company, Category, Membership, Invitation } from '@/lib/types'
import SettingsTabs from './SettingsTabs'

export const dynamic = 'force-dynamic'

interface SettingsPageProps {
  params: Promise<{ companyId: string }>
}

export default async function SettingsPage({ params }: SettingsPageProps) {
  const { companyId } = await params

  const [company, categories] = await Promise.all([
    serverFetch<Company>(`/api/companies/${companyId}`),
    serverFetch<Category[]>(`/api/companies/${companyId}/categories`),
  ])

  let members: Membership[] = []
  let invitations: Invitation[] = []

  try {
    members = await serverFetch<Membership[]>(
      `/api/companies/${companyId}/members`,
    )
  } catch (err) {
    unstable_rethrow(err)
    members = []
  }

  if (company.role === 'owner') {
    try {
      invitations = await serverFetch<Invitation[]>(
        `/api/companies/${companyId}/invitations`,
      )
    } catch (err) {
      unstable_rethrow(err)
      invitations = []
    }
  }

  return (
    <main className='app-container' style={{ paddingTop: 'var(--space-4)' }}>
      <SettingsTabs
        company={company}
        categories={categories}
        members={members}
        invitations={invitations}
      />
    </main>
  )
}
