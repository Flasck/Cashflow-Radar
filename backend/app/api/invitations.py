import hashlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_csrf
from app.crud.companies import lock_company
from app.crud.invitations import (
    accept_invitation,
    get_invitation_by_token_hash_for_update,
    require_pending_invitation,
    revoke_pending_invitations,
)
from app.crud.members import get_membership
from app.db.connection import get_db
from app.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.company import Company
from app.models.invitation import Invitation
from app.models.membership import Membership
from app.models.user import User
from app.schemas.companies import (
    AcceptInvitationRequest,
    InvitationResponse,
    PersonalInvitationResponse,
)

router = APIRouter(prefix="/invitations", tags=["invitations"])


def invitation_response(
    invitation: Invitation, token: str | None = None
) -> InvitationResponse:
    status = invitation.status
    if status == "pending" and invitation.expires_at <= datetime.now(UTC):
        status = "expired"
    return InvitationResponse(
        id=invitation.id,
        company_id=invitation.company_id,
        email=invitation.email,
        role=invitation.role,
        created_at=invitation.created_at.isoformat() if invitation.created_at else None,
        expires_at=invitation.expires_at.isoformat(),
        status=status,
        responded_at=invitation.responded_at.isoformat()
        if invitation.responded_at
        else None,
        token=token,
        invite_url=f"/invite#token={token}" if token else None,
    )


async def get_pending_invitation(
    session: AsyncSession,
    token: str,
    user: User,
) -> Invitation:
    token_hash = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
    company_id = await session.scalar(
        select(Invitation.company_id).where(Invitation.token_hash == token_hash)
    )
    if company_id is None:
        raise NotFoundError(
            message="Приглашение не найдено", code="INVITATION_NOT_FOUND"
        )
    await lock_company(session, company_id)
    invitation = await get_invitation_by_token_hash_for_update(session, token_hash)
    if invitation is None:
        raise NotFoundError(
            message="Приглашение не найдено", code="INVITATION_NOT_FOUND"
        )
    if invitation.email.lower() != user.email.lower():
        raise ForbiddenError(
            message="Приглашение выдано на другой адрес электронной почты",
            code="EMAIL_MISMATCH",
        )
    require_pending_invitation(invitation)
    if invitation.expires_at <= datetime.now(UTC):
        raise UnprocessableError(
            message="Срок действия приглашения истек", code="INVITATION_EXPIRED"
        )
    return invitation


@router.get("", response_model=list[PersonalInvitationResponse])
async def personal_invitations(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    direction: Annotated[str, Query(pattern="^(received|sent)$")] = "received",
) -> list[PersonalInvitationResponse]:
    stmt = (
        select(Invitation, Company.name, User.full_name)
        .join(Company, Company.id == Invitation.company_id)
        .join(
            Membership,
            (Membership.company_id == Company.id) & (Membership.role == "owner"),
        )
        .join(User, User.id == Membership.user_id)
        .order_by(Invitation.id.desc())
    )
    stmt = (
        stmt.where(Invitation.email == current_user.email)
        if direction == "received"
        else stmt.where(Membership.user_id == current_user.id)
    )
    member_ids = set(
        (
            await session.scalars(
                select(Membership.company_id).where(
                    Membership.user_id == current_user.id
                )
            )
        ).all()
    )
    rows = (await session.execute(stmt)).all()
    return [
        PersonalInvitationResponse(
            **invitation_response(inv).model_dump(),
            company_name=name,
            owner_name=owner,
            is_member=inv.company_id in member_ids,
        )
        for inv, name, owner in rows
    ]


async def received_invitation(
    session: AsyncSession, invitation_id: int, user: User
) -> Invitation:
    company_id = await session.scalar(
        select(Invitation.company_id).where(
            Invitation.id == invitation_id, Invitation.email == user.email
        )
    )
    if company_id is None:
        raise NotFoundError(
            message="Приглашение не найдено", code="INVITATION_NOT_FOUND"
        )
    await lock_company(session, company_id)
    invitation = await session.scalar(
        select(Invitation)
        .where(
            Invitation.id == invitation_id,
            Invitation.email == user.email,
        )
        .with_for_update()
    )
    if invitation is None:
        raise NotFoundError(
            message="Приглашение не найдено", code="INVITATION_NOT_FOUND"
        )
    require_pending_invitation(invitation)
    if invitation.expires_at <= datetime.now(UTC):
        raise UnprocessableError(
            message="Срок действия приглашения истек", code="INVITATION_EXPIRED"
        )
    return invitation


async def accept_for_user(
    session: AsyncSession, invitation: Invitation, user: User
) -> dict[str, str | int]:
    if await get_membership(session, invitation.company_id, user.id) is not None:
        raise ConflictError(
            message="Вы уже являетесь участником этой компании", code="ALREADY_MEMBER"
        )
    try:
        membership = await accept_invitation(session, invitation, user.id)
        await revoke_pending_invitations(session, invitation.company_id, user.email)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ConflictError(
            message="Вы уже являетесь участником этой компании", code="ALREADY_MEMBER"
        ) from None
    return {
        "status": "ok",
        "company_id": membership.company_id,
        "role": membership.role,
    }


@router.post("/{invitation_id}/accept")
async def accept_received(
    invitation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str | int]:
    invitation = await received_invitation(session, invitation_id, current_user)
    return await accept_for_user(session, invitation, current_user)


@router.post("/{invitation_id}/decline")
async def decline_received(
    invitation_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    invitation = await received_invitation(session, invitation_id, current_user)
    invitation.status = "declined"
    invitation.responded_at = datetime.now(UTC)
    await session.commit()
    return {"status": "declined"}


@router.post("/accept")
async def accept_company_invitation(
    payload: AcceptInvitationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str | int]:
    invitation = await get_pending_invitation(session, payload.token, current_user)

    return await accept_for_user(session, invitation, current_user)


@router.post("/decline")
async def decline_company_invitation(
    payload: AcceptInvitationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    invitation = await get_pending_invitation(session, payload.token, current_user)
    invitation.status = "declined"
    invitation.responded_at = datetime.now(UTC)
    await session.commit()
    return {"status": "declined"}
