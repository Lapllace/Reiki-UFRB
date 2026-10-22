"""fase 1: usuarios, sessoes de autenticacao, locais, ciclos e sessoes

Migração inicial revisada manualmente (a anterior foi gerada por autogenerate
contra SQLite e omitia os timestamps e os valores dos enums).

Revision ID: 3bbfdbd42a4c
Revises:
Create Date: 2026-10-22

PENDENTE DE EXECUÇÃO REAL: esta migração ainda NÃO foi executada contra o
PostgreSQL local (acesso ao banco indisponível nesta sessão). Quando o acesso
for configurado, rodar `alembic upgrade head` e validar com `alembic check`
ou inspeção real do esquema.
"""

import sqlalchemy as sa
from alembic import op

revision = "3bbfdbd42a4c"
down_revision = None
branch_labels = None
depends_on = None

# Enums persistidos pelos VALORES (minúsculas), coerentes com o frontend.
USER_ROLE_VALUES = ("participant", "instructor", "coordinator")
CYCLE_PHASE_VALUES = (
    "collecting_availability",
    "enrollment_pending",
    "enrollment_open",
    "in_progress",
    "closed",
)
SESSION_STATUS_VALUES = (
    "scheduled",
    "open",
    "full",
    "cancelled",
    "needs_cover",
    "uncovered",
    "completed",
)


def _varchar_enum(values: tuple[str, ...], name: str, length: int) -> sa.Enum:
    # native_enum=False: VARCHAR + CHECK (futuro ALTER de valores é simples
    # no PostgreSQL, sem depender de CREATE TYPE).
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        length=length,
        validate_strings=True,
    )


def upgrade() -> None:
    user_role = _varchar_enum(USER_ROLE_VALUES, "user_role", 20)
    cycle_phase = _varchar_enum(CYCLE_PHASE_VALUES, "cycle_phase", 40)
    session_status = _varchar_enum(SESSION_STATUS_VALUES, "session_status", 20)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "role IN ('participant', 'instructor', 'coordinator')", name="ck_users_role"
        ),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=True),
        sa.Column("reference", sa.String(length=300), nullable=True),
        sa.Column("map_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "weekly_cycles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("phase", cycle_phase, nullable=False),
        sa.Column("availability_deadline_note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("week_start"),
        sa.CheckConstraint(
            "phase IN ("
            "'collecting_availability', 'enrollment_pending', 'enrollment_open', "
            "'in_progress', 'closed')",
            name="ck_weekly_cycles_phase",
        ),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_sessions_expiry"),
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_auth_sessions_token_hash", "auth_sessions", ["token_hash"], unique=True
    )

    op.create_table(
        "reiki_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=True),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("instructor_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("status", session_status, nullable=False),
        sa.Column("is_extra", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["weekly_cycles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_reiki_sessions_period"),
        sa.CheckConstraint(
            "status IN ("
            "'scheduled', 'open', 'full', 'cancelled', 'needs_cover', "
            "'uncovered', 'completed')",
            name="ck_reiki_sessions_status",
        ),
    )
    op.create_index(op.f("ix_reiki_sessions_cycle_id"), "reiki_sessions", ["cycle_id"], unique=False)
    op.create_index(op.f("ix_reiki_sessions_instructor_id"), "reiki_sessions", ["instructor_id"], unique=False)
    op.create_index(op.f("ix_reiki_sessions_location_id"), "reiki_sessions", ["location_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reiki_sessions_location_id"), table_name="reiki_sessions")
    op.drop_index(op.f("ix_reiki_sessions_instructor_id"), table_name="reiki_sessions")
    op.drop_index(op.f("ix_reiki_sessions_cycle_id"), table_name="reiki_sessions")
    op.drop_table("reiki_sessions")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_token_hash", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("weekly_cycles")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_table("locations")
