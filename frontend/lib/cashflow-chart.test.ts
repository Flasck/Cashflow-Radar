import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  axisTicks,
  cashflowSeries,
  hasActivity,
  chartBuckets,
  clampWindow,
  fromCents,
  toCents,
  zoomWindow,
} from './cashflow-chart.ts'

const days = [
  {
    date: '2026-11-01',
    inflow: '0.30',
    outflow: '0.10',
    net_cash_flow: '0.20',
  },
  {
    date: '2026-11-02',
    inflow: '0.00',
    outflow: '0.25',
    net_cash_flow: '-0.25',
  },
  {
    date: '2026-11-03',
    inflow: '0.00',
    outflow: '0.00',
    net_cash_flow: '0.00',
  },
]

describe('Cashflow chart data', () => {
  it('distinguishes absent operations from a real zero net flow', () => {
    assert.equal(hasActivity(days[2]), false)
    assert.equal(
      hasActivity({ ...days[2], inflow: '1.00', outflow: '1.00' }),
      true,
    )
    assert.equal(
      hasActivity({ ...days[2], inflow: '0', outflow: '0.0' }),
      false,
    )
  })
  it('accumulates exact cents and carries the total over empty days', () => {
    assert.deepEqual(
      cashflowSeries(days).map(day => day.cumulative),
      ['0.20', '-0.05', '-0.05'],
    )
  })
  it('preserves large decimal values without floating point arithmetic', () => {
    assert.equal(
      fromCents(toCents('9999999999999.99') + toCents('0.01')),
      '10000000000000.00',
    )
    assert.equal(fromCents(toCents('-0.01')), '-0.01')
  })
  it('aggregates both directions separately and uses the closing cumulative value', () => {
    const { buckets, size } = chartBuckets(cashflowSeries(days), 2)
    assert.equal(size, 2)
    assert.deepEqual(buckets[0], {
      start: 0,
      count: 2,
      inflow: '0.30',
      outflow: '0.35',
      cumulative: '-0.05',
    })
    assert.equal(buckets[1].count, 1)
  })
  it('keeps viewport within period and preserves the zoom anchor', () => {
    assert.deepEqual(clampWindow(-10, 30, 90), { start: 0, count: 30 })
    assert.deepEqual(clampWindow(80, 30, 90), { start: 60, count: 30 })
    assert.deepEqual(zoomWindow({ start: 0, count: 90 }, 30, 90, 1), {
      start: 60,
      count: 30,
    })
    assert.deepEqual(zoomWindow({ start: 60, count: 30 }, 90, 90), {
      start: 0,
      count: 90,
    })
    assert.deepEqual(zoomWindow({ start: 0, count: 3 }, 1, 3), {
      start: 0,
      count: 3,
    })
  })
  it('creates bounded readable ticks including zero and both extremes', () => {
    const ticks = axisTicks(-14200, 18200)
    assert.ok(ticks[0] <= -14200 && ticks.at(-1)! >= 18200)
    assert.ok(ticks.includes(0) && ticks.length < 10)
    assert.deepEqual(axisTicks(0, 0), [-1, 0, 1])
  })
  it('handles empty and single-day series, negative totals and sub-ruble axes', () => {
    assert.deepEqual(cashflowSeries([]), [])
    assert.deepEqual(chartBuckets([]), { buckets: [], size: 1 })
    assert.deepEqual(clampWindow(10, 0, 0), { start: 0, count: 1 })
    assert.deepEqual(zoomWindow({ start: 0, count: 1 }, 30, 1), {
      start: 0,
      count: 1,
    })
    assert.equal(cashflowSeries([days[1]])[0].cumulative, '-0.25')
    assert.ok(axisTicks(-0.01, 0.03).includes(0))
  })
})
