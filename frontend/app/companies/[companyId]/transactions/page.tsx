import Link from 'next/link'
import { unstable_rethrow } from 'next/navigation'
import { serverFetch, ApiServerError } from '@/lib/api-server'
import type {
  Company,
  TransactionsResponse,
  DailyAnalyticsResponse,
  CategoriesAnalyticsResponse,
  Category,
} from '@/lib/types'
import { formatMoneyRub, formatNetCfRub } from '@/lib/money'
import DailyChart from '@/components/DailyChart'
import CategoryBreakdown from '@/components/CategoryBreakdown'

export const dynamic = 'force-dynamic'

interface TransactionsPageProps {
  params: Promise<{ companyId: string }>
  searchParams: Promise<{
    date_from?: string
    date_to?: string
    direction?: string
    category_id?: string
    uncategorized?: string
    page?: string
  }>
}

const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/

export default async function TransactionsPage({
  params,
  searchParams,
}: TransactionsPageProps) {
  const { companyId } = await params
  const sParams = await searchParams

  // Europe/Moscow current month dates
  const now = new Date()
  const moscowDateStr = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Moscow',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)

  const [currentYear, currentMonth] = moscowDateStr.split('-')
  const lastDayOfMonth = new Date(
    Number(currentYear),
    Number(currentMonth),
    0,
  ).getDate()

  let dateFrom =
    sParams.date_from && DATE_REGEX.test(sParams.date_from)
      ? sParams.date_from
      : `${currentYear}-${currentMonth}-01`

  let dateTo =
    sParams.date_to && DATE_REGEX.test(sParams.date_to)
      ? sParams.date_to
      : `${currentYear}-${currentMonth}-${String(lastDayOfMonth).padStart(2, '0')}`

  // Safe bounds check
  if (dateFrom > dateTo) {
    const temp = dateFrom
    dateFrom = dateTo
    dateTo = temp
  }

  // Direction validation
  const direction =
    sParams.direction === 'inflow' || sParams.direction === 'outflow'
      ? sParams.direction
      : ''

  // Sentinel normalization: __uncat__ vs uncategorized vs valid integer category_id
  const isUncategorized =
    sParams.uncategorized === 'true' || sParams.category_id === '__uncat__'
  const validCategoryId =
    !isUncategorized && sParams.category_id && /^\d+$/.test(sParams.category_id)
      ? sParams.category_id
      : ''

  // Safe pagination
  const rawPage = parseInt(sParams.page || '1', 10)
  const page = Number.isFinite(rawPage) && rawPage > 0 ? rawPage : 1
  const pageSize = 50

  // Build query string for transactions API
  const txQuery = new URLSearchParams()
  txQuery.set('date_from', dateFrom)
  txQuery.set('date_to', dateTo)
  if (direction) txQuery.set('direction', direction)
  if (isUncategorized) {
    txQuery.set('uncategorized', 'true')
  } else if (validCategoryId) {
    txQuery.set('category_id', validCategoryId)
  }
  txQuery.set('page', String(page))
  txQuery.set('page_size', String(pageSize))

  // Analytics query string (no pagination)
  const analyticsQuery = new URLSearchParams()
  analyticsQuery.set('date_from', dateFrom)
  analyticsQuery.set('date_to', dateTo)
  if (direction) analyticsQuery.set('direction', direction)
  if (isUncategorized) {
    analyticsQuery.set('uncategorized', 'true')
  } else if (validCategoryId) {
    analyticsQuery.set('category_id', validCategoryId)
  }

  let company: Company | null = null
  let txData: TransactionsResponse = {
    items: [],
    total: 0,
    page: 1,
    page_size: pageSize,
  }
  let dailyData: DailyAnalyticsResponse = {
    items: [],
    totals: { inflow: '0.00', outflow: '0.00', net_cash_flow: '0.00' },
  }
  let catData: CategoriesAnalyticsResponse = { items: [] }
  let categories: Category[] = []
  let loadError: string | null = null

  try {
    const [compRes, txRes, dailyRes, catRes, categoriesRes] = await Promise.all(
      [
        serverFetch<Company>(`/api/companies/${companyId}`),
        serverFetch<TransactionsResponse>(
          `/api/companies/${companyId}/transactions?${txQuery.toString()}`,
        ),
        serverFetch<DailyAnalyticsResponse>(
          `/api/companies/${companyId}/analytics/daily?${analyticsQuery.toString()}`,
        ),
        serverFetch<CategoriesAnalyticsResponse>(
          `/api/companies/${companyId}/analytics/categories?${analyticsQuery.toString()}`,
        ),
        serverFetch<Category[]>(`/api/companies/${companyId}/categories`),
      ],
    )

    company = compRes
    txData = txRes
    dailyData = dailyRes
    catData = catRes
    categories = categoriesRes
  } catch (err) {
    unstable_rethrow(err)
    if (err instanceof ApiServerError) {
      loadError = err.message || `Ошибка сервера (${err.status})`
    } else {
      loadError = 'Не удалось загрузить данные журнала операций'
    }
  }

  const canEdit = company
    ? company.role === 'owner' || company.role === 'treasurer'
    : false
  const categoryMap = new Map<number, string>()
  categories.forEach(c => categoryMap.set(c.id, c.name))

  const totalPages = Math.max(1, Math.ceil(txData.total / pageSize))

  // Helper for pagination URLs
  const createPageUrl = (targetPage: number) => {
    const p = new URLSearchParams()
    if (sParams.date_from) p.set('date_from', sParams.date_from)
    if (sParams.date_to) p.set('date_to', sParams.date_to)
    if (direction) p.set('direction', direction)
    if (isUncategorized) {
      p.set('uncategorized', 'true')
    } else if (validCategoryId) {
      p.set('category_id', validCategoryId)
    }
    p.set('page', String(targetPage))
    return `/companies/${companyId}/transactions?${p.toString()}`
  }

  return (
    <main className='app-container'>
      {/* Page Header */}
      <div className='page-header'>
        <div>
          <h1 className='page-title'>Журнал операций</h1>
          <p className='page-subtitle'>
            Фактические поступления и выплаты денежных средств
          </p>
        </div>

        {canEdit && (
          <div
            style={{
              display: 'flex',
              gap: 'var(--space-3)',
              alignItems: 'center',
            }}
          >
            <Link
              href={`/companies/${companyId}/import`}
              className='btn btn-secondary'
            >
              Загрузить файл
            </Link>
            <Link
              href={`/companies/${companyId}/transactions/new`}
              className='btn btn-primary'
            >
              + Добавить операцию
            </Link>
          </div>
        )}
      </div>

      {loadError && (
        <div
          className='notice notice-error'
          role='alert'
          style={{ marginBottom: 'var(--space-4)' }}
        >
          {loadError}
        </div>
      )}

      {/* Filter Toolbar */}
      <form
        method='GET'
        className='toolbar'
        style={{
          backgroundColor: 'var(--color-paper-2)',
          padding: 'var(--space-3) var(--space-4)',
          borderRadius: 'var(--radius-surface)',
          border: '1px solid var(--color-rule)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
          }}
        >
          <label
            htmlFor='filter-from'
            style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}
          >
            С
          </label>
          <input
            id='filter-from'
            type='date'
            name='date_from'
            defaultValue={dateFrom}
            className='form-input'
            style={{
              minHeight: '34px',
              padding: '4px 8px',
              fontSize: '0.875rem',
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
          }}
        >
          <label
            htmlFor='filter-to'
            style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}
          >
            По
          </label>
          <input
            id='filter-to'
            type='date'
            name='date_to'
            defaultValue={dateTo}
            className='form-input'
            style={{
              minHeight: '34px',
              padding: '4px 8px',
              fontSize: '0.875rem',
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
          }}
        >
          <label
            htmlFor='filter-direction'
            style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}
          >
            Тип
          </label>
          <select
            id='filter-direction'
            name='direction'
            defaultValue={direction}
            className='form-select'
            style={{
              minHeight: '34px',
              padding: '4px 8px',
              fontSize: '0.875rem',
            }}
          >
            <option value=''>Все типы</option>
            <option value='inflow'>Поступления (+)</option>
            <option value='outflow'>Выплаты (−)</option>
          </select>
        </div>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-2)',
          }}
        >
          <label
            htmlFor='filter-category'
            style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}
          >
            Категория
          </label>
          <select
            id='filter-category'
            name='category_id'
            defaultValue={isUncategorized ? '__uncat__' : validCategoryId}
            className='form-select'
            style={{
              minHeight: '34px',
              padding: '4px 8px',
              fontSize: '0.875rem',
            }}
          >
            <option value=''>Все категории</option>
            <option value='__uncat__'>Без категории</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>

        <button
          type='submit'
          className='btn btn-secondary'
          style={{
            minHeight: '34px',
            padding: '4px 12px',
            fontSize: '0.875rem',
          }}
        >
          Применить
        </button>

        <Link
          href={`/companies/${companyId}/transactions`}
          style={{
            fontSize: '0.8125rem',
            color: 'var(--color-muted)',
            marginLeft: 'var(--space-2)',
          }}
        >
          Сбросить
        </Link>
      </form>

      {/* Totals Ribbon */}
      <div className='totals-ribbon' style={{ marginTop: 'var(--space-4)' }}>
        <div className='totals-item'>
          <span className='totals-label'>Поступления за период</span>
          <span className='totals-value amount-inflow'>
            {formatMoneyRub(dailyData.totals.inflow, 'inflow')}
          </span>
        </div>

        <div className='totals-item'>
          <span className='totals-label'>Выплаты за период</span>
          <span className='totals-value amount-outflow'>
            {formatMoneyRub(dailyData.totals.outflow, 'outflow')}
          </span>
        </div>

        <div className='totals-item'>
          <span className='totals-label'>Чистый денежный поток (NetCF)</span>
          <span className='totals-value' style={{ color: 'var(--color-ink)' }}>
            {formatNetCfRub(dailyData.totals.net_cash_flow)}
          </span>
        </div>
      </div>

      {/* Ledger Table */}
      {txData.items.length === 0 ? (
        <div
          style={{
            padding: 'var(--space-6)',
            textAlign: 'center',
            backgroundColor: 'var(--color-paper-2)',
            borderRadius: 'var(--radius-surface)',
            border: '1px solid var(--color-rule)',
            marginTop: 'var(--space-4)',
          }}
        >
          <h2
            style={{
              fontSize: '1.125rem',
              marginTop: 0,
              marginBottom: 'var(--space-2)',
            }}
          >
            {txData.total === 0 && !sParams.date_from && !direction
              ? 'Операций пока нет'
              : 'По выбранным условиям операций не найдено'}
          </h2>
          <p
            style={{
              color: 'var(--color-muted)',
              fontSize: '0.875rem',
              marginBottom: 'var(--space-4)',
            }}
          >
            {canEdit
              ? 'Вы можете добавить платеж вручную или загрузить выписку из файла.'
              : 'В выбранном диапазоне дат записей не обнаружено.'}
          </p>
          {canEdit && (
            <Link
              href={`/companies/${companyId}/transactions/new`}
              className='btn btn-primary'
            >
              Добавить первую операцию
            </Link>
          )}
        </div>
      ) : (
        <div
          className='ledger-wrapper'
          style={{
            marginTop: 'var(--space-4)',
            borderRadius: 'var(--radius-surface)',
            border: '1px solid var(--color-rule)',
          }}
        >
          <table className='ledger-table'>
            <thead>
              <tr>
                <th style={{ width: '130px' }}>Дата</th>
                <th>Назначение</th>
                <th>Категория</th>
                <th style={{ width: '120px' }}>Тип</th>
                <th className='num-cell' style={{ width: '160px' }}>
                  Сумма
                </th>
                {canEdit && (
                  <th style={{ width: '90px', textAlign: 'right' }}>
                    Действия
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {txData.items.map(tx => {
                const categoryName = tx.category_id
                  ? categoryMap.get(tx.category_id) || 'Категория удалена'
                  : 'Без категории'
                const isInflow = tx.direction === 'inflow'

                return (
                  <tr key={tx.id}>
                    <td
                      style={{
                        whiteSpace: 'nowrap',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {tx.operation_date}
                    </td>
                    <td>
                      {tx.purpose ? (
                        <span>{tx.purpose}</span>
                      ) : (
                        <span style={{ color: 'var(--color-muted)' }}>
                          {'\u2014'}
                        </span>
                      )}
                    </td>
                    <td>
                      <span
                        style={{
                          color: tx.category_id
                            ? 'var(--color-ink)'
                            : 'var(--color-muted)',
                          fontStyle: tx.category_id ? 'normal' : 'italic',
                        }}
                      >
                        {categoryName}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`badge ${isInflow ? 'badge-inflow' : 'badge-outflow'}`}
                      >
                        {isInflow ? 'Поступление' : 'Выплата'}
                      </span>
                    </td>
                    <td
                      className={`num-cell ${isInflow ? 'amount-inflow' : 'amount-outflow'}`}
                    >
                      {formatMoneyRub(tx.amount, tx.direction)}
                    </td>
                    {canEdit && (
                      <td style={{ textAlign: 'right' }}>
                        <Link
                          href={`/companies/${companyId}/transactions/${tx.id}`}
                          className='btn btn-secondary'
                          style={{
                            padding: '3px 8px',
                            minHeight: '28px',
                            fontSize: '0.75rem',
                          }}
                        >
                          Изменить
                        </Link>
                      </td>
                    )}
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Footer */}
      {txData.total > 0 && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: 'var(--space-3)',
            fontSize: '0.875rem',
            color: 'var(--color-muted)',
            flexWrap: 'wrap',
            gap: 'var(--space-3)',
          }}
        >
          <span>
            Найдено {txData.total}{' '}
            {txData.total === 1 ? 'операция' : 'операций'} (страница {page} из{' '}
            {totalPages})
          </span>

          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            {page > 1 ? (
              <Link
                href={createPageUrl(page - 1)}
                className='btn btn-secondary'
                style={{
                  padding: '4px 10px',
                  minHeight: '32px',
                  fontSize: '0.8125rem',
                }}
              >
                Назад
              </Link>
            ) : (
              <button
                disabled
                className='btn btn-secondary'
                style={{
                  padding: '4px 10px',
                  minHeight: '32px',
                  fontSize: '0.8125rem',
                }}
              >
                Назад
              </button>
            )}

            {page < totalPages ? (
              <Link
                href={createPageUrl(page + 1)}
                className='btn btn-secondary'
                style={{
                  padding: '4px 10px',
                  minHeight: '32px',
                  fontSize: '0.8125rem',
                }}
              >
                Далее
              </Link>
            ) : (
              <button
                disabled
                className='btn btn-secondary'
                style={{
                  padding: '4px 10px',
                  minHeight: '32px',
                  fontSize: '0.8125rem',
                }}
              >
                Далее
              </button>
            )}
          </div>
        </div>
      )}

      {/* Inline Daily NetCF SVG Chart */}
      <DailyChart items={dailyData.items} />

      {/* Collapsible Category Breakdown */}
      <CategoryBreakdown items={catData.items} />
    </main>
  )
}
