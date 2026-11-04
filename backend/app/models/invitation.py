from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base

if TYPE_CHECKING:
    from app.models.company import Company


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("treasurer", "viewer", name="invitation_role"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(UTC),
    )
    status: Mapped[str] = mapped_column(
        Enum("pending", "accepted", "declined", "revoked", name="invitation_status"),
        nullable=False,
        default="pending",
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    company: Mapped["Company"] = relationship(back_populates="invitations")

    __table_args__ = (
        Index("ix_invitations_company_email", "company_id", "email"),
        CheckConstraint(
            "(status = 'pending' AND responded_at IS NULL) OR "
            "(status <> 'pending' AND responded_at IS NOT NULL)",
            name="check_invitation_response",
        ),
    )

    def __repr__(self) -> str:
        return f"<Invitation(id={self.id}, company_id={self.company_id}, email={self.email}, role={self.role})>"
