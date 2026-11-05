import AppFrame from '@/components/AppFrame'
import { serverFetch } from '@/lib/api-server'
import type { User } from '@/lib/types'
import AccountSettings from './AccountSettings'

export const dynamic = 'force-dynamic'

export default async function AccountPage() {
  const user = await serverFetch<User>('/api/auth/me')
  return (
    <AppFrame>
      <main className='app-container account-page'>
        <div className='page-header'>
          <div>
            <h1 className='page-title'>Настройки аккаунта</h1>
            <p className='page-subtitle'>
              Личные данные и безопасность. Эти настройки общие для всех
              компаний.
            </p>
          </div>
        </div>
        <AccountSettings user={user} />
      </main>
    </AppFrame>
  )
}
