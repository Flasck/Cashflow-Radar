'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import type { Company, Category, Membership, Invitation } from '@/lib/types'
import {
  clientPost,
  clientPatch,
  clientDelete,
  ApiClientError,
} from '@/lib/api-client'

interface SettingsTabsProps {
  company: Company
  categories: Category[]
  members: Membership[]
  invitations: Invitation[]
}

const invitationStatusLabels: Record<Invitation['status'], string> = {
  pending: 'Ожидает ответа',
  accepted: 'Принято',
  declined: 'Отклонено',
  revoked: 'Отозвано',
  expired: 'Срок истёк',
}

function invitationDate(value: string | null): string {
  return value
    ? new Date(value).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' })
    : '—'
}

function roleToRussian(role: string): string {
  switch (role) {
    case 'owner':
      return 'Владелец'
    case 'treasurer':
      return 'Казначей'
    case 'viewer':
      return 'Наблюдатель'
    default:
      return role
  }
}

export default function SettingsTabs({
  company,
  categories,
  members,
  invitations,
}: SettingsTabsProps) {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<
    'categories' | 'members' | 'company'
  >('categories')

  const isOwner = company.role === 'owner'
  const canEditCategories =
    company.role === 'owner' || company.role === 'treasurer'

  // Category State
  const [newCatName, setNewCatName] = useState('')
  const [editingCatId, setEditingCatId] = useState<number | null>(null)
  const [editingCatName, setEditingCatName] = useState('')
  const [catError, setCatError] = useState<string | null>(null)
  const [catSuccess, setCatSuccess] = useState<string | null>(null)
  const [catLoading, setCatLoading] = useState(false)

  // Invite State
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<'treasurer' | 'viewer'>(
    'treasurer',
  )
  const [inviteError, setInviteError] = useState<string | null>(null)
  const [generatedInviteUrl, setGeneratedInviteUrl] = useState<string | null>(
    null,
  )
  const [inviteLoading, setInviteLoading] = useState(false)

  // Company State
  const [compName, setCompName] = useState(company.name)
  const [compIndustry, setCompIndustry] = useState(company.industry_code || '')
  const [compError, setCompError] = useState<string | null>(null)
  const [compSuccess, setCompSuccess] = useState<string | null>(null)
  const [compLoading, setCompLoading] = useState(false)

  // Handlers: Categories
  const handleAddCategory = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newCatName.trim()) return

    setCatLoading(true)
    setCatError(null)
    setCatSuccess(null)

    try {
      await clientPost(`/api/companies/${company.id}/categories`, {
        name: newCatName.trim(),
      })
      setNewCatName('')
      setCatSuccess('Категория успешно добавлена')
      router.refresh()
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.status === 409) {
          setCatError('Категория с таким названием уже существует')
        } else {
          setCatError(err.message || 'Ошибка создания категории')
        }
      } else {
        setCatError('Не удалось создать категорию')
      }
    } finally {
      setCatLoading(false)
    }
  }

  const handleUpdateCategory = async (id: number) => {
    if (!editingCatName.trim()) return

    setCatLoading(true)
    setCatError(null)
    setCatSuccess(null)

    try {
      await clientPatch(`/api/companies/${company.id}/categories/${id}`, {
        name: editingCatName.trim(),
      })
      setEditingCatId(null)
      setCatSuccess('Название категории обновлено')
      router.refresh()
    } catch (err) {
      if (err instanceof ApiClientError) {
        setCatError(err.message || 'Ошибка обновления категории')
      } else {
        setCatError('Не удалось обновить категорию')
      }
    } finally {
      setCatLoading(false)
    }
  }

  const handleDeleteCategory = async (id: number, name: string) => {
    if (
      !confirm(
        `Удалить категорию «${name}»? Если по ней есть операции, удаление будет отклонено.`,
      )
    ) {
      return
    }

    setCatLoading(true)
    setCatError(null)
    setCatSuccess(null)

    try {
      await clientDelete(`/api/companies/${company.id}/categories/${id}`)
      setCatSuccess(`Категория «${name}» удалена`)
      router.refresh()
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.status === 409) {
          setCatError(
            `Категория «${name}» используется в существующих операциях. Сначала перенесите или удалите операции.`,
          )
        } else {
          setCatError(err.message || 'Не удалось удалить категорию')
        }
      } else {
        setCatError('Не удалось удалить категорию')
      }
    } finally {
      setCatLoading(false)
    }
  }

  // Handlers: Members & Invites
  const handleUpdateMemberRole = async (
    userId: number,
    newRole: 'treasurer' | 'viewer',
  ) => {
    try {
      await clientPatch(`/api/companies/${company.id}/members/${userId}`, {
        role: newRole,
      })
      router.refresh()
    } catch (err) {
      alert(
        err instanceof ApiClientError ? err.message : 'Ошибка изменения роли',
      )
    }
  }

  const handleRemoveMember = async (userId: number, name?: string) => {
    if (!confirm(`Исключить участника ${name || userId} из компании?`)) return

    try {
      await clientDelete(`/api/companies/${company.id}/members/${userId}`)
      router.refresh()
    } catch (err) {
      alert(
        err instanceof ApiClientError
          ? err.message
          : 'Ошибка исключения участника',
      )
    }
  }

  const handleCreateInvite = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inviteEmail.trim()) return

    setInviteLoading(true)
    setInviteError(null)
    setGeneratedInviteUrl(null)

    try {
      const res = await clientPost<Invitation>(
        `/api/companies/${company.id}/invitations`,
        {
          email: inviteEmail.trim(),
          role: inviteRole,
        },
      )

      setInviteEmail('')
      router.refresh()

      setGeneratedInviteUrl(
        res.invite_url
          ? new URL(res.invite_url, window.location.origin).href
          : null,
      )
    } catch (err) {
      if (err instanceof ApiClientError) {
        setInviteError(err.message || 'Ошибка создания приглашения')
      } else {
        setInviteError('Не удалось создать приглашение')
      }
    } finally {
      setInviteLoading(false)
    }
  }

  const handleRevokeInvite = async (inviteId: number) => {
    if (!confirm('Отозвать приглашение? Ссылка станет недействительной.'))
      return

    setInviteLoading(true)
    setInviteError(null)
    setGeneratedInviteUrl(null)
    try {
      await clientDelete(`/api/companies/${company.id}/invitations/${inviteId}`)
      router.refresh()
    } catch (err) {
      setInviteError(
        err instanceof ApiClientError
          ? err.message
          : 'Ошибка отзыва приглашения',
      )
    } finally {
      setInviteLoading(false)
    }
  }

  const handleRenewInvite = async (inviteId: number) => {
    if (
      !confirm(
        'Создать новую ссылку на 48 часов? Старая ссылка станет недействительной, обе записи останутся в истории.',
      )
    )
      return
    setInviteLoading(true)
    setInviteError(null)
    setGeneratedInviteUrl(null)
    try {
      const res = await clientPost<Invitation>(
        `/api/companies/${company.id}/invitations/${inviteId}/renew`,
        {},
      )
      setGeneratedInviteUrl(
        res.invite_url
          ? new URL(res.invite_url, window.location.origin).href
          : null,
      )
      router.refresh()
    } catch (err) {
      setInviteError(
        err instanceof ApiClientError
          ? err.message
          : 'Ошибка продления приглашения',
      )
    } finally {
      setInviteLoading(false)
    }
  }

  // Handlers: Company
  const handleUpdateCompany = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!compName.trim()) return

    setCompLoading(true)
    setCompError(null)
    setCompSuccess(null)

    try {
      await clientPatch(`/api/companies/${company.id}`, {
        name: compName.trim(),
        industry_code: compIndustry.trim() || null,
      })
      setCompSuccess('Параметры компании обновлены')
      router.refresh()
    } catch (err) {
      if (err instanceof ApiClientError) {
        setCompError(err.message || 'Ошибка обновления компании')
      } else {
        setCompError('Не удалось обновить параметры компании')
      }
    } finally {
      setCompLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <div className='page-header'>
        <div>
          <h1 className='page-title'>Настройки компании</h1>
          <p className='page-subtitle'>
            Управление справочником статей, участниками и параметрами
            организации
          </p>
        </div>
      </div>

      {/* Tabs Header */}
      <div
        style={{
          display: 'flex',
          gap: 'var(--space-2)',
          borderBottom: '1px solid var(--color-rule)',
          marginBottom: 'var(--space-5)',
        }}
      >
        <button
          type='button'
          className={`btn ${activeTab === 'categories' ? 'btn-primary' : 'btn-secondary'}`}
          style={{
            borderBottomLeftRadius: 0,
            borderBottomRightRadius: 0,
            borderBottom: 'none',
          }}
          onClick={() => setActiveTab('categories')}
        >
          Категории ({categories.length})
        </button>

        <button
          type='button'
          className={`btn ${activeTab === 'members' ? 'btn-primary' : 'btn-secondary'}`}
          style={{
            borderBottomLeftRadius: 0,
            borderBottomRightRadius: 0,
            borderBottom: 'none',
          }}
          onClick={() => setActiveTab('members')}
        >
          Участники ({members.length})
        </button>

        <button
          type='button'
          className={`btn ${activeTab === 'company' ? 'btn-primary' : 'btn-secondary'}`}
          style={{
            borderBottomLeftRadius: 0,
            borderBottomRightRadius: 0,
            borderBottom: 'none',
          }}
          onClick={() => setActiveTab('company')}
        >
          Организация
        </button>
      </div>

      {/* TAB 1: CATEGORIES */}
      {activeTab === 'categories' && (
        <div
          style={{
            backgroundColor: 'var(--color-paper-2)',
            padding: 'var(--space-5)',
            borderRadius: 'var(--radius-surface)',
            border: '1px solid var(--color-rule)',
          }}
        >
          <div style={{ marginBottom: 'var(--space-4)' }}>
            <h2 style={{ fontSize: '1.125rem', margin: 0 }}>
              Справочник категорий операций
            </h2>
            <span
              style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}
            >
              Категории используются для классификации и сводок. Удаление
              возможно только для категорий без операций.
            </span>
          </div>

          {catError && <div className='notice notice-error'>{catError}</div>}
          {catSuccess && (
            <div className='notice notice-success'>{catSuccess}</div>
          )}

          {/* Add Category Form (owner/treasurer) */}
          {canEditCategories && (
            <form
              onSubmit={handleAddCategory}
              style={{
                display: 'flex',
                gap: 'var(--space-2)',
                marginBottom: 'var(--space-4)',
                maxWidth: '520px',
              }}
            >
              <input
                type='text'
                required
                maxLength={100}
                placeholder='Новая категория (например, Маркетинг)'
                className='form-input'
                value={newCatName}
                onChange={e => setNewCatName(e.target.value)}
                disabled={catLoading}
                style={{ flex: 1 }}
              />
              <button
                type='submit'
                className='btn btn-primary'
                disabled={catLoading}
              >
                {catLoading ? '...' : '+ Добавить'}
              </button>
            </form>
          )}

          {/* Categories List */}
          {categories.length === 0 ? (
            <p style={{ color: 'var(--color-muted)', fontStyle: 'italic' }}>
              Категорий пока нет. Вы можете добавить первую категорию выше.
            </p>
          ) : (
            <div
              className='ledger-wrapper'
              style={{
                borderRadius: 'var(--radius-field)',
                border: '1px solid var(--color-rule)',
              }}
            >
              <table className='ledger-table'>
                <thead>
                  <tr>
                    <th>Название категории</th>
                    {canEditCategories && (
                      <th style={{ width: '160px', textAlign: 'right' }}>
                        Действия
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {categories.map(c => (
                    <tr key={c.id}>
                      <td>
                        {editingCatId === c.id ? (
                          <div
                            style={{ display: 'flex', gap: 'var(--space-2)' }}
                          >
                            <input
                              type='text'
                              required
                              className='form-input'
                              style={{ minHeight: '32px', padding: '4px 8px' }}
                              value={editingCatName}
                              onChange={e => setEditingCatName(e.target.value)}
                            />
                            <button
                              type='button'
                              className='btn btn-primary'
                              style={{
                                minHeight: '32px',
                                padding: '4px 10px',
                                fontSize: '0.8125rem',
                              }}
                              onClick={() => handleUpdateCategory(c.id)}
                            >
                              ОК
                            </button>
                            <button
                              type='button'
                              className='btn btn-secondary'
                              style={{
                                minHeight: '32px',
                                padding: '4px 8px',
                                fontSize: '0.8125rem',
                              }}
                              onClick={() => setEditingCatId(null)}
                            >
                              Отмена
                            </button>
                          </div>
                        ) : (
                          <span style={{ fontWeight: 600 }}>{c.name}</span>
                        )}
                      </td>
                      {canEditCategories && (
                        <td style={{ textAlign: 'right' }}>
                          {editingCatId !== c.id && (
                            <div
                              style={{
                                display: 'inline-flex',
                                gap: 'var(--space-2)',
                              }}
                            >
                              <button
                                type='button'
                                className='btn btn-secondary'
                                style={{
                                  padding: '3px 8px',
                                  minHeight: '28px',
                                  fontSize: '0.75rem',
                                }}
                                onClick={() => {
                                  setEditingCatId(c.id)
                                  setEditingCatName(c.name)
                                }}
                              >
                                Изменить
                              </button>
                              <button
                                type='button'
                                className='btn btn-danger'
                                style={{
                                  padding: '3px 8px',
                                  minHeight: '28px',
                                  fontSize: '0.75rem',
                                }}
                                onClick={() =>
                                  handleDeleteCategory(c.id, c.name)
                                }
                              >
                                Удалить
                              </button>
                            </div>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: MEMBERS & INVITATIONS */}
      {activeTab === 'members' && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-5)',
          }}
        >
          {/* Members List */}
          <div
            style={{
              backgroundColor: 'var(--color-paper-2)',
              padding: 'var(--space-5)',
              borderRadius: 'var(--radius-surface)',
              border: '1px solid var(--color-rule)',
            }}
          >
            <h2
              style={{
                fontSize: '1.125rem',
                marginTop: 0,
                marginBottom: 'var(--space-3)',
              }}
            >
              Текущие участники ({members.length})
            </h2>

            <div
              className='ledger-wrapper'
              style={{
                borderRadius: 'var(--radius-field)',
                border: '1px solid var(--color-rule)',
              }}
            >
              <table className='ledger-table'>
                <thead>
                  <tr>
                    <th>Имя</th>
                    <th>Email</th>
                    <th>Роль</th>
                    {isOwner && (
                      <th style={{ textAlign: 'right' }}>Действия</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {members.map(m => {
                    const isMemberOwner = m.role === 'owner'
                    return (
                      <tr key={m.user_id}>
                        <td style={{ fontWeight: 600 }}>
                          {m.full_name || '\u2014'}
                        </td>
                        <td>{m.email || '\u2014'}</td>
                        <td>
                          <span className='badge badge-role'>
                            {roleToRussian(m.role)}
                          </span>
                        </td>
                        {isOwner && (
                          <td style={{ textAlign: 'right' }}>
                            {!isMemberOwner ? (
                              <div
                                style={{
                                  display: 'inline-flex',
                                  gap: 'var(--space-2)',
                                }}
                              >
                                <select
                                  value={m.role}
                                  onChange={e =>
                                    handleUpdateMemberRole(
                                      m.user_id,
                                      e.target.value as 'treasurer' | 'viewer',
                                    )
                                  }
                                  className='form-select'
                                  style={{
                                    minHeight: '28px',
                                    padding: '2px 6px',
                                    fontSize: '0.75rem',
                                  }}
                                >
                                  <option value='treasurer'>Казначей</option>
                                  <option value='viewer'>Наблюдатель</option>
                                </select>
                                <button
                                  type='button'
                                  className='btn btn-danger'
                                  style={{
                                    padding: '2px 8px',
                                    minHeight: '28px',
                                    fontSize: '0.75rem',
                                  }}
                                  onClick={() =>
                                    handleRemoveMember(m.user_id, m.full_name)
                                  }
                                >
                                  Исключить
                                </button>
                              </div>
                            ) : (
                              <span
                                style={{
                                  fontSize: '0.75rem',
                                  color: 'var(--color-muted)',
                                }}
                              >
                                Владелец
                              </span>
                            )}
                          </td>
                        )}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {!isOwner && (
              <p
                style={{
                  fontSize: '0.8125rem',
                  color: 'var(--color-muted)',
                  marginTop: 'var(--space-3)',
                  marginBottom: 0,
                }}
              >
                Управление составом участников и отправка приглашений доступны
                только владельцу организации.
              </p>
            )}
          </div>

          {/* Create Invitation (Owner Only) */}
          {isOwner && (
            <div
              style={{
                backgroundColor: 'var(--color-paper-2)',
                padding: 'var(--space-5)',
                borderRadius: 'var(--radius-surface)',
                border: '1px solid var(--color-rule)',
              }}
            >
              <h2
                style={{
                  fontSize: '1.125rem',
                  marginTop: 0,
                  marginBottom: 'var(--space-2)',
                }}
              >
                Пригласить нового сотрудника
              </h2>
              <p
                style={{
                  fontSize: '0.8125rem',
                  color: 'var(--color-muted)',
                  margin: '0 0 var(--space-4)',
                }}
              >
                Создайте одноразовую ссылку на 48 часов и передайте её
                сотруднику доверенным способом. Продление заменяет ссылку новой,
                история сохраняется.
              </p>

              {inviteError && (
                <div className='notice notice-error'>{inviteError}</div>
              )}

              {generatedInviteUrl && (
                <div
                  className='notice notice-success'
                  style={{ marginBottom: 'var(--space-4)' }}
                >
                  <p style={{ margin: '0 0 var(--space-1)', fontWeight: 600 }}>
                    Ссылка-приглашение создана:
                  </p>
                  <input
                    type='text'
                    readOnly
                    value={generatedInviteUrl}
                    className='form-input'
                    style={{ width: '100%', fontSize: '0.8125rem' }}
                    onClick={e => (e.target as HTMLInputElement).select()}
                  />
                  <span
                    style={{
                      fontSize: '0.75rem',
                      color: 'var(--color-muted)',
                      marginTop: '4px',
                      display: 'block',
                    }}
                  >
                    Скопируйте ссылку и отправьте приглашенному сотруднику.
                  </span>
                </div>
              )}

              <form
                onSubmit={handleCreateInvite}
                style={{
                  display: 'flex',
                  gap: 'var(--space-3)',
                  flexWrap: 'wrap',
                  alignItems: 'flex-end',
                }}
              >
                <div
                  className='form-group'
                  style={{ marginBottom: 0, flex: 2, minWidth: '220px' }}
                >
                  <label className='form-label' htmlFor='invEmail'>
                    Email сотрудника
                  </label>
                  <input
                    id='invEmail'
                    type='email'
                    required
                    placeholder='colleague@example.com'
                    className='form-input'
                    value={inviteEmail}
                    onChange={e => setInviteEmail(e.target.value)}
                    disabled={inviteLoading}
                  />
                </div>

                <div
                  className='form-group'
                  style={{ marginBottom: 0, flex: 1, minWidth: '150px' }}
                >
                  <label className='form-label' htmlFor='invRole'>
                    Назначаемая роль
                  </label>
                  <select
                    id='invRole'
                    className='form-select'
                    value={inviteRole}
                    onChange={e =>
                      setInviteRole(e.target.value as 'treasurer' | 'viewer')
                    }
                    disabled={inviteLoading}
                  >
                    <option value='treasurer'>Казначей</option>
                    <option value='viewer'>Наблюдатель</option>
                  </select>
                </div>

                <button
                  type='submit'
                  className='btn btn-primary'
                  disabled={inviteLoading}
                  style={{ minHeight: '40px' }}
                >
                  {inviteLoading ? 'Создание...' : 'Создать ссылку'}
                </button>
              </form>

              {/* Invitation History */}
              {invitations.length > 0 && (
                <div style={{ marginTop: 'var(--space-5)' }}>
                  <h3
                    style={{
                      fontSize: '0.9375rem',
                      marginBottom: 'var(--space-2)',
                    }}
                  >
                    История приглашений ({invitations.length})
                  </h3>
                  <div
                    className='ledger-wrapper'
                    style={{
                      borderRadius: 'var(--radius-field)',
                      border: '1px solid var(--color-rule)',
                    }}
                  >
                    <table
                      className='ledger-table'
                      style={{ fontSize: '0.8125rem' }}
                    >
                      <thead>
                        <tr>
                          <th>Email</th>
                          <th>Роль</th>
                          <th>Статус</th>
                          <th>Создано (МСК)</th>
                          <th>Срок действия (МСК)</th>
                          <th>Завершено (МСК)</th>
                          <th style={{ textAlign: 'right' }}>Действие</th>
                        </tr>
                      </thead>
                      <tbody>
                        {invitations.map(inv => (
                          <tr key={inv.id}>
                            <td>{inv.email}</td>
                            <td>{roleToRussian(inv.role)}</td>
                            <td>{invitationStatusLabels[inv.status]}</td>
                            <td>{invitationDate(inv.created_at)}</td>
                            <td style={{ color: 'var(--color-muted)' }}>
                              {invitationDate(inv.expires_at)}
                            </td>
                            <td>{invitationDate(inv.responded_at)}</td>
                            <td style={{ textAlign: 'right' }}>
                              {(inv.status === 'pending' ||
                                inv.status === 'expired') && (
                                <div
                                  style={{
                                    display: 'inline-flex',
                                    gap: 'var(--space-2)',
                                  }}
                                >
                                  <button
                                    type='button'
                                    className='btn btn-secondary'
                                    disabled={inviteLoading}
                                    onClick={() => handleRenewInvite(inv.id)}
                                  >
                                    Продлить
                                  </button>
                                  <button
                                    type='button'
                                    className='btn btn-danger'
                                    style={{
                                      padding: '2px 8px',
                                      minHeight: '26px',
                                      fontSize: '0.75rem',
                                    }}
                                    onClick={() => handleRevokeInvite(inv.id)}
                                    disabled={inviteLoading}
                                  >
                                    Отозвать
                                  </button>
                                </div>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: COMPANY PARAMETERS */}
      {activeTab === 'company' && (
        <div
          style={{
            backgroundColor: 'var(--color-paper-2)',
            padding: 'var(--space-5)',
            borderRadius: 'var(--radius-surface)',
            border: '1px solid var(--color-rule)',
            maxWidth: '560px',
          }}
        >
          <h2
            style={{
              fontSize: '1.125rem',
              marginTop: 0,
              marginBottom: 'var(--space-3)',
            }}
          >
            Реквизиты организации
          </h2>

          {compError && <div className='notice notice-error'>{compError}</div>}
          {compSuccess && (
            <div className='notice notice-success'>{compSuccess}</div>
          )}

          <form onSubmit={handleUpdateCompany}>
            <div className='form-group'>
              <label className='form-label' htmlFor='companyNameField'>
                Название компании *
              </label>
              <input
                id='companyNameField'
                type='text'
                required
                maxLength={160}
                className='form-input'
                value={compName}
                onChange={e => setCompName(e.target.value)}
                disabled={!isOwner || compLoading}
              />
            </div>

            <div className='form-group'>
              <label className='form-label' htmlFor='companyIndustryField'>
                Код или наименование отрасли
              </label>
              <input
                id='companyIndustryField'
                type='text'
                maxLength={50}
                className='form-input'
                value={compIndustry}
                onChange={e => setCompIndustry(e.target.value)}
                disabled={!isOwner || compLoading}
              />
              <span className='form-hint'>Пока не влияет на прогноз</span>
            </div>

            <div className='form-group'>
              <label className='form-label' htmlFor='companyCurrencyField'>
                Валюта расчетов
              </label>
              <input
                id='companyCurrencyField'
                type='text'
                readOnly
                value='RUB (Российский рубль)'
                className='form-input'
                style={{
                  backgroundColor: 'var(--color-paper)',
                  color: 'var(--color-muted)',
                }}
                disabled
              />
              <span className='form-hint'>
                Единственная поддерживаемая валюта системы
              </span>
            </div>

            {isOwner ? (
              <button
                type='submit'
                className='btn btn-primary'
                disabled={compLoading}
                style={{ marginTop: 'var(--space-3)' }}
              >
                {compLoading ? 'Сохранение...' : 'Сохранить изменения'}
              </button>
            ) : (
              <p
                style={{
                  color: 'var(--color-muted)',
                  fontSize: '0.8125rem',
                  marginTop: 'var(--space-3)',
                }}
              >
                Изменение параметров компании доступно только владельцу.
              </p>
            )}
          </form>
        </div>
      )}
    </div>
  )
}
