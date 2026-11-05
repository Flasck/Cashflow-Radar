export function dateISO(date: Date): string {
  return date.toISOString().slice(0, 10)
}

export function shiftDate(value: string, days: number): string {
  const date = new Date(`${value}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return dateISO(date)
}

export function shiftMonth(value: string, months: number): string {
  const date = new Date(`${value}T00:00:00Z`)
  const day = date.getUTCDate()
  date.setUTCDate(1)
  date.setUTCMonth(date.getUTCMonth() + months)
  const end = new Date(date.getTime())
  end.setUTCMonth(end.getUTCMonth() + 1, 0)
  date.setUTCDate(Math.min(day, end.getUTCDate()))
  return dateISO(date)
}

export function monthDays(value: string): string[] {
  const first = `${value.slice(0, 7)}-01`
  const weekday = (new Date(`${first}T00:00:00Z`).getUTCDay() + 6) % 7
  return Array.from({ length: 42 }, (_, index) =>
    shiftDate(first, index - weekday),
  )
}

export function boundDate(value: string, min?: string, max?: string): string {
  return min && value < min ? min : max && value > max ? max : value
}
