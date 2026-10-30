"""fase 3: cancelamentos, solicitação de cobertura e convites

Revision ID: b8d4e2f6a9c1
Revises: a7c3d9e1f2b4
Create Date: 2026-10-22

PENDENTE DE EXECUÇÃO REAL no PostgreSQL. SQL offline em
`migrations_offline_postgresql_phase3.sql` — inspeção apenas, não substitui
`alembic upgrade head`.
"""

from alembic import op
import sqlalchemy as sa

revision = "b8d4e2f6a9c1"
down_revision = "a7c3d9e1f2b4"
branch_labels = None
depends_on = None

REQUEST_STATUS_VALUES = ("open", "covered", "uncovered")
INVITE_STATUS_VALUES = (
    "pending",
    "accepted",
    "taken",
    "declined",
    "expired",
    "withdrawn",
)


def upgrade() -> None:
    op.create_table(
        "cover_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("original_instructor_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("previous_session_status", sa.String(length=20), nullable=False),
        sa.Column("covered_by", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["reiki_sessions.id"],
            name="fk_cover_requests_session_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["covered_by"],
            ["users.id"],
            name="fk_cover_requests_covered_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('open', 'covered', 'uncovered')",
            name="ck_cover_requests_status",
        ),
        # Uma única solicitação por sessão (idempotência do cancelamento).
        sa.UniqueConstraint("session_id", name="uq_cover_requests_session"),
    )
    op.create_index(op.f("ix_cover_requests_session_id"), "cover_requests", ["session_id"])

    op.create_table(
        "cover_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("invited_instructor_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["cover_requests.id"],
            name="fk_cover_invites_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_instructor_id"],
            ["users.id"],
            name="fk_cover_invites_invited_instructor_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'taken', 'declined', "
            "'expired', 'withdrawn')",
            name="ck_cover_invites_status",
        ),
        # Sem convites duplicados (solicitação, ministrante).
        sa.UniqueConstraint(
            "request_id", "invited_instructor_id", name="uq_cover_invite_req_instructor"
        ),
    )
    op.create_index(op.f("ix_cover_invites_request_id"), "cover_invites", ["request_id"])
    op.create_index(
        op.f("ix_cover_invites_invited_instructor_id"),
        "cover_invites",
        ["invited_instructor_id"],
    )
    op.create_index(
        "ix_cover_invites_instructor_status",
        "cover_invites",
        ["invited_instructor_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cover_invites_instructor_status", table_name="cover_invites"
    )
    op.drop_index(
        op.f("ix_cover_invites_invited_instructor_id"), table_name="cover_invites"
    )
    op.drop_index(op.f("ix_cover_invites_request_id"), table_name="cover_invites")
    op.drop_table("cover_invites")
    op.drop_index(op.f("ix_cover_requests_session_id"), table_name="cover_requests")
    op.drop_table("cover_requests")
