export type CompanyRole = 'owner' | 'treasurer' | 'viewer'

export type TransactionDirection = 'inflow' | 'outflow'

export interface User {
  id: number
  full_name: string
  email: string
}

export interface Company {
  id: number
  name: string
  industry_code: string | null
  role: CompanyRole
  last_operation_date: string | null
}

export interface Category {
  id: number
  company_id: number
  name: string
}

export interface Transaction {
  id: number
  company_id: number
  operation_date: string
  amount: string
  direction: TransactionDirection
  category_id: number | null
  purpose: string | null
}

export interface TransactionsResponse {
  items: Transaction[]
  total: number
  page: number
  page_size: number
}

export interface DailyAnalyticsItem {
  date: string
  inflow: string
  outflow: string
  net_cash_flow: string
}

export interface DailyAnalyticsResponse {
  items: DailyAnalyticsItem[]
  totals: {
    inflow: string
    outflow: string
    net_cash_flow: string
  }
}

export interface CategoryAnalyticsItem {
  category_id: number | null
  category_name: string
  inflow: string
  outflow: string
  net_cash_flow: string
}

export interface CategoriesAnalyticsResponse {
  items: CategoryAnalyticsItem[]
}

export interface ImportPreviewRow {
  row_number: number
  operation_date: string
  amount: string
  direction: string
  category: string | null
  purpose: string | null
  is_valid: boolean
  errors?: string[]
}

export interface ImportPreviewError {
  row_number: number
  column?: string
  message: string
}

export interface ImportSummary {
  total_rows: number
  valid_rows: number
  error_rows: number
  date_from: string | null
  date_to: string | null
  total_inflow: string
  total_outflow: string
  total_net: string
}

export interface ImportPreviewResponse {
  rows: ImportPreviewRow[]
  errors: ImportPreviewError[]
  new_categories: string[]
  summary: ImportSummary
  can_commit: boolean
}

export interface ImportCommitRow {
  operation_date: string
  amount: string
  direction: TransactionDirection
  category: string | null
  purpose: string | null
}

export interface ImportCommitPayload {
  rows: ImportCommitRow[]
}

export interface ImportCommitResponse {
  imported_count: number
  created_categories_count: number
}

export interface ForecastPoint {
  date: string
  net_cash_flow: string
}

export interface ForecastResponse {
  history_end: string
  history_start: string
  last_operation_date: string | null
  history_days: number
  horizon_days: number
  model: string
  currency: string
  generated_at: string
  warnings: string[]
  forecast: ForecastPoint[]
}

export interface Membership {
  user_id: number
  company_id: number
  role: CompanyRole
  full_name?: string
  email?: string
}

export interface Invitation {
  id: number
  company_id: number
  email: string
  role: 'treasurer' | 'viewer'
  expires_at: string
  created_at: string | null
  status: 'pending' | 'accepted' | 'declined' | 'revoked' | 'expired'
  responded_at: string | null
  token?: string | null
  invite_url?: string | null
}

export interface ApiErrorDetail {
  code: string
  message: string
  fields?: Record<string, string>
}

export interface ApiErrorResponse {
  error: ApiErrorDetail
}
