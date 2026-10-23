from datetime import date
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class ForecastRequest(BaseModel):
    date: date
    meal: str = Field(min_length=1, max_length=32)
    dish: str = Field(min_length=1, max_length=120)
    attendance: int = Field(ge=0)
    event_factor: float = Field(default=1.0, gt=0)
    extra_context: list[str] = Field(default_factory=list)
    synthetic_liking_score: float | None = Field(default=None, ge=0, le=1)
    exam_intensity: float | None = Field(default=None, ge=0, le=1)
    temperature_c: float | None = Field(default=None, ge=-10, le=60)
    rainfall_mm: float | None = Field(default=None, ge=0, le=1000)
    historical_demand_rate: float | None = Field(default=None, ge=0, le=1)


class ForecastResponse(BaseModel):
    date: date
    meal: str
    dish: str
    predicted_portions: int = Field(ge=0)
    method: str
    confidence: str
    explanation: list[str]


class PlanRequest(ForecastRequest):
    batch_size: int = Field(default=25, gt=0)
    minimum_buffer_pct: float = Field(default=0.05, ge=0, le=0.5)


class PlanResponse(BaseModel):
    id: int | None = None
    date: date
    meal: str
    dish: str
    forecast_portions: int
    recommended_portions: int
    batches: int
    batch_size: int
    expected_buffer_portions: int
    approval_required: bool = True
    status: str = "pending_review"
    explanation: list[str]


class DecisionFeedback(BaseModel):
    approved: bool
    reviewer: str = Field(default="kitchen_operator", min_length=1, max_length=80)
    note: str = Field(default="", max_length=500)
