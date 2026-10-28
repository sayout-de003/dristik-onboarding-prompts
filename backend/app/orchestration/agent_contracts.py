"""Runtime contracts for specialist-agent outputs.

Agent outputs are untrusted inputs to scoring and report synthesis. This module
normalizes only the execution envelope; it does not certify the claims themselves.
Claim/evidence certification remains the responsibility of the evidence integrity gate.
"""
from __future__ import annotations

from typing import Any


VALID_AGENT_STATUSES = {
    "completed", "success", "partial", "unavailable", "skipped", "error", "failed"
}


def validate_agent_result(expected_agent_id: str, payload: Any) -> dict[str, Any]:
    """Return a safe, explicit result envelope or a non-success error record."""
    if not isinstance(payload, dict):
        return {
            "agent_id": expected_agent_id,
            "status": "error",
            "error_code": "INVALID_RESULT_TYPE",
            "unavailable_reason": "Agent returned a non-object result.",
            "claims": [],
        }

    returned_id = payload.get("agent_id")
    if returned_id and returned_id != expected_agent_id:
        return {
            "agent_id": expected_agent_id,
            "status": "error",
            "error_code": "AGENT_ID_MISMATCH",
            "unavailable_reason": "Agent result identity did not match the scheduled agent.",
            "claims": [],
        }

    status = payload.get("status")
    if not isinstance(status, str) or status.strip().lower() not in VALID_AGENT_STATUSES:
        return {
            "agent_id": expected_agent_id,
            "status": "error",
            "error_code": "INVALID_AGENT_STATUS",
            "unavailable_reason": "Agent result omitted a recognized execution status.",
            "claims": [],
        }

    claims = payload.get("claims", [])
    if not isinstance(claims, list) or any(not isinstance(claim, dict) for claim in claims):
        return {
            "agent_id": expected_agent_id,
            "status": "error",
            "error_code": "INVALID_CLAIMS_SHAPE",
            "unavailable_reason": "Agent claims field must be a list of claim objects.",
            "claims": [],
        }

    normalized_status = status.strip().lower()
    if normalized_status in {"unavailable", "skipped", "error", "failed"} and claims:
        return {
            "agent_id": expected_agent_id,
            "status": "error",
            "error_code": "CLAIMS_ON_NON_SUCCESS_STATUS",
            "unavailable_reason": "An unavailable, skipped, or failed agent cannot publish claims.",
            "claims": [],
        }

    refs = payload.get("evidence_refs", [])
    if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        return {
            "agent_id": expected_agent_id,
            "status": "error",
            "error_code": "INVALID_EVIDENCE_REFS_SHAPE",
            "unavailable_reason": "Agent evidence_refs must be a list of non-empty strings.",
            "claims": [],
        }

    normalized = dict(payload)
    normalized["agent_id"] = expected_agent_id
    normalized["status"] = normalized_status
    normalized["claims"] = claims
    normalized["evidence_refs"] = list(dict.fromkeys(refs))
    return normalized
