'use client'

import { useState } from 'react'
import type { DailyAnalyticsItem } from '@/lib/types'
import { formatNetCfRub, formatMoneyRub } from '@/lib/money'

interface DailyChartProps {
  items: DailyAnalyticsItem[]
  title?: string
}

export default function DailyChart({
  items,
  title = 'Фактический дневной NetCF',
}: DailyChartProps) {
  const [showTable, setShowTable] = useState(false)

  if (!items || items.length === 0) {
    return (
      <div
        style={{
          padding: 'var(--space-4)',
          backgroundColor: 'var(--color-paper-2)',
          borderRadius: 'var(--radius-surface)',
          border: '1px solid var(--color-rule)',
          textAlign: 'center',
          color: 'var(--color-muted)',
        }}
      >
        Нет данных за выбранный период для построения графика
      </div>
    )
  }

  // Calculate min/max for SVG coordinates (Number() used strictly for plotting)
  const numericValues = items.map(it => Number(it.net_cash_flow) || 0)
  let minVal = Math.min(0, ...numericValues)
  let maxVal = Math.max(0, ...numericValues)

  // Add 10% breathing room
  const range = maxVal - minVal || 1
  minVal = minVal - range * 0.08
  maxVal = maxVal + range * 0.08
  const totalRange = maxVal - minVal

  const width = 800
  const height = 240
  const paddingLeft = 60
  const paddingRight = 20
  const paddingTop = 20
  const paddingBottom = 40

  const chartWidth = width - paddingLeft - paddingRight
  const chartHeight = height - paddingTop - paddingBottom

  const getY = (val: number) => {
    return (
      paddingTop + chartHeight - ((val - minVal) / totalRange) * chartHeight
    )
  }

  const getX = (index: number) => {
    if (items.length === 1) return paddingLeft + chartWidth / 2
    return paddingLeft + (index / (items.length - 1)) * chartWidth
  }

  const zeroY = getY(0)

  // Build SVG path
  const points = items.map((it, idx) => ({
    x: getX(idx),
    y: getY(Number(it.net_cash_flow) || 0),
    item: it,
  }))

  const pathD =
    points.length > 0
      ? `M ${points[0].x} ${points[0].y} ` +
        points
          .slice(1)
          .map(p => `L ${p.x} ${p.y}`)
          .join(' ')
      : ''

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
          marginBottom: 'var(--space-3)',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>
            {title}
          </h2>
          <span style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>
            Сплошная темная линия — чистый поток (поступления минус выплаты за
            день)
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
          onClick={() => setShowTable(!showTable)}
        >
          {showTable ? 'Скрыть таблицу' : 'Показать значения таблицей'}
        </button>
      </div>

      {/* Accessible inline SVG chart */}
      <div style={{ width: '100%', overflowX: 'auto' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{
            width: '100%',
            minWidth: '500px',
            height: 'auto',
            display: 'block',
          }}
          role='img'
          aria-label={`График дневного денежного потока за ${items.length} дней`}
        >
          {/* Zero reference line */}
          <line
            x1={paddingLeft}
            y1={zeroY}
            x2={width - paddingRight}
            y2={zeroY}
            stroke='var(--color-field-border)'
            strokeWidth='1.5'
            strokeDasharray='4 4'
          />
          <text
            x={paddingLeft - 8}
            y={zeroY + 4}
            textAnchor='end'
            fontSize='11'
            fill='var(--color-muted)'
            fontFamily='var(--font-body)'
          >
            0
          </text>

          {/* Top/bottom guide lines */}
          <line
            x1={paddingLeft}
            y1={paddingTop}
            x2={width - paddingRight}
            y2={paddingTop}
            stroke='var(--color-rule)'
            strokeWidth='1'
          />
          <text
            x={paddingLeft - 8}
            y={paddingTop + 4}
            textAnchor='end'
            fontSize='10'
            fill='var(--color-muted)'
            fontFamily='var(--font-body)'
          >
            {formatNetCfRub(String(Math.round(maxVal)), { showSymbol: false })}
          </text>

          <line
            x1={paddingLeft}
            y1={height - paddingBottom}
            x2={width - paddingRight}
            y2={height - paddingBottom}
            stroke='var(--color-rule)'
            strokeWidth='1'
          />
          <text
            x={paddingLeft - 8}
            y={height - paddingBottom + 4}
            textAnchor='end'
            fontSize='10'
            fill='var(--color-muted)'
            fontFamily='var(--font-body)'
          >
            {formatNetCfRub(String(Math.round(minVal)), { showSymbol: false })}
          </text>

          {/* NetCF Line */}
          <path
            d={pathD}
            fill='none'
            stroke='var(--color-ink)'
            strokeWidth='2.5'
            strokeLinejoin='round'
            strokeLinecap='round'
          />

          {/* Data Points */}
          {points.map((p, idx) => (
            <g key={p.item.date}>
              <circle
                cx={p.x}
                cy={p.y}
                r='3.5'
                fill='var(--color-paper)'
                stroke='var(--color-ink)'
                strokeWidth='2'
              >
                <title>{`${p.item.date}: ${formatNetCfRub(p.item.net_cash_flow)}`}</title>
              </circle>
              {/* Show date label on x-axis for first, last, and every few points */}
              {(idx === 0 ||
                idx === points.length - 1 ||
                (points.length <= 14 && idx % 2 === 0) ||
                (points.length > 14 &&
                  idx % Math.ceil(points.length / 6) === 0)) && (
                <text
                  x={p.x}
                  y={height - paddingBottom + 16}
                  textAnchor='middle'
                  fontSize='10'
                  fill='var(--color-muted)'
                  fontFamily='var(--font-body)'
                >
                  {p.item.date.slice(5)}
                </text>
              )}
            </g>
          ))}
        </svg>
      </div>

      {/* Accessible tabular view */}
      {showTable && (
        <div
          style={{
            marginTop: 'var(--space-3)',
            maxHeight: '240px',
            overflowY: 'auto',
          }}
        >
          <table className='ledger-table' style={{ fontSize: '0.8125rem' }}>
            <thead>
              <tr>
                <th>Дата</th>
                <th className='num-cell'>Поступления</th>
                <th className='num-cell'>Выплаты</th>
                <th className='num-cell'>Чистый поток (NetCF)</th>
              </tr>
            </thead>
            <tbody>
              {items.map(row => (
                <tr key={row.date}>
                  <td>{row.date}</td>
                  <td className='num-cell amount-inflow'>
                    {formatMoneyRub(row.inflow, 'inflow')}
                  </td>
                  <td className='num-cell amount-outflow'>
                    {formatMoneyRub(row.outflow, 'outflow')}
                  </td>
                  <td className='num-cell' style={{ fontWeight: 600 }}>
                    {formatNetCfRub(row.net_cash_flow)}
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
