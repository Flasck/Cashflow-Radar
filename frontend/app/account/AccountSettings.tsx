'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ApiClientError, clientPatch, clientPost } from '@/lib/api-client'
import type { User } from '@/lib/types'
import Field from '@/components/ui/Field'
import Input from '@/components/ui/Input'
import PasswordInput from '@/components/ui/PasswordInput'
import Button from '@/components/ui/Button'
import Notice from '@/components/ui/Notice'
import { useToast } from '@/components/ui/ToastProvider'

function message(error: unknown): string {
  return error instanceof ApiClientError
    ? error.message
    : 'Не удалось сохранить изменения. Попробуйте ещё раз.'
}

export default function AccountSettings({ user }: { user: User }) {
  const router = useRouter()
  const notify = useToast()
  const [name, setName] = useState(user.full_name)
  const [profileBusy, setProfileBusy] = useState(false)
  const [profileError, setProfileError] = useState<string | null>(null)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [repeatPassword, setRepeatPassword] = useState('')
  const [code, setCode] = useState('')
  const [step, setStep] = useState<'password' | 'code'>('password')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [deadline, setDeadline] = useState(0)
  const [remaining, setRemaining] = useState(0)

  useEffect(() => {
    if (!deadline) return
    const update = () =>
      setRemaining(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)))
    const timer = window.setInterval(update, 1000)
    window.addEventListener('focus', update)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', update)
    }
  }, [deadline])

  function cooldown(seconds: number) {
    setRemaining(seconds)
    setDeadline(Date.now() + seconds * 1000)
  }

  async function saveProfile(event: React.FormEvent) {
    event.preventDefault()
    setProfileBusy(true)
    setProfileError(null)
    try {
      const result = await clientPatch<User>('/api/account', {
        full_name: name.trim(),
      })
      setName(result.full_name)
      notify('Имя сохранено')
      router.refresh()
    } catch (err) {
      setProfileError(message(err))
    } finally {
      setProfileBusy(false)
    }
  }

  async function requestCode(event?: React.FormEvent) {
    event?.preventDefault()
    setError(null)
    if (newPassword !== repeatPassword) {
      setError('Новые пароли не совпадают')
      return
    }
    setBusy(true)
    try {
      const result = await clientPost<{ retry_after: number }>(
        '/api/account/password/code',
        { current_password: currentPassword, new_password: newPassword },
      )
      cooldown(result.retry_after)
      setCode('')
      setStep('code')
      notify('Код для смены пароля отправлен на почту')
    } catch (err) {
      setError(message(err))
      if (err instanceof ApiClientError && err.code === 'EMAIL_RATE_LIMIT')
        cooldown(Number(err.fields?.retry_after ?? 0))
    } finally {
      setBusy(false)
    }
  }

  async function confirm(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await clientPost('/api/account/password/confirm', { code })
      setCurrentPassword('')
      setNewPassword('')
      setRepeatPassword('')
      setCode('')
      setStep('password')
      notify('Пароль изменён. Остальные сеансы завершены.')
      router.refresh()
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <section className='settings-section' aria-labelledby='profileHeading'>
        <div className='settings-description'>
          <h2 id='profileHeading'>Личные данные</h2>
          <p>
            Имя видно участникам ваших компаний. Почта используется для входа и
            подтверждения действий.
          </p>
        </div>
        <form
          className='settings-form'
          onSubmit={saveProfile}
          aria-busy={profileBusy}
        >
          {profileError && <Notice>{profileError}</Notice>}
          <Field id='accountName' label='Имя'>
            <Input
              id='accountName'
              autoComplete='name'
              value={name}
              onChange={event => {
                setName(event.target.value)
              }}
              maxLength={120}
              required
              disabled={profileBusy}
            />
          </Field>
          <Field
            id='accountEmail'
            label='Email'
            hint='Почта подтверждена. Изменение адреса пока недоступно.'
          >
            <Input
              id='accountEmail'
              value={user.email}
              readOnly
              type='email'
              aria-describedby='accountEmail-hint'
            />
          </Field>
          <Button pending={profileBusy} pendingLabel='Сохранение…'>
            Сохранить имя
          </Button>
        </form>
      </section>
      <section className='settings-section' aria-labelledby='passwordHeading'>
        <div className='settings-description'>
          <h2 id='passwordHeading'>Пароль и безопасность</h2>
          <p>
            Для смены пароля понадобятся текущий пароль и код с вашей почты.
          </p>
          <p>
            После смены пароля остальные сеансы завершатся. Текущий останется
            открытым.
          </p>
        </div>
        <div className='settings-form'>
          {error && <Notice>{error}</Notice>}
          {step === 'password' ? (
            <form key='password' onSubmit={requestCode} aria-busy={busy}>
              <Field id='currentPassword' label='Текущий пароль'>
                <PasswordInput
                  id='currentPassword'
                  autoComplete='current-password'
                  value={currentPassword}
                  onChange={event => setCurrentPassword(event.target.value)}
                  maxLength={128}
                  required
                  disabled={busy}
                />
              </Field>
              <Field
                id='newPassword'
                label='Новый пароль'
                hint='От 8 до 128 символов'
              >
                <PasswordInput
                  id='newPassword'
                  autoComplete='new-password'
                  value={newPassword}
                  onChange={event => setNewPassword(event.target.value)}
                  minLength={8}
                  maxLength={128}
                  required
                  disabled={busy}
                  aria-describedby='newPassword-hint'
                />
              </Field>
              <Field id='repeatPassword' label='Повторите новый пароль'>
                <PasswordInput
                  id='repeatPassword'
                  autoComplete='new-password'
                  value={repeatPassword}
                  onChange={event => setRepeatPassword(event.target.value)}
                  minLength={8}
                  maxLength={128}
                  required
                  disabled={busy}
                  aria-invalid={
                    newPassword !== repeatPassword && repeatPassword.length > 0
                  }
                />
              </Field>
              <Button
                pending={busy}
                pendingLabel='Отправка…'
                disabled={remaining > 0}
              >
                {remaining > 0
                  ? `Получить код через ${remaining} с`
                  : 'Получить код'}
              </Button>
            </form>
          ) : (
            <form key='code' onSubmit={confirm} aria-busy={busy}>
              <p className='verification-description'>
                Код отправлен на <strong>{user.email}</strong>. Введите его,
                чтобы подтвердить смену пароля. Код действует 10 минут, старый
                пароль пока не изменён.
              </p>
              <div className='form-group'>
                <label className='form-label' htmlFor='passwordCode'>
                  Код из письма
                </label>
                <Input
                  className='form-input code-input'
                  id='passwordCode'
                  inputMode='numeric'
                  autoComplete='one-time-code'
                  pattern='[0-9]{6}'
                  maxLength={6}
                  minLength={6}
                  value={code}
                  onChange={event =>
                    setCode(event.target.value.replace(/\D/g, ''))
                  }
                  required
                  autoFocus
                  disabled={busy}
                />
              </div>
              <div className='stack-actions'>
                <Button pending={busy} pendingLabel='Проверка…'>
                  Изменить пароль
                </Button>
                <Button
                  variant='secondary'
                  type='button'
                  disabled={busy || remaining > 0}
                  onClick={() => requestCode()}
                >
                  {remaining > 0
                    ? `Отправить повторно через ${remaining} с`
                    : 'Отправить код повторно'}
                </Button>
                <button
                  className='text-button'
                  type='button'
                  disabled={busy}
                  onClick={() => {
                    setStep('password')
                    setError(null)
                    setCode('')
                  }}
                >
                  Вернуться к вводу пароля
                </button>
              </div>
            </form>
          )}
        </div>
      </section>
    </>
  )
}
