from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.connection import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    full_name: Mapped[str] = mapped_column(String(255))

    email: Mapped[str] = mapped_column(String(255), unique=True)

    role: Mapped[str] = mapped_column(Enum("treasurer", "cfo", name="user_role"))

    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, full_name={self.full_name}, email={self.email}, role={self.role})>"
