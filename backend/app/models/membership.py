from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class Membership(Base):
    __tablename__ = "memberships"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(
        Enum("owner", "treasurer", "viewer", name="membership_role"),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="memberships")
    company: Mapped["Company"] = relationship(back_populates="memberships")

    __table_args__ = (
        Index("ix_memberships_company_id", "company_id"),
        Index(
            "uq_company_owner",
            "company_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Membership(user_id={self.user_id}, company_id={self.company_id}, role={self.role})>"
