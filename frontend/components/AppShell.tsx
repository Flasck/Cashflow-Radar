'use client'

import { useEffect, useId, useOptimistic, useState, useTransition } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import type { Company, User } from '@/lib/types'
import { roleLabels } from '@/lib/labels'
import LogoutButton from './LogoutButton'
import Modal from './Modal'
import PendingLink from './ui/PendingLink'
import Spinner from './ui/Spinner'

const iconPaths = {
  operations: 'M4 5h16M4 12h16M4 19h16M8 3v18',
  forecast: 'M3 17l6-7 4 4 8-10M15 4h6v6',
  settings: 'M4 7h16M4 17h16M9 4v6M16 14v6',
  companies: 'M4 21V3h11v18M15 9h5v12M8 7h3M8 11h3M8 15h3M2 21h20',
  invitations: 'M3 5h18v14H3zM3 6l9 7 9-7',
  account: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-2a8 8 0 0 1 16 0v2',
}

function Icon({ name }: { name: keyof typeof iconPaths }) {
  return (
    <svg
      width='20'
      height='20'
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='1.6'
      strokeLinecap='round'
      strokeLinejoin='round'
      aria-hidden='true'
    >
      <path d={iconPaths[name]} />
    </svg>
  )
}

interface NavigationProps {
  user: User
  companies: Company[]
  currentCompany?: Company
  pendingCount: number
  onNavigate?: () => void
}

function Navigation({
  user,
  companies,
  currentCompany,
  pendingCount,
  onNavigate,
}: NavigationProps) {
  const pathname = usePathname()
  const router = useRouter()
  const companyId = currentCompany?.id
  const [expandedId, setExpandedId] = useOptimistic(companyId)
  const [navigating, startNavigation] = useTransition()
  const navigationId = useId()
  const links: {
    href: string
    label: string
    icon: keyof typeof iconPaths
    active: boolean
  }[] = [
    {
      href: 'transactions',
      label: 'Операции',
      icon: 'operations',
      active:
        pathname.includes('/transactions') || pathname.includes('/import'),
    },
    {
      href: 'forecast',
      label: 'Прогноз',
      icon: 'forecast',
      active: pathname.includes('/forecast'),
    },
    {
      href: 'settings',
      label: 'Настройки компании',
      icon: 'settings',
      active: pathname.includes('/settings'),
    },
  ]

  return (
    <>
      <Link
        href='/companies'
        className='app-brand sidebar-brand'
        onClick={onNavigate}
      >
        <span className='brand-mark' aria-hidden='true'>
          ↗
        </span>{' '}
        CashFlow Radar
      </Link>
      <div className='sidebar-companies'>
        <div className='sidebar-section-heading'>
          Ваши компании <span>{companies.length}</span>
        </div>
        {companies.length === 0 && (
          <p className='sidebar-empty'>
            Создайте компанию или примите приглашение.
          </p>
        )}
        <ul className='company-tree' aria-label='Компании'>
          {companies.map(company => {
            const selected = company.id === companyId
            const expanded = company.id === expandedId
            const sectionsId = `${navigationId}-company-${company.id}`
            return (
              <li key={company.id}>
                <PendingLink
                  href={`/companies/${company.id}/transactions`}
                  onClick={event => {
                    if (
                      event.button !== 0 ||
                      event.metaKey ||
                      event.ctrlKey ||
                      event.shiftKey ||
                      event.altKey
                    )
                      return
                    event.preventDefault()
                    startNavigation(() => {
                      setExpandedId(company.id)
                      router.push(`/companies/${company.id}/transactions`)
                    })
                    onNavigate?.()
                  }}
                  className={`company-entry ${selected ? 'selected' : ''}`}
                  aria-current={selected ? 'true' : undefined}
                  aria-expanded={expanded}
                  aria-controls={sectionsId}
                >
                  <span className='company-monogram' aria-hidden='true'>
                    {company.name.slice(0, 1).toLocaleUpperCase('ru')}
                  </span>
                  <span className='company-entry-copy'>
                    <strong title={company.name}>{company.name}</strong>
                    <span>
                      {roleLabels[company.role]}
                      {selected ? ' · Рабочая' : ''}
                    </span>
                  </span>
                  {navigating && expanded ? (
                    <Spinner />
                  ) : (
                    <svg
                      className='company-chevron'
                      width='16'
                      height='16'
                      viewBox='0 0 24 24'
                      fill='none'
                      stroke='currentColor'
                      strokeWidth='1.6'
                      aria-hidden='true'
                    >
                      <path d='m7 10 5 5 5-5' />
                    </svg>
                  )}
                </PendingLink>
                <div
                  className={`company-reveal ${expanded ? 'is-expanded' : ''}`}
                  inert={!expanded}
                  aria-hidden={!expanded}
                  id={sectionsId}
                >
                  <div className='company-reveal-inner'>
                    <nav
                      className='company-sections'
                      aria-label={`Разделы компании ${company.name}`}
                    >
                      {links.map(link => (
                        <PendingLink
                          key={link.href}
                          href={`/companies/${company.id}/${link.href}`}
                          onClick={onNavigate}
                          className={`sidebar-link ${selected && link.active ? 'active' : ''}`}
                          aria-current={
                            selected && link.active ? 'page' : undefined
                          }
                        >
                          <Icon name={link.icon} />
                          {link.label}
                        </PendingLink>
                      ))}
                    </nav>
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      </div>
      <nav
        className='sidebar-nav personal-nav'
        aria-label='Личное пространство'
      >
        <PendingLink
          href='/companies'
          onClick={onNavigate}
          className={`sidebar-link ${pathname === '/companies' ? 'active' : ''}`}
          aria-current={pathname === '/companies' ? 'page' : undefined}
        >
          <Icon name='companies' />
          Все компании
        </PendingLink>
        <PendingLink
          href='/invitations'
          onClick={onNavigate}
          className={`sidebar-link ${pathname === '/invitations' ? 'active' : ''}`}
          aria-current={pathname === '/invitations' ? 'page' : undefined}
        >
          <Icon name='invitations' />
          Приглашения
          {pendingCount > 0 && (
            <span
              className='nav-count'
              aria-label={`${pendingCount} ожидают ответа`}
            >
              {pendingCount}
            </span>
          )}
        </PendingLink>
      </nav>
      <div className='sidebar-profile'>
        <PendingLink
          href='/account'
          onClick={onNavigate}
          className={`profile-link ${pathname === '/account' ? 'active' : ''}`}
          aria-current={pathname === '/account' ? 'page' : undefined}
        >
          <span className='avatar' aria-hidden='true'>
            {user.full_name.slice(0, 1).toLocaleUpperCase('ru')}
          </span>
          <span className='profile-copy'>
            <strong title={user.full_name}>{user.full_name}</strong>
            <span>Настройки аккаунта</span>
          </span>
          <Icon name='settings' />
        </PendingLink>
        <LogoutButton />
      </div>
    </>
  )
}

export default function AppShell({
  children,
  ...navigation
}: NavigationProps & { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false)
  useEffect(() => {
    if (navigation.currentCompany) {
      document.cookie = `radar_company_${navigation.user.id}=${navigation.currentCompany.id}; Path=/; SameSite=Lax`
    }
  }, [navigation.currentCompany, navigation.user.id])
  return (
    <div className='app-shell'>
      <a href='#workspace' className='skip-link'>
        К содержимому
      </a>
      <aside className='sidebar'>
        <Navigation {...navigation} />
      </aside>
      <header className='mobile-header'>
        <Link className='app-brand' href='/companies'>
          CashFlow Radar
        </Link>
        <button
          className='btn btn-secondary'
          type='button'
          aria-haspopup='dialog'
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen(true)}
        >
          Меню
          {navigation.pendingCount > 0 ? ` (${navigation.pendingCount})` : ''}
        </button>
        {navigation.currentCompany && (
          <span className='mobile-company'>
            {navigation.currentCompany.name}
          </span>
        )}
      </header>
      {menuOpen && (
        <Modal title='Навигация' onClose={() => setMenuOpen(false)}>
          <div className='mobile-navigation'>
            <Navigation {...navigation} onNavigate={() => setMenuOpen(false)} />
          </div>
        </Modal>
      )}
      <div className='workspace' id='workspace' tabIndex={-1}>
        {children}
      </div>
    </div>
  )
}
