from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.transaction import Transaction


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    company: Mapped["Company"] = relationship(back_populates="categories")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="category",
        passive_deletes=True,
        overlaps="company,transactions",
    )

    __table_args__ = (
        UniqueConstraint("company_id", "id", name="uq_categories_company_id"),
        Index(
            "uq_categories_company_lower_name",
            "company_id",
            text("lower(name)"),
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Category(id={self.id}, company_id={self.company_id}, name={self.name})>"
        )
