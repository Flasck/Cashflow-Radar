import { unstable_rethrow } from 'next/navigation'
import { serverFetch } from '@/lib/api-server'
import type {
  Company,
  DailyAnalyticsResponse,
  DailyAnalyticsItem,
} from '@/lib/types'
import ForecastView from './ForecastView'

export const dynamic = 'force-dynamic'

interface ForecastPageProps {
  params: Promise<{ companyId: string }>
}

export default async function ForecastPage({ params }: ForecastPageProps) {
  const { companyId } = await params

  // Server computed today in Europe/Moscow timezone (avoids UTC client hydration mismatch)
  const now = new Date()
  const todayMoscow = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Moscow',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)

  const company = await serverFetch<Company>(`/api/companies/${companyId}`)

  // Fetch recent daily analytics up to todayMoscow for initial chart context
  const past45Obj = new Date(now.getTime() - 45 * 24 * 60 * 60 * 1000)
  const fromStr = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Moscow',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(past45Obj)

  let initialHistory: DailyAnalyticsItem[] = []
  try {
    const dailyRes = await serverFetch<DailyAnalyticsResponse>(
      `/api/companies/${companyId}/analytics/daily?date_from=${fromStr}&date_to=${todayMoscow}`,
    )
    initialHistory = dailyRes.items || []
  } catch (err) {
    unstable_rethrow(err)
    // If no transactions yet or error
  }

  return (
    <main className='app-container' style={{ paddingTop: 'var(--space-4)' }}>
      <ForecastView
        company={company}
        initialHistory={initialHistory}
        todayMoscow={todayMoscow}
      />
    </main>
  )
}
