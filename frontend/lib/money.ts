import type { TransactionDirection } from './types'

export interface ParsedMoneySuccess {
  ok: true
  amount: string
  direction: TransactionDirection
}

export interface ParsedMoneyError {
  ok: false
  error: string
}

export type ParsedMoneyResult = ParsedMoneySuccess | ParsedMoneyError

/**
 * Pure string parser for currency input without JavaScript float arithmetic.
 * Accepts: "+15000", "-15 000,50", "1234.56", "100 000".
 * Leading +/- determines direction. Unsigned input preserves defaultDirection.
 */
export function parseSignedMoney(
  rawInput: string,
  defaultDirection: TransactionDirection = 'inflow',
): ParsedMoneyResult {
  if (!rawInput || typeof rawInput !== 'string') {
    return { ok: false, error: 'Введите сумму' }
  }

  // 1. Trim whitespace
  let trimmed = rawInput.trim()
  if (trimmed.length === 0) {
    return { ok: false, error: 'Введите сумму' }
  }

  // 2. Determine explicit sign if present
  let direction = defaultDirection
  const firstChar = trimmed[0]

  if (firstChar === '+') {
    direction = 'inflow'
    trimmed = trimmed.slice(1).trim()
  } else if (
    firstChar === '-' ||
    firstChar === '\u2212' ||
    firstChar === '\u2013' ||
    firstChar === '\u2014'
  ) {
    direction = 'outflow'
    trimmed = trimmed.slice(1).trim()
  }

  if (trimmed.length === 0) {
    return { ok: false, error: 'Укажите числовое значение суммы' }
  }

  // 3. Strip grouping spaces (standard, non-breaking, narrow non-breaking)
  const cleaned = trimmed.replace(/[\s\u00A0\u202F]/g, '')

  if (cleaned.length === 0) {
    return { ok: false, error: 'Укажите числовое значение суммы' }
  }

  // 4. Check for multiple decimal separators
  const hasDot = cleaned.includes('.')
  const hasComma = cleaned.includes(',')

  if (hasDot && hasComma) {
    return {
      ok: false,
      error: 'Нельзя одновременно использовать точку и запятую',
    }
  }

  const dotCount = (cleaned.match(/\./g) || []).length
  const commaCount = (cleaned.match(/,/g) || []).length

  if (dotCount > 1 || commaCount > 1) {
    return { ok: false, error: 'Несколько разделителей дробной части' }
  }

  const sep = hasComma ? ',' : hasDot ? '.' : null
  let intPart = ''
  let fracPart = ''

  if (sep) {
    const parts = cleaned.split(sep)
    intPart = parts[0]
    fracPart = parts[1]
  } else {
    intPart = cleaned
    fracPart = ''
  }

  // 5. Validate characters
  if (intPart.length > 0 && !/^\d+$/.test(intPart)) {
    return { ok: false, error: 'Недопустимые символы в целой части суммы' }
  }
  if (fracPart.length > 0 && !/^\d+$/.test(fracPart)) {
    return { ok: false, error: 'Недопустимые символы в дробной части суммы' }
  }

  if (fracPart.length > 2) {
    return { ok: false, error: 'Не более двух знаков после запятой' }
  }

  // Normalize integer part
  intPart = intPart.replace(/^0+/, '')
  if (intPart.length === 0) {
    intPart = '0'
  }

  // Maximum digits check (PostgreSQL Numeric(15,2) -> max 13 digits in integer part)
  if (intPart.length > 13) {
    return { ok: false, error: 'Сумма превышает максимально допустимый размер' }
  }

  // Normalize fractional part to exactly 2 digits
  if (fracPart.length === 0) {
    fracPart = '00'
  } else if (fracPart.length === 1) {
    fracPart = fracPart + '0'
  }

  // 6. Check strictly positive (no zero amount)
  if (intPart === '0' && fracPart === '00') {
    return { ok: false, error: 'Сумма операции должна быть больше нуля' }
  }

  return {
    ok: true,
    amount: `${intPart}.${fracPart}`,
    direction,
  }
}

/**
 * Formats integer digits into space-separated thousands groups: "15000" -> "15 000".
 */
export function groupThousands(intStr: string): string {
  if (!intStr || intStr.length === 0) return '0'
  const clean = intStr.replace(/^0+(?=\d)/, '')
  return clean.replace(/\B(?=(\d{3})+(?!\d))/g, '\u00A0')
}

/**
 * Format decimal amount string (e.g. "15000.00") with Russian ledger conventions.
 */
export function formatMoneyRub(
  amount: string,
  direction?: TransactionDirection,
  options?: { showSign?: boolean; showSymbol?: boolean },
): string {
  if (!amount || typeof amount !== 'string') {
    return '0,00 ₽'
  }

  const [intPart = '0', fracPart = '00'] = amount.split('.')
  const formattedInt = groupThousands(intPart)
  const formattedFrac = (fracPart + '00').slice(0, 2)
  const base = `${formattedInt},${formattedFrac}`

  const showSign = options?.showSign ?? direction !== undefined
  const showSymbol = options?.showSymbol ?? true

  let signPrefix = ''
  if (showSign && direction === 'inflow') {
    signPrefix = '+'
  } else if (showSign && direction === 'outflow') {
    signPrefix = '\u2212' // Minus sign −
  }

  const suffix = showSymbol ? '\u00A0₽' : ''
  return `${signPrefix}${base}${suffix}`
}

/**
 * Formats Net Cash Flow which may be signed string like "-1500.00", "2500.00", "0.00".
 */
export function formatNetCfRub(
  netCf: string,
  options?: { showSymbol?: boolean },
): string {
  if (!netCf || typeof netCf !== 'string') {
    return '0,00 ₽'
  }

  let isNegative = false
  let trimmed = netCf.trim()

  if (trimmed.startsWith('-') || trimmed.startsWith('\u2212')) {
    isNegative = true
    trimmed = trimmed.replace(/^[-−]/, '').trim()
  } else if (trimmed.startsWith('+')) {
    trimmed = trimmed.slice(1).trim()
  }

  const [intPart = '0', fracPart = '00'] = trimmed.split('.')
  const formattedInt = groupThousands(intPart)
  const formattedFrac = (fracPart + '00').slice(0, 2)
  const isZero = formattedInt === '0' && formattedFrac === '00'

  const sign = isZero ? '' : isNegative ? '\u2212' : '+'
  const suffix = options?.showSymbol !== false ? '\u00A0₽' : ''

  return `${sign}${formattedInt},${formattedFrac}${suffix}`
}
