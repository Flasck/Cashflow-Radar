from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.company import Company


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    direction: Mapped[str] = mapped_column(
        Enum("inflow", "outflow", name="transaction_direction"),
        nullable=False,
    )
    category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped["Company"] = relationship(
        back_populates="transactions", overlaps="transactions"
    )
    category: Mapped["Category | None"] = relationship(
        back_populates="transactions", overlaps="company,transactions"
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="check_positive_amount"),
        ForeignKeyConstraint(
            ["company_id", "category_id"],
            ["categories.company_id", "categories.id"],
            ondelete="RESTRICT",
            name="fk_transactions_category_company",
        ),
        Index("ix_transactions_company_date_id", "company_id", "operation_date", "id"),
        Index("ix_transactions_company_category", "company_id", "category_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, company_id={self.company_id}, "
            f"date={self.operation_date}, amount={self.amount}, direction={self.direction})>"
        )
