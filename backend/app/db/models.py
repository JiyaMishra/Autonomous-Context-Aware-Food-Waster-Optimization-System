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


class PlanAudit(Base):
    __tablename__ = "plan_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(32))
    dish: Mapped[str] = mapped_column(String(120))
    forecast_portions: Mapped[int] = mapped_column(Integer)
    recommended_portions: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="pending_review")
    reviewer: Mapped[str | None] = mapped_column(String(80), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
