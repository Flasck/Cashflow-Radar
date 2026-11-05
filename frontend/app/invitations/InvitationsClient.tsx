'use client'

import { useEffect, useState, useTransition } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Modal from '@/components/Modal'
import { ApiClientError, clientDelete, clientPost } from '@/lib/api-client'
import {
  displayDate,
  invitationLabels,
  invitationStatus,
  roleLabels,
} from '@/lib/labels'
import type { Company, Invitation, PersonalInvitation } from '@/lib/types'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import Button from '@/components/ui/Button'
import Spinner from '@/components/ui/Spinner'
import { useToast } from '@/components/ui/ToastProvider'

type Action = {
  invitation: PersonalInvitation
  type: 'decline' | 'revoke' | 'renew'
}

export default function InvitationsClient({
  received,
  sent,
  companies,
}: {
  received: PersonalInvitation[]
  sent: PersonalInvitation[]
  companies: Company[]
}) {
  const router = useRouter()
  const notify = useToast()
  const [refreshing, startRefresh] = useTransition()
  const [direction, setDirection] = useState<'received' | 'sent'>('received')
  const [now, setNow] = useState(() => Date.now())
  const [busy, setBusy] = useState(false)
  const [acceptingId, setAcceptingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [confirmation, setConfirmation] = useState<Action | null>(null)
  const [inviteUrl, setInviteUrl] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'treasurer' | 'viewer'>('viewer')
  const owned = companies.filter(company => company.role === 'owner')
  const [targetCompany, setTargetCompany] = useState(String(owned[0]?.id ?? ''))

  useEffect(() => {
    const update = () => setNow(Date.now())
    const timer = window.setInterval(update, 1000)
    window.addEventListener('focus', update)
    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', update)
    }
  }, [])

  const invitations = direction === 'received' ? received : sent
  const pendingCount = received.filter(
    inv => invitationStatus(inv, now) === 'pending' && !inv.is_member,
  ).length

  async function act(
    invitation: PersonalInvitation,
    action: 'accept' | 'decline' | 'revoke' | 'renew',
  ) {
    setBusy(true)
    if (action === 'accept') setAcceptingId(invitation.id)
    setError(null)
    setInviteUrl(null)
    try {
      if (action === 'revoke') {
        await clientDelete(
          `/api/companies/${invitation.company_id}/invitations/${invitation.id}`,
        )
        notify('Приглашение отозвано')
      } else if (action === 'renew') {
        const result = await clientPost<Invitation>(
          `/api/companies/${invitation.company_id}/invitations/${invitation.id}/renew`,
        )
        setInviteUrl(
          result.invite_url
            ? new URL(result.invite_url, window.location.origin).href
            : null,
        )
        notify('Новое приглашение создано. Предыдущее отозвано.')
      } else {
        const result = await clientPost<{ company_id?: number }>(
          `/api/invitations/${invitation.id}/${action}`,
        )
        notify(
          action === 'accept' ? 'Приглашение принято' : 'Приглашение отклонено',
        )
        if (action === 'accept' && result.company_id)
          router.push(`/companies/${result.company_id}/transactions`)
      }
      setConfirmation(null)
      startRefresh(() => router.refresh())
    } catch (err) {
      setConfirmation(null)
      setError(
        err instanceof ApiClientError
          ? err.message
          : 'Не удалось выполнить действие. Попробуйте ещё раз.',
      )
      startRefresh(() => router.refresh())
    } finally {
      setBusy(false)
      setAcceptingId(null)
    }
  }

  async function create(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await clientPost<Invitation>(
        `/api/companies/${targetCompany}/invitations`,
        { email, role },
      )
      setInviteUrl(
        result.invite_url
          ? new URL(result.invite_url, window.location.origin).href
          : null,
      )
      notify('Приглашение создано. Передайте ссылку получателю.')
      setEmail('')
      setCreating(false)
      setDirection('sent')
      startRefresh(() => router.refresh())
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? err.message
          : 'Не удалось создать приглашение',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className='section-tabs' aria-label='Списки приглашений'>
        <button
          type='button'
          aria-pressed={direction === 'received'}
          className={direction === 'received' ? 'selected' : ''}
          onClick={() => setDirection('received')}
        >
          Полученные{' '}
          {pendingCount > 0 && (
            <span className='nav-count'>{pendingCount}</span>
          )}
        </button>
        <button
          type='button'
          aria-pressed={direction === 'sent'}
          className={direction === 'sent' ? 'selected' : ''}
          onClick={() => setDirection('sent')}
        >
          Отправленные
        </button>
      </div>
      {error && !creating && (
        <div className='notice notice-error' role='alert'>
          {error}
        </div>
      )}
      {inviteUrl && (
        <div className='notice'>
          <label className='form-label' htmlFor='generatedInvitation'>
            Ссылка-приглашение
          </label>
          <Input
            id='generatedInvitation'
            className='form-input invitation-url'
            value={inviteUrl}
            readOnly
            onFocus={event => event.target.select()}
          />
          <p className='form-hint'>
            Скопируйте ссылку и передайте получателю. Он также увидит
            приглашение в своём аккаунте.
          </p>
        </div>
      )}
      <div className='invitation-toolbar'>
        {direction === 'sent' && owned.length > 0 && (
          <button
            type='button'
            className='btn btn-primary'
            onClick={() => {
              setError(null)
              setCreating(true)
            }}
          >
            Пригласить участника
          </button>
        )}
      </div>
      {direction === 'sent' && (
        <p className='muted'>
          Приглашения из компаний, которыми вы управляете. Отправка доступна
          только владельцу.
        </p>
      )}
      {refreshing && (
        <p role='status' className='loading-status'>
          <Spinner /> Обновляем приглашения…
        </p>
      )}
      {invitations.length === 0 && refreshing ? null : invitations.length ===
        0 ? (
        <div className='empty-state'>
          <h2>
            {direction === 'received'
              ? 'Полученных приглашений пока нет'
              : 'Отправленных приглашений пока нет'}
          </h2>
          <p>
            {direction === 'received'
              ? 'Приглашения, созданные на вашу почту, появятся здесь.'
              : owned.length
                ? 'Пригласите коллегу и выберите его роль в компании.'
                : 'Создайте компанию, чтобы приглашать участников.'}
          </p>
        </div>
      ) : (
        <div
          className='invitation-list'
          key={direction}
          aria-busy={busy || refreshing}
        >
          {invitations.map(inv => {
            const currentStatus = invitationStatus(inv, now)
            return (
              <article className='invitation-row' key={inv.id}>
                <div className='invitation-main'>
                  <h2>{inv.company_name}</h2>
                  <p>
                    {direction === 'received'
                      ? `Владелец: ${inv.owner_name}`
                      : inv.email}
                  </p>
                  <span className='badge badge-role'>
                    {roleLabels[inv.role]}
                  </span>
                </div>
                <div className='invitation-meta'>
                  <span
                    className={`invitation-status ${currentStatus === 'pending' ? 'pending' : ''}`}
                  >
                    {invitationLabels[currentStatus]}
                  </span>
                  <span>Создано: {displayDate(inv.created_at)}</span>
                  <span>
                    {inv.responded_at
                      ? `Ответ: ${displayDate(inv.responded_at)}`
                      : `До ${displayDate(inv.expires_at)} МСК`}
                  </span>
                </div>
                <div className='row-actions'>
                  {direction === 'received' &&
                    currentStatus === 'pending' &&
                    !inv.is_member && (
                      <>
                        <Button
                          disabled={busy || refreshing}
                          pending={acceptingId === inv.id}
                          pendingLabel='Принимаем…'
                          onClick={() => act(inv, 'accept')}
                        >
                          Принять
                        </Button>
                        <button
                          className='btn btn-secondary'
                          disabled={busy}
                          onClick={() =>
                            setConfirmation({
                              invitation: inv,
                              type: 'decline',
                            })
                          }
                        >
                          Отклонить
                        </button>
                      </>
                    )}
                  {direction === 'received' && inv.is_member && (
                    <Link
                      href={`/companies/${inv.company_id}/transactions`}
                      className='btn btn-secondary'
                    >
                      Открыть компанию
                    </Link>
                  )}
                  {direction === 'sent' &&
                    (currentStatus === 'pending' ||
                      currentStatus === 'expired') && (
                      <>
                        <button
                          className='btn btn-secondary'
                          disabled={busy}
                          onClick={() =>
                            setConfirmation({ invitation: inv, type: 'renew' })
                          }
                        >
                          Пригласить повторно
                        </button>
                        <button
                          className='btn btn-danger'
                          disabled={busy}
                          onClick={() =>
                            setConfirmation({ invitation: inv, type: 'revoke' })
                          }
                        >
                          Отозвать
                        </button>
                      </>
                    )}
                  {direction === 'sent' &&
                    (currentStatus === 'declined' ||
                      currentStatus === 'revoked') && (
                      <button
                        className='btn btn-secondary'
                        disabled={busy}
                        onClick={() => {
                          setTargetCompany(String(inv.company_id))
                          setEmail(inv.email)
                          setRole(inv.role)
                          setCreating(true)
                          setError(null)
                        }}
                      >
                        Пригласить повторно
                      </button>
                    )}
                </div>
              </article>
            )
          })}
        </div>
      )}
      {confirmation && (
        <Modal
          title={
            confirmation.type === 'decline'
              ? 'Отклонить приглашение?'
              : confirmation.type === 'revoke'
                ? 'Отозвать приглашение?'
                : 'Пригласить повторно?'
          }
          onClose={() => {
            if (!busy) setConfirmation(null)
          }}
        >
          <p>Компания «{confirmation.invitation.company_name}».</p>
          <p>
            {confirmation.type === 'decline'
              ? 'Доступ к компании не будет предоставлен. Ответ сохранится в истории.'
              : confirmation.type === 'revoke'
                ? 'Приглашение и его ссылка станут недействительными.'
                : 'Будет создано новое приглашение на 48 часов. Старое станет недействительным; история сохранится.'}
          </p>
          <div className='row-actions'>
            <Button
              pending={busy}
              pendingLabel='Выполняем…'
              onClick={() => act(confirmation.invitation, confirmation.type)}
            >
              Подтвердить
            </Button>
            <button
              className='btn btn-secondary'
              disabled={busy}
              onClick={() => setConfirmation(null)}
            >
              Отмена
            </button>
          </div>
        </Modal>
      )}
      {creating && (
        <Modal
          title='Пригласить участника'
          onClose={() => {
            if (!busy) {
              setCreating(false)
              setError(null)
            }
          }}
        >
          {error && (
            <div className='notice notice-error' role='alert'>
              {error}
            </div>
          )}
          <form onSubmit={create} aria-busy={busy}>
            <div className='form-group'>
              <label htmlFor='inviteCompany' className='form-label'>
                Компания
              </label>
              <Select
                id='inviteCompany'
                className='form-select'
                value={targetCompany}
                onChange={event => setTargetCompany(event.target.value)}
                required
                disabled={busy}
              >
                {owned.map(company => (
                  <option key={company.id} value={company.id}>
                    {company.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className='form-group'>
              <label htmlFor='inviteEmail' className='form-label'>
                Email участника
              </label>
              <Input
                id='inviteEmail'
                className='form-input'
                type='email'
                maxLength={254}
                value={email}
                onChange={event => setEmail(event.target.value)}
                required
                disabled={busy}
              />
            </div>
            <div className='form-group'>
              <label htmlFor='inviteRole' className='form-label'>
                Роль в компании
              </label>
              <Select
                id='inviteRole'
                className='form-select'
                value={role}
                onChange={event =>
                  setRole(event.target.value as 'viewer' | 'treasurer')
                }
                disabled={busy}
              >
                <option value='viewer'>Наблюдатель</option>
                <option value='treasurer'>Казначей</option>
              </Select>
              <span className='form-hint'>
                {role === 'viewer'
                  ? 'Просмотр операций и прогнозов без изменения данных.'
                  : 'Добавление операций, импорт и управление категориями.'}
              </span>
            </div>
            <p className='muted'>
              Приглашение действует 48 часов. Письмо автоматически не
              отправляется.
            </p>
            <div className='row-actions'>
              <Button pending={busy} pendingLabel='Создание…'>
                Создать приглашение
              </Button>
              <button
                className='btn btn-secondary'
                type='button'
                disabled={busy}
                onClick={() => setCreating(false)}
              >
                Отмена
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
