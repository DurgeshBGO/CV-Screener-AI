"""The check_qualifications tool: deterministic CV checks (experience, skills, red flags).

Split in two: the schema the model sees (CHECK_QUALIFICATIONS_TOOL) and the plain
Python function that actually runs the checks (check_qualifications), which has no
model/API dependency and can be called directly for offline testing.
"""
import re
from typing import Any, Dict, List

from google.genai import types

EXPERIENCE_KEYWORDS = [
    "call center",
    "call centre",
    "customer service",
    "customer support",
    "customer care",
    "support representative",
    "help desk",
    "helpdesk",
]

SKILL_KEYWORDS = [
    "crm",
    "salesforce",
    "zendesk",
    "freshdesk",
    "livechat",
    "live chat",
    "typing",
    "microsoft office",
]

PLACEHOLDER_EMAIL_PATTERN = re.compile(
    r"@(test|example|sample|fake|dummy|foo|sffdf)\w*\.\w+", re.IGNORECASE
)
YEAR_PATTERN = re.compile(r"(19|20)\d{2}")


def check_qualifications(cv_text: str) -> Dict[str, Any]:
    """Run deterministic keyword/pattern checks over CV text. Pure logic, no LLM call."""
    text_lower = cv_text.lower()

    matched_experience: List[str] = [k for k in EXPERIENCE_KEYWORDS if k in text_lower]
    matched_skills: List[str] = [k for k in SKILL_KEYWORDS if k in text_lower]

    red_flags = {
        "placeholder_email": bool(PLACEHOLDER_EMAIL_PATTERN.search(cv_text)),
        "no_dates_found": not bool(YEAR_PATTERN.search(cv_text)),
    }

    return {
        "has_relevant_experience": bool(matched_experience),
        "matched_experience_keywords": matched_experience,
        "matched_skills": matched_skills,
        "red_flags": red_flags,
    }


CHECK_QUALIFICATIONS_DECLARATION = types.FunctionDeclaration(
    name="check_qualifications",
    description=(
        "Use this to get a deterministic, keyword/pattern-based check of a CV's "
        "call-center-relevant experience, tool/skill mentions, and red flags "
        "(placeholder-looking email, missing dates), instead of guessing from the "
        "raw text alone."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "cv_text": types.Schema(
                type=types.Type.STRING,
                description="The raw candidate CV/resume text to check.",
            ),
        },
        required=["cv_text"],
    ),
)

CHECK_QUALIFICATIONS_TOOL = types.Tool(
    function_declarations=[CHECK_QUALIFICATIONS_DECLARATION]
)
