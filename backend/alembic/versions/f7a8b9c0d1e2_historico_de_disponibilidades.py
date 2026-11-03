"""histórico de disponibilidades com indicador de vigência."""

from alembic import op
import sqlalchemy as sa

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Registros existentes passam a ser vigentes; reenvios futuros marcam as
    # entradas antigas como históricas sem removê-las.
    op.add_column(
        "availability_entries",
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("availability_entries", "is_current")
