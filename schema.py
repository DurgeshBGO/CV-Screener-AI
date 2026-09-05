"""Output contract for cv-screener: the screening scorecard shape and its validator.

No agent/API logic lives here - just the typed schema and a function that rejects
any candidate result missing a field or carrying an out-of-range value.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, model_validator

Criterion = Literal[
    "customer_service_experience",
    "communication_skills",
    "computer_literacy",
    "schedule_flexibility",
    "employment_stability",
    "education_certifications",
    "red_flags",
]

Result = Literal["meets", "partially meets", "fails"]

Recommendation = Literal["advance", "hold", "reject"]


class Finding(BaseModel):
    """One criterion's assessment. A critical finding must carry a recruiter note."""

    criterion: Criterion
    result: Result
    detail: str = Field(min_length=1)
    is_critical: bool
    recruiter_note: Optional[str] = None

    @model_validator(mode="after")
    def _critical_requires_note(self) -> "Finding":
        if self.is_critical and not (self.recruiter_note and self.recruiter_note.strip()):
            raise ValueError("recruiter_note is required when is_critical is true")
        if not self.is_critical and self.recruiter_note:
            raise ValueError("recruiter_note must be empty when is_critical is false")
        return self


class Scorecard(BaseModel):
    """The full screening result for one candidate."""

    score: int = Field(ge=0, le=100)
    recommendation: Recommendation
    summary: str = Field(min_length=1)
    findings: List[Finding] = Field(min_length=1)


def validate_scorecard(data: dict) -> tuple[Optional[Scorecard], List[str]]:
    """Validate a raw dict against the Scorecard contract.

    Returns (scorecard, []) on success, or (None, errors) if any field is
    missing, out of range, or fails a cross-field rule (e.g. a critical
    finding with no recruiter note).
    """
    try:
        return Scorecard.model_validate(data), []
    except ValidationError as exc:
        errors = [
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()
        ]
        return None, errors
