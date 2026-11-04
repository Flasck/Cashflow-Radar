import Link from 'next/link'
import { serverFetch } from '@/lib/api-server'
import type { Company, User } from '@/lib/types'
import LogoutButton from '@/components/LogoutButton'
import CreateCompanySection from './CreateCompanySection'

export const dynamic = 'force-dynamic'

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

export default async function CompaniesPage() {
  const [user, companies] = await Promise.all([
    serverFetch<User>('/api/auth/me'),
    serverFetch<Company[]>('/api/companies'),
  ])

  return (
    <div
      style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}
    >
      <header className='app-header'>
        <div className='app-container app-header-inner'>
          <div className='app-brand'>
            <span>CashFlow Radar</span>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--space-3)',
            }}
          >
            <span style={{ fontSize: '0.875rem', color: 'var(--color-muted)' }}>
              {user.full_name} ({user.email})
            </span>
            <LogoutButton />
          </div>
        </div>
      </header>

      <main
        className='app-container'
        style={{ flex: 1, paddingBottom: 'var(--space-6)' }}
      >
        <div className='page-header'>
          <div>
            <h1 className='page-title'>Организации</h1>
            <p className='page-subtitle'>
              Выберите компанию для перехода к журналу операций или
              зарегистрируйте новую
            </p>
          </div>
          <div>
            <CreateCompanySection />
          </div>
        </div>

        {companies.length === 0 ? (
          <div
            style={{
              padding: 'var(--space-6)',
              textAlign: 'center',
              backgroundColor: 'var(--color-paper-2)',
              borderRadius: 'var(--radius-surface)',
              border: '1px solid var(--color-rule)',
            }}
          >
            <h2
              style={{
                fontSize: '1.25rem',
                marginTop: 0,
                marginBottom: 'var(--space-2)',
              }}
            >
              У вас пока нет доступных компаний
            </h2>
            <p
              style={{
                color: 'var(--color-muted)',
                maxWidth: '480px',
                margin: '0 auto var(--space-4)',
              }}
            >
              Создайте вашу первую организацию для ведения реестра операций и
              прогнозирования NetCF, либо запросите ссылку-приглашение у
              владельца.
            </p>
          </div>
        ) : (
          <div
            className='ledger-wrapper'
            style={{
              borderRadius: 'var(--radius-surface)',
              border: '1px solid var(--color-rule)',
            }}
          >
            <table className='ledger-table'>
              <thead>
                <tr>
                  <th>Компания</th>
                  <th>Отрасль</th>
                  <th>Ваша роль</th>
                  <th>Последняя операция</th>
                  <th style={{ textAlign: 'right' }}>Действие</th>
                </tr>
              </thead>
              <tbody>
                {companies.map(company => (
                  <tr key={company.id}>
                    <td style={{ fontWeight: 600 }}>
                      <Link
                        href={`/companies/${company.id}/transactions`}
                        style={{ textDecoration: 'none' }}
                      >
                        {company.name}
                      </Link>
                    </td>
                    <td
                      style={{
                        color: company.industry_code
                          ? 'var(--color-ink)'
                          : 'var(--color-muted)',
                      }}
                    >
                      {company.industry_code || '—'}
                    </td>
                    <td>
                      <span className='badge badge-role'>
                        {roleToRussian(company.role)}
                      </span>
                    </td>
                    <td
                      style={{
                        color: company.last_operation_date
                          ? 'var(--color-ink)'
                          : 'var(--color-muted)',
                      }}
                    >
                      {company.last_operation_date || 'Операций нет'}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <Link
                        href={`/companies/${company.id}/transactions`}
                        className='btn btn-secondary'
                        style={{
                          padding: '4px 10px',
                          minHeight: '32px',
                          fontSize: '0.8125rem',
                        }}
                      >
                        Открыть журнал
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
