"""sessões regulares a partir da disponibilidade ofertada."""

from alembic import op
import sqlalchemy as sa

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reiki_sessions",
        sa.Column("availability_entry_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_reiki_sessions_availability_entry_id",
        "reiki_sessions",
        "availability_entries",
        ["availability_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_reiki_sessions_availability_entry",
        "reiki_sessions",
        ["availability_entry_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_reiki_sessions_availability_entry",
        "reiki_sessions",
        type_="unique",
    )
    op.drop_constraint(
        "fk_reiki_sessions_availability_entry_id",
        "reiki_sessions",
        type_="foreignkey",
    )
    op.drop_column("reiki_sessions", "availability_entry_id")
