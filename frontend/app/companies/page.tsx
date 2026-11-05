import Link from 'next/link'
import { serverFetch } from '@/lib/api-server'
import type { Company } from '@/lib/types'
import AppFrame from '@/components/AppFrame'
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
  const companies = await serverFetch<Company[]>('/api/companies')

  return (
    <AppFrame>
      <main
        className='app-container'
        style={{ flex: 1, paddingBottom: 'var(--space-6)' }}
      >
        <div className='page-header'>
          <div>
            <h1 className='page-title'>Компании</h1>
            <p className='page-subtitle'>
              Выберите компанию для перехода к журналу операций или создайте
              новую. Доступ к каждой компании определяется вашей ролью.
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
              Создайте компанию для учёта денежных потоков или примите
              приглашение от владельца.
            </p>
            <Link href='/invitations' className='btn btn-secondary'>
              Посмотреть приглашения
            </Link>
          </div>
        ) : (
          <div
            className='ledger-wrapper companies-list'
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
    </AppFrame>
  )
}
