'use client'

import Link from 'next/link'
import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from 'react'
import type {
  DailyAnalyticsItem,
  TransactionsResponse,
  Category,
} from '@/lib/types'
import { formatNetCfRub, formatMoneyRub } from '@/lib/money'
import {
  axisTicks,
  cashflowSeries,
  hasActivity,
  toCents,
  fromCents,
  chartBuckets,
  clampWindow,
  zoomWindow,
  type ChartWindow,
} from '@/lib/cashflow-chart'
import { clientFetch } from '@/lib/api-client'
import Spinner from './ui/Spinner'

interface DailyChartProps {
  items: DailyAnalyticsItem[]
  companyId: string
  filters: string
  categories: Category[]
  canEdit: boolean
}

const shortDateFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
  timeZone: 'UTC',
})
const periodDateFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})
const fullDateFormat = new Intl.DateTimeFormat('ru-RU', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
  timeZone: 'UTC',
})
const compactFormat = new Intl.NumberFormat('ru-RU', {
  notation: 'compact',
  maximumFractionDigits: 1,
})
const shortDate = (date: string) =>
  shortDateFormat.format(new Date(`${date}T00:00:00Z`))
const fullDate = (date: string) =>
  fullDateFormat.format(new Date(`${date}T00:00:00Z`))
const compact = (value: number) => compactFormat.format(value)
const periodLabel = (items: DailyAnalyticsItem[]) => {
  if (!items.length) return ''
  const first = new Date(`${items[0].date}T00:00:00Z`)
  const last = new Date(`${items[items.length - 1].date}T00:00:00Z`)
  return periodDateFormat.formatRange(first, last).replace(/\s/g, ' ')
}

function DayPayments({
  date,
  companyId,
  filters,
  categories,
  canEdit,
}: Omit<DailyChartProps, 'items'> & { date: string }) {
  const [result, setResult] = useState<TransactionsResponse | null>(null)
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      const query = new URLSearchParams(filters)
      query.set('date_from', date)
      query.set('date_to', date)
      query.set('page', String(page))
      query.set('page_size', '5')
      clientFetch<TransactionsResponse>(
        `/api/companies/${companyId}/transactions?${query}`,
        { signal: controller.signal },
      )
        .then(data => {
          if (!controller.signal.aborted) {
            setResult(data)
            setError('')
          }
        })
        .catch(() => {
          if (!controller.signal.aborted)
            setError('Не удалось загрузить платежи за день')
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false)
        })
    }, 180)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [date, companyId, filters, page, retry])

  return (
    <div className='day-payments' aria-busy={loading}>
      <div className='day-payments-heading'>
        <h4>Платежи за день</h4>
        {result && <span>{result.total}</span>}
      </div>
      {loading && (
        <p className='loading-status' role='status'>
          <Spinner /> Загружаем платежи…
        </p>
      )}
      {!loading && error ? (
        <div role='alert'>
          <p className='form-error'>{error}</p>
          <button
            type='button'
            className='text-button'
            onClick={() => {
              setLoading(true)
              setRetry(value => value + 1)
            }}
          >
            Повторить
          </button>
        </div>
      ) : (
        !loading &&
        result && (
          <>
            {result.total === 0 ? (
              <p className='muted'>В этот день операций нет.</p>
            ) : (
              <ul className='day-payment-list'>
                {result.items.map(tx => (
                  <li key={tx.id}>
                    <div>
                      <span>{tx.purpose || 'Без назначения'}</span>
                      <small>
                        {categories.find(
                          category => category.id === tx.category_id,
                        )?.name ?? 'Без категории'}
                      </small>
                    </div>
                    <strong className={`amount-${tx.direction}`}>
                      {formatMoneyRub(tx.amount, tx.direction)}
                    </strong>
                    {canEdit && (
                      <Link
                        href={`/companies/${companyId}/transactions/${tx.id}`}
                        aria-label={`Открыть платёж: ${tx.purpose || 'Без назначения'}`}
                      >
                        Открыть
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {result.total > 5 && (
              <div className='day-payment-pages'>
                <button
                  type='button'
                  className='btn btn-secondary'
                  disabled={page === 1 || loading}
                  onClick={() => {
                    setLoading(true)
                    setPage(value => value - 1)
                  }}
                  aria-label='Предыдущие платежи за день'
                >
                  ←
                </button>
                <span>
                  {page} / {Math.ceil(result.total / 5)}
                </span>
                <button
                  type='button'
                  className='btn btn-secondary'
                  disabled={page * 5 >= result.total || loading}
                  onClick={() => {
                    setLoading(true)
                    setPage(value => value + 1)
                  }}
                  aria-label='Следующие платежи за день'
                >
                  →
                </button>
              </div>
            )}
          </>
        )
      )}
    </div>
  )
}

export default function DailyChart({ items, ...details }: DailyChartProps) {
  const series = useMemo(() => cashflowSeries(items), [items])
  const [window, setWindow] = useState<ChartWindow>({
    start: 0,
    count: items.length || 1,
  })
  const view = clampWindow(window.start, window.count, items.length)
  const [active, setActive] = useState<number | null>(null)
  const [pinned, setPinned] = useState(false)
  const [width, setWidth] = useState(900)
  const plot = useRef<HTMLDivElement>(null)
  const drag = useRef<{ x: number; start: number; moved: boolean } | null>(null)
  const clipId = useId()
  const hintId = useId()
  useEffect(() => {
    const element = plot.current
    if (!element) return
    const observer = new ResizeObserver(entries =>
      setWidth(Math.max(280, entries[0].contentRect.width)),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const visible = series.slice(view.start, view.start + view.count)
  const { buckets, size } = chartBuckets(
    visible,
    Math.max(14, Math.floor((width - 130) / 10)),
  )
  const left = width < 500 ? 50 : 64
  const right = 24
  const top = 20
  const bottom = 286
  const plotWidth = width - left - right
  const flowValues = buckets.flatMap(item => [
    Number(item.inflow),
    -Number(item.outflow),
  ])
  const totalValues = visible.map(item => Number(item.cumulative))
  const flowTicks = axisTicks(
    Math.min(0, ...flowValues),
    Math.max(0, ...flowValues),
  )
  const totalTicks = axisTicks(
    Math.min(0, ...totalValues),
    Math.max(0, ...totalValues),
    3,
  )
  const scale = (value: number, ticks: number[], start: number, end: number) =>
    end -
    ((value - ticks[0]) / (ticks[ticks.length - 1] - ticks[0])) * (end - start)
  const x = (index: number) => left + ((index + 0.5) / view.count) * plotWidth
  const y = (value: number) => scale(value, flowTicks, 216, bottom)
  const totalY = (value: number) => scale(value, totalTicks, top, 168)
  const zero = y(0)
  const selectedIndex = active ?? -1
  const selected = series[selectedIndex]
  const activeVisible =
    !!selected &&
    selectedIndex >= view.start &&
    selectedIndex < view.start + view.count
  const hasData = items.some(hasActivity)
  const totals = series.reduce(
    (sum, day) => ({
      inflow: sum.inflow + toCents(day.inflow),
      outflow: sum.outflow + toCents(day.outflow),
    }),
    { inflow: 0n, outflow: 0n },
  )
  const overviewMax = Math.max(
    1,
    ...series.map(day => Math.abs(Number(day.cumulative))),
  )
  const line = visible
    .map(
      (item, index) =>
        `${index === 0 ? 'M' : 'L'}${x(index).toFixed(2)},${totalY(Number(item.cumulative)).toFixed(2)}`,
    )
    .join(' ')
  const zoom = (factor: number, anchor = 0.5) =>
    setWindow(previous =>
      zoomWindow(
        clampWindow(previous.start, previous.count, items.length),
        previous.count * factor,
        items.length,
        anchor,
      ),
    )

  useEffect(() => {
    const element = plot.current
    if (!element) return
    const wheel = (event: WheelEvent) => {
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault()
        const rect = element.getBoundingClientRect()
        const anchor = Math.max(
          0,
          Math.min(1, (event.clientX - rect.left - left) / plotWidth),
        )
        setWindow(previous =>
          zoomWindow(
            previous,
            previous.count * (event.deltaY > 0 ? 1.2 : 0.8),
            items.length,
            anchor,
          ),
        )
      } else if (
        view.count < items.length &&
        (event.shiftKey || Math.abs(event.deltaX) > Math.abs(event.deltaY))
      ) {
        event.preventDefault()
        setWindow(previous =>
          clampWindow(
            previous.start +
              ((event.deltaX || event.deltaY) / plotWidth) * previous.count,
            previous.count,
            items.length,
          ),
        )
      }
    }
    element.addEventListener('wheel', wheel, { passive: false })
    return () => element.removeEventListener('wheel', wheel)
  }, [items.length, left, plotWidth, view.count])

  if (!hasData)
    return (
      <section className='cashflow-chart'>
        <div className='chart-heading'>
          <h2>Движение денег</h2>
          {items.length > 0 && (
            <span className='chart-period'>{periodLabel(items)}</span>
          )}
        </div>
        <div className='chart-empty'>
          <svg
            width='48'
            height='36'
            viewBox='0 0 48 36'
            fill='none'
            aria-hidden='true'
          >
            <path
              d='M3 3v30h42M12 23l9-9 8 5 13-13'
              stroke='currentColor'
              strokeWidth='1.5'
              strokeLinecap='round'
              strokeLinejoin='round'
            />
          </svg>
          <p>За выбранный период операций нет</p>
          <span>Выберите другой период или измените фильтры.</span>
        </div>
      </section>
    )

  function indexAt(clientX: number) {
    const rect = plot.current!.getBoundingClientRect()
    return Math.max(
      view.start,
      Math.min(
        view.start + view.count - 1,
        view.start +
          Math.floor(((clientX - rect.left - left) / plotWidth) * view.count),
      ),
    )
  }

  return (
    <section
      className='cashflow-chart'
      aria-labelledby={`${hintId}-title`}
      onKeyDown={event => {
        if (event.key === 'Escape') {
          setPinned(false)
          setActive(null)
        }
      }}
    >
      <div className='chart-heading'>
        <div className='chart-title'>
          <h2 id={`${hintId}-title`}>Движение денег</h2>
          <details
            className='chart-info'
            onKeyDown={event => {
              if (event.key === 'Escape') {
                event.currentTarget.open = false
                event.currentTarget.querySelector('summary')?.focus()
              }
            }}
          >
            <summary aria-label='Как пользоваться графиком'>?</summary>
            <div className='chart-info-content' id={hintId}>
              <strong>Как читать график</strong>
              <p>
                Столбцы — поступления и выплаты, линия — накопленный поток с
                начала выбранного периода. Сверху — накопление, снизу — дневные
                суммы; у каждой области своя шкала в рублях. Это не остаток на
                счёте.
              </p>
              <p>
                Наведите на день для просмотра. Клик или касание закрепляет
                день; повторный клик, крестик или Escape снимает закрепление.
              </p>
              <p>
                Кнопки + и − приближают график внутри периода из фильтров.
                Сдвигайте окно перетаскиванием, полосой снизу или горизонтальным
                скроллом. Ctrl/⌘ + колесо — масштаб; обычный скролл прокручивает
                страницу.
              </p>
              <p>
                Клавиатура: ← →, Home/End — дни, Enter — закрепить, Escape —
                снять, +/− — масштаб.
              </p>
              {size > 1 && (
                <p>
                  Столбцы объединены по {size} дней. Приблизьте, чтобы увидеть
                  отдельные дни; детали всегда за конкретную дату.
                </p>
              )}
            </div>
          </details>
        </div>
        <span className='chart-period'>{periodLabel(items)}</span>
      </div>
      <div className='chart-legend'>
        <span>
          <i className='legend-inflow' />
          Поступления
        </span>
        <span>
          <i className='legend-outflow' />
          Выплаты
        </span>
        <span>
          <i className='legend-cumulative' />
          Накопленный поток
        </span>
      </div>
      <div className='cashflow-chart-grid'>
        <div className='chart-main'>
          <div
            className='cashflow-plot'
            ref={plot}
            role='group'
            aria-label='Интерактивный график движения денег'
            tabIndex={0}
            onKeyDown={event => {
              if (
                event.key === 'ArrowLeft' ||
                event.key === 'ArrowRight' ||
                event.key === 'Home' ||
                event.key === 'End'
              ) {
                event.preventDefault()
                const next =
                  event.key === 'Home'
                    ? view.start
                    : event.key === 'End'
                      ? view.start + view.count - 1
                      : Math.max(
                          0,
                          Math.min(
                            items.length - 1,
                            (selectedIndex < 0 ? view.start : selectedIndex) +
                              (event.key === 'ArrowRight' ? 1 : -1),
                          ),
                        )
                setActive(next)
                if (next < view.start || next >= view.start + view.count)
                  setWindow(
                    clampWindow(
                      next < view.start ? next : next - view.count + 1,
                      view.count,
                      items.length,
                    ),
                  )
              } else if (event.key === '+' || event.key === '=') {
                event.preventDefault()
                zoom(0.5)
              } else if (event.key === '-') {
                event.preventDefault()
                zoom(2)
              } else if (event.key === 'Escape') {
                setPinned(false)
                setActive(null)
              } else if (event.key === 'Enter') {
                if (active === null) setActive(view.start)
                setPinned(value => !value)
              }
            }}
            onPointerDown={event => {
              if (event.button !== 0) return
              drag.current = {
                x: event.clientX,
                start: view.start,
                moved: false,
              }
              event.currentTarget.setPointerCapture(event.pointerId)
            }}
            onPointerMove={event => {
              if (
                drag.current &&
                Math.abs(event.clientX - drag.current.x) > 5
              ) {
                drag.current.moved = true
                setWindow(
                  clampWindow(
                    drag.current.start -
                      ((event.clientX - drag.current.x) / plotWidth) *
                        view.count,
                    view.count,
                    items.length,
                  ),
                )
              } else if (!pinned && !drag.current?.moved)
                setActive(indexAt(event.clientX))
            }}
            onPointerUp={event => {
              if (drag.current && !drag.current.moved) {
                const next = indexAt(event.clientX)
                if (pinned && active === next) {
                  setPinned(false)
                  setActive(null)
                } else {
                  setActive(next)
                  setPinned(true)
                }
              }
              drag.current = null
              if (event.currentTarget.hasPointerCapture(event.pointerId))
                event.currentTarget.releasePointerCapture(event.pointerId)
            }}
            onPointerCancel={() => {
              drag.current = null
            }}
            onLostPointerCapture={() => {
              drag.current = null
            }}
          >
            <svg
              viewBox={`0 0 ${width} 322`}
              preserveAspectRatio='none'
              role='img'
              aria-label={`Поступления, выплаты и накопленный денежный поток: ${shortDate(visible[0].date)} — ${shortDate(visible[visible.length - 1].date)}`}
            >
              <defs>
                <clipPath id={clipId}>
                  <rect
                    x={left}
                    y={top - 4}
                    width={plotWidth}
                    height={bottom - top + 8}
                  />
                </clipPath>
              </defs>
              <text x={left} y={12} className='chart-axis-label'>
                Накопленный поток, ₽
              </text>
              <text x={left} y={201} className='chart-axis-label'>
                Поступления / выплаты, ₽{size > 1 ? ` · за ${size} дн.` : ''}
              </text>
              {totalTicks.map(tick => (
                <g key={tick}>
                  <line
                    x1={left}
                    x2={width - right}
                    y1={totalY(tick)}
                    y2={totalY(tick)}
                    className={tick === 0 ? 'chart-zero' : 'chart-gridline'}
                  />
                  <text
                    x={left - 8}
                    y={totalY(tick) + 4}
                    textAnchor='end'
                    className='chart-axis-label'
                  >
                    {compact(tick)}
                  </text>
                </g>
              ))}
              {flowTicks.map(tick => (
                <g key={tick}>
                  <line
                    x1={left}
                    x2={width - right}
                    y1={y(tick)}
                    y2={y(tick)}
                    className={tick === 0 ? 'chart-zero' : 'chart-gridline'}
                  />
                  <text
                    x={left - 8}
                    y={y(tick) + 4}
                    textAnchor='end'
                    className='chart-axis-label'
                  >
                    {compact(tick)}
                  </text>
                </g>
              ))}
              <g clipPath={`url(#${clipId})`}>
                {activeVisible && (
                  <rect
                    x={
                      x(selectedIndex - view.start) - plotWidth / view.count / 2
                    }
                    y={top}
                    width={plotWidth / view.count}
                    height={bottom - top}
                    className='chart-active-band'
                  />
                )}
                {buckets.map(bucket => {
                  const center = x(bucket.start + (bucket.count - 1) / 2)
                  const barWidth = Math.max(
                    1,
                    Math.min(13, (plotWidth / view.count) * bucket.count * 0.3),
                  )
                  return (
                    <g key={bucket.start}>
                      <rect
                        className='cashflow-bar inflow-bar'
                        x={center - barWidth - 1}
                        y={y(Number(bucket.inflow))}
                        width={barWidth}
                        height={Math.max(0, zero - y(Number(bucket.inflow)))}
                        rx='1.5'
                      />
                      <rect
                        className='cashflow-bar outflow-bar'
                        x={center + 1}
                        y={zero}
                        width={barWidth}
                        height={Math.max(0, y(-Number(bucket.outflow)) - zero)}
                        rx='1.5'
                      />
                    </g>
                  )
                })}
                <path d={line} className='cumulative-line' />
                {visible.length === 1 && (
                  <circle
                    cx={x(0)}
                    cy={totalY(Number(visible[0].cumulative))}
                    r='4'
                    className='cumulative-point'
                  />
                )}
                {activeVisible && (
                  <>
                    <line
                      x1={x(selectedIndex - view.start)}
                      x2={x(selectedIndex - view.start)}
                      y1={top}
                      y2={bottom}
                      className='chart-crosshair'
                    />
                    <circle
                      cx={x(selectedIndex - view.start)}
                      cy={totalY(Number(selected.cumulative))}
                      r='4.5'
                      className='cumulative-point'
                    />
                  </>
                )}
              </g>
              {Array.from(
                new Set([
                  0,
                  ...Array.from({ length: width < 500 ? 3 : 6 }, (_, index) =>
                    Math.round(
                      (index * (view.count - 1)) / (width < 500 ? 2 : 5),
                    ),
                  ),
                  view.count - 1,
                ]),
              ).map(index => (
                <text
                  key={index}
                  x={x(index)}
                  y={311}
                  textAnchor='middle'
                  className='chart-axis-label'
                >
                  {shortDate(visible[index].date)}
                </text>
              ))}
            </svg>
          </div>
          <div className='chart-navigator'>
            <button
              type='button'
              className='btn btn-secondary'
              aria-label='Уменьшить масштаб'
              disabled={view.count >= items.length}
              onClick={() => zoom(2)}
            >
              −
            </button>
            <button
              type='button'
              className='btn btn-secondary'
              aria-label='Увеличить масштаб'
              disabled={view.count <= Math.min(7, items.length)}
              onClick={() => zoom(0.5)}
            >
              +
            </button>
            {view.count < items.length && (
              <button
                type='button'
                className='text-button chart-reset'
                onClick={() => setWindow({ start: 0, count: items.length })}
              >
                Весь период
              </button>
            )}
            <div
              className='chart-scrollbar'
              data-zoomed={view.count < items.length}
            >
              <svg
                viewBox='0 0 1000 24'
                preserveAspectRatio='none'
                aria-hidden='true'
              >
                <path
                  d={series
                    .map(
                      (day, index) =>
                        `${index ? 'L' : 'M'}${((index / Math.max(1, series.length - 1)) * 1000).toFixed(1)},${(12 - (Number(day.cumulative) / overviewMax) * 10).toFixed(1)}`,
                    )
                    .join(' ')}
                />
              </svg>
              <input
                type='range'
                min={0}
                max={Math.max(0, items.length - view.count)}
                step={1}
                value={view.start}
                disabled={view.count === items.length}
                style={
                  {
                    '--scroll-thumb': `${Math.max(8, (view.count / items.length) * 100)}%`,
                  } as CSSProperties
                }
                aria-label='Положение графика в периоде'
                onChange={event =>
                  setWindow(
                    clampWindow(
                      Number(event.target.value),
                      view.count,
                      items.length,
                    ),
                  )
                }
              />
            </div>
            {view.count < items.length && (
              <span className='chart-visible-period'>
                {shortDate(visible[0].date)} —{' '}
                {shortDate(visible[visible.length - 1].date)}
              </span>
            )}
          </div>
        </div>
        <aside className='chart-day-detail' aria-label='Детали выбранного дня'>
          <div className='chart-day-heading'>
            <h3 aria-live={pinned ? 'polite' : 'off'}>
              {selected ? fullDate(selected.date) : 'За выбранный период'}
            </h3>
            {pinned && (
              <button
                type='button'
                className='text-button'
                aria-label='Снять выделение дня'
                onClick={() => {
                  setPinned(false)
                  setActive(null)
                }}
              >
                Закреплено ×
              </button>
            )}
          </div>
          <dl className='chart-day-totals'>
            <div>
              <dt>Поступления</dt>
              <dd className='amount-inflow'>
                {selected && !hasActivity(selected)
                  ? '—'
                  : formatMoneyRub(
                      selected?.inflow ?? fromCents(totals.inflow),
                      'inflow',
                    )}
              </dd>
            </div>
            <div>
              <dt>Выплаты</dt>
              <dd className='amount-outflow'>
                {selected && !hasActivity(selected)
                  ? '—'
                  : formatMoneyRub(
                      selected?.outflow ?? fromCents(totals.outflow),
                      'outflow',
                    )}
              </dd>
            </div>
            <div>
              <dt>Чистый поток{selected ? ' за день' : ''}</dt>
              <dd>
                {selected && !hasActivity(selected)
                  ? '—'
                  : formatNetCfRub(
                      selected?.net_cash_flow ??
                        series[series.length - 1].cumulative,
                    )}
              </dd>
            </div>
            <div>
              <dt>Накоплено с начала периода</dt>
              <dd>
                {formatNetCfRub(
                  selected?.cumulative ?? series[series.length - 1].cumulative,
                )}
              </dd>
            </div>
          </dl>
          {selected ? (
            <DayPayments
              key={`${selected.date}:${details.filters}`}
              date={selected.date}
              {...details}
            />
          ) : (
            <p className='chart-idle'>
              Наведите на день, чтобы увидеть операции.
            </p>
          )}
        </aside>
      </div>
      <noscript>
        <p className='muted'>
          Масштаб и детали платежей доступны с JavaScript. Все операции и сводка
          по дням доступны ниже.
        </p>
      </noscript>
    </section>
  )
}
