from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError
from app.models.invitation import Invitation
from app.models.membership import Membership


async def create_invitation(
    session: AsyncSession,
    company_id: int,
    email: str,
    token_hash: str,
    role: str,
    expires_at: datetime,
) -> Invitation:
    invitation = Invitation(
        company_id=company_id,
        email=email.strip().lower(),
        token_hash=token_hash,
        role=role,
        expires_at=expires_at,
    )
    session.add(invitation)
    await session.flush()
    return invitation


async def list_invitations(
    session: AsyncSession,
    company_id: int,
) -> Sequence[Invitation]:
    stmt = (
        select(Invitation)
        .where(Invitation.company_id == company_id)
        .order_by(Invitation.id.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_invitation(
    session: AsyncSession,
    company_id: int,
    invitation_id: int,
) -> Invitation | None:
    stmt = (
        select(Invitation)
        .where(
            Invitation.company_id == company_id,
            Invitation.id == invitation_id,
        )
        .with_for_update()
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_invitation_by_token_hash_for_update(
    session: AsyncSession,
    token_hash: str,
) -> Invitation | None:
    stmt = (
        select(Invitation).where(Invitation.token_hash == token_hash).with_for_update()
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def revoke_invitation(
    session: AsyncSession,
    company_id: int,
    invitation_id: int,
) -> bool:
    invitation = await get_invitation(session, company_id, invitation_id)
    if invitation is None:
        return False
    if invitation.status == "revoked":
        return True
    require_pending_invitation(invitation)
    invitation.status = "revoked"
    invitation.responded_at = datetime.now(UTC)
    await session.flush()
    return True


async def accept_invitation(
    session: AsyncSession,
    invitation: Invitation,
    user_id: int,
) -> Membership:
    invitation.status = "accepted"
    invitation.responded_at = datetime.now(UTC)
    membership = Membership(
        user_id=user_id,
        company_id=invitation.company_id,
        role=invitation.role,
    )
    session.add(membership)
    await session.flush()
    return membership


def require_pending_invitation(invitation: Invitation) -> None:
    if invitation.status != "pending":
        raise ConflictError(
            message="Приглашение уже завершено", code="INVITATION_CLOSED"
        )
