from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.transaction import Transaction


class TransactionSplit(Base):
    __tablename__ = "transaction_splits"

    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))

    __table_args__ = (
        CheckConstraint("allocated_amount > 0", name="check_positive_split_amount"),
    )

    transaction: Mapped["Transaction"] = relationship(back_populates="splits")
    category: Mapped["Category"] = relationship(back_populates="splits")

    def __repr__(self) -> str:
        return (
            f"<TransactionSplit(tx={self.transaction_id}, "
            f"cat={self.category_id}, amount={self.allocated_amount})>"
        )
