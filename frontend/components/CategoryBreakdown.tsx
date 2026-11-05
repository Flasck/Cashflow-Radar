'use client'

import { useId, useState } from 'react'
import type { CategoryAnalyticsItem, TransactionDirection } from '@/lib/types'
import { formatMoneyRub } from '@/lib/money'
import { fromCents, toCents } from '@/lib/cashflow-chart'

const colors = [
  'var(--color-category-1)',
  'var(--color-category-2)',
  'var(--color-category-3)',
  'var(--color-category-4)',
  'var(--color-category-5)',
  'var(--color-category-6)',
  'var(--color-category-7)',
  'var(--color-category-8)',
]

export default function CategoryBreakdown({
  items,
}: {
  items: CategoryAnalyticsItem[]
}) {
  const [direction, setDirection] = useState<TransactionDirection>(() =>
    items.some(item => toCents(item.outflow) > 0n) ? 'outflow' : 'inflow',
  )
  const [active, setActive] = useState<number | null>(null)
  const titleId = useId()
  const segments = items
    .map(item => ({ ...item, cents: toCents(item[direction]) }))
    .filter(item => item.cents > 0n)
    .sort((a, b) => (a.cents > b.cents ? -1 : a.cents < b.cents ? 1 : 0))
  const total = segments.reduce((sum, item) => sum + item.cents, 0n)
  let offset = 0
  const selected = active === null ? null : segments[active]

  return (
    <section className='category-breakdown' aria-labelledby={titleId}>
      <div className='chart-heading'>
        <div>
          <h2 id={titleId}>По категориям</h2>
          <p>Распределение сумм за весь выбранный период</p>
        </div>
        <div className='chart-presets' aria-label='Направление распределения'>
          <button
            type='button'
            aria-pressed={direction === 'outflow'}
            onClick={() => {
              setDirection('outflow')
              setActive(null)
            }}
          >
            Выплаты
          </button>
          <button
            type='button'
            aria-pressed={direction === 'inflow'}
            onClick={() => {
              setDirection('inflow')
              setActive(null)
            }}
          >
            Поступления
          </button>
        </div>
      </div>
      {total === 0n ? (
        <p className='category-empty'>
          За выбранный период{' '}
          {direction === 'outflow' ? 'выплат' : 'поступлений'} нет.
        </p>
      ) : (
        <div className='category-layout'>
          <div className='category-donut'>
            <svg
              viewBox='0 0 240 240'
              role='img'
              aria-label={`Распределение по категориям: ${direction === 'outflow' ? 'выплаты' : 'поступления'}`}
            >
              {segments.map((segment, index) => {
                const percent = (Number(segment.cents) / Number(total)) * 100
                const start = offset
                offset += percent
                return (
                  <circle
                    key={segment.category_id ?? 'uncategorized'}
                    cx='120'
                    cy='120'
                    r='94'
                    fill='none'
                    stroke={colors[index % colors.length]}
                    strokeWidth={active === index ? 30 : 24}
                    pathLength='100'
                    strokeDasharray={`${percent} ${100 - percent}`}
                    strokeDashoffset={-start}
                    transform='rotate(-90 120 120)'
                    className='category-segment'
                    opacity={active === null || active === index ? 1 : 0.35}
                    onPointerEnter={() => setActive(index)}
                    onPointerLeave={() => setActive(null)}
                  >
                    <title>{`${segment.category_name}: ${formatMoneyRub(segment[direction])}`}</title>
                  </circle>
                )
              })}
            </svg>
            <div className='category-center'>
              <span>
                {selected?.category_name ??
                  (direction === 'outflow'
                    ? 'Всего выплат'
                    : 'Всего поступлений')}
              </span>
              <strong>
                {formatMoneyRub(
                  selected ? selected[direction] : fromCents(total),
                )}
              </strong>
            </div>
          </div>
          <ul className='category-legend'>
            {segments.map((segment, index) => (
              <li key={segment.category_id ?? 'uncategorized'}>
                <button
                  type='button'
                  className={active === index ? 'is-active' : ''}
                  onPointerEnter={() => setActive(index)}
                  onPointerLeave={() => setActive(null)}
                  onFocus={() => setActive(index)}
                  onBlur={() => setActive(null)}
                  onClick={() =>
                    setActive(value => (value === index ? null : index))
                  }
                  aria-label={`${segment.category_name}: ${formatMoneyRub(segment[direction])}, ${(Number((segment.cents * 1000n) / total) / 10).toLocaleString('ru-RU')}%`}
                >
                  <i style={{ background: colors[index % colors.length] }} />
                  <span>{segment.category_name}</span>
                  <strong>{formatMoneyRub(segment[direction])}</strong>
                  <small>
                    {(
                      Number((segment.cents * 1000n) / total) / 10
                    ).toLocaleString('ru-RU')}
                    %
                  </small>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      <noscript>
        <div className='ledger-wrapper'>
          <table className='ledger-table'>
            <caption>Все категории — поступления и выплаты</caption>
            <thead>
              <tr>
                <th>Категория</th>
                <th>Поступления</th>
                <th>Выплаты</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.category_id ?? 'uncategorized'}>
                  <td>{item.category_name}</td>
                  <td>{formatMoneyRub(item.inflow)}</td>
                  <td>{formatMoneyRub(item.outflow)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </noscript>
    </section>
  )
}
