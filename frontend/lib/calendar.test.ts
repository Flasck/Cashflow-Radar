import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { boundDate, monthDays, shiftDate, shiftMonth } from './calendar.ts'

describe('Calendar dates (UTC, Monday first)', () => {
  it('builds complete Monday-first weeks across year boundaries', () => {
    const days = monthDays('2026-01-15')
    assert.equal(days.length, 42)
    assert.equal(days[0], '2025-12-29')
    assert.equal(days[41], '2026-02-08')
  })
  it('preserves the day where possible and clamps at month end', () => {
    assert.equal(shiftMonth('2024-01-31', 1), '2024-02-29')
    assert.equal(shiftMonth('2026-03-31', -1), '2026-02-28')
    assert.equal(shiftMonth('2026-12-15', 1), '2027-01-15')
    assert.equal(shiftDate('2024-02-28', 1), '2024-02-29')
  })
  it('enforces both date bounds', () => {
    assert.equal(boundDate('2026-01-01', '2026-02-01'), '2026-02-01')
    assert.equal(boundDate('2026-12-01', undefined, '2026-11-05'), '2026-11-05')
  })
})
