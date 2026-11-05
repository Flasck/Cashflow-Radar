'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import type {
  ImportPreviewResponse,
  ImportCommitResponse,
  ImportCommitRow,
  TransactionDirection,
} from '@/lib/types'
import { clientUpload, clientPost, ApiClientError } from '@/lib/api-client'
import { formatMoneyRub } from '@/lib/money'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { useToast } from '@/components/ui/ToastProvider'

interface ImportFlowProps {
  companyId: number
}

export default function ImportFlow({ companyId }: ImportFlowProps) {
  const router = useRouter()
  const notify = useToast()

  const [step, setStep] = useState<'upload' | 'preview' | 'success'>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(
    null,
  )
  const [commitResult, setCommitResult] = useState<ImportCommitResponse | null>(
    null,
  )

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0]
      if (selected.size > 5 * 1024 * 1024) {
        setFile(null)
        e.target.value = ''
        setError('Файл превышает допустимый размер 5 МБ')
        return
      }
      setFile(selected)
      setError(null)
    } else {
      setFile(null)
    }
  }

  const handleUploadPreview = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError('Выберите файл для загрузки')
      return
    }

    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await clientUpload<ImportPreviewResponse>(
        `/api/companies/${companyId}/imports/preview`,
        formData,
      )
      setPreviewData(res)
      setStep('preview')
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Ошибка обработки файла на сервере')
      } else {
        setError('Не удалось загрузить файл на проверку')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleCommit = async () => {
    if (
      !previewData ||
      !previewData.can_commit ||
      previewData.summary.error_rows > 0
    ) {
      setError('Нельзя подтвердить импорт файла с ошибками')
      return
    }

    setLoading(true)
    setError(null)

    const payloadRows: ImportCommitRow[] = previewData.rows.map(r => ({
      operation_date: r.operation_date,
      amount: r.amount,
      direction: r.direction as TransactionDirection,
      category: r.category,
      purpose: r.purpose,
    }))

    try {
      const res = await clientPost<ImportCommitResponse>(
        `/api/companies/${companyId}/imports/commit`,
        { rows: payloadRows },
      )
      setCommitResult(res)
      setStep('success')
      notify('Импорт завершён. Операции добавлены.')
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Ошибка сохранения импортированных записей')
      } else {
        setError(
          'Не удалось сохранить данные. Проверьте список операций перед повторной отправкой.',
        )
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto' }}>
      <div className='page-header' style={{ marginBottom: 'var(--space-4)' }}>
        <div>
          <h1 className='page-title'>Импорт выписки</h1>
          <p className='page-subtitle'>
            Загрузка операций из файлов CSV или XLSX по единому шаблону
          </p>
        </div>
        <Link
          href={`/companies/${companyId}/transactions`}
          className='btn btn-secondary'
        >
          Вернуться в журнал
        </Link>
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

      {/* STEP 1: FILE SELECTION */}
      {step === 'upload' && (
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
              marginBottom: 'var(--space-4)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 'var(--space-3)',
            }}
          >
            <div>
              <h2 style={{ fontSize: '1.125rem', margin: 0 }}>
                Шаг 1: Выбор файла
              </h2>
              <span
                style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}
              >
                Поддерживаются форматы .csv (UTF-8) и .xlsx (лист transactions,
                до 5 МБ, до 5000 строк)
              </span>
            </div>
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              <a
                href={`/api/companies/${companyId}/imports/template?format=csv`}
                download='cashflow_template.csv'
                className='btn btn-secondary'
                style={{ fontSize: '0.8125rem', padding: '6px 12px' }}
              >
                Скачать шаблон CSV
              </a>
              <a
                href={`/api/companies/${companyId}/imports/template?format=xlsx`}
                download='cashflow_template.xlsx'
                className='btn btn-secondary'
                style={{ fontSize: '0.8125rem', padding: '6px 12px' }}
              >
                Скачать шаблон XLSX
              </a>
            </div>
          </div>

          <div
            style={{
              padding: 'var(--space-4)',
              border: '1px dashed var(--color-field-border)',
              borderRadius: 'var(--radius-field)',
              backgroundColor: 'var(--color-paper)',
              marginBottom: 'var(--space-4)',
            }}
          >
            <p
              style={{
                margin: '0 0 var(--space-2)',
                fontSize: '0.875rem',
                fontWeight: 600,
              }}
            >
              Требования к колонкам шаблона:
            </p>
            <ul
              style={{
                margin: 0,
                paddingLeft: '20px',
                fontSize: '0.8125rem',
                color: 'var(--color-muted)',
                lineHeight: 1.6,
              }}
            >
              <li>
                <code>date</code>: дата операции в формате YYYY-MM-DD (или
                нативная дата Excel без времени).
              </li>
              <li>
                <code>amount</code>: сумма (может быть со знаком: отрицательная
                сумма автоматически трактуется как выплата).
              </li>
              <li>
                <code>direction</code>: необязательно (<code>inflow</code> или{' '}
                <code>outflow</code>).
              </li>
              <li>
                <code>category</code>: необязательно (название категории, новые
                будут созданы автоматически).
              </li>
              <li>
                <code>purpose</code>: необязательно (назначение платежа).
              </li>
            </ul>
          </div>

          <form onSubmit={handleUploadPreview} aria-busy={loading}>
            <div className='form-group'>
              <label className='form-label' htmlFor='importFile'>
                Файл для загрузки (.csv или .xlsx)
              </label>
              <Input
                id='importFile'
                type='file'
                accept='.csv, .xlsx, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, text/csv'
                onChange={handleFileChange}
                className='form-input'
                style={{ padding: '8px' }}
                disabled={loading}
              />
              {file && (
                <span
                  className='form-hint'
                  style={{ marginTop: 'var(--space-1)' }}
                >
                  Выбран: {file.name} ({(file.size / 1024).toFixed(1)} КБ)
                </span>
              )}
            </div>

            <Button
              type='submit'
              className='btn btn-primary'
              pending={loading}
              pendingLabel='Проверяем файл…'
              disabled={!file}
              style={{ minWidth: '160px', marginTop: 'var(--space-2)' }}
            >
              Проверить файл
            </Button>
          </form>
        </div>
      )}

      {/* STEP 2: PREVIEW */}
      {step === 'preview' && previewData && (
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
              flexWrap: 'wrap',
              gap: 'var(--space-3)',
            }}
          >
            <div>
              <h2 style={{ fontSize: '1.125rem', margin: 0 }}>
                Шаг 2: Предпросмотр и сверка
              </h2>
              <span
                style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}
              >
                Проверьте распознанные строки и суммы перед внесением в базу
                данных
              </span>
            </div>
            <button
              type='button'
              className='btn btn-secondary'
              onClick={() => {
                setStep('upload')
                setPreviewData(null)
              }}
              disabled={loading}
              style={{ fontSize: '0.8125rem', padding: '6px 12px' }}
            >
              Выбрать другой файл
            </button>
          </div>

          {/* Summary metrics */}
          <div
            className='totals-ribbon'
            style={{ marginBottom: 'var(--space-4)' }}
          >
            <div className='totals-item'>
              <span className='totals-label'>Всего строк в файле</span>
              <span className='totals-value'>
                {previewData.summary.total_rows}
              </span>
            </div>
            <div className='totals-item'>
              <span className='totals-label'>Корректных строк</span>
              <span
                className='totals-value'
                style={{ color: 'var(--color-inflow)' }}
              >
                {previewData.summary.valid_rows}
              </span>
            </div>
            {previewData.summary.error_rows > 0 && (
              <div className='totals-item'>
                <span className='totals-label'>Строк с ошибками</span>
                <span
                  className='totals-value'
                  style={{ color: 'var(--color-error)' }}
                >
                  {previewData.summary.error_rows}
                </span>
              </div>
            )}
            <div className='totals-item'>
              <span className='totals-label'>Поступления</span>
              <span className='totals-value amount-inflow'>
                {formatMoneyRub(previewData.summary.total_inflow, 'inflow')}
              </span>
            </div>
            <div className='totals-item'>
              <span className='totals-label'>Выплаты</span>
              <span className='totals-value amount-outflow'>
                {formatMoneyRub(previewData.summary.total_outflow, 'outflow')}
              </span>
            </div>
          </div>

          {/* New categories notice */}
          {previewData.new_categories &&
            previewData.new_categories.length > 0 && (
              <div
                className='notice notice-warning'
                style={{ marginBottom: 'var(--space-4)' }}
              >
                <strong>
                  Будут созданы новые категории (
                  {previewData.new_categories.length}):
                </strong>{' '}
                {previewData.new_categories.join(', ')}
              </div>
            )}

          {/* Blocking error banner */}
          {(!previewData.can_commit ||
            (previewData.errors && previewData.errors.length > 0)) && (
            <div
              className='notice notice-error'
              style={{ marginBottom: 'var(--space-4)' }}
            >
              <p style={{ margin: 0, fontWeight: 600 }}>
                В файле обнаружены ошибки ({previewData.errors.length}). Импорт
                заблокирован:
              </p>
              <ul style={{ margin: 'var(--space-2) 0 0', paddingLeft: '20px' }}>
                {previewData.errors.map((errItem, idx) => (
                  <li key={idx}>
                    {errItem.row_number > 0
                      ? `Строка ${errItem.row_number}${errItem.column ? ` (${errItem.column})` : ''}: ${errItem.message}`
                      : errItem.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Rows preview table or empty state */}
          {previewData.rows.length === 0 ? (
            <div
              style={{
                padding: 'var(--space-4)',
                textAlign: 'center',
                color: 'var(--color-muted)',
                backgroundColor: 'var(--color-paper)',
                borderRadius: 'var(--radius-field)',
                border: '1px solid var(--color-rule)',
                marginBottom: 'var(--space-4)',
              }}
            >
              Строки операций не обнаружены в файле.
            </div>
          ) : (
            <div
              className='ledger-wrapper'
              style={{
                maxHeight: '360px',
                overflowY: 'auto',
                marginBottom: 'var(--space-4)',
                borderRadius: 'var(--radius-field)',
                border: '1px solid var(--color-rule)',
              }}
            >
              <table className='ledger-table' style={{ fontSize: '0.8125rem' }}>
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}>№</th>
                    <th style={{ width: '100px' }}>Дата</th>
                    <th style={{ width: '110px' }}>Тип</th>
                    <th className='num-cell' style={{ width: '120px' }}>
                      Сумма
                    </th>
                    <th>Категория</th>
                    <th>Назначение</th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {previewData.rows.map(row => {
                    const isValidDirection =
                      row.direction === 'inflow' || row.direction === 'outflow'
                    const showFormatted = row.is_valid && isValidDirection

                    return (
                      <tr
                        key={row.row_number}
                        style={{
                          backgroundColor: !row.is_valid
                            ? 'var(--color-error-surface)'
                            : undefined,
                        }}
                      >
                        <td style={{ color: 'var(--color-muted)' }}>
                          {row.row_number}
                        </td>
                        <td>
                          {row.operation_date || (
                            <span style={{ color: 'var(--color-muted)' }}>
                              {'\u2014'}
                            </span>
                          )}
                        </td>
                        <td>
                          {showFormatted ? (
                            <span
                              className={`badge ${row.direction === 'inflow' ? 'badge-inflow' : 'badge-outflow'}`}
                            >
                              {row.direction === 'inflow'
                                ? 'Поступление'
                                : 'Выплата'}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--color-error)' }}>
                              {row.direction || '\u2014'}
                            </span>
                          )}
                        </td>
                        <td
                          className={`num-cell ${showFormatted ? (row.direction === 'inflow' ? 'amount-inflow' : 'amount-outflow') : ''}`}
                        >
                          {showFormatted ? (
                            formatMoneyRub(
                              row.amount,
                              row.direction as TransactionDirection,
                            )
                          ) : (
                            <span
                              style={{
                                color: 'var(--color-error)',
                                fontVariantNumeric: 'tabular-nums',
                              }}
                            >
                              {row.amount}
                            </span>
                          )}
                        </td>
                        <td>
                          {row.category || (
                            <span style={{ color: 'var(--color-muted)' }}>
                              {'\u2014'}
                            </span>
                          )}
                        </td>
                        <td>
                          {row.purpose || (
                            <span style={{ color: 'var(--color-muted)' }}>
                              {'\u2014'}
                            </span>
                          )}
                        </td>
                        <td>
                          {row.is_valid ? (
                            <span
                              style={{
                                color: 'var(--color-inflow)',
                                fontWeight: 600,
                              }}
                            >
                              ОК
                            </span>
                          ) : (
                            <span style={{ color: 'var(--color-error)' }}>
                              {row.errors && row.errors.length > 0
                                ? row.errors.join('; ')
                                : 'Ошибка'}
                            </span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Action buttons */}
          <div
            style={{
              display: 'flex',
              gap: 'var(--space-3)',
              alignItems: 'center',
            }}
          >
            <Button
              type='button'
              className='btn btn-primary'
              pending={loading}
              pendingLabel='Импортируем…'
              disabled={!previewData.can_commit}
              onClick={handleCommit}
              style={{ minWidth: '180px' }}
            >
              {`Добавить ${previewData.summary.valid_rows} операций`}
            </Button>
            <span
              style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}
            >
              Внимание: повторная загрузка того же файла создаст повторные
              операции.
            </span>
          </div>
        </div>
      )}

      {/* STEP 3: SUCCESS */}
      {step === 'success' && commitResult && (
        <div
          style={{
            backgroundColor: 'var(--color-paper-2)',
            padding: 'var(--space-6)',
            borderRadius: 'var(--radius-surface)',
            border: '1px solid var(--color-rule)',
            textAlign: 'center',
          }}
        >
          <h2
            style={{
              fontSize: '1.25rem',
              color: 'var(--color-inflow)',
              marginTop: 0,
              marginBottom: 'var(--space-2)',
            }}
          >
            Импорт успешно завершен
          </h2>
          <p
            style={{
              color: 'var(--color-ink)',
              marginBottom: 'var(--space-4)',
              fontSize: '0.9375rem',
            }}
          >
            Добавлено операций: <strong>{commitResult.imported_count}</strong>.
            {commitResult.created_categories_count > 0 && (
              <>
                {' '}
                Создано новых категорий:{' '}
                <strong>{commitResult.created_categories_count}</strong>.
              </>
            )}
          </p>
          <button
            type='button'
            className='btn btn-primary'
            onClick={() => {
              router.push(`/companies/${companyId}/transactions`)
              router.refresh()
            }}
          >
            Перейти в журнал операций
          </button>
        </div>
      )}
    </div>
  )
}
