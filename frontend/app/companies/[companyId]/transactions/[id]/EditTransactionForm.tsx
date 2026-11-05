'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import type { Category, Transaction, TransactionDirection } from '@/lib/types'
import { parseSignedMoney, formatMoneyRub } from '@/lib/money'
import { clientPatch, clientDelete, ApiClientError } from '@/lib/api-client'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import Button from '@/components/ui/Button'
import { useToast } from '@/components/ui/ToastProvider'

interface EditTransactionFormProps {
  companyId: number
  transaction: Transaction
  categories: Category[]
  todayMoscow: string
}

export default function EditTransactionForm({
  companyId,
  transaction,
  categories,
  todayMoscow,
}: EditTransactionFormProps) {
  const router = useRouter()
  const notify = useToast()

  const [operationDate, setOperationDate] = useState(transaction.operation_date)
  const [rawAmount, setRawAmount] = useState(
    transaction.direction === 'inflow'
      ? `+${transaction.amount}`
      : `−${transaction.amount}`,
  )
  const [direction, setDirection] = useState<TransactionDirection>(
    transaction.direction,
  )
  const [categoryId, setCategoryId] = useState<string>(
    transaction.category_id !== null ? String(transaction.category_id) : '',
  )
  const [purpose, setPurpose] = useState(transaction.purpose || '')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const handleAmountChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setRawAmount(val)

    if (val.startsWith('+')) {
      setDirection('inflow')
    } else if (val.startsWith('-') || val.startsWith('−')) {
      setDirection('outflow')
    }
  }

  const handleDirectionToggle = (newDir: TransactionDirection) => {
    setDirection(newDir)
    if (
      rawAmount.startsWith('+') ||
      rawAmount.startsWith('-') ||
      rawAmount.startsWith('−')
    ) {
      const rest = rawAmount.slice(1).trim()
      setRawAmount(newDir === 'inflow' ? `+${rest}` : `−${rest}`)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const parsed = parseSignedMoney(rawAmount, direction)
    if (!parsed.ok) {
      setError(parsed.error)
      return
    }

    setLoading(true)

    try {
      await clientPatch(
        `/api/companies/${companyId}/transactions/${transaction.id}`,
        {
          operation_date: operationDate,
          amount: parsed.amount,
          direction: parsed.direction,
          category_id: categoryId ? parseInt(categoryId, 10) : null,
          purpose: purpose.trim() || null,
        },
      )

      notify('Операция сохранена')
      router.push(`/companies/${companyId}/transactions`)
      router.refresh()
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Ошибка сохранения операции')
      } else {
        setError('Не удалось обновить операцию')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    setLoading(true)
    setError(null)

    try {
      await clientDelete(
        `/api/companies/${companyId}/transactions/${transaction.id}`,
      )
      notify('Операция удалена')
      router.push(`/companies/${companyId}/transactions`)
      router.refresh()
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Ошибка при удалении операции')
      } else {
        setError('Не удалось удалить операцию')
      }
      setConfirmDelete(false)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        backgroundColor: 'var(--color-paper-2)',
        padding: 'var(--space-5)',
        borderRadius: 'var(--radius-surface)',
        border: '1px solid var(--color-rule)',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 'var(--space-4)',
        }}
      >
        <div>
          <h1
            className='page-title'
            style={{ fontSize: '1.5rem', marginBottom: 'var(--space-1)' }}
          >
            Редактирование операции #{transaction.id}
          </h1>
          <p className='page-subtitle'>
            Изменение параметров или удаление существующей проводки
          </p>
        </div>

        {!confirmDelete && (
          <button
            type='button'
            className='btn btn-danger'
            style={{ padding: '6px 12px', fontSize: '0.8125rem' }}
            onClick={() => setConfirmDelete(true)}
            disabled={loading}
          >
            Удалить операцию
          </button>
        )}
      </div>

      {confirmDelete && (
        <div
          className='notice notice-error'
          style={{ marginBottom: 'var(--space-4)' }}
        >
          <p style={{ margin: '0 0 var(--space-3)' }}>
            <strong>Подтверждение удаления:</strong> Вы уверены, что хотите
            удалить операцию от{' '}
            <span style={{ fontVariantNumeric: 'tabular-nums' }}>
              {transaction.operation_date}
            </span>{' '}
            на сумму{' '}
            <strong>
              {formatMoneyRub(transaction.amount, transaction.direction)}
            </strong>
            ?
          </p>
          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            <Button
              type='button'
              variant='danger'
              style={{
                padding: '6px 14px',
                minHeight: '34px',
                fontSize: '0.875rem',
              }}
              onClick={handleDelete}
              pending={loading}
              pendingLabel='Удаление…'
            >
              Да, удалить безвозвратно
            </Button>
            <button
              type='button'
              className='btn btn-secondary'
              style={{
                padding: '6px 14px',
                minHeight: '34px',
                fontSize: '0.875rem',
              }}
              onClick={() => setConfirmDelete(false)}
              disabled={loading}
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {error && (
        <div
          className='notice notice-error'
          role='alert'
          style={{ marginBottom: 'var(--space-4)' }}
        >
          {error}
        </div>
      )}

      <form onSubmit={handleSave} aria-busy={loading}>
        {/* Date */}
        <div className='form-group'>
          <label className='form-label' htmlFor='txDate'>
            Дата операции *
          </label>
          <Input
            id='txDate'
            type='date'
            required
            max={todayMoscow}
            className='form-input'
            value={operationDate}
            onChange={e => setOperationDate(e.target.value)}
            disabled={loading}
          />
        </div>

        {/* Direction & Amount */}
        <div className='form-group'>
          <label className='form-label' htmlFor='txAmount'>
            Сумма и направление *
          </label>
          <div
            style={{
              display: 'flex',
              gap: 'var(--space-2)',
              marginBottom: 'var(--space-2)',
            }}
          >
            <button
              type='button'
              className={`btn ${direction === 'inflow' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, minHeight: '36px', fontSize: '0.875rem' }}
              onClick={() => handleDirectionToggle('inflow')}
              disabled={loading}
            >
              + Поступление
            </button>
            <button
              type='button'
              className={`btn ${direction === 'outflow' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ flex: 1, minHeight: '36px', fontSize: '0.875rem' }}
              onClick={() => handleDirectionToggle('outflow')}
              disabled={loading}
            >
              − Выплата
            </button>
          </div>

          <Input
            id='txAmount'
            type='text'
            required
            className='form-input'
            value={rawAmount}
            onChange={handleAmountChange}
            disabled={loading}
            style={{
              fontSize: '1.125rem',
              fontWeight: 600,
              fontVariantNumeric: 'tabular-nums',
            }}
          />
        </div>

        {/* Category */}
        <div className='form-group'>
          <label className='form-label' htmlFor='txCategory'>
            Категория
          </label>
          <Select
            id='txCategory'
            className='form-select'
            value={categoryId}
            onChange={e => setCategoryId(e.target.value)}
            disabled={loading}
          >
            <option value=''>Без категории</option>
            {categories.map(c => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>

        {/* Purpose */}
        <div className='form-group'>
          <label className='form-label' htmlFor='txPurpose'>
            Назначение платежа
          </label>
          <Input
            id='txPurpose'
            type='text'
            maxLength={500}
            className='form-input'
            value={purpose}
            onChange={e => setPurpose(e.target.value)}
            disabled={loading}
          />
        </div>

        <div
          style={{
            display: 'flex',
            gap: 'var(--space-3)',
            marginTop: 'var(--space-5)',
          }}
        >
          <Button
            type='submit'
            className='btn btn-primary'
            style={{ minWidth: '140px' }}
            pending={loading}
            pendingLabel='Сохранение…'
          >
            Сохранить изменения
          </Button>
          <Link
            href={`/companies/${companyId}/transactions`}
            className='btn btn-secondary'
          >
            Отмена
          </Link>
        </div>
      </form>
    </div>
  )
}
