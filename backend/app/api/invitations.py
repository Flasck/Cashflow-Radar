import hashlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, require_csrf
from app.crud.invitations import (
    accept_invitation,
    get_invitation_by_token_hash_for_update,
    require_pending_invitation,
)
from app.crud.members import get_membership
from app.db.connection import get_db
from app.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.invitation import Invitation
from app.models.user import User
from app.schemas.companies import AcceptInvitationRequest, InvitationResponse

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


@router.post("/accept")
async def accept_company_invitation(
    payload: AcceptInvitationRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str | int]:
    invitation = await get_pending_invitation(session, payload.token, current_user)

    existing_membership = await get_membership(
        session, invitation.company_id, current_user.id
    )
    if existing_membership is not None:
        raise ConflictError(
            message="Вы уже являетесь участником этой компании", code="ALREADY_MEMBER"
        )

    try:
        membership = await accept_invitation(session, invitation, current_user.id)
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
