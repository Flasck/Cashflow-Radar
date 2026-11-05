import type { DailyAnalyticsItem } from './types'

export function toCents(value: string): bigint {
  const negative = value.startsWith('-')
  const [whole, fraction = ''] = value.replace(/^[+-]/, '').split('.')
  const cents =
    BigInt(whole || '0') * 100n + BigInt((fraction + '00').slice(0, 2))
  return negative ? -cents : cents
}

export function fromCents(value: bigint): string {
  const absolute = value < 0n ? -value : value
  return `${value < 0n ? '-' : ''}${absolute / 100n}.${String(absolute % 100n).padStart(2, '0')}`
}

export function hasActivity(item: DailyAnalyticsItem): boolean {
  return toCents(item.inflow) !== 0n || toCents(item.outflow) !== 0n
}

export function cashflowSeries(items: DailyAnalyticsItem[]) {
  let cumulative = 0n
  return items.map(item => {
    cumulative += toCents(item.inflow) - toCents(item.outflow)
    return { ...item, cumulative: fromCents(cumulative) }
  })
}

export interface ChartWindow {
  start: number
  count: number
}

export function clampWindow(
  start: number,
  count: number,
  total: number,
): ChartWindow {
  const boundedCount = Math.max(1, Math.min(total || 1, Math.round(count)))
  return {
    start: Math.max(0, Math.min(Math.round(start), total - boundedCount)),
    count: boundedCount,
  }
}

export function zoomWindow(
  window: ChartWindow,
  count: number,
  total: number,
  anchor = 0.5,
): ChartWindow {
  const nextCount = Math.max(
    Math.min(7, total),
    Math.min(total, Math.round(count)),
  )
  return clampWindow(
    window.start + (window.count - nextCount) * anchor,
    nextCount,
    total,
  )
}

export function chartBuckets(
  items: ReturnType<typeof cashflowSeries>,
  maxBars = 100,
) {
  const size = Math.max(1, Math.ceil(items.length / maxBars))
  const buckets = []
  for (let start = 0; start < items.length; start += size) {
    const group = items.slice(start, start + size)
    const inflow = group.reduce((sum, day) => sum + toCents(day.inflow), 0n)
    const outflow = group.reduce((sum, day) => sum + toCents(day.outflow), 0n)
    buckets.push({
      start,
      count: group.length,
      inflow: fromCents(inflow),
      outflow: fromCents(outflow),
      cumulative: group[group.length - 1].cumulative,
    })
  }
  return { buckets, size }
}

export function axisTicks(min: number, max: number, target = 4) {
  if (min === 0 && max === 0) return [-1, 0, 1]
  const raw = (max - min || Math.abs(max) || 1) / target
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const ratio = raw / magnitude
  const step =
    (ratio <= 1 ? 1 : ratio <= 2 ? 2 : ratio <= 5 ? 5 : 10) * magnitude
  const first = Math.floor(min / step) * step
  const last = Math.ceil(max / step) * step
  return Array.from(
    { length: Math.round((last - first) / step) + 1 },
    (_, index) => Number((first + index * step).toPrecision(12)),
  )
}
