import sqlalchemy as sa
from alembic import op

revision = "0003_unique_pending_invitations"
down_revision = "0002_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE invitations
        SET status = 'revoked', responded_at = CURRENT_TIMESTAMP
        WHERE status = 'pending' AND (
            expires_at <= CURRENT_TIMESTAMP
            OR EXISTS (
                SELECT 1 FROM memberships JOIN users ON users.id = memberships.user_id
                WHERE memberships.company_id = invitations.company_id
                AND lower(users.email) = lower(invitations.email)
            )
            OR id IN (
                SELECT id FROM (
                    SELECT id, row_number() OVER (
                        PARTITION BY company_id, lower(email) ORDER BY id DESC
                    ) AS position
                    FROM invitations
                    WHERE status = 'pending' AND expires_at > CURRENT_TIMESTAMP
                ) AS duplicates WHERE position > 1
            )
        )
        """
    )
    op.create_index(
        "uq_invitations_pending_company_email",
        "invitations",
        ["company_id", sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_invitations_pending_company_email", table_name="invitations")
