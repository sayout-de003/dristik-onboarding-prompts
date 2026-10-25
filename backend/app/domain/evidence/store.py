"""
Dristik AI Immutable Evidence Store
Thread-safe registry of all deterministic observations for an audit run.
"""
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from app.domain.evidence.models import Evidence, MachineObservation
from app.domain.evidence.provenance import compute_evidence_hash, compute_raw_source_hash

class EvidenceStore:
    def __init__(self, run_id: str, snapshots=None):
        self.run_id = run_id
        self._evidence: Dict[str, Evidence] = {}
        self._observations: Dict[str, MachineObservation] = {}
        self._counter: int = 0
        self._ext_counter: int = 0
        self._obs_counter: int = 0
        self.snapshots = snapshots
        self._current_fetch: Optional[Dict[str, Any]] = None

    def _ensure_snapshots(self):
        if self.snapshots is None:
            from app.crawl.audit.snapshots import SnapshotStore
            self.snapshots = SnapshotStore(self.run_id)
        return self.snapshots

    def record_fetch(
        self,
        url: str,
        raw_body: Any,
        *,
        source: str = "http",
        source_type: str = "http",
        media_type: str = "text/html",
    ) -> Any:
        """Snapshot the raw page/API body. Subsequent add_evidence inherits this fetch."""
        fetched_at = datetime.now(timezone.utc)
        store = self._ensure_snapshots()
        record = store.put(
            source=source,
            body=raw_body,
            source_type=source_type,
            media_type=media_type,
            url=url,
            fetched_at=fetched_at.isoformat(),
        )
        self._current_fetch = {
            "url": url,
            "raw_snapshot_id": record.snapshot_id,
            "content_sha256": record.sha256,
            "fetched_at": fetched_at,
        }
        return record

    def add_evidence(
        self,
        source_type: str,
        analyzer: str,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        value: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        raw_source: Optional[Any] = None,
    ) -> Evidence:
        self._counter += 1
        ev_id = f"ev_{self._counter:03d}"
        ev_hash = compute_evidence_hash(source_type, analyzer, url, selector, text, value)
        fetch = self._current_fetch or {}
        fetched_at = fetch.get("fetched_at") or datetime.now(timezone.utc)
        snapshot_id = fetch.get("raw_snapshot_id")
        meta = dict(metadata or {})
        if fetch.get("content_sha256"):
            meta["parent_document_sha256"] = fetch.get("content_sha256")

        if raw_source is not None:
            content_sha = compute_raw_source_hash(raw_source)
            snap = self._ensure_snapshots().put(
                source=analyzer,
                body=raw_source,
                source_type=source_type,
                url=url,
                token_id=ev_id,
                fetched_at=fetched_at.isoformat() if hasattr(fetched_at, "isoformat") else str(fetched_at),
            )
            snapshot_id = snap.snapshot_id
            content_sha = snap.sha256
        else:
            content_sha = fetch.get("content_sha256") or compute_raw_source_hash(
                {"text": text or "", "value": value, "url": url or "", "selector": selector or ""}
            )

        evidence = Evidence(
            id=ev_id,
            source_type=source_type,
            url=url,
            selector=selector,
            text=text,
            value=value,
            analyzer=analyzer,
            hash=ev_hash,
            content_sha256=content_sha,
            fetched_at=fetched_at if isinstance(fetched_at, datetime) else None,
            raw_snapshot_id=snapshot_id,
            metadata=meta,
        )
        self._evidence[ev_id] = evidence
        return evidence

    def add_external_evidence(
        self,
        source: str,
        claim: str,
        raw_value: Optional[Any] = None,
        confidence_basis: str = "direct_api",
        conflicts_with: Optional[List[str]] = None,
        fetched_at: Optional[str] = None,
        url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Evidence:
        """Append an EXTERNAL_EVIDENCE item with token prefix ext_001, ext_002, ..."""
        self._ext_counter += 1
        ext_id = f"ext_{self._ext_counter:03d}"
        now = datetime.now(timezone.utc)
        fetched = fetched_at or now.isoformat()
        meta = dict(metadata or {})
        payload = raw_value if raw_value is not None else {}
        snap = self._ensure_snapshots().put(
            source=source,
            body=payload,
            source_type="api",
            media_type="application/json",
            url=url,
            token_id=ext_id,
            fetched_at=fetched,
        )
        meta.update({
            "source": source,
            "confidence_basis": confidence_basis,
            "conflicts_with": list(conflicts_with or []),
            "fetched_at": fetched,
            "evidence_class": "EXTERNAL_EVIDENCE",
            "raw_snapshot_id": snap.snapshot_id,
        })
        ev_hash = compute_evidence_hash("external", source, url, None, claim, payload)
        evidence = Evidence(
            id=ext_id,
            source_type="external",
            url=url,
            text=claim,
            value=payload,
            analyzer=source,
            hash=ev_hash,
            content_sha256=snap.sha256,
            fetched_at=now,
            raw_snapshot_id=snap.snapshot_id,
            metadata=meta,
        )
        self._evidence[ext_id] = evidence
        return evidence

    def get_external(self) -> List[Evidence]:
        return [ev for ev in self._evidence.values() if ev.id.startswith("ext_")]

    def add(self, evidence: Evidence) -> Evidence:
        self._evidence[evidence.id] = evidence
        if evidence.id.startswith("ext_"):
            try:
                n = int(evidence.id.split("_", 1)[1])
                self._ext_counter = max(self._ext_counter, n)
            except (ValueError, IndexError):
                pass
        return evidence

    def add_observation(
        self,
        attribute: str,
        value: Any,
        source: str = "html",
        url: Optional[str] = None,
        selector: Optional[str] = None,
        content_sha256: Optional[str] = None,
        evidence_id: Optional[str] = None,
        element: Optional[str] = None,
        expected_condition: Optional[str] = None,
        test_method: Optional[str] = None,
        response_status: Optional[int] = None,
        snippet: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MachineObservation:
        """
        Record an immutable Layer 1 Machine Observation.
        Canonical contract:
        {
          "type": "observation",
          "attribute": "title",
          "value": "Business Consulting",
          "source": "html",
          "evidence_id": "EV_001"
        }
        """
        if not evidence_id:
            self._obs_counter += 1
            evidence_id = f"EV_{self._obs_counter:03d}"

        if content_sha256 is None:
            fetch = self._current_fetch or {}
            content_sha256 = fetch.get("content_sha256") or compute_raw_source_hash(value)

        meta = dict(metadata or {})

        obs = MachineObservation(
            type="observation",
            attribute=attribute,
            value=value,
            source=source,
            evidence_id=evidence_id,
            url=url,
            selector=selector,
            element=element,
            expected_condition=expected_condition,
            test_method=test_method,
            response_status=response_status,
            snippet=snippet,
            metadata=meta,
            content_sha256=content_sha256,
            timestamp=datetime.now(timezone.utc),
        )
        self._observations[evidence_id] = obs
        self._observations[evidence_id.lower()] = obs
        self._observations[evidence_id.upper()] = obs

        # Backward compatibility registration in legacy Evidence table
        legacy_meta = {"attribute": attribute, "is_machine_observation": True}
        if element:
            legacy_meta["element"] = element
        if expected_condition:
            legacy_meta["expected_condition"] = expected_condition
        if test_method:
            legacy_meta["test_method"] = test_method
        if response_status:
            legacy_meta["response_status"] = response_status
        legacy_meta.update(meta)

        ev_legacy = Evidence(
            id=evidence_id,
            source_type=source,
            url=url,
            selector=selector,
            text=str(value) if value is not None else "",
            value=value,
            analyzer=f"layer1_{source}",
            hash=compute_evidence_hash(source, f"layer1_{source}", url, selector, str(value), value),
            content_sha256=content_sha256 or "",
            fetched_at=datetime.now(timezone.utc),
            raw_snapshot_id=(self._current_fetch or {}).get("raw_snapshot_id"),
            metadata=legacy_meta,
        )
        self._evidence[evidence_id] = ev_legacy
        self._evidence[evidence_id.lower()] = ev_legacy
        self._evidence[evidence_id.upper()] = ev_legacy
        return obs

    def get_observation(self, evidence_id: str) -> Optional[MachineObservation]:
        return (
            self._observations.get(evidence_id)
            or self._observations.get(evidence_id.lower())
            or self._observations.get(evidence_id.upper())
        )

    def get_all_observations(self) -> List[MachineObservation]:
        seen = set()
        res = []
        for obs in self._observations.values():
            if obs.evidence_id not in seen:
                seen.add(obs.evidence_id)
                res.append(obs)
        return res

    def get_observations_by_attribute(self, attribute: str) -> List[MachineObservation]:
        return [o for o in self.get_all_observations() if o.attribute.lower() == attribute.lower()]

    def get(self, evidence_id: str) -> Optional[Evidence]:
        return (
            self._evidence.get(evidence_id)
            or self._evidence.get(evidence_id.lower())
            or self._evidence.get(evidence_id.upper())
        )

    def get_all(self) -> List[Evidence]:
        seen = set()
        res = []
        for ev in self._evidence.values():
            if ev.id not in seen:
                seen.add(ev.id)
                res.append(ev)
        return res

    def get_by_source_type(self, source_type: str) -> List[Evidence]:
        return [ev for ev in self.get_all() if ev.source_type == source_type]

    def count(self) -> int:
        return len(self.get_all())
