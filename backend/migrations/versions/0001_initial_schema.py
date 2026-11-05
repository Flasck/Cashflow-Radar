from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("verification_code_hash", sa.String(length=64), nullable=True),
        sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "verification_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.Column(
            "session_version", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("password_change_hash", sa.String(255), nullable=True),
        sa.Column("password_code_hash", sa.String(64), nullable=True),
        sa.Column(
            "password_code_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("password_code_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "password_code_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("industry_code", sa.String(length=50), nullable=True),
    )

    membership_role = sa.Enum("owner", "treasurer", "viewer", name="membership_role")
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("role", membership_role, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_memberships_user"
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_memberships_company",
        ),
        sa.PrimaryKeyConstraint("user_id", "company_id", name="pk_memberships"),
    )
    op.create_index("ix_memberships_company_id", "memberships", ["company_id"])
    op.create_index(
        "uq_company_owner",
        "memberships",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner'"),
    )

    invitation_role = sa.Enum("treasurer", "viewer", name="invitation_role")
    invitation_status = sa.Enum(
        "pending", "accepted", "declined", "revoked", name="invitation_status"
    )
    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("role", invitation_role, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", invitation_status, nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'pending' AND responded_at IS NULL) OR "
            "(status <> 'pending' AND responded_at IS NOT NULL)",
            name="check_invitation_response",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_invitations_company",
        ),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
    )
    op.create_index(
        "ix_invitations_company_email", "invitations", ["company_id", "email"]
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_categories_company",
        ),
        sa.UniqueConstraint("company_id", "id", name="uq_categories_company_id"),
    )
    op.create_index(
        "uq_categories_company_lower_name",
        "categories",
        ["company_id", sa.text("lower(name)")],
        unique=True,
    )

    direction_enum = sa.Enum("inflow", "outflow", name="transaction_direction")
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("direction", direction_enum, nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.CheckConstraint("amount > 0", name="check_positive_amount"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            ondelete="CASCADE",
            name="fk_transactions_company",
        ),
        sa.ForeignKeyConstraint(
            ["company_id", "category_id"],
            ["categories.company_id", "categories.id"],
            ondelete="RESTRICT",
            name="fk_transactions_category_company",
        ),
    )
    op.create_index(
        "ix_transactions_company_date_id",
        "transactions",
        ["company_id", "operation_date", "id"],
    )
    op.create_index(
        "ix_transactions_company_category",
        "transactions",
        ["company_id", "category_id"],
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("categories")
    op.drop_table("invitations")
    op.drop_table("memberships")
    op.drop_table("companies")
    op.drop_table("users")

    sa.Enum("inflow", "outflow", name="transaction_direction").drop(
        op.get_bind(), checkfirst=True
    )
    sa.Enum("treasurer", "viewer", name="invitation_role").drop(
        op.get_bind(), checkfirst=True
    )
    sa.Enum(
        "pending", "accepted", "declined", "revoked", name="invitation_status"
    ).drop(op.get_bind(), checkfirst=True)
    sa.Enum("owner", "treasurer", "viewer", name="membership_role").drop(
        op.get_bind(), checkfirst=True
    )
