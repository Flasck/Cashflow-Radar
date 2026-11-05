import type { CompanyRole, Invitation } from './types'

export const roleLabels: Record<CompanyRole, string> = {
  owner: 'Владелец',
  treasurer: 'Казначей',
  viewer: 'Наблюдатель',
}

export const invitationLabels: Record<Invitation['status'], string> = {
  pending: 'Ожидает ответа',
  accepted: 'Принято',
  declined: 'Отклонено',
  revoked: 'Отозвано',
  expired: 'Срок истёк',
}

export function invitationStatus(
  invitation: Invitation,
  now: number,
): Invitation['status'] {
  return invitation.status === 'pending' &&
    Date.parse(invitation.expires_at) <= now
    ? 'expired'
    : invitation.status
}

export function displayDate(value: string | null): string {
  return value
    ? new Date(value).toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Europe/Moscow',
      })
    : '—'
}
