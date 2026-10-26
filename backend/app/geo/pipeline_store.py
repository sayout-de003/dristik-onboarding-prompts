"""
Dristik AI GEO/AEO Time-Series Snapshot Store
Persistent SQLite storage for live LLM answer engine queries.
Stores raw verbatim model responses, citations, positions, and computes deltas over time.
"""
import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

def _backend_data_dir() -> str:
    """Return ``backend/data`` no matter how deep this module sits under ``app``."""
    cursor = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.basename(cursor) == "app":
            return os.path.join(os.path.dirname(cursor), "data")
        parent = os.path.dirname(cursor)
        if parent == cursor:
            break
        cursor = parent
    raise RuntimeError("could not locate backend/app from geo pipeline store")


DB_DIR = _backend_data_dir()
DB_PATH = os.path.join(DB_DIR, "geo_aeo_pipeline.db")


class GeoQueryRecord(BaseModel):
    query_id: str
    buyer_query: str
    commercial_intent: str
    engine_id: str
    engine_name: str
    raw_response_text: str
    was_mentioned: bool
    mention_position: Optional[int] = None
    was_cited: bool
    cited_urls: List[str] = Field(default_factory=list)
    competitor_cited_instead: Optional[str] = None
    extractability_health: str = "GOOD"
    delta_vs_previous: Optional[str] = None


class GeoSnapshotSummary(BaseModel):
    snapshot_id: str
    domain: str
    brand_name: str
    industry: str
    timestamp: str
    overall_score: int
    delta_score: Optional[int] = None
    total_queries: int
    engines_measured_count: int
    engine_scores: Dict[str, float] = Field(default_factory=dict)
    critical_blindspots: List[str] = Field(default_factory=list)


class GeoSnapshotDetail(GeoSnapshotSummary):
    query_results: List[GeoQueryRecord] = Field(default_factory=list)


class GeoPipelineStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_dir()
        self.init_db()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes the SQLite tables for snapshots and query results."""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS geo_snapshots (
                    id TEXT PRIMARY KEY,
                    domain TEXT NOT NULL,
                    brand_name TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    overall_score INTEGER NOT NULL,
                    delta_score INTEGER,
                    total_queries INTEGER NOT NULL,
                    engines_measured_count INTEGER NOT NULL,
                    engine_scores_json TEXT NOT NULL,
                    critical_blindspots_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_geo_snapshots_domain ON geo_snapshots(domain, timestamp DESC)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS geo_query_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id TEXT NOT NULL,
                    query_id TEXT NOT NULL,
                    buyer_query TEXT NOT NULL,
                    commercial_intent TEXT NOT NULL,
                    engine_id TEXT NOT NULL,
                    engine_name TEXT NOT NULL,
                    raw_response_text TEXT NOT NULL,
                    was_mentioned BOOLEAN NOT NULL,
                    mention_position INTEGER,
                    was_cited BOOLEAN NOT NULL,
                    cited_urls_json TEXT NOT NULL,
                    competitor_cited_instead TEXT,
                    extractability_health TEXT NOT NULL,
                    delta_vs_previous TEXT,
                    FOREIGN KEY(snapshot_id) REFERENCES geo_snapshots(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_geo_query_snapshot ON geo_query_results(snapshot_id)
            """)
            conn.commit()

    def get_latest_snapshot(self, domain: str) -> Optional[GeoSnapshotSummary]:
        """Returns the most recent snapshot for a domain."""
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM geo_snapshots WHERE domain = ? ORDER BY timestamp DESC LIMIT 1",
                (clean_domain,)
            ).fetchone()
            if not row:
                return None
            return GeoSnapshotSummary(
                snapshot_id=row["id"],
                domain=row["domain"],
                brand_name=row["brand_name"],
                industry=row["industry"],
                timestamp=row["timestamp"],
                overall_score=row["overall_score"],
                delta_score=row["delta_score"],
                total_queries=row["total_queries"],
                engines_measured_count=row["engines_measured_count"],
                engine_scores=json.loads(row["engine_scores_json"] or "{}"),
                critical_blindspots=json.loads(row["critical_blindspots_json"] or "[]"),
            )

    def save_snapshot(
        self,
        snapshot_id: str,
        domain: str,
        brand_name: str,
        industry: str,
        overall_score: int,
        engine_scores: Dict[str, float],
        critical_blindspots: List[str],
        query_results: List[GeoQueryRecord],
        engines_measured_count: int,
        timestamp: Optional[str] = None
    ) -> GeoSnapshotDetail:
        """
        Saves a full live snapshot, calculating delta against the most recent prior snapshot.
        """
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
        ts = timestamp or datetime.now(timezone.utc).isoformat()

        # Compute delta vs prior snapshot
        prev = self.get_latest_snapshot(clean_domain)
        delta_score = (overall_score - prev.overall_score) if prev else None

        # Calculate per-query deltas if previous snapshot exists
        if prev:
            prev_detail = self.get_snapshot_detail(prev.snapshot_id)
            prev_map = {}
            if prev_detail:
                for r in prev_detail.query_results:
                    prev_map[(r.query_id, r.engine_id)] = r

            for qr in query_results:
                prior = prev_map.get((qr.query_id, qr.engine_id))
                if prior:
                    if not prior.was_cited and qr.was_cited:
                        qr.delta_vs_previous = "+NEW CITATION"
                    elif prior.was_cited and not qr.was_cited:
                        qr.delta_vs_previous = "-LOST CITATION"
                    elif not prior.was_mentioned and qr.was_mentioned:
                        qr.delta_vs_previous = "+NEW MENTION"
                    elif prior.was_mentioned and not qr.was_mentioned:
                        qr.delta_vs_previous = "-LOST MENTION"
                    else:
                        qr.delta_vs_previous = "UNCHANGED"
                else:
                    qr.delta_vs_previous = "BASELINE"
        else:
            for qr in query_results:
                qr.delta_vs_previous = "BASELINE"

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO geo_snapshots (
                    id, domain, brand_name, industry, timestamp,
                    overall_score, delta_score, total_queries,
                    engines_measured_count, engine_scores_json, critical_blindspots_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    clean_domain,
                    brand_name,
                    industry,
                    ts,
                    overall_score,
                    delta_score,
                    len(query_results),
                    engines_measured_count,
                    json.dumps(engine_scores),
                    json.dumps(critical_blindspots)
                )
            )

            for qr in query_results:
                conn.execute(
                    """
                    INSERT INTO geo_query_results (
                        snapshot_id, query_id, buyer_query, commercial_intent,
                        engine_id, engine_name, raw_response_text,
                        was_mentioned, mention_position, was_cited,
                        cited_urls_json, competitor_cited_instead,
                        extractability_health, delta_vs_previous
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot_id,
                        qr.query_id,
                        qr.buyer_query,
                        qr.commercial_intent,
                        qr.engine_id,
                        qr.engine_name,
                        qr.raw_response_text,
                        qr.was_mentioned,
                        qr.mention_position,
                        qr.was_cited,
                        json.dumps(qr.cited_urls),
                        qr.competitor_cited_instead,
                        qr.extractability_health,
                        qr.delta_vs_previous
                    )
                )
            conn.commit()

        return GeoSnapshotDetail(
            snapshot_id=snapshot_id,
            domain=clean_domain,
            brand_name=brand_name,
            industry=industry,
            timestamp=ts,
            overall_score=overall_score,
            delta_score=delta_score,
            total_queries=len(query_results),
            engines_measured_count=engines_measured_count,
            engine_scores=engine_scores,
            critical_blindspots=critical_blindspots,
            query_results=query_results
        )

    def get_domain_history(self, domain: str, limit: int = 30) -> List[GeoSnapshotSummary]:
        """Returns chronological time-series list of snapshots for trend charting."""
        clean_domain = domain.lower().replace("https://", "").replace("http://", "").split("/")[0]
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM geo_snapshots
                WHERE domain = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (clean_domain, limit)
            ).fetchall()
            rows = list(reversed(rows))

            return [
                GeoSnapshotSummary(
                    snapshot_id=r["id"],
                    domain=r["domain"],
                    brand_name=r["brand_name"],
                    industry=r["industry"],
                    timestamp=r["timestamp"],
                    overall_score=r["overall_score"],
                    delta_score=r["delta_score"],
                    total_queries=r["total_queries"],
                    engines_measured_count=r["engines_measured_count"],
                    engine_scores=json.loads(r["engine_scores_json"] or "{}"),
                    critical_blindspots=json.loads(r["critical_blindspots_json"] or "[]"),
                )
                for r in rows
            ]

    def get_snapshot_detail(self, snapshot_id: str) -> Optional[GeoSnapshotDetail]:
        """Returns full snapshot details including all raw model outputs."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM geo_snapshots WHERE id = ?", (snapshot_id,)
            ).fetchone()
            if not row:
                return None

            q_rows = conn.execute(
                "SELECT * FROM geo_query_results WHERE snapshot_id = ? ORDER BY id ASC",
                (snapshot_id,)
            ).fetchall()

            results = [
                GeoQueryRecord(
                    query_id=qr["query_id"],
                    buyer_query=qr["buyer_query"],
                    commercial_intent=qr["commercial_intent"],
                    engine_id=qr["engine_id"],
                    engine_name=qr["engine_name"],
                    raw_response_text=qr["raw_response_text"],
                    was_mentioned=bool(qr["was_mentioned"]),
                    mention_position=qr["mention_position"],
                    was_cited=bool(qr["was_cited"]),
                    cited_urls=json.loads(qr["cited_urls_json"] or "[]"),
                    competitor_cited_instead=qr["competitor_cited_instead"],
                    extractability_health=qr["extractability_health"],
                    delta_vs_previous=qr["delta_vs_previous"],
                )
                for qr in q_rows
            ]

            return GeoSnapshotDetail(
                snapshot_id=row["id"],
                domain=row["domain"],
                brand_name=row["brand_name"],
                industry=row["industry"],
                timestamp=row["timestamp"],
                overall_score=row["overall_score"],
                delta_score=row["delta_score"],
                total_queries=row["total_queries"],
                engines_measured_count=row["engines_measured_count"],
                engine_scores=json.loads(row["engine_scores_json"] or "{}"),
                critical_blindspots=json.loads(row["critical_blindspots_json"] or "[]"),
                query_results=results
            )

    def list_tracked_domains(self) -> List[Dict[str, Any]]:
        """Lists all distinct tracked domains with snapshot count and latest score."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT
                    domain,
                    brand_name,
                    industry,
                    COUNT(id) as snapshot_count,
                    MAX(timestamp) as last_run,
                    (SELECT overall_score FROM geo_snapshots s2 WHERE s2.domain = s1.domain ORDER BY s2.timestamp DESC LIMIT 1) as latest_score,
                    (SELECT delta_score FROM geo_snapshots s3 WHERE s3.domain = s1.domain ORDER BY s3.timestamp DESC LIMIT 1) as latest_delta
                FROM geo_snapshots s1
                GROUP BY domain
                ORDER BY last_run DESC
            """).fetchall()

            return [
                {
                    "domain": r["domain"],
                    "brand_name": r["brand_name"],
                    "industry": r["industry"],
                    "snapshot_count": r["snapshot_count"],
                    "last_run": r["last_run"],
                    "latest_score": r["latest_score"],
                    "latest_delta": r["latest_delta"],
                }
                for r in rows
            ]


geo_pipeline_store = GeoPipelineStore()
