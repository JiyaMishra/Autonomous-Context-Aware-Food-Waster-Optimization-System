"""Academic calendar with configurable exam periods for attendance prediction.

Provides exam intensity lookup for any target date. Intensity represents
how strongly exams affect student dining patterns: 0 = no effect, 1 = peak
exam period (FAT finals).

The exam schedule is configurable — update EXAM_PERIODS for each semester.
"""
from __future__ import annotations

from datetime import date, timedelta


# ── Configurable exam schedule ──────────────────────────────────────────────
# Update these entries each semester. Each period has:
#   - start / end: inclusive date range of the exam window
#   - intensity: 0.0–1.0 representing peak impact on attendance
#   - label: human-readable name
#   - ramp_days: how many days before the exam window students start
#     changing their dining patterns (studying late, skipping meals, etc.)
EXAM_PERIODS: list[dict] = [
    # ── Odd Semester 2026–27 (typical VIT schedule) ──
    {
        "start": "2026-09-14",
        "end": "2026-09-24",
        "intensity": 0.7,
        "label": "CAT-1",
        "ramp_days": 5,
    },
    {
        "start": "2026-11-23",
        "end": "2026-12-08",
        "intensity": 1.0,
        "label": "FAT (Final Assessment Test)",
        "ramp_days": 7,
    },
    # ── Even Semester 2027 ──
    {
        "start": "2027-02-16",
        "end": "2027-02-26",
        "intensity": 0.7,
        "label": "CAT-1",
        "ramp_days": 5,
    },
    {
        "start": "2027-03-22",
        "end": "2027-04-01",
        "intensity": 0.8,
        "label": "CAT-2",
        "ramp_days": 5,
    },
    {
        "start": "2027-05-10",
        "end": "2027-05-25",
        "intensity": 1.0,
        "label": "FAT (Final Assessment Test)",
        "ramp_days": 7,
    },
]


def _parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def get_exam_intensity(target_date: date) -> dict:
    """Look up exam intensity and context for a given date.

    Parameters
    ----------
    target_date : date
        The date to check.

    Returns
    -------
    dict
        {
            "exam_intensity": float,       # 0.0–1.0
            "exam_label": str | None,      # e.g. "CAT-1"
            "is_exam_period": bool,
            "is_ramp_up": bool,            # True if in the preparation days
            "days_until_exam": int | None, # None if not near any exam
            "effect_description": str,     # Human-readable summary
        }
    """
    closest_distance = float("inf")
    best_match: dict | None = None
    best_phase: str = ""

    for period in EXAM_PERIODS:
        start = _parse_date(period["start"])
        end = _parse_date(period["end"])
        ramp_days = period.get("ramp_days", 5)
        peak_intensity = period["intensity"]
        label = period["label"]

        ramp_start = start - timedelta(days=ramp_days)

        if start <= target_date <= end:
            # Inside the exam window itself.
            return {
                "exam_intensity": peak_intensity,
                "exam_label": label,
                "is_exam_period": True,
                "is_ramp_up": False,
                "days_until_exam": 0,
                "effect_description": (
                    f"Currently in {label} exam period. "
                    f"Expect {_attendance_impact(peak_intensity)} attendance impact."
                ),
            }

        if ramp_start <= target_date < start:
            # In the ramp-up window before exams.
            days_until = (start - target_date).days
            # Intensity ramps linearly from 30% to 80% of peak.
            progress = 1 - (days_until / ramp_days)
            ramp_intensity = round(peak_intensity * (0.3 + 0.5 * progress), 2)

            distance = days_until
            if distance < closest_distance:
                closest_distance = distance
                best_match = {
                    "exam_intensity": ramp_intensity,
                    "exam_label": label,
                    "is_exam_period": False,
                    "is_ramp_up": True,
                    "days_until_exam": days_until,
                    "effect_description": (
                        f"{label} starts in {days_until} day(s). "
                        f"Pre-exam period: students altering meal habits. "
                        f"Expect {_attendance_impact(ramp_intensity)} attendance impact."
                    ),
                }
                best_phase = "ramp"

        # Check how far away the nearest future exam is.
        if target_date < ramp_start:
            days_away = (start - target_date).days
            if days_away < closest_distance and best_phase != "ramp":
                closest_distance = days_away
                best_match = {
                    "exam_intensity": 0.0,
                    "exam_label": None,
                    "is_exam_period": False,
                    "is_ramp_up": False,
                    "days_until_exam": days_away,
                    "effect_description": (
                        f"Next exam ({label}) is {days_away} days away. "
                        f"No significant exam impact expected."
                    ),
                }

    if best_match is not None:
        return best_match

    # No matching exam period found at all.
    return {
        "exam_intensity": 0.0,
        "exam_label": None,
        "is_exam_period": False,
        "is_ramp_up": False,
        "days_until_exam": None,
        "effect_description": "No scheduled exams found near this date.",
    }


def _attendance_impact(intensity: float) -> str:
    """Translate a 0–1 intensity to a human description."""
    if intensity >= 0.8:
        return "significant (15–25% drop)"
    if intensity >= 0.5:
        return "moderate (8–15% drop)"
    if intensity >= 0.2:
        return "mild (3–8% drop)"
    return "negligible"
