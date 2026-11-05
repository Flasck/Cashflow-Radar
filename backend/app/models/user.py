from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base

if TYPE_CHECKING:
    from app.models.membership import Membership


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_email", "email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    verification_code_hash: Mapped[str | None] = mapped_column(String(64))
    verification_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    verification_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    verification_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    session_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    password_change_hash: Mapped[str | None] = mapped_column(String(255))
    password_code_hash: Mapped[str | None] = mapped_column(String(64))
    password_code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    password_code_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    password_code_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"
