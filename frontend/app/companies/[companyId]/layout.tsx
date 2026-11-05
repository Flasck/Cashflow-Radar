import { serverFetch } from '@/lib/api-server'
import type { Company } from '@/lib/types'
import AppFrame from '@/components/AppFrame'

export const dynamic = 'force-dynamic'

export default async function CompanyLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ companyId: string }>
}) {
  const { companyId } = await params

  const currentCompany = await serverFetch<Company>(
    `/api/companies/${companyId}`,
  )

  return <AppFrame currentCompany={currentCompany}>{children}</AppFrame>
}
