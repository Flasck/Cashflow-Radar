'use client'

import { useState } from 'react'
import type { DailyAnalyticsItem, ForecastPoint } from '@/lib/types'
import { formatNetCfRub } from '@/lib/money'

interface ForecastChartProps {
  historyPoints: DailyAnalyticsItem[]
  forecastPoints: ForecastPoint[]
  cutoffDate: string
}

export default function ForecastChart({
  historyPoints,
  forecastPoints,
  cutoffDate,
}: ForecastChartProps) {
  const [showTable, setShowTable] = useState(false)

  // Combine points for overall bounding box calculation
  const historyNumeric = historyPoints.map(p => ({
    date: p.date,
    val: Number(p.net_cash_flow) || 0,
    raw: p.net_cash_flow,
    type: 'history' as const,
  }))

  const forecastNumeric = forecastPoints.map(p => ({
    date: p.date,
    val: Number(p.net_cash_flow) || 0,
    raw: p.net_cash_flow,
    type: 'forecast' as const,
  }))

  const allPoints = [...historyNumeric, ...forecastNumeric]

  if (allPoints.length === 0) {
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
        Нет данных для отображения графика
      </div>
    )
  }

  const values = allPoints.map(p => p.val)
  let minVal = Math.min(0, ...values)
  let maxVal = Math.max(0, ...values)

  const range = maxVal - minVal || 1
  minVal = minVal - range * 0.08
  maxVal = maxVal + range * 0.08
  const totalRange = maxVal - minVal

  const width = 860
  const height = 280
  const paddingLeft = 70
  const paddingRight = 30
  const paddingTop = 24
  const paddingBottom = 44

  const chartWidth = width - paddingLeft - paddingRight
  const chartHeight = height - paddingTop - paddingBottom

  const getY = (val: number) => {
    return (
      paddingTop + chartHeight - ((val - minVal) / totalRange) * chartHeight
    )
  }

  const getX = (index: number) => {
    if (allPoints.length === 1) return paddingLeft + chartWidth / 2
    return paddingLeft + (index / (allPoints.length - 1)) * chartWidth
  }

  const zeroY = getY(0)

  // Coordinated points
  const historyCoords = historyNumeric.map((p, idx) => ({
    x: getX(idx),
    y: getY(p.val),
    point: p,
  }))

  const historyLength = historyNumeric.length

  const forecastCoords = forecastNumeric.map((p, idx) => ({
    x: getX(historyLength + idx),
    y: getY(p.val),
    point: p,
  }))

  // Connection point between history end and forecast start
  const lastHistory = historyCoords[historyCoords.length - 1]

  const historyD =
    historyCoords.length > 0
      ? `M ${historyCoords[0].x} ${historyCoords[0].y} ` +
        historyCoords
          .slice(1)
          .map(p => `L ${p.x} ${p.y}`)
          .join(' ')
      : ''

  // Forecast path connects from last history point if available
  let forecastD = ''
  if (lastHistory && forecastCoords.length > 0) {
    forecastD =
      `M ${lastHistory.x} ${lastHistory.y} ` +
      forecastCoords.map(p => `L ${p.x} ${p.y}`).join(' ')
  } else if (forecastCoords.length > 0) {
    forecastD =
      `M ${forecastCoords[0].x} ${forecastCoords[0].y} ` +
      forecastCoords
        .slice(1)
        .map(p => `L ${p.x} ${p.y}`)
        .join(' ')
  }

  // Cutoff vertical line X coordinate
  const cutoffX = lastHistory ? lastHistory.x : paddingLeft + chartWidth / 2

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
      {/* Legend & Controls */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 'var(--space-3)',
          flexWrap: 'wrap',
          gap: 'var(--space-3)',
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: 'var(--space-4)',
            alignItems: 'center',
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
            }}
          >
            <span
              style={{
                width: 16,
                height: 3,
                backgroundColor: 'var(--color-ink)',
                display: 'inline-block',
              }}
            />
            <span style={{ fontSize: '0.8125rem', fontWeight: 600 }}>
              Факт (история NetCF)
            </span>
          </div>

          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 'var(--space-2)',
            }}
          >
            <span
              style={{
                width: 16,
                height: 3,
                borderTop: '3px dashed var(--color-accent)',
                display: 'inline-block',
              }}
            />
            <span
              style={{
                fontSize: '0.8125rem',
                fontWeight: 600,
                color: 'var(--color-accent)',
              }}
            >
              Прогноз NetCF
            </span>
          </div>

          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 'var(--space-1)',
              color: 'var(--color-muted)',
              fontSize: '0.75rem',
            }}
          >
            <span>| отсечка: {cutoffDate}</span>
          </div>
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

      {/* SVG Chart */}
      <p className='chart-scroll-hint'>
        График можно прокрутить по горизонтали
      </p>
      <div style={{ width: '100%', overflowX: 'auto' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{
            width: '100%',
            minWidth: '600px',
            height: 'auto',
            display: 'block',
          }}
          role='img'
          aria-label='График фактического денежного потока и рассчитанного прогноза'
        >
          {/* Zero line */}
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

          {/* Cutoff vertical separator line */}
          <line
            x1={cutoffX}
            y1={paddingTop}
            x2={cutoffX}
            y2={height - paddingBottom}
            stroke='var(--color-field-border)'
            strokeWidth='1.5'
          />
          <text
            x={cutoffX}
            y={paddingTop - 8}
            textAnchor='middle'
            fontSize='10'
            fill='var(--color-muted)'
            fontFamily='var(--font-body)'
            fontWeight='600'
          >
            отсечка {cutoffDate.slice(5)}
          </text>

          {/* Guide bounds */}
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

          {/* History line (solid ink) */}
          {historyD && (
            <path
              d={historyD}
              fill='none'
              stroke='var(--color-ink)'
              strokeWidth='2.5'
              strokeLinejoin='round'
              strokeLinecap='round'
            />
          )}

          {/* Forecast line (dashed coral) */}
          {forecastD && (
            <path
              d={forecastD}
              fill='none'
              stroke='var(--color-accent)'
              strokeWidth='2.5'
              strokeDasharray='6 4'
              strokeLinejoin='round'
              strokeLinecap='round'
            />
          )}

          {/* History points */}
          {historyCoords.map(p => (
            <circle
              key={p.point.date}
              cx={p.x}
              cy={p.y}
              r='3'
              fill='var(--color-paper)'
              stroke='var(--color-ink)'
              strokeWidth='1.5'
            >
              <title>{`Факт ${p.point.date}: ${formatNetCfRub(p.point.raw)}`}</title>
            </circle>
          ))}

          {/* Forecast points */}
          {forecastCoords.map(p => (
            <circle
              key={p.point.date}
              cx={p.x}
              cy={p.y}
              r='3.5'
              fill='var(--color-accent)'
              stroke='var(--color-paper)'
              strokeWidth='1.5'
            >
              <title>{`Прогноз ${p.point.date}: ${formatNetCfRub(p.point.raw)}`}</title>
            </circle>
          ))}

          {/* X Axis dates */}
          {allPoints.map((p, idx) => {
            const x = getX(idx)
            const isFirstForecast = historyLength > 0 && idx === historyLength

            // Omit first forecast date label if too close to cutoff date to avoid collision
            if (isFirstForecast && x - getX(historyLength - 1) < 35) {
              return null
            }

            const shouldLabel =
              idx === 0 ||
              idx === historyLength - 1 ||
              idx === historyLength ||
              idx === allPoints.length - 1 ||
              (allPoints.length <= 20 && idx % 3 === 0)

            if (!shouldLabel) return null
            const isForecastPoint = idx >= historyLength

            return (
              <text
                key={`label-${p.date}-${idx}`}
                x={x}
                y={height - paddingBottom + 16}
                textAnchor='middle'
                fontSize='10'
                fill={
                  isForecastPoint ? 'var(--color-accent)' : 'var(--color-muted)'
                }
                fontFamily='var(--font-body)'
                fontWeight={isForecastPoint ? '600' : '400'}
              >
                {p.date.slice(5)}
              </text>
            )
          })}
        </svg>
      </div>

      {/* Accessible Table */}
      {showTable && (
        <div
          style={{
            marginTop: 'var(--space-4)',
            maxHeight: '280px',
            overflowY: 'auto',
          }}
        >
          <table className='ledger-table' style={{ fontSize: '0.8125rem' }}>
            <thead>
              <tr>
                <th>Дата</th>
                <th>Тип точки</th>
                <th className='num-cell'>Ожидаемый чистый поток (NetCF)</th>
              </tr>
            </thead>
            <tbody>
              {forecastPoints.map(fp => (
                <tr key={fp.date}>
                  <td style={{ fontWeight: 600 }}>{fp.date}</td>
                  <td>
                    <span
                      className='badge'
                      style={{
                        backgroundColor: 'var(--color-accent)',
                        color: 'var(--color-accent-ink)',
                      }}
                    >
                      Прогноз
                    </span>
                  </td>
                  <td
                    className='num-cell'
                    style={{ fontWeight: 600, color: 'var(--color-accent)' }}
                  >
                    {formatNetCfRub(fp.net_cash_flow)}
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
