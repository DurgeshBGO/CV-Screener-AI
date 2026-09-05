"""Entry point: screen a candidate CV for BGO call center agent fitness."""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

import ledger
from guardrails import GuardrailBlocked, ScreeningOutcome, enforce_guardrails
from prompts.system_prompt import SYSTEM_PROMPT
from schema import Scorecard, validate_scorecard
from tools import CHECK_QUALIFICATIONS_TOOL, check_qualifications

AVAILABLE_TOOLS = {"check_qualifications": check_qualifications}

load_dotenv()

MODEL = os.environ.get("CV_SCREENER_MODEL", "gemini-3.6-flash")
MAX_TOOL_CALLS = 5


def smoke_test() -> None:
    """One-off connectivity check: single message, no system prompt, no tools."""
    client = genai.Client()
    response = client.models.generate_content(
        model=MODEL,
        contents="Say hello and name the model you are.",
    )
    print(response.text)


def _text_of(content: types.Content) -> str:
    """Concatenate the text parts of a Content, ignoring function_call/response parts."""
    return "".join(part.text for part in content.parts if part.text).strip()


def _finish(outcome: ScreeningOutcome, tool_calls_made: int) -> ScreeningOutcome:
    """Report the run to Spine Central (fail-open no-op if unconfigured), then return it."""
    ledger.record_run(
        status=outcome.status,
        tool_calls_made=tool_calls_made,
        requires_human_review=outcome.requires_human_review,
        message=outcome.message,
    )
    return outcome


def screen_cv(cv_text: str, client: genai.Client | None = None) -> ScreeningOutcome:
    """Run the agent loop: call the model, execute any requested tool, repeat until
    a normal (non-tool-call) message comes back.

    Stop rule: the loop ends after one final scorecard, or after MAX_TOOL_CALLS tool
    calls - whichever comes first. Guardrail: the model's proposed scorecard is
    checked against the routing/approval rule in code before it is ever returned.
    """
    client = client or genai.Client()

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=Scorecard,
        tools=[CHECK_QUALIFICATIONS_TOOL],
    )
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"Screen this CV:\n\n{cv_text}")],
        )
    ]

    turn = 0
    tool_calls_made = 0
    while True:
        turn += 1
        response = client.models.generate_content(model=MODEL, contents=contents, config=config)
        message = response.candidates[0].content
        thought = _text_of(message)

        print(f"\n=== Turn {turn} ===")
        if thought:
            print(f"[model] {thought}")

        if not response.function_calls:
            # Normal message - this is the model's proposed final answer.
            scorecard, errors = validate_scorecard(json.loads(thought))
            if scorecard is None:
                raise ValueError(f"Model output failed the scorecard contract: {errors}")

            try:
                requires_human_review = enforce_guardrails(scorecard)
            except GuardrailBlocked as exc:
                print(f"[guardrail] BLOCKED: {exc}")
                return _finish(
                    ScreeningOutcome(
                        status="blocked",
                        requires_human_review=True,
                        message=f"Result blocked and flagged for human review: {exc}",
                    ),
                    tool_calls_made,
                )

            print(f"[guardrail] requires_human_review={requires_human_review}")
            return _finish(
                ScreeningOutcome(
                    status="ok", scorecard=scorecard, requires_human_review=requires_human_review
                ),
                tool_calls_made,
            )

        # Tool call(s) - stop rule: never exceed MAX_TOOL_CALLS total.
        contents.append(message)
        for call in response.function_calls:
            if tool_calls_made >= MAX_TOOL_CALLS:
                break
            tool_calls_made += 1
            print(f"[tool call {tool_calls_made}/{MAX_TOOL_CALLS}] {call.name}({call.args})")
            tool_fn = AVAILABLE_TOOLS.get(call.name)
            result = tool_fn(**call.args) if tool_fn else {"error": f"unknown tool: {call.name}"}
            print(f"[tool result] {json.dumps(result)}")
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(name=call.name, response={"result": result})],
                )
            )

        if tool_calls_made >= MAX_TOOL_CALLS:
            print(f"[stop rule] tool-call cap ({MAX_TOOL_CALLS}) reached without a final answer")
            return _finish(
                ScreeningOutcome(
                    status="incomplete",
                    requires_human_review=True,
                    message=f"Agent could not complete within {MAX_TOOL_CALLS} tool calls.",
                ),
                tool_calls_made,
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Screen a CV for BGO call center agent fitness."
    )
    parser.add_argument(
        "cv_file",
        nargs="?",
        help="Path to a plain-text CV file. Reads from stdin if omitted.",
    )
    args = parser.parse_args()

    cv_text = Path(args.cv_file).read_text(encoding="utf-8") if args.cv_file else sys.stdin.read()

    if not cv_text.strip():
        parser.error("No CV text provided (pass a file path or pipe text via stdin).")

    outcome = screen_cv(cv_text)
    print(json.dumps(outcome.model_dump(), indent=2))


if __name__ == "__main__":
    main()
