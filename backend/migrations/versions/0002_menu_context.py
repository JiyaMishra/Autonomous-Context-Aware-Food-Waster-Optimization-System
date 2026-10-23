"""Add context fields used by the August 2026 menu dataset."""
from alembic import op
import sqlalchemy as sa

revision = "0002_menu_context"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

COLUMNS = [
    sa.Column("day_of_week", sa.String(length=16), nullable=True),
    sa.Column("menu_version", sa.Integer(), nullable=True),
    sa.Column("synthetic_liking_score", sa.Float(), nullable=True),
    sa.Column("exam_intensity", sa.Float(), nullable=True),
    sa.Column("temperature_c", sa.Float(), nullable=True),
    sa.Column("rainfall_mm", sa.Float(), nullable=True),
    sa.Column("hostel_attendance_estimate", sa.Integer(), nullable=True),
    sa.Column("historical_demand_rate", sa.Float(), nullable=True),
    sa.Column("expected_consumers", sa.Integer(), nullable=True),
    sa.Column("recommended_preparation_portions", sa.Integer(), nullable=True),
    sa.Column("prepared_portions", sa.Integer(), nullable=True),
    sa.Column("waste_rate_pct", sa.Float(), nullable=True),
    sa.Column("quantity_unit_hint", sa.String(length=40), nullable=True),
]


def upgrade():
    # The application also has a guarded startup compatibility upgrade. Keep
    # this migration safe if startup already added one or more nullable fields.
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("meal_history")}
    for column in COLUMNS:
        if column.name not in existing:
            op.add_column("meal_history", column)


def downgrade():
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("meal_history")}
    for column in reversed(COLUMNS):
        if column.name in existing:
            op.drop_column("meal_history", column.name)
