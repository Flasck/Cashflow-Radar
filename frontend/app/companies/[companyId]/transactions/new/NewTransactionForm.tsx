'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import type { Category, TransactionDirection, Transaction } from '@/lib/types'
import { parseSignedMoney } from '@/lib/money'
import { clientPost, ApiClientError } from '@/lib/api-client'
import Input from '@/components/ui/Input'
import Select from '@/components/ui/Select'
import Button from '@/components/ui/Button'
import { useToast } from '@/components/ui/ToastProvider'

interface NewTransactionFormProps {
  companyId: number
  categories: Category[]
  todayMoscow: string
}

export default function NewTransactionForm({
  companyId,
  categories,
  todayMoscow,
}: NewTransactionFormProps) {
  const router = useRouter()
  const notify = useToast()

  const [operationDate, setOperationDate] = useState(todayMoscow)
  const [rawAmount, setRawAmount] = useState('')
  const [direction, setDirection] = useState<TransactionDirection>('inflow')
  const [categoryId, setCategoryId] = useState<string>('')
  const [purpose, setPurpose] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAmountChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    setRawAmount(val)

    // Dynamic sync of sign with direction
    if (val.startsWith('+')) {
      setDirection('inflow')
    } else if (val.startsWith('-') || val.startsWith('−')) {
      setDirection('outflow')
    }
  }

  const handleDirectionToggle = (newDir: TransactionDirection) => {
    setDirection(newDir)
    // If rawAmount already has a sign prefix, replace it
    if (
      rawAmount.startsWith('+') ||
      rawAmount.startsWith('-') ||
      rawAmount.startsWith('−')
    ) {
      const rest = rawAmount.slice(1).trim()
      setRawAmount(newDir === 'inflow' ? `+${rest}` : `−${rest}`)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const parsed = parseSignedMoney(rawAmount, direction)
    if (!parsed.ok) {
      setError(parsed.error)
      return
    }

    setLoading(true)

    try {
      await clientPost<Transaction>(
        `/api/companies/${companyId}/transactions`,
        {
          operation_date: operationDate,
          amount: parsed.amount,
          direction: parsed.direction,
          category_id: categoryId ? parseInt(categoryId, 10) : null,
          purpose: purpose.trim() || null,
        },
      )

      notify('Операция добавлена')
      router.push(`/companies/${companyId}/transactions`)
      router.refresh()
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Ошибка сохранения операции')
      } else {
        setError('Не удалось сохранить операцию')
      }
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
      <div style={{ marginBottom: 'var(--space-4)' }}>
        <h1
          className='page-title'
          style={{ fontSize: '1.5rem', marginBottom: 'var(--space-1)' }}
        >
          Новая операция
        </h1>
        <p className='page-subtitle'>
          Внесение фактического поступления или выплаты в журнал
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

      <form onSubmit={handleSubmit} aria-busy={loading}>
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

        {/* Direction Toggle & Amount */}
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
            placeholder={direction === 'inflow' ? '+15 000,00' : '−15 000,00'}
            value={rawAmount}
            onChange={handleAmountChange}
            disabled={loading}
            style={{
              fontSize: '1.125rem',
              fontWeight: 600,
              fontVariantNumeric: 'tabular-nums',
            }}
          />
          <span className='form-hint'>
            Разрешены пробелы группировки, точка или запятая. Знак (+/−) в
            строке автоматически определяет тип.
          </span>
        </div>

        {/* Category (Optional) */}
        <div className='form-group'>
          <label className='form-label' htmlFor='txCategory'>
            Категория (необязательно)
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

        {/* Purpose (Optional) */}
        <div className='form-group'>
          <label className='form-label' htmlFor='txPurpose'>
            Назначение платежа / контрагент (необязательно)
          </label>
          <Input
            id='txPurpose'
            type='text'
            maxLength={500}
            className='form-input'
            placeholder='например, Оплата аренды склада за ноябрь'
            value={purpose}
            onChange={e => setPurpose(e.target.value)}
            disabled={loading}
          />
        </div>

        {/* Action buttons */}
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
            Сохранить
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
