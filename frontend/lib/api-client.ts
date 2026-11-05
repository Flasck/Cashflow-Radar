import type { ApiErrorResponse } from './types'

export class ApiClientError extends Error {
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
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
    this.fields = fields
  }
}

function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null
  const match = document.cookie.match(
    new RegExp('(^|;\\s*)(' + name + ')=([^;]*)'),
  )
  return match ? decodeURIComponent(match[3]) : null
}

let refreshRequest: Promise<boolean> | null = null

export function refreshSession(): Promise<boolean> {
  if (!refreshRequest) {
    refreshRequest = fetch('/api/auth/refresh', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRF-Token': getCookie('csrf_token') || '' },
    }).then(res => res.ok).finally(() => { refreshRequest = null })
  }
  return refreshRequest
}

export async function clientFetch<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)

  const csrfToken = getCookie('csrf_token')
  if (csrfToken && !headers.has('X-CSRF-Token')) {
    headers.set('X-CSRF-Token', csrfToken)
  }

  if (!(options.body instanceof FormData)) {
    if (!headers.has('Content-Type') && options.body) {
      headers.set('Content-Type', 'application/json')
    }
  }
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json')
  }

  const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`

  let res = await fetch(url, {
    ...options,
    headers,
    credentials: 'same-origin',
  })

  if (
    res.status === 401 &&
    (!url.startsWith('/api/auth/') || url === '/api/auth/me' || url === '/api/auth/logout') &&
    await refreshSession()
  ) {
    headers.set('X-CSRF-Token', getCookie('csrf_token') || '')
    res = await fetch(url, { ...options, headers, credentials: 'same-origin' })
  }

  if (res.status === 401) {
    if (
      typeof window !== 'undefined' &&
      !window.location.pathname.startsWith('/login') &&
      !window.location.pathname.startsWith('/register') &&
      !window.location.pathname.startsWith('/invite')
    ) {
      window.location.href = '/login'
    }
  }

  if (!res.ok) {
    let errorCode = `HTTP_${res.status}`
    let errorMessage = `Ошибка запроса (${res.status})`
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

    throw new ApiClientError(res.status, errorCode, errorMessage, fields)
  }

  if (res.status === 204) {
    return {} as T
  }

  return (await res.json()) as T
}

export function clientPost<T>(endpoint: string, body?: unknown): Promise<T> {
  return clientFetch<T>(endpoint, {
    method: 'POST',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
}

export function clientPatch<T>(endpoint: string, body?: unknown): Promise<T> {
  return clientFetch<T>(endpoint, {
    method: 'PATCH',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
}

export function clientDelete<T>(endpoint: string): Promise<T> {
  return clientFetch<T>(endpoint, {
    method: 'DELETE',
  })
}

export function clientUpload<T>(
  endpoint: string,
  formData: FormData,
): Promise<T> {
  return clientFetch<T>(endpoint, {
    method: 'POST',
    body: formData,
  })
}
