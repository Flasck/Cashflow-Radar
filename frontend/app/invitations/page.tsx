import AppFrame from '@/components/AppFrame'
import { serverFetch } from '@/lib/api-server'
import type { Company, PersonalInvitation } from '@/lib/types'
import InvitationsClient from './InvitationsClient'

export const dynamic = 'force-dynamic'

export default async function InvitationsPage() {
  const [received, sent, companies] = await Promise.all([
    serverFetch<PersonalInvitation[]>('/api/invitations?direction=received'),
    serverFetch<PersonalInvitation[]>('/api/invitations?direction=sent'),
    serverFetch<Company[]>('/api/companies'),
  ])
  return (
    <AppFrame>
      <main className='app-container'>
        <div className='page-header'>
          <div>
            <h1 className='page-title'>Приглашения</h1>
            <p className='page-subtitle'>
              Доступ к компаниям и история ответов — в одном месте.
            </p>
          </div>
        </div>
        <InvitationsClient
          received={received}
          sent={sent}
          companies={companies}
        />
      </main>
    </AppFrame>
  )
}
