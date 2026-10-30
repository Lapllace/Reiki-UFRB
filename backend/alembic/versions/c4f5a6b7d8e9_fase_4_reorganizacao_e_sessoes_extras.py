"""fase 4: reorganização de participantes e sessões extras

PENDENTE DE EXECUÇÃO REAL no PostgreSQL. Gere o SQL com:
`alembic upgrade c4f5a6b7d8e9 --sql`.
"""

from alembic import op
import sqlalchemy as sa

revision = "c4f5a6b7d8e9"
down_revision = "b8d4e2f6a9c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "enrollments",
        sa.Column("reallocation_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_enrollments_reallocation_id", "enrollments", ["reallocation_id"]
    )
    op.create_table(
        "reallocation_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("origin_session_id", sa.Uuid(), nullable=False),
        sa.Column("origin_enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("alternative", sa.String(length=30), nullable=True),
        sa.Column("target_session_id", sa.Uuid(), nullable=True),
        sa.Column("priority_granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("dismissal_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["origin_session_id"], ["reiki_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["origin_enrollment_id"], ["enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["participant_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_session_id"], ["reiki_sessions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("origin_enrollment_id", name="uq_reallocation_origin_enrollment"),
        sa.CheckConstraint("status IN ('pending', 'applied', 'dismissed')", name="ck_reallocation_status"),
        sa.CheckConstraint(
            "alternative IS NULL OR alternative IN ('extra_session', 'future_priority')",
            name="ck_reallocation_alternative",
        ),
    )
    for column in ("origin_session_id", "origin_enrollment_id", "participant_id", "target_session_id"):
        op.create_index(f"ix_reallocation_cases_{column}", "reallocation_cases", [column])
    op.create_table(
        "reallocation_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["reallocation_cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reallocation_history_case_id", "reallocation_history", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_reallocation_history_case_id", table_name="reallocation_history")
    op.drop_table("reallocation_history")
    for column in ("target_session_id", "participant_id", "origin_enrollment_id", "origin_session_id"):
        op.drop_index(f"ix_reallocation_cases_{column}", table_name="reallocation_cases")
    op.drop_table("reallocation_cases")
    op.drop_index("ix_enrollments_reallocation_id", table_name="enrollments")
    op.drop_column("enrollments", "reallocation_id")
