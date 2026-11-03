"""fase 2: disponibilidade semanal e inscrições

Revision ID: a7c3d9e1f2b4
Revises: 3bbfdbd42a4c
Create Date: 2026-10-22

PENDENTE DE EXECUÇÃO REAL no PostgreSQL. O SQL offline
(`alembic upgrade a7c3d9e1f2b4 --sql`) está em
`migrations_offline_postgresql_phase2.sql` para inspeção — isso NÃO
substitui `alembic upgrade head` contra o banco.

O índice único de inscrições é PARCIAL (apenas inscrições ativas), recurso
específico do PostgreSQL — não reproduzível como constraint em SQLite.
"""

from alembic import op
import sqlalchemy as sa

revision = "a7c3d9e1f2b4"
down_revision = "3bbfdbd42a4c"
branch_labels = None
depends_on = None

AVAIL_STATUS_VALUES = ("pending", "submitted", "unavailable")
ENTRY_KIND_VALUES = ("available", "unavailable")
ENROLL_STATUS_VALUES = ("confirmed", "waitlisted", "attended", "cancelled")


def upgrade() -> None:
    op.create_table(
        "weekly_availabilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("instructor_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
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
            ["cycle_id"],
            ["weekly_cycles.id"],
            name="fk_weekly_availabilities_cycle_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["instructor_id"],
            ["users.id"],
            name="fk_weekly_availabilities_instructor_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", "instructor_id", name="uq_avail_cycle_instructor"),
        sa.CheckConstraint(
            "status IN ('pending', 'submitted', 'unavailable')",
            name="ck_weekly_availabilities_status",
        ),
    )
    op.create_index(
        op.f("ix_weekly_availabilities_cycle_id"),
        "weekly_availabilities",
        ["cycle_id"],
    )
    op.create_index(
        op.f("ix_weekly_availabilities_instructor_id"),
        "weekly_availabilities",
        ["instructor_id"],
    )

    op.create_table(
        "availability_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("availability_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(
            ["availability_id"],
            ["weekly_availabilities.id"],
            name="fk_availability_entries_availability_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_availability_entries_location_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_avail_entry_period"),
        sa.CheckConstraint(
            "kind IN ('available', 'unavailable')",
            name="ck_availability_entries_kind",
        ),
    )
    op.create_index(
        op.f("ix_availability_entries_availability_id"),
        "availability_entries",
        ["availability_id"],
    )
    op.create_index(
        op.f("ix_availability_entries_location_id"),
        "availability_entries",
        ["location_id"],
    )

    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("participant_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("waitlist_position", sa.Integer(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=500), nullable=True),
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
            name="fk_enrollments_session_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["participant_id"],
            ["users.id"],
            name="fk_enrollments_participant_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('confirmed', 'waitlisted', 'attended', 'cancelled')",
            name="ck_enrollments_status",
        ),
        sa.CheckConstraint(
            "status != 'waitlisted' OR waitlist_position IS NOT NULL",
            name="ck_enrollments_waitlist_position",
        ),
    )
    # Índice PARCIAL: unicidade só entre inscrições ativas (PostgreSQL).
    op.create_index(
        "uq_enrollments_session_participant_active",
        "enrollments",
        ["session_id", "participant_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('confirmed', 'waitlisted', 'attended')"
        ),
    )
    op.create_index(op.f("ix_enrollments_session_id"), "enrollments", ["session_id"])
    op.create_index(
        op.f("ix_enrollments_participant_id"), "enrollments", ["participant_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_enrollments_participant_id"), table_name="enrollments")
    op.drop_index(op.f("ix_enrollments_session_id"), table_name="enrollments")
    op.drop_index(
        "uq_enrollments_session_participant_active", table_name="enrollments"
    )
    op.drop_table("enrollments")
    op.drop_index(
        op.f("ix_availability_entries_location_id"), table_name="availability_entries"
    )
    op.drop_index(
        op.f("ix_availability_entries_availability_id"),
        table_name="availability_entries",
    )
    op.drop_table("availability_entries")
    op.drop_index(
        op.f("ix_weekly_availabilities_instructor_id"),
        table_name="weekly_availabilities",
    )
    op.drop_index(
        op.f("ix_weekly_availabilities_cycle_id"), table_name="weekly_availabilities"
    )
    op.drop_table("weekly_availabilities")
