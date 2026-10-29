from datetime import date
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class AttendancePredictionRequest(BaseModel):
    """Request body for the AI attendance prediction endpoint with optional parameter overrides."""
    date: date
    meal: str = Field(min_length=1, max_length=32)
    total_registered: int | None = Field(default=None, ge=0)
    # Contextual parameters that the user can set if the AI does not know them:
    exam_intensity: float | None = Field(default=None, ge=0, le=1)
    exam_label: str | None = Field(default=None, max_length=80)
    temperature_c: float | None = Field(default=None, ge=-10, le=60)
    rainfall_mm: float | None = Field(default=None, ge=0, le=1000)
    campus_situation: str | None = Field(default=None, max_length=80)
    campus_factor: float = Field(default=1.0, gt=0, le=2.0)


class AttendancePredictionResponse(BaseModel):
    """Full attendance prediction with weather, exam, and confidence details."""
    date: date
    meal: str
    predicted_attendance: int
    predicted_absent: int
    total_registered: int
    turnout_pct: float
    weather: dict
    exam: dict
    campus_situation: str | None = None
    campus_factor: float = 1.0
    confidence: str
    method: str
    training_samples: int
    training_rmse: float | None
    factors: dict
    factors_summary: list[str]
    parameters_used: dict | None = None


class ForecastRequest(BaseModel):
    date: date
    meal: str = Field(min_length=1, max_length=32)
    dish: str = Field(min_length=1, max_length=120)
    attendance: int | None = Field(default=None, ge=0)  # None = AI auto-predicts
    event_factor: float = Field(default=1.0, gt=0)
    extra_context: list[str] = Field(default_factory=list)
    synthetic_liking_score: float | None = Field(default=None, ge=0, le=1)
    exam_intensity: float | None = Field(default=None, ge=0, le=1)
    exam_label: str | None = Field(default=None, max_length=80)
    temperature_c: float | None = Field(default=None, ge=-10, le=60)
    rainfall_mm: float | None = Field(default=None, ge=0, le=1000)
    campus_situation: str | None = Field(default=None, max_length=80)
    campus_factor: float = Field(default=1.0, gt=0, le=2.0)
    historical_demand_rate: float | None = Field(default=None, ge=0, le=1)


class ForecastResponse(BaseModel):
    date: date
    meal: str
    dish: str
    predicted_portions: int = Field(ge=0)
    method: str
    confidence: str
    explanation: list[str]
    auto_predicted_attendance: int | None = None


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
    auto_predicted_attendance: int | None = None


class DecisionFeedback(BaseModel):
    approved: bool
    reviewer: str = Field(default="kitchen_operator", min_length=1, max_length=80)
    note: str = Field(default="", max_length=500)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    context: dict | None = None


class ChatResponse(BaseModel):
    reply: str
    suggestions: list[str] = Field(default_factory=list)

