'use client'

import { useState } from 'react'
import type {
  Company,
  ForecastResponse,
  DailyAnalyticsResponse,
  DailyAnalyticsItem,
} from '@/lib/types'
import { clientPost, clientFetch, ApiClientError } from '@/lib/api-client'
import ForecastChart from '@/components/ForecastChart'

interface ForecastViewProps {
  company: Company
  initialHistory: DailyAnalyticsItem[]
  todayMoscow: string
}

export default function ForecastView({
  company,
  initialHistory,
  todayMoscow,
}: ForecastViewProps) {
  // Default cutoff is today in Europe/Moscow timezone (computed by server, avoiding UTC client mismatch)
  const [cutoffDate, setCutoffDate] = useState(todayMoscow)
  const [horizonDays, setHorizonDays] = useState<7 | 30>(30)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [forecastResult, setForecastResult] = useState<ForecastResponse | null>(
    null,
  )
  const [historyPoints, setHistoryPoints] =
    useState<DailyAnalyticsItem[]>(initialHistory)
  const [isStale, setIsStale] = useState(false)
  const [staleReason, setStaleReason] = useState<string | null>(null)

  const handleBuildForecast = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      // 1. Calculate past 45 days range for history using strict UTC arithmetic
      const [year, month, day] = cutoffDate.split('-').map(Number)
      const cutoffUtc = new Date(Date.UTC(year, month - 1, day))
      cutoffUtc.setUTCDate(cutoffUtc.getUTCDate() - 45)
      const fromDateStr = cutoffUtc.toISOString().slice(0, 10)

      // Both forecast and analytics must succeed; do not catch analytics silently
      const [forecastRes, dailyRes] = await Promise.all([
        clientPost<ForecastResponse>(`/api/companies/${company.id}/forecast`, {
          history_end: cutoffDate,
          horizon_days: horizonDays,
        }),
        clientFetch<DailyAnalyticsResponse>(
          `/api/companies/${company.id}/analytics/daily?date_from=${fromDateStr}&date_to=${cutoffDate}`,
        ),
      ])

      setForecastResult(forecastRes)
      setHistoryPoints(dailyRes.items || [])

      setIsStale(false)
      setStaleReason(null)
    } catch (err) {
      // On failed rerun, clear old result to prevent presenting invalid prior data as current
      setForecastResult(null)
      setIsStale(false)
      setStaleReason(null)

      if (err instanceof ApiClientError) {
        if (err.code === 'INSUFFICIENT_HISTORY') {
          setError(
            'Для построения прогноза требуется минимум 30 календарных дней истории операций.',
          )
        } else {
          setError(err.message || 'Ошибка сервиса прогнозирования')
        }
      } else {
        setError('Сервис прогноза временно недоступен. Попробуйте позже.')
      }
    } finally {
      setLoading(false)
    }
  }

  const getWarningText = (warn: string): string => {
    switch (warn) {
      case 'SHORT_HISTORY':
        return 'История менее 90 дней: прогноз имеет повышенную погрешность и носит предварительный характер.'
      case 'SPARSE_HISTORY':
        return 'Разреженная история: менее 10 дней с ненулевым денежным потоком.'
      case 'CONSTANT_HISTORY':
        return 'Постоянный поток: значения в истории не меняются.'
      case 'HISTORY_TRUNCATED':
        return 'История усечена до последних 1825 календарных дней.'
      default:
        return warn
    }
  }

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <div className='page-header'>
        <div>
          <h1 className='page-title'>Прогноз денежных потоков</h1>
          <p className='page-subtitle'>
            Обучаемая модель градиентного бустинга на дневных потоках NetCF
          </p>
        </div>
      </div>

      {/* Configuration Form */}
      <form
        onSubmit={handleBuildForecast}
        style={{
          backgroundColor: 'var(--color-paper-2)',
          padding: 'var(--space-4)',
          borderRadius: 'var(--radius-surface)',
          border: '1px solid var(--color-rule)',
          marginBottom: 'var(--space-4)',
        }}
      >
        <div
          style={{
            display: 'flex',
            gap: 'var(--space-4)',
            flexWrap: 'wrap',
            alignItems: 'flex-end',
          }}
        >
          <div className='form-group' style={{ marginBottom: 0 }}>
            <label className='form-label' htmlFor='cutoffDate'>
              История учтена по (отсечка, МСК)
            </label>
            <input
              id='cutoffDate'
              type='date'
              required
              max={todayMoscow}
              className='form-input'
              value={cutoffDate}
              onChange={e => {
                setCutoffDate(e.target.value)
                if (forecastResult) {
                  setIsStale(true)
                  setStaleReason(
                    'Параметры отсечки изменены. Нажмите «Построить прогноз» для расчета.',
                  )
                }
              }}
              disabled={loading}
              style={{ minHeight: '38px' }}
            />
          </div>

          <div className='form-group' style={{ marginBottom: 0 }}>
            <label className='form-label' id='horizon-label'>
              Горизонт прогноза
            </label>
            <div
              style={{ display: 'flex', gap: 'var(--space-2)' }}
              role='radiogroup'
              aria-labelledby='horizon-label'
            >
              <button
                type='button'
                className={`btn ${horizonDays === 7 ? 'btn-primary' : 'btn-secondary'}`}
                style={{
                  padding: '6px 14px',
                  minHeight: '38px',
                  fontSize: '0.875rem',
                }}
                onClick={() => {
                  setHorizonDays(7)
                  if (forecastResult) {
                    setIsStale(true)
                    setStaleReason(
                      'Горизонт изменен. Нажмите «Построить прогноз» для расчета.',
                    )
                  }
                }}
                disabled={loading}
              >
                7 дней
              </button>
              <button
                type='button'
                className={`btn ${horizonDays === 30 ? 'btn-primary' : 'btn-secondary'}`}
                style={{
                  padding: '6px 14px',
                  minHeight: '38px',
                  fontSize: '0.875rem',
                }}
                onClick={() => {
                  setHorizonDays(30)
                  if (forecastResult) {
                    setIsStale(true)
                    setStaleReason(
                      'Горизонт изменен. Нажмите «Построить прогноз» для расчета.',
                    )
                  }
                }}
                disabled={loading}
              >
                30 дней
              </button>
            </div>
          </div>

          <button
            type='submit'
            className='btn btn-accent'
            style={{ minHeight: '38px', padding: '8px 20px', fontWeight: 600 }}
            disabled={loading}
          >
            {loading ? 'Рассчитываем...' : 'Построить прогноз'}
          </button>
        </div>

        <div
          style={{
            marginTop: 'var(--space-3)',
            fontSize: '0.8125rem',
            color: 'var(--color-muted)',
          }}
        >
          Последняя операция в базе:{' '}
          <strong>{company.last_operation_date || 'нет операций'}</strong>. По
          умолчанию отсечка равна сегодняшнему дню (МСК). Пропуски в истории
          считаются нулями. Если сегодняшний день еще не завершен, выберите
          вчерашнюю дату.
        </div>
      </form>

      {error && (
        <div
          className='notice notice-error'
          role='alert'
          style={{ marginBottom: 'var(--space-4)' }}
        >
          {error}
        </div>
      )}

      {isStale && (
        <div
          className='notice notice-warning'
          style={{ marginBottom: 'var(--space-4)' }}
        >
          {staleReason ||
            'Данные устарели. Нажмите «Построить прогноз» для пересчета.'}
        </div>
      )}

      {/* Warnings from server */}
      {forecastResult &&
        forecastResult.warnings &&
        forecastResult.warnings.length > 0 && (
          <div
            className='notice notice-warning'
            style={{ marginBottom: 'var(--space-4)' }}
          >
            <strong>Предупреждения модели:</strong>
            <ul style={{ margin: 'var(--space-1) 0 0', paddingLeft: '20px' }}>
              {forecastResult.warnings.map((w, idx) => (
                <li key={idx}>{getWarningText(w)}</li>
              ))}
            </ul>
          </div>
        )}

      {/* Forecast Result and Chart */}
      {forecastResult && (
        <div>
          {/* Metadata bar */}
          <div
            style={{
              display: 'flex',
              gap: 'var(--space-4)',
              flexWrap: 'wrap',
              fontSize: '0.8125rem',
              color: 'var(--color-muted)',
              marginBottom: 'var(--space-2)',
              padding: '0 var(--space-2)',
            }}
          >
            <span>
              Модель: <strong>{forecastResult.model}</strong>
            </span>
            <span>
              Валюта: <strong>{forecastResult.currency}</strong>
            </span>
            <span>
              История: с <strong>{forecastResult.history_start}</strong> по{' '}
              <strong>{forecastResult.history_end}</strong> (
              {forecastResult.history_days} дн.)
            </span>
            <span>
              Рассчитано:{' '}
              <strong>
                {forecastResult.generated_at
                  ? new Date(forecastResult.generated_at).toLocaleTimeString(
                      'ru-RU',
                      { hour: '2-digit', minute: '2-digit' },
                    )
                  : 'нет данных'}
              </strong>
            </span>
          </div>

          <ForecastChart
            historyPoints={historyPoints}
            forecastPoints={forecastResult.forecast}
            cutoffDate={forecastResult.history_end}
          />
        </div>
      )}

      {!forecastResult && !loading && (
        <div
          style={{
            padding: 'var(--space-6)',
            textAlign: 'center',
            backgroundColor: 'var(--color-paper-2)',
            borderRadius: 'var(--radius-surface)',
            border: '1px solid var(--color-rule)',
            marginTop: 'var(--space-4)',
          }}
        >
          <h2
            style={{
              fontSize: '1.125rem',
              marginTop: 0,
              marginBottom: 'var(--space-2)',
            }}
          >
            Прогноз еще не построен
          </h2>
          <p
            style={{
              color: 'var(--color-muted)',
              fontSize: '0.875rem',
              maxWidth: '520px',
              margin: '0 auto',
            }}
          >
            Выберите дату окончания истории и горизонт, затем нажмите кнопку
            «Построить прогноз». График отобразит фактическую линию денежного
            потока до отсечки и пунктирную коралловую линию ожидаемого NetCF.
          </p>
        </div>
      )}
    </div>
  )
}
