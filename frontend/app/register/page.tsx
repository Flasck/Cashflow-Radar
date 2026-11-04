'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { clientPost, ApiClientError } from '@/lib/api-client'

export default function RegisterPage() {
  const router = useRouter()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [verificationEmail, setVerificationEmail] = useState<string | null>(
    null,
  )
  const [code, setCode] = useState('')
  const [retryAfter, setRetryAfter] = useState(0)

  useEffect(() => {
    if (retryAfter <= 0) return
    const timer = window.setTimeout(
      () => setRetryAfter(value => value - 1),
      1000,
    )
    return () => window.clearTimeout(timer)
  }, [retryAfter])

  const finishRegistration = () => {
    const pendingInvite = sessionStorage.getItem('radar_invite_token')
    router.push(pendingInvite ? '/invite' : '/companies')
    router.refresh()
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (password.length < 8) {
      setError('Пароль должен содержать не менее 8 символов')
      return
    }

    setLoading(true)

    try {
      const result = await clientPost<{ email: string }>('/api/auth/register', {
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      })

      setVerificationEmail(result.email)
      setCode('')
      setRetryAfter(60)
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Ошибка при регистрации')
      } else {
        setError('Не удалось зарегистрироваться. Попробуйте позже.')
      }
    } finally {
      setLoading(false)
    }
  }

  const verifyCode = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await clientPost('/api/auth/verify-email', {
        email: verificationEmail,
        code,
      })
      finishRegistration()
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : 'Не удалось подтвердить почту',
      )
    } finally {
      setLoading(false)
    }
  }

  const resendCode = async () => {
    setLoading(true)
    setError(null)
    try {
      await clientPost('/api/auth/resend-code', {
        email: verificationEmail,
        password,
      })
      setCode('')
      setRetryAfter(60)
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 429) setRetryAfter(60)
      setError(
        err instanceof ApiClientError
          ? err.message
          : 'Не удалось отправить код',
      )
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
            {verificationEmail ? 'Подтверждение почты' : 'Регистрация'}
          </h1>
          <p className='page-subtitle'>
            {verificationEmail
              ? `Код отправлен на ${verificationEmail}. Он действует 10 минут. Проверьте также папку «Спам».`
              : 'Создание аккаунта в CashFlow Radar'}
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

        {verificationEmail ? (
          <form onSubmit={verifyCode}>
            <div className='form-group'>
              <label className='form-label' htmlFor='verificationCode'>
                Код из письма
              </label>
              <input
                id='verificationCode'
                type='text'
                inputMode='numeric'
                autoComplete='one-time-code'
                pattern='[0-9]{6}'
                minLength={6}
                maxLength={6}
                required
                autoFocus
                value={code}
                onChange={e => setCode(e.target.value.replace(/\D/g, ''))}
                className='form-input'
                disabled={loading}
              />
            </div>
            <button
              type='submit'
              className='btn btn-primary'
              style={{ width: '100%' }}
              disabled={loading}
            >
              {loading ? 'Подождите...' : 'Подтвердить почту'}
            </button>
            <button
              type='button'
              className='btn btn-secondary'
              style={{ width: '100%', marginTop: 'var(--space-3)' }}
              onClick={resendCode}
              disabled={loading || retryAfter > 0}
            >
              {retryAfter > 0
                ? `Отправить повторно через ${retryAfter} с`
                : 'Отправить код повторно'}
            </button>
            <button
              type='button'
              className='btn btn-secondary'
              style={{ width: '100%', marginTop: 'var(--space-2)' }}
              disabled={loading}
              onClick={() => {
                setVerificationEmail(null)
                setCode('')
                setError(null)
              }}
            >
              Вернуться к регистрации
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className='form-group'>
              <label className='form-label' htmlFor='fullName'>
                Имя и фамилия
              </label>
              <input
                id='fullName'
                type='text'
                required
                autoComplete='name'
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                className='form-input'
                placeholder='Иван Петров'
                disabled={loading}
              />
            </div>

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
                minLength={8}
                autoComplete='new-password'
                value={password}
                onChange={e => setPassword(e.target.value)}
                className='form-input'
                placeholder='Минимум 8 символов'
                disabled={loading}
              />
            </div>

            <button
              type='submit'
              className='btn btn-primary'
              style={{ width: '100%', marginTop: 'var(--space-3)' }}
              disabled={loading}
            >
              {loading ? 'Отправка кода...' : 'Зарегистрироваться'}
            </button>
          </form>
        )}

        <div
          style={{
            marginTop: 'var(--space-4)',
            textAlign: 'center',
            fontSize: '0.875rem',
            color: 'var(--color-muted)',
          }}
        >
          Уже есть учетная запись?{' '}
          <Link href='/login' style={{ fontWeight: 600 }}>
            Войти
          </Link>
        </div>
      </div>
    </main>
  )
}
