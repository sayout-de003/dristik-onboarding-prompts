import pytest

from app.orchestration.agent_contracts import validate_agent_result


def test_valid_agent_result_preserves_claims_and_extra_metadata():
    payload = {
        "agent_id": "seo.title",
        "status": "completed",
        "claims": [{"claim_id": "c1"}],
        "evidence_refs": ["ev_001"],
        "elapsed_ms": 123,
    }
    result = validate_agent_result("seo.title", payload)
    assert result["status"] == "completed"
    assert result["claims"] == [{"claim_id": "c1"}]
    assert result["elapsed_ms"] == 123


@pytest.mark.parametrize("payload", [None, [], "completed", 17])
def test_non_object_result_becomes_explicit_error(payload):
    result = validate_agent_result("seo.title", payload)
    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_RESULT_TYPE"
    assert result["claims"] == []


def test_missing_or_unknown_status_never_defaults_to_success():
    result = validate_agent_result("seo.title", {"claims": []})
    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_AGENT_STATUS"


def test_mismatched_agent_identity_is_rejected():
    result = validate_agent_result("seo.title", {
        "agent_id": "geo.identity", "status": "completed", "claims": []
    })
    assert result["status"] == "error"
    assert result["error_code"] == "AGENT_ID_MISMATCH"


def test_invalid_claim_shape_is_rejected():
    result = validate_agent_result("seo.title", {
        "status": "completed", "claims": {"not": "a list"}
    })
    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_CLAIMS_SHAPE"


def test_invalid_evidence_refs_shape_is_rejected():
    result = validate_agent_result("seo.title", {
        "status": "completed", "claims": [], "evidence_refs": ["ev_1", ""]
    })
    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_EVIDENCE_REFS_SHAPE"


def test_agent_status_is_normalized():
    result = validate_agent_result("seo.title", {
        "status": " COMPLETED ", "claims": []
    })
    assert result["status"] == "completed"



def test_claims_must_be_objects_not_arbitrary_scalars():
    result = validate_agent_result("seo.title", {
        "status": "completed", "claims": ["this is not a claim object"]
    })
    assert result["status"] == "error"
    assert result["error_code"] == "INVALID_CLAIMS_SHAPE"


def test_unavailable_agent_cannot_publish_claims():
    result = validate_agent_result("seo.title", {
        "status": "unavailable",
        "claims": [{"claim_id": "unsupported"}],
    })
    assert result["status"] == "error"
    assert result["error_code"] == "CLAIMS_ON_NON_SUCCESS_STATUS"
    assert result["claims"] == []


def test_evidence_references_are_deduplicated():
    result = validate_agent_result("seo.title", {
        "status": "completed",
        "claims": [],
        "evidence_refs": ["ev_001", "ev_001"],
    })
    assert result["evidence_refs"] == ["ev_001"]
