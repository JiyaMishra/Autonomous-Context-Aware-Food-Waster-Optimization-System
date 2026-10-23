from datetime import date
from pydantic import BaseModel, Field, ConfigDict


class HealthResponse(BaseModel):
    status: str
    service: str


class MealRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    date: date
    meal: str = Field(min_length=1, max_length=32)
    dish: str = Field(min_length=1, max_length=120)
    planned_portions: int = Field(ge=0)
    served_portions: int = Field(ge=0)
    waste_portions: int = Field(ge=0)
    attendance: int = Field(ge=0)
    is_weekend: bool | None = None
    event_factor: float = Field(default=1.0, gt=0)
    weather: str | None = None


class ForecastRequest(BaseModel):
    date: date
    meal: str = Field(min_length=1, max_length=32)
    dish: str = Field(min_length=1, max_length=120)
    attendance: int = Field(ge=0)
    event_factor: float = Field(default=1.0, gt=0)
    extra_context: list[str] = Field(default_factory=list)


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
