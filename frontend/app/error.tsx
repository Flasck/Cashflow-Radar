'use client'

import Link from 'next/link'

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className='app-container'>
      <div className='page-header'>
        <h1 className='page-title'>Не удалось загрузить страницу</h1>
      </div>
      <div className='notice notice-error' role='alert'>
        Проверьте соединение и попробуйте ещё раз. Несохранённые изменения могли
        быть потеряны.
      </div>
      <div className='row-actions'>
        <button className='btn btn-primary' onClick={reset}>
          Попробовать снова
        </button>
        <Link href='/companies' className='btn btn-secondary'>
          К компаниям
        </Link>
      </div>
    </main>
  )
}
