import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_user,
    require_csrf,
    require_role,
)
from app.api.invitations import invitation_response
from app.crud.companies import (
    UNSET,
    create_company_with_owner,
    get_company,
    get_company_last_operation_date,
    list_user_companies,
    update_company,
)
from app.crud.invitations import (
    create_invitation,
    get_invitation,
    list_invitations,
    require_pending_invitation,
    revoke_invitation,
)
from app.crud.members import (
    delete_membership,
    get_membership,
    list_members,
    update_member_role,
)
from app.crud.users import get_user
from app.db.connection import get_db
from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.membership import Membership
from app.models.user import User
from app.schemas.companies import (
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    InvitationCreate,
    InvitationResponse,
    MemberResponse,
    UpdateMemberRoleRequest,
)

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CompanyResponse]:
    rows = await list_user_companies(session, current_user.id)
    result: list[CompanyResponse] = []
    for company, role in rows:
        last_op = await get_company_last_operation_date(session, company.id)
        result.append(
            CompanyResponse(
                id=company.id,
                name=company.name,
                industry_code=company.industry_code,
                role=role,
                last_operation_date=last_op.isoformat() if last_op else None,
            )
        )
    return result


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> CompanyResponse:
    company, membership = await create_company_with_owner(
        session=session,
        name=payload.name,
        industry_code=payload.industry_code,
        owner_user_id=current_user.id,
    )
    await session.commit()

    return CompanyResponse(
        id=company.id,
        name=company.name,
        industry_code=company.industry_code,
        role=membership.role,
        last_operation_date=None,
    )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company_details(
    company_id: int,
    membership: Annotated[
        Membership, Depends(require_role("owner", "treasurer", "viewer"))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CompanyResponse:
    company = await get_company(session, company_id)
    if company is None:
        raise NotFoundError(message="Компания не найдена", code="COMPANY_NOT_FOUND")

    last_op = await get_company_last_operation_date(session, company.id)
    return CompanyResponse(
        id=company.id,
        name=company.name,
        industry_code=company.industry_code,
        role=membership.role,
        last_operation_date=last_op.isoformat() if last_op else None,
    )


@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company_details(
    company_id: int,
    payload: CompanyUpdate,
    membership: Annotated[Membership, Depends(require_role("owner"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> CompanyResponse:
    fields_set = payload.model_fields_set
    name = payload.name if "name" in fields_set else UNSET
    industry = payload.industry_code if "industry_code" in fields_set else UNSET

    company = await update_company(
        session=session,
        company_id=company_id,
        name=name,
        industry_code=industry,
    )
    if company is None:
        raise NotFoundError(message="Компания не найдена", code="COMPANY_NOT_FOUND")

    await session.commit()
    last_op = await get_company_last_operation_date(session, company.id)
    return CompanyResponse(
        id=company.id,
        name=company.name,
        industry_code=company.industry_code,
        role=membership.role,
        last_operation_date=last_op.isoformat() if last_op else None,
    )


# --- Members ---


@router.get("/{company_id}/members", response_model=list[MemberResponse])
async def get_company_members(
    company_id: int,
    _membership: Annotated[
        Membership, Depends(require_role("owner", "treasurer", "viewer"))
    ],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[MemberResponse]:
    rows = await list_members(session, company_id)
    return [
        MemberResponse(
            user_id=user.id,
            company_id=company_id,
            full_name=user.full_name,
            email=user.email,
            role=mem.role,
        )
        for mem, user in rows
    ]


@router.patch("/{company_id}/members/{user_id}", response_model=MemberResponse)
async def update_member(
    company_id: int,
    user_id: int,
    payload: UpdateMemberRoleRequest,
    _membership: Annotated[Membership, Depends(require_role("owner"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> MemberResponse:
    target_mem = await get_membership(session, company_id, user_id)
    if target_mem is None:
        raise NotFoundError(message="Участник не найден", code="MEMBER_NOT_FOUND")

    if target_mem.role == "owner":
        raise ForbiddenError(
            message="Нельзя изменять роль владельца компании",
            code="CANNOT_MODIFY_OWNER",
        )

    updated = await update_member_role(session, company_id, user_id, payload.role)
    assert updated is not None
    user = await get_user(session, user_id)
    assert user is not None

    await session.commit()
    return MemberResponse(
        user_id=user.id,
        company_id=company_id,
        full_name=user.full_name,
        email=user.email,
        role=updated.role,
    )


@router.delete("/{company_id}/members/{user_id}")
async def remove_member(
    company_id: int,
    user_id: int,
    _membership: Annotated[Membership, Depends(require_role("owner"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    target_mem = await get_membership(session, company_id, user_id)
    if target_mem is None:
        raise NotFoundError(message="Участник не найден", code="MEMBER_NOT_FOUND")

    if target_mem.role == "owner":
        raise ForbiddenError(
            message="Нельзя удалить владельца компании", code="CANNOT_REMOVE_OWNER"
        )

    deleted = await delete_membership(session, company_id, user_id)
    if not deleted:
        raise NotFoundError(message="Участник не найден", code="MEMBER_NOT_FOUND")

    await session.commit()
    return {"status": "ok"}


# --- Invitations ---


@router.get("/{company_id}/invitations", response_model=list[InvitationResponse])
async def get_company_invitations(
    company_id: int,
    _membership: Annotated[Membership, Depends(require_role("owner"))],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[InvitationResponse]:
    invites = await list_invitations(session, company_id)
    return [invitation_response(inv) for inv in invites]


@router.post(
    "/{company_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_invitation(
    company_id: int,
    payload: InvitationCreate,
    _membership: Annotated[Membership, Depends(require_role("owner"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> InvitationResponse:
    all_members = await list_members(session, company_id)
    for _, u in all_members:
        if u.email.lower() == payload.email.lower():
            raise ConflictError(
                message="Пользователь уже является участником этой компании",
                code="ALREADY_MEMBER",
            )

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(hours=48)

    inv = await create_invitation(
        session=session,
        company_id=company_id,
        email=payload.email,
        token_hash=token_hash,
        role=payload.role,
        expires_at=expires_at,
    )
    await session.commit()

    return invitation_response(inv, raw_token)


@router.post(
    "/{company_id}/invitations/{invitation_id}/renew",
    response_model=InvitationResponse,
    status_code=201,
)
async def renew_company_invitation(
    company_id: int,
    invitation_id: int,
    _membership: Annotated[Membership, Depends(require_role("owner"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> InvitationResponse:
    previous = await get_invitation(session, company_id, invitation_id)
    if previous is None:
        raise NotFoundError(
            message="Приглашение не найдено", code="INVITATION_NOT_FOUND"
        )
    require_pending_invitation(previous)
    for _, user in await list_members(session, company_id):
        if user.email.lower() == previous.email.lower():
            raise ConflictError(
                message="Пользователь уже является участником компании",
                code="ALREADY_MEMBER",
            )
    await revoke_invitation(session, company_id, invitation_id)
    token = secrets.token_urlsafe(32)
    invitation = await create_invitation(
        session,
        company_id,
        previous.email,
        hashlib.sha256(token.encode("utf-8")).hexdigest(),
        previous.role,
        datetime.now(UTC) + timedelta(hours=48),
    )
    await session.commit()
    return invitation_response(invitation, token)


@router.delete("/{company_id}/invitations/{invitation_id}")
async def revoke_company_invitation(
    company_id: int,
    invitation_id: int,
    _membership: Annotated[Membership, Depends(require_role("owner"))],
    session: Annotated[AsyncSession, Depends(get_db)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, str]:
    deleted = await revoke_invitation(session, company_id, invitation_id)
    if not deleted:
        raise NotFoundError(
            message="Приглашение не найдено", code="INVITATION_NOT_FOUND"
        )

    await session.commit()
    return {"status": "ok"}
