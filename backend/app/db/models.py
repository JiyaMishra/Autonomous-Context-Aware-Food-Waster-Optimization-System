from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.db.session import Base


class MealHistory(Base):
    __tablename__ = "meal_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(32), index=True)
    dish: Mapped[str] = mapped_column(String(120), index=True)
    planned_portions: Mapped[int] = mapped_column(Integer)
    served_portions: Mapped[int] = mapped_column(Integer)
    waste_portions: Mapped[int] = mapped_column(Integer)
    attendance: Mapped[int] = mapped_column(Integer)
    is_weekend: Mapped[bool] = mapped_column(Boolean, default=False)
    event_factor: Mapped[float] = mapped_column(Float, default=1.0)
    weather: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Source-dataset fields. Nullable so the generic CSV contract still works.
    day_of_week: Mapped[str | None] = mapped_column(String(16), nullable=True)
    menu_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    synthetic_liking_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    exam_intensity: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    hostel_attendance_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    historical_demand_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_consumers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommended_preparation_portions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prepared_portions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    waste_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity_unit_hint: Mapped[str | None] = mapped_column(String(40), nullable=True)


class PlanAudit(Base):
    __tablename__ = "plan_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(32))
    dish: Mapped[str] = mapped_column(String(120))
    forecast_portions: Mapped[int] = mapped_column(Integer)
    recommended_portions: Mapped[int] = mapped_column(Integer)
    batches: Mapped[int] = mapped_column(Integer, default=0)
    batch_size: Mapped[int] = mapped_column(Integer, default=25)
    expected_buffer_portions: Mapped[int] = mapped_column(Integer, default=0)
    explanation: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="pending_review")
    reviewer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
