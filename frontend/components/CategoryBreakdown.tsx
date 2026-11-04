'use client'

import { useState } from 'react'
import type { CategoryAnalyticsItem } from '@/lib/types'
import { formatMoneyRub, formatNetCfRub } from '@/lib/money'

interface CategoryBreakdownProps {
  items: CategoryAnalyticsItem[]
}

export default function CategoryBreakdown({ items }: CategoryBreakdownProps) {
  const [open, setOpen] = useState(false)

  if (!items || items.length === 0) {
    return null
  }

  return (
    <div
      style={{
        marginTop: 'var(--space-4)',
        backgroundColor: 'var(--color-paper-2)',
        borderRadius: 'var(--radius-surface)',
        border: '1px solid var(--color-rule)',
        padding: 'var(--space-4)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>
            Сводка по категориям
          </h2>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>
            Распределение фактических сумм за выбранный период ({items.length}{' '}
            категорий)
          </span>
        </div>
        <button
          type='button'
          className='btn btn-secondary'
          style={{
            padding: '4px 10px',
            minHeight: '32px',
            fontSize: '0.8125rem',
          }}
          onClick={() => setOpen(!open)}
          aria-expanded={open}
        >
          {open ? 'Скрыть детали' : 'Раскрыть суммы по категориям'}
        </button>
      </div>

      {open && (
        <div
          className='ledger-wrapper'
          style={{ marginTop: 'var(--space-3)', border: 'none' }}
        >
          <table className='ledger-table' style={{ fontSize: '0.875rem' }}>
            <thead>
              <tr>
                <th>Категория</th>
                <th className='num-cell'>Поступления</th>
                <th className='num-cell'>Выплаты</th>
                <th className='num-cell'>Чистый поток</th>
              </tr>
            </thead>
            <tbody>
              {items.map((cat, idx) => (
                <tr
                  key={
                    cat.category_id !== null ? cat.category_id : `uncat-${idx}`
                  }
                >
                  <td
                    style={{
                      fontWeight: cat.category_id === null ? 400 : 600,
                      fontStyle: cat.category_id === null ? 'italic' : 'normal',
                    }}
                  >
                    {cat.category_name}
                  </td>
                  <td className='num-cell amount-inflow'>
                    {formatMoneyRub(cat.inflow, 'inflow')}
                  </td>
                  <td className='num-cell amount-outflow'>
                    {formatMoneyRub(cat.outflow, 'outflow')}
                  </td>
                  <td className='num-cell' style={{ fontWeight: 600 }}>
                    {formatNetCfRub(cat.net_cash_flow)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
