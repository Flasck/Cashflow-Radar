'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { clientPost, ApiClientError } from '@/lib/api-client'
import Button from '@/components/ui/Button'
import { useToast } from '@/components/ui/ToastProvider'

const SESSION_INVITE_TOKEN_KEY = 'radar_invite_token'

export default function InvitePage() {
  const router = useRouter()
  const notify = useToast()
  const [token, setToken] = useState<string | null>(null)
  const [loading, setLoading] = useState<'accept' | 'decline' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<'accepted' | 'declined' | null>(null)

  useEffect(() => {
    const readToken = () => {
      let foundToken: string | null = null
      const hash = window.location.hash
      if (hash && hash.startsWith('#')) {
        const params = new URLSearchParams(hash.slice(1))
        foundToken = params.get('token')
        if (foundToken) {
          // Store token strictly in sessionStorage for this tab only
          sessionStorage.setItem(SESSION_INVITE_TOKEN_KEY, foundToken)
          // Strip fragment from address bar immediately to avoid leaking into history/referrers
          window.history.replaceState(null, '', window.location.pathname)
        }
      }

      if (!foundToken) {
        foundToken = sessionStorage.getItem(SESSION_INVITE_TOKEN_KEY)
      }

      setToken(foundToken)
      setSuccess(null)
      setError(null)
    }
    readToken()
    window.addEventListener('hashchange', readToken)
    return () => window.removeEventListener('hashchange', readToken)
  }, [])

  const handleRespond = async (action: 'accept' | 'decline') => {
    if (!token) {
      setError('Токен приглашения не найден или ссылка недействительна')
      return
    }

    setLoading(action)
    setError(null)

    try {
      const res = await clientPost<{ company_id?: number }>(
        `/api/invitations/${action}`,
        { token },
      )
      sessionStorage.removeItem(SESSION_INVITE_TOKEN_KEY)
      setToken(null)
      setSuccess(action === 'accept' ? 'accepted' : 'declined')
      notify(
        action === 'accept' ? 'Приглашение принято' : 'Приглашение отклонено',
      )

      if (action === 'accept') {
        const targetUrl = res.company_id
          ? `/companies/${res.company_id}/transactions`
          : '/companies'
        router.push(targetUrl)
        router.refresh()
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.status === 401) {
          setError('Чтобы ответить на приглашение, сначала войдите в аккаунт')
        } else {
          setError(
            err.message ||
              'Не удалось ответить на приглашение. Возможно, ссылка устарела или уже использована.',
          )
        }
      } else {
        setError('Ошибка при обработке запроса.')
      }
    } finally {
      setLoading(null)
    }
  }

  return (
    <main
      className='app-container'
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-5)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '460px',
          backgroundColor: 'var(--color-paper-2)',
          padding: 'var(--space-5)',
          borderRadius: 'var(--radius-surface)',
          border: '1px solid var(--color-rule)',
        }}
      >
        <h1
          className='page-title'
          style={{ fontSize: '1.5rem', marginBottom: 'var(--space-2)' }}
        >
          Приглашение в компанию
        </h1>

        {error && (
          <div
            className='notice notice-error'
            role='alert'
            style={{ marginBottom: 'var(--space-4)' }}
          >
            {error}
          </div>
        )}

        {success ? (
          <div className='notice notice-success'>
            {success === 'accepted'
              ? 'Приглашение успешно принято! Перенаправляем в компанию…'
              : 'Приглашение отклонено. Доступ к компании не предоставлен.'}
            {success === 'declined' && (
              <p>
                <Link href='/companies'>К списку компаний</Link>
              </p>
            )}
          </div>
        ) : token ? (
          <div>
            <p
              style={{
                color: 'var(--color-muted)',
                marginBottom: 'var(--space-4)',
                fontSize: '0.9375rem',
              }}
            >
              Вы получили приглашение на присоединение к компании в качестве
              сотрудника.
            </p>

            <Button
              type='button'
              onClick={() => handleRespond('accept')}
              className='btn btn-primary'
              style={{ width: '100%', marginBottom: 'var(--space-3)' }}
              disabled={loading !== null}
              pending={loading === 'accept'}
              pendingLabel='Принятие…'
            >
              Принять приглашение
            </Button>
            <Button
              type='button'
              onClick={() => handleRespond('decline')}
              variant='secondary'
              style={{ width: '100%' }}
              disabled={loading !== null}
              pending={loading === 'decline'}
              pendingLabel='Отклонение…'
            >
              Отклонить приглашение
            </Button>

            <div
              style={{
                display: 'flex',
                gap: 'var(--space-3)',
                justifyContent: 'center',
                fontSize: '0.875rem',
                marginTop: 'var(--space-4)',
              }}
            >
              <Link href='/login'>Войти под другим аккаунтом</Link>
              <span style={{ color: 'var(--color-muted)' }}>•</span>
              <Link href='/register'>Зарегистрироваться</Link>
            </div>
          </div>
        ) : (
          <div>
            <div
              className='notice notice-warning'
              style={{ marginBottom: 'var(--space-4)' }}
            >
              Ссылка не содержит токена приглашения. Проверьте правильность
              полученной ссылки.
            </div>
            <Link
              href='/login'
              className='btn btn-secondary'
              style={{ width: '100%' }}
            >
              Перейти ко входу
            </Link>
          </div>
        )}
      </div>
    </main>
  )
}
