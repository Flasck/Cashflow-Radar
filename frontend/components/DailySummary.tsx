import type { DailyAnalyticsItem } from '@/lib/types'
import { cashflowSeries, hasActivity } from '@/lib/cashflow-chart'
import { formatMoneyRub, formatNetCfRub } from '@/lib/money'

export default function DailySummary({
  items,
}: {
  items: DailyAnalyticsItem[]
}) {
  const activeDays = items.filter(hasActivity).length

  return (
    <details className='daily-summary'>
      <summary>
        Сводка по дням{' '}
        <span>
          {activeDays ? `Дней с операциями: ${activeDays}` : 'Нет операций'}
        </span>
      </summary>
      {activeDays === 0 ? (
        <p className='summary-empty'>За выбранный период операций нет.</p>
      ) : (
        <>
          <div
            className='ledger-wrapper'
            tabIndex={0}
            role='region'
            aria-label='Сводка по дням, прокручиваемая таблица'
          >
            <table className='ledger-table'>
              <caption className='sr-only'>
                Поступления, выплаты, чистый и накопленный поток по дням
              </caption>
              <thead>
                <tr>
                  <th scope='col'>Дата</th>
                  <th scope='col' className='num-cell'>
                    Поступления
                  </th>
                  <th scope='col' className='num-cell'>
                    Выплаты
                  </th>
                  <th scope='col' className='num-cell'>
                    Чистый поток
                  </th>
                  <th scope='col' className='num-cell'>
                    Накоплено за период
                  </th>
                </tr>
              </thead>
              <tbody>
                {cashflowSeries(items).map(day => (
                  <tr key={day.date}>
                    <th scope='row'>{day.date}</th>
                    <td className='num-cell amount-inflow'>
                      {hasActivity(day)
                        ? formatMoneyRub(day.inflow, 'inflow')
                        : '—'}
                    </td>
                    <td className='num-cell amount-outflow'>
                      {hasActivity(day)
                        ? formatMoneyRub(day.outflow, 'outflow')
                        : '—'}
                    </td>
                    <td className='num-cell'>
                      {hasActivity(day) ? (
                        formatNetCfRub(day.net_cash_flow)
                      ) : (
                        <span className='muted'>Нет операций</span>
                      )}
                    </td>
                    <td className='num-cell'>
                      {formatNetCfRub(day.cumulative)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </details>
  )
}
