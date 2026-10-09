from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.connection import Base

if TYPE_CHECKING:
    from app.models.split import TransactionSplit


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(128), unique=True)

    splits: Mapped[list["TransactionSplit"]] = relationship(
        back_populates="category",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name})>"
