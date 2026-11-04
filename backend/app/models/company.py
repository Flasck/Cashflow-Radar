from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.invitation import Invitation
    from app.models.membership import Membership
    from app.models.transaction import Transaction


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    industry_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    categories: Mapped[list["Category"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        overlaps="transactions",
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name={self.name})>"
