'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { clientPost, ApiClientError } from '@/lib/api-client'
import type { Company } from '@/lib/types'
import Modal from '@/components/Modal'
import Input from '@/components/ui/Input'
import Button from '@/components/ui/Button'
import { useToast } from '@/components/ui/ToastProvider'

export default function CreateCompanySection() {
  const router = useRouter()
  const notify = useToast()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [industryCode, setIndustryCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) {
      setError('Укажите название компании')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const res = await clientPost<Company>('/api/companies', {
        name: name.trim(),
        industry_code: industryCode.trim() || null,
      })

      setName('')
      setIndustryCode('')
      setOpen(false)
      notify('Компания создана')

      if (res.id) {
        router.push(`/companies/${res.id}/transactions`)
      } else {
        router.refresh()
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        setError(err.message || 'Не удалось создать компанию')
      } else {
        setError('Ошибка при создании компании')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <button
        type='button'
        onClick={() => setOpen(true)}
        className='btn btn-primary'
        aria-haspopup='dialog'
      >
        + Создать компанию
      </button>
      {open && (
        <Modal
          title='Создать компанию'
          onClose={() => {
            if (!loading) {
              setOpen(false)
              setError(null)
            }
          }}
        >
          {error && (
            <div
              className='notice notice-error'
              role='alert'
              style={{ marginBottom: 'var(--space-3)' }}
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} aria-busy={loading}>
            <div className='form-group'>
              <label className='form-label' htmlFor='companyName'>
                Название компании *
              </label>
              <Input
                id='companyName'
                type='text'
                required
                maxLength={160}
                className='form-input'
                placeholder='ООО «Пример»'
                value={name}
                onChange={e => setName(e.target.value)}
                disabled={loading}
              />
            </div>

            <div className='form-group'>
              <label className='form-label' htmlFor='companyIndustry'>
                Код или наименование отрасли (необязательно)
              </label>
              <Input
                id='companyIndustry'
                type='text'
                maxLength={50}
                className='form-input'
                placeholder='например, Оптовая торговля или 46.90'
                value={industryCode}
                onChange={e => setIndustryCode(e.target.value)}
                disabled={loading}
              />
              <span className='form-hint'>Пока не влияет на прогноз</span>
            </div>

            <div
              style={{
                display: 'flex',
                gap: 'var(--space-3)',
                marginTop: 'var(--space-3)',
              }}
            >
              <Button
                type='submit'
                className='btn btn-primary'
                pending={loading}
                pendingLabel='Создание…'
              >
                Создать компанию
              </Button>
              <button
                type='button'
                className='btn btn-secondary'
                onClick={() => {
                  setOpen(false)
                  setError(null)
                }}
                disabled={loading}
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
