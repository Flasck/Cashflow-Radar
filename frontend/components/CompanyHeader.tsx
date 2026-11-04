'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import type { Company, User } from '@/lib/types'
import LogoutButton from './LogoutButton'

interface CompanyHeaderProps {
  currentCompany: Company
  allCompanies: Company[]
  user: User
}

function roleToRussian(role: string): string {
  switch (role) {
    case 'owner':
      return 'Владелец'
    case 'treasurer':
      return 'Казначей'
    case 'viewer':
      return 'Наблюдатель'
    default:
      return role
  }
}

export default function CompanyHeader({
  currentCompany,
  allCompanies,
  user,
}: CompanyHeaderProps) {
  const pathname = usePathname()
  const router = useRouter()
  const handleCompanyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value
    if (val === '__new__') {
      router.push('/companies')
    } else {
      router.push(`/companies/${val}/transactions`)
    }
  }

  const isTransactionsActive =
    pathname?.includes('/transactions') || pathname?.includes('/import')
  const isForecastActive = pathname?.includes('/forecast')
  const isSettingsActive = pathname?.includes('/settings')

  return (
    <header className='app-header'>
      <div className='app-container app-header-inner'>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-4)',
            flexWrap: 'wrap',
            minWidth: 0,
            maxWidth: '100%',
          }}
        >
          <Link href='/companies' className='app-brand'>
            CashFlow Radar
          </Link>

          {/* Company switcher */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
              flexWrap: 'wrap',
              minWidth: 0,
              maxWidth: '100%',
            }}
          >
            <select
              value={currentCompany.id}
              onChange={handleCompanyChange}
              className='form-select'
              style={{
                minHeight: '34px',
                padding: '4px 10px',
                fontSize: '0.875rem',
                fontWeight: 600,
                backgroundColor: 'var(--color-paper)',
                minWidth: 0,
                maxWidth: '100%',
              }}
              aria-label='Выбор компании'
            >
              {allCompanies.map(c => (
                <option key={c.id} value={c.id}>
                  {c.name} ({roleToRussian(c.role)})
                </option>
              ))}
              <option value='__new__'>+ Все компании / Создать</option>
            </select>

            <span
              className='badge badge-role'
              style={{ fontSize: '0.75rem', flexShrink: 0 }}
            >
              {roleToRussian(currentCompany.role)}
            </span>
          </div>

          {/* Navigation links */}
          <nav aria-label='Разделы компании'>
            <ul className='app-nav'>
              <li>
                <Link
                  href={`/companies/${currentCompany.id}/transactions`}
                  className={`app-nav-link ${isTransactionsActive ? 'active' : ''}`}
                >
                  Операции
                </Link>
              </li>
              <li>
                <Link
                  href={`/companies/${currentCompany.id}/forecast`}
                  className={`app-nav-link ${isForecastActive ? 'active' : ''}`}
                >
                  Прогноз
                </Link>
              </li>
              <li>
                <Link
                  href={`/companies/${currentCompany.id}/settings`}
                  className={`app-nav-link ${isSettingsActive ? 'active' : ''}`}
                >
                  Настройки
                </Link>
              </li>
            </ul>
          </nav>
        </div>

        {/* Profile */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-3)',
          }}
        >
          <span style={{ fontSize: '0.875rem', color: 'var(--color-muted)' }}>
            {user.full_name}
          </span>
          <LogoutButton />
        </div>
      </div>
    </header>
  )
}
