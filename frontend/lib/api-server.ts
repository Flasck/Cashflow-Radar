import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import type { ApiErrorResponse } from './types'

const RADAR_API_URL = process.env.RADAR_API_URL || 'http://localhost:8000'

export class ApiServerError extends Error {
  code: string
  status: number
  fields?: Record<string, string>

  constructor(
    status: number,
    code: string,
    message: string,
    fields?: Record<string, string>,
  ) {
    super(message)
    this.name = 'ApiServerError'
    this.status = status
    this.code = code
    this.fields = fields
  }
}

export async function serverFetch<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const cookieStore = await cookies()
  const accessToken = cookieStore.get('access_token')?.value

  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')

  if (accessToken) {
    headers.set('Cookie', `access_token=${accessToken}`)
  }

  const url = `${RADAR_API_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`

  const res = await fetch(url, {
    ...options,
    headers,
    cache: 'no-store',
  })

  if (res.status === 401) {
    if (cookieStore.get('refresh_token')) {
      redirect('/session/refresh')
    }
    redirect('/login')
  }

  if (!res.ok) {
    let errorCode = `HTTP_${res.status}`
    let errorMessage = `Ошибка сервера (${res.status})`
    let fields: Record<string, string> | undefined

    try {
      const errJson = (await res.json()) as ApiErrorResponse
      if (errJson.error) {
        errorCode = errJson.error.code || errorCode
        errorMessage = errJson.error.message || errorMessage
        fields = errJson.error.fields
      }
    } catch {
    }

    throw new ApiServerError(res.status, errorCode, errorMessage, fields)
  }

  return (await res.json()) as T
}
