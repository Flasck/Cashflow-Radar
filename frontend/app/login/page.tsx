'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { clientPost, ApiClientError } from '@/lib/api-client'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      await clientPost('/api/auth/login', { email, password })
      const pendingInvite =
        typeof window !== 'undefined'
          ? sessionStorage.getItem('radar_invite_token')
          : null
      if (pendingInvite) {
        router.push('/invite')
      } else {
        router.push('/companies')
      }
      router.refresh()
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.code === 'EMAIL_NOT_VERIFIED') {
          router.push('/register')
          return
        }
        setError(err.message || 'Неверный email или пароль')
      } else {
        setError('Не удалось войти в систему. Проверьте подключение.')
      }
    } finally {
      setLoading(false)
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
          maxWidth: '420px',
          backgroundColor: 'var(--color-paper-2)',
          padding: 'var(--space-5)',
          borderRadius: 'var(--radius-surface)',
          border: '1px solid var(--color-rule)',
        }}
      >
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <h1
            className='page-title'
            style={{ fontSize: '1.5rem', marginBottom: 'var(--space-1)' }}
          >
            CashFlow Radar
          </h1>
          <p className='page-subtitle'>
            Вход в систему учета и прогноза денежных потоков
          </p>
        </div>

        {error && (
          <div
            className='notice notice-error'
            role='alert'
            style={{ marginBottom: 'var(--space-4)' }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className='form-group'>
            <label className='form-label' htmlFor='email'>
              Email
            </label>
            <input
              id='email'
              type='email'
              required
              autoComplete='email'
              value={email}
              onChange={e => setEmail(e.target.value)}
              className='form-input'
              placeholder='user@example.com'
              disabled={loading}
            />
          </div>

          <div className='form-group'>
            <label className='form-label' htmlFor='password'>
              Пароль
            </label>
            <input
              id='password'
              type='password'
              required
              autoComplete='current-password'
              value={password}
              onChange={e => setPassword(e.target.value)}
              className='form-input'
              placeholder='••••••••'
              disabled={loading}
            />
          </div>

          <button
            type='submit'
            className='btn btn-primary'
            style={{ width: '100%', marginTop: 'var(--space-3)' }}
            disabled={loading}
          >
            {loading ? 'Вход...' : 'Войти'}
          </button>
        </form>

        <div
          style={{
            marginTop: 'var(--space-4)',
            textAlign: 'center',
            fontSize: '0.875rem',
            color: 'var(--color-muted)',
          }}
        >
          Нет учетной записи?{' '}
          <Link href='/register' style={{ fontWeight: 600 }}>
            Зарегистрироваться
          </Link>
        </div>
      </div>
    </main>
  )
}
