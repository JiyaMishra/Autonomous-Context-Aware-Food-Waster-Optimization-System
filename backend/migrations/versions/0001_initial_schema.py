"""Initial MessWise database schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "meal_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("meal", sa.String(length=32), nullable=False),
        sa.Column("dish", sa.String(length=120), nullable=False),
        sa.Column("planned_portions", sa.Integer(), nullable=False),
        sa.Column("served_portions", sa.Integer(), nullable=False),
        sa.Column("waste_portions", sa.Integer(), nullable=False),
        sa.Column("attendance", sa.Integer(), nullable=False),
        sa.Column("is_weekend", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("event_factor", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("weather", sa.String(length=80), nullable=True),
    )
    op.create_index("ix_meal_history_date", "meal_history", ["date"])
    op.create_index("ix_meal_history_meal", "meal_history", ["meal"])
    op.create_index("ix_meal_history_dish", "meal_history", ["dish"])
    op.create_table(
        "plan_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("meal", sa.String(length=32), nullable=False),
        sa.Column("dish", sa.String(length=120), nullable=False),
        sa.Column("forecast_portions", sa.Integer(), nullable=False),
        sa.Column("recommended_portions", sa.Integer(), nullable=False),
        sa.Column("batches", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batch_size", sa.Integer(), nullable=False, server_default="25"),
        sa.Column("expected_buffer_portions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("explanation", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("reviewer", sa.String(length=80), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_plan_audits_date", "plan_audits", ["date"])


def downgrade():
    op.drop_index("ix_plan_audits_date", table_name="plan_audits")
    op.drop_table("plan_audits")
    op.drop_index("ix_meal_history_dish", table_name="meal_history")
    op.drop_index("ix_meal_history_meal", table_name="meal_history")
    op.drop_index("ix_meal_history_date", table_name="meal_history")
    op.drop_table("meal_history")
