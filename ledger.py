"""Fail-open ledger: reports each run to Spine Central as a metering event and
an outcome, cross-linked by the same run id.

Fail-open in two senses:
- If SPINE_CENTRAL_URL is unset, record_run() is a silent no-op - the demo
  runs standalone with no platform dependency.
- If it is set but the platform is unreachable or errors, the failure is
  logged and swallowed. The ledger must never break a screening run.
"""
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, Optional

TENANT_ID = "bgo-internal"
TENANT_HEADER = "X-Tenant-ID"
REQUEST_TIMEOUT_SECONDS = 5


def _post(url: str, payload: Dict[str, Any]) -> None:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", TENANT_HEADER: TENANT_ID},
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        response.read()


def record_run(
    *,
    agent: str = "cv-screener",
    status: str,
    tool_calls_made: int,
    requires_human_review: bool,
    message: Optional[str] = None,
) -> None:
    """Report one agent run to Spine Central. No-ops if SPINE_CENTRAL_URL is unset."""
    base_url = os.environ.get("SPINE_CENTRAL_URL")
    if not base_url:
        return

    run_id = str(uuid.uuid4())
    timestamp = time.time()

    event = {
        "id": run_id,
        "tenant": TENANT_ID,
        "agent": agent,
        "type": "agent_run",
        "timestamp": timestamp,
    }
    outcome = {
        "id": run_id,
        "tenant": TENANT_ID,
        "agent": agent,
        "status": status,
        "tool_calls_made": tool_calls_made,
        "requires_human_review": requires_human_review,
        "message": message,
        "timestamp": timestamp,
    }

    base_url = base_url.rstrip("/")
    try:
        _post(f"{base_url}/metering/events", event)
        _post(f"{base_url}/outcomes", outcome)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"[ledger] fail-open: could not report run {run_id} to Spine Central: {exc}")
