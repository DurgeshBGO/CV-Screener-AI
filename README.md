# CV Screener

An AI agent that screens a candidate CV for fitness as a BGO call center agent and
produces a structured hiring recommendation. Built on Gemini with tool calling, a
validated output schema, and business-rule guardrails enforced in code (not just
in the prompt). Includes a CLI and a Streamlit UI.

## How it works

1. **Agent loop** (`main.screen_cv`) — sends the CV plus a system prompt to Gemini,
   lets the model call the `check_qualifications` tool for deterministic keyword/
   pattern checks, and repeats until the model returns a final scorecard or a
   5-call tool cap is hit.
2. **Schema validation** (`schema.py`) — the model's JSON output must match the
   `Scorecard` contract: a 0-100 score, an `advance` / `hold` / `reject`
   recommendation, and per-criterion findings, each with a required recruiter
   note if marked critical.
3. **Guardrails** (`guardrails.py`) — enforced in code, independent of what the
   model claims:
   - Any `reject` recommendation, or any critical finding, always sets
     `requires_human_review = True`.
   - Recruiter notes are internal proposals only; a note that reads as already
     sent to the candidate blocks the result and flags it for human review.
4. **Ledger** (`ledger.py`) — reports each run to an external "Spine Central"
   service if `SPINE_CENTRAL_URL` is configured; a silent no-op otherwise.

Screening criteria: customer service experience, communication skills, computer
literacy, schedule flexibility, employment stability, education/certifications,
and red flags.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add your GEMINI_API_KEY
```

## Usage

### CLI

```bash
python main.py path/to/cv.txt
# or pipe text in:
cat path/to/cv.txt | python main.py
```

Prints the agent's turn-by-turn trace, then a JSON `ScreeningOutcome`.

### Streamlit UI

```bash
streamlit run app.py
```

Paste or upload a CV, run the screening agent, and review the scorecard
(score, recommendation, per-criterion findings, recruiter notes, and a
human-review flag) along with the full agent trace.

### Evals

```bash
python eval.py
```

Runs a handful of fixed CVs (clear fit, clear misfit, disqualifying red flag,
borderline gap, adversarial prompt injection) against the real agent and checks
each result against a rule a hiring manager would agree with. Exits non-zero on
any failure, so it can run as a CI gate.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Agent loop entry point (CLI + `screen_cv`) |
| `app.py` | Streamlit UI |
| `schema.py` | Output contract (`Scorecard`) and validator |
| `guardrails.py` | Business-rule enforcement, independent of the model |
| `ledger.py` | Fail-open reporting to Spine Central |
| `prompts/system_prompt.py` | System prompt |
| `tools/qualification_checks.py` | `check_qualifications` tool (deterministic CV checks) |
| `eval.py` | Scenario-based eval suite |
| `aop/cv_screening.yaml`, `spine.skills.json` | Agent operating procedure / Spine registration metadata |

## Configuration

| Env var | Purpose |
|---|---|
| `GEMINI_API_KEY` | Required. Gemini API key. |
| `CV_SCREENER_MODEL` | Optional. Overrides the default model (`gemini-3.6-flash`). |
| `SPINE_CENTRAL_URL` | Optional. Enables run reporting to Spine Central; unset = no-op. |

## Notes

- `reject` recommendations and critical findings always require human review —
  the agent makes a recommendation, not a final hiring decision.
- The agent treats CV content strictly as data: instructions embedded in a CV
  (prompt injection) are ignored, which `eval.py`'s adversarial case checks for.
