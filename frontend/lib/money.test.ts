import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { parseSignedMoney, formatMoneyRub, formatNetCfRub } from './money.ts'

describe('Signed Money Parser (pure string)', () => {
  it('parses plain unsigned integer with default direction', () => {
    const res = parseSignedMoney('15000', 'inflow')
    assert.deepEqual(res, { ok: true, amount: '15000.00', direction: 'inflow' })
  })

  it('preserves outflow default direction when unsigned', () => {
    const res = parseSignedMoney('500', 'outflow')
    assert.deepEqual(res, { ok: true, amount: '500.00', direction: 'outflow' })
  })

  it('parses explicit plus as inflow', () => {
    const res = parseSignedMoney('+2 500,50', 'outflow')
    assert.deepEqual(res, { ok: true, amount: '2500.50', direction: 'inflow' })
  })

  it('parses explicit minus as outflow', () => {
    const res = parseSignedMoney('-15 000,00', 'inflow')
    assert.deepEqual(res, {
      ok: true,
      amount: '15000.00',
      direction: 'outflow',
    })
  })

  it('parses unicode minus character', () => {
    const res = parseSignedMoney('−850.7', 'inflow')
    assert.deepEqual(res, { ok: true, amount: '850.70', direction: 'outflow' })
  })

  it('parses en-dash and em-dash as outflow', () => {
    const resEn = parseSignedMoney('–1200.50', 'inflow')
    assert.deepEqual(resEn, {
      ok: true,
      amount: '1200.50',
      direction: 'outflow',
    })

    const resEm = parseSignedMoney('—3400,00', 'inflow')
    assert.deepEqual(resEm, {
      ok: true,
      amount: '3400.00',
      direction: 'outflow',
    })
  })

  it('handles trailing dot and comma separator', () => {
    const resDot = parseSignedMoney('1500.', 'inflow')
    assert.deepEqual(resDot, {
      ok: true,
      amount: '1500.00',
      direction: 'inflow',
    })

    const resComma = parseSignedMoney('-2500,', 'inflow')
    assert.deepEqual(resComma, {
      ok: true,
      amount: '2500.00',
      direction: 'outflow',
    })
  })

  it('handles spaces, non-breaking spaces and narrow spaces', () => {
    const input = '1\u00A0234\u202F567.89'
    const res = parseSignedMoney(input, 'inflow')
    assert.deepEqual(res, {
      ok: true,
      amount: '1234567.89',
      direction: 'inflow',
    })
  })

  it('handles dot decimal separator', () => {
    const res = parseSignedMoney('123.45', 'inflow')
    assert.deepEqual(res, { ok: true, amount: '123.45', direction: 'inflow' })
  })

  it('handles comma decimal separator', () => {
    const res = parseSignedMoney('123,45', 'inflow')
    assert.deepEqual(res, { ok: true, amount: '123.45', direction: 'inflow' })
  })

  it('normalizes single decimal digit with trailing zero', () => {
    const res = parseSignedMoney('123.4', 'inflow')
    assert.deepEqual(res, { ok: true, amount: '123.40', direction: 'inflow' })
  })

  it('normalizes leading decimal separator to zero integer part', () => {
    const res = parseSignedMoney('.75', 'inflow')
    assert.deepEqual(res, { ok: true, amount: '0.75', direction: 'inflow' })
  })

  it('rejects multiple decimal points', () => {
    const res = parseSignedMoney('12.34.56', 'inflow')
    assert.equal(res.ok, false)
    if (!res.ok) {
      assert.match(res.error, /Несколько разделителей/)
    }
  })

  it('rejects simultaneous comma and dot', () => {
    const res = parseSignedMoney('12,345.67', 'inflow')
    assert.equal(res.ok, false)
    if (!res.ok) {
      assert.match(
        res.error,
        /Нельзя одновременно использовать точку и запятую/,
      )
    }
  })

  it('rejects more than 2 decimal digits', () => {
    const res = parseSignedMoney('100.123', 'inflow')
    assert.equal(res.ok, false)
    if (!res.ok) {
      assert.match(res.error, /Не более двух знаков/)
    }
  })

  it('rejects zero amount', () => {
    const res = parseSignedMoney('0.00', 'inflow')
    assert.equal(res.ok, false)
    if (!res.ok) {
      assert.match(res.error, /больше нуля/)
    }
  })

  it('rejects invalid characters and scientific notation', () => {
    const res1 = parseSignedMoney('1e5', 'inflow')
    assert.equal(res1.ok, false)

    const res2 = parseSignedMoney('abc', 'inflow')
    assert.equal(res2.ok, false)

    const res3 = parseSignedMoney('15000$', 'inflow')
    assert.equal(res3.ok, false)
  })
})

describe('Money Formatter (Russian ledger)', () => {
  it('formats inflow with plus sign and ruble symbol', () => {
    const out = formatMoneyRub('15000.00', 'inflow')
    assert.equal(out, '+15\u00A0000,00\u00A0₽')
  })

  it('formats outflow with unicode minus sign and ruble symbol', () => {
    const out = formatMoneyRub('15000.00', 'outflow')
    assert.equal(out, '−15\u00A0000,00\u00A0₽')
  })

  it('formats NetCF with negative, positive and zero correctly', () => {
    assert.equal(formatNetCfRub('-15000.00'), '−15\u00A0000,00\u00A0₽')
    assert.equal(formatNetCfRub('25000.50'), '+25\u00A0000,50\u00A0₽')
    assert.equal(formatNetCfRub('0.00'), '0,00\u00A0₽')
  })
})
