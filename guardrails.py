"""Guardrail: check the model's proposed scorecard against fixed business rules in
code, not just in the prompt.

Rule being enforced: a "reject" recommendation always routes to a human recruiter
for review, and recruiter notes are proposals that require human approval - never
auto-sent to candidates.
"""
from typing import Optional

from pydantic import BaseModel

from schema import Scorecard

# Phrasing that would mean a recruiter note has stopped being an internal proposal
# and started reading like a message already delivered to the candidate.
CANDIDATE_FACING_PATTERNS = [
    "dear candidate",
    "sent to the candidate",
    "email sent",
    "email has been sent",
    "notified the candidate",
    "we regret to inform you",
    "we are pleased to inform you",
    "your application",
]


class GuardrailBlocked(Exception):
    """Raised when the model's proposed result violates a hard business rule."""


class ScreeningOutcome(BaseModel):
    """What screen_cv actually returns: the safety-checked result, not the raw model output."""

    status: str  # "ok" | "blocked" | "incomplete"
    scorecard: Optional[Scorecard] = None
    requires_human_review: bool = False
    message: Optional[str] = None


def enforce_guardrails(scorecard: Scorecard) -> bool:
    """Check a proposed scorecard against the routing/approval rule.

    Returns requires_human_review (always True for a "reject" recommendation or any
    critical finding, regardless of what the model's text claims). Raises
    GuardrailBlocked if any recruiter_note reads as already delivered to the
    candidate - that would violate "notes are proposals only".
    """
    violations = []
    for finding in scorecard.findings:
        if not finding.recruiter_note:
            continue
        note_lower = finding.recruiter_note.lower()
        for pattern in CANDIDATE_FACING_PATTERNS:
            if pattern in note_lower:
                violations.append(
                    f"recruiter_note for '{finding.criterion}' reads as candidate-facing "
                    f"(matched '{pattern}') - recruiter notes must stay internal proposals"
                )

    if violations:
        raise GuardrailBlocked("; ".join(violations))

    return scorecard.recommendation == "reject" or any(f.is_critical for f in scorecard.findings)
