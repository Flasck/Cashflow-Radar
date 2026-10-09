from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Enum, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base

if TYPE_CHECKING:
    from app.models.split import TransactionSplit


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    operation_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    direction: Mapped[str] = mapped_column(
        Enum("inflow", "outflow", name="transaction_direction")
    )
    purpose: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (CheckConstraint("amount > 0", name="check_positive_amount"),)

    splits: Mapped[list["TransactionSplit"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, date={self.operation_date}, "
            f"amount={self.amount}, direction={self.direction})>"
        )
