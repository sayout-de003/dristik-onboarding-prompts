"""Tenant-scoped persistent monthly website intelligence."""
from __future__ import annotations
import json, logging, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from app.core.config import settings

logger = logging.getLogger("dristik.continuous_intelligence")
PAID_PLAN_LIMITS = {"starter":3,"professional":10,"diagnostic":15,"business":35,"growth":50,"enterprise":100,"monitoring-growth":50,"monitoring-agency":100,"monitoring-enterprise":200}
PILLARS = ["seo", "geo", "aeo", "cro"]
def _now(): return datetime.now(timezone.utc).isoformat()
def _month(): return datetime.now(timezone.utc).strftime("%Y-%m")
def _normalise_url(raw: str) -> str:
    value=(raw or "").strip()
    if not value: raise ValueError("website_url is required")
    if not value.startswith(("https://","http://")): value="https://"+value
    parsed=urlparse(value)
    if parsed.scheme not in {"http","https"} or not parsed.hostname or "." not in parsed.hostname: raise ValueError("Provide a valid website URL")
    if parsed.username or parsed.password: raise ValueError("Website URLs must not contain embedded credentials")
    return value.rstrip("/")

class ContinuousIntelligenceStore:
    def __init__(self,path:Optional[str]=None):
        self.path=path or settings.AUTH_DATABASE_PATH
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        self.ensure_schema()
    def _connect(self):
        c=sqlite3.connect(self.path,timeout=20); c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON"); c.execute("PRAGMA busy_timeout=20000"); return c
    def ensure_schema(self):
        with self._connect() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS continuous_website_profiles(
              profile_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, website_url TEXT NOT NULL, domain TEXT NOT NULL,
              niche TEXT NOT NULL DEFAULT '', business_model TEXT NOT NULL DEFAULT '', target_audience TEXT NOT NULL DEFAULT '',
              audience_pain_points_json TEXT NOT NULL DEFAULT '[]', target_markets_json TEXT NOT NULL DEFAULT '[]',
              languages_json TEXT NOT NULL DEFAULT '[]', competitors_json TEXT NOT NULL DEFAULT '[]', goals_json TEXT NOT NULL DEFAULT '[]',
              max_pages INTEGER NOT NULL DEFAULT 10, schedule_enabled INTEGER NOT NULL DEFAULT 1,
              last_scheduled_month TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(org_id,domain));
            CREATE TABLE IF NOT EXISTS continuous_audit_runs(
              run_id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, org_id TEXT NOT NULL, domain TEXT NOT NULL,
              scheduled_month TEXT NOT NULL, trigger_type TEXT NOT NULL, status TEXT NOT NULL, analysis_id TEXT,
              started_at TEXT NOT NULL, completed_at TEXT, error_code TEXT, error_message TEXT,
              result_json TEXT NOT NULL DEFAULT '{}', FOREIGN KEY(profile_id) REFERENCES continuous_website_profiles(profile_id));
            CREATE INDEX IF NOT EXISTS idx_continuous_profiles_due ON continuous_website_profiles(schedule_enabled,last_scheduled_month);
            CREATE INDEX IF NOT EXISTS idx_continuous_runs_org ON continuous_audit_runs(org_id,started_at);
            """)
            c.commit()
    def _decode(self,row):
        if not row:return None
        d=dict(row)
        for k in ("audience_pain_points","target_markets","languages","competitors","goals"): d[k]=json.loads(d.pop(k+"_json") or "[]")
        d["schedule_enabled"]=bool(d["schedule_enabled"]); return d
    def upsert_profile(self,org_id:str,data:Dict[str,Any],max_pages:int):
        url=_normalise_url(data["website_url"]); domain=(urlparse(url).hostname or "").lower().removeprefix("www."); now=_now()
        arrays={k:json.dumps(data.get(k) or []) for k in ("audience_pain_points","target_markets","languages","competitors","goals")}
        with self._connect() as c:
            old=c.execute("SELECT profile_id,created_at FROM continuous_website_profiles WHERE org_id=? AND domain=?",(org_id,domain)).fetchone()
            pid=old["profile_id"] if old else "wip_"+uuid.uuid4().hex; created=old["created_at"] if old else now
            c.execute("""INSERT INTO continuous_website_profiles(profile_id,org_id,website_url,domain,niche,business_model,target_audience,
              audience_pain_points_json,target_markets_json,languages_json,competitors_json,goals_json,max_pages,schedule_enabled,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(org_id,domain) DO UPDATE SET website_url=excluded.website_url,niche=excluded.niche,business_model=excluded.business_model,
              target_audience=excluded.target_audience,audience_pain_points_json=excluded.audience_pain_points_json,
              target_markets_json=excluded.target_markets_json,languages_json=excluded.languages_json,competitors_json=excluded.competitors_json,
              goals_json=excluded.goals_json,max_pages=excluded.max_pages,schedule_enabled=excluded.schedule_enabled,updated_at=excluded.updated_at""",
              (pid,org_id,url,domain,str(data.get("niche") or "")[:300],str(data.get("business_model") or "")[:300],
               str(data.get("target_audience") or "")[:2000],arrays["audience_pain_points"],arrays["target_markets"],arrays["languages"],
               arrays["competitors"],arrays["goals"],max_pages,int(bool(data.get("schedule_enabled",True))),created,now)); c.commit()
        return self.get_profile(org_id,pid)
    def get_profile(self,org_id,pid):
        with self._connect() as c:r=c.execute("SELECT * FROM continuous_website_profiles WHERE org_id=? AND profile_id=?",(org_id,pid)).fetchone()
        return self._decode(r)
    def list_profiles(self,org_id):
        with self._connect() as c:rows=c.execute("SELECT * FROM continuous_website_profiles WHERE org_id=? ORDER BY updated_at DESC",(org_id,)).fetchall()
        return [self._decode(r) for r in rows]
    def due_profiles(self,month):
        with self._connect() as c: rows=c.execute("""SELECT p.* FROM continuous_website_profiles p JOIN organizations o ON o.org_id=p.org_id
          WHERE p.schedule_enabled=1 AND (p.last_scheduled_month IS NULL OR p.last_scheduled_month<>?) AND o.is_active=1
          AND lower(o.plan) IN ('starter','professional','diagnostic','business','growth','enterprise','monitoring-growth','monitoring-agency','monitoring-enterprise')
          ORDER BY p.created_at""",(month,)).fetchall()
        return [self._decode(r) for r in rows]
    def create_run(self,profile,trigger,month):
        rid="cir_"+uuid.uuid4().hex
        with self._connect() as c:
            if trigger=="monthly":
                existing=c.execute("SELECT run_id FROM continuous_audit_runs WHERE profile_id=? AND scheduled_month=? AND trigger_type='monthly' AND status IN ('QUEUED','RUNNING','COMPLETED')",(profile["profile_id"],month)).fetchone()
                if existing:return None
            c.execute("INSERT INTO continuous_audit_runs(run_id,profile_id,org_id,domain,scheduled_month,trigger_type,status,started_at) VALUES(?,?,?,?,?,?,'QUEUED',?)",
              (rid,profile["profile_id"],profile["org_id"],profile["domain"],month,trigger,_now()))
            if trigger=="monthly":c.execute("UPDATE continuous_website_profiles SET last_scheduled_month=?,updated_at=? WHERE profile_id=?",(month,_now(),profile["profile_id"]))
            c.commit()
        return rid
    def update_run(self,rid,**fields):
        allowed={"status","analysis_id","completed_at","error_code","error_message","result_json"}; fields={k:v for k,v in fields.items() if k in allowed}
        if not fields:return
        with self._connect() as c:c.execute("UPDATE continuous_audit_runs SET "+", ".join(k+"=?" for k in fields)+" WHERE run_id=?",(*fields.values(),rid));c.commit()
    def list_runs(self,org_id,limit=20):
        with self._connect() as c:rows=c.execute("SELECT * FROM continuous_audit_runs WHERE org_id=? ORDER BY started_at DESC LIMIT ?",(org_id,max(1,min(limit,100)))).fetchall()
        result=[]
        for r in rows:
            d=dict(r); d["result"]=json.loads(d.pop("result_json") or "{}"); result.append(d)
        return result
    def update_schedule(self,org_id,pid,enabled):
        with self._connect() as c:cur=c.execute("UPDATE continuous_website_profiles SET schedule_enabled=?,updated_at=? WHERE org_id=? AND profile_id=?",(int(enabled),_now(),org_id,pid));c.commit()
        return self.get_profile(org_id,pid) if cur.rowcount else None

store=ContinuousIntelligenceStore()
def _paid_page_limit(org_id):
    from app.identity.store import get_store
    org=get_store().get_organization(org_id)
    if not org:raise PermissionError("Organization not found.")
    d=dict(org)
    if not d.get("is_active",1):raise PermissionError("Organization is inactive.")
    plan=str(d.get("plan") or "free_scan").lower()
    if plan not in PAID_PLAN_LIMITS:raise PermissionError("Continuous intelligence requires an eligible paid organization plan.")
    return PAID_PLAN_LIMITS[plan]
def entitlement_for_org(org_id):
    try:return {"eligible":True,"max_pages":_paid_page_limit(org_id),"source":"active organization plan"}
    except PermissionError as e:return {"eligible":False,"max_pages":1,"reason":str(e)}

async def execute_continuous_run(profile,run_id,trigger_type):
    from app.identity.store import get_store
    from app.orchestration.orchestrator import orchestrator
    try:
        limit=min(int(profile.get("max_pages") or 10),_paid_page_limit(profile["org_id"]))
        store.update_run(run_id,status="RUNNING")
        run=orchestrator.create_run(profile["website_url"],org_id=profile["org_id"],created_by=None,target_pillars=PILLARS)
        get_store().record_audit(analysis_id=run.analysis_id,org_id=profile["org_id"],user_id=None,website_url=profile["website_url"],
          status=run.status.value if hasattr(run.status,"value") else str(run.status),page_count=limit)
        store.update_run(run_id,analysis_id=run.analysis_id)
        await orchestrator.execute_analysis_pipeline(run.analysis_id,profile["website_url"],limit,profile.get("niche") or None,
          "Business model: "+profile.get("business_model","")+"; Target audience: "+profile.get("target_audience",""),
          (profile.get("target_markets") or [None])[0],(profile.get("languages") or ["en"])[0],PILLARS)
        completed=orchestrator.runs.get(run.analysis_id); report=getattr(completed,"report",None) if completed else None
        if report is None:
            result={"analysis_id":run.analysis_id,"status":"DATA_UNAVAILABLE","pillars_requested":PILLARS,"trend_status":"UNAVAILABLE","message":"Pipeline produced no report; metrics were not fabricated."}
            store.update_run(run_id,status="DATA_UNAVAILABLE",completed_at=_now(),result_json=json.dumps(result));return result
        payload=report.model_dump(mode="json") if hasattr(report,"model_dump") else (report if isinstance(report,dict) else {"summary":str(report)})
        findings=payload.get("findings") or payload.get("issues") or []
        result={"analysis_id":run.analysis_id,"status":"COMPLETED","pillars_requested":PILLARS,
          "findings_count":len(findings) if isinstance(findings,list) else None,"report_available":True,"trend_status":"UNAVAILABLE",
          "trend_note":"Live keyword-trend data is not inferred from an audit. Connect a supported trend/search-data provider for measured trend comparisons.",
          "profile_context_used":{"niche":profile.get("niche") or None,"business_model":profile.get("business_model") or None,
          "target_audience":profile.get("target_audience") or None,"target_markets":profile.get("target_markets") or [],
          "competitors":profile.get("competitors") or [],"goals":profile.get("goals") or []},
          "report_summary":str(payload.get("executive_summary") or payload.get("summary") or "")[:5000]}
        store.update_run(run_id,status="COMPLETED",completed_at=_now(),result_json=json.dumps(result,ensure_ascii=False));return result
    except Exception as exc:
        logger.exception("Continuous intelligence run failed: %s",run_id)
        store.update_run(run_id,status="FAILED",completed_at=_now(),error_code=type(exc).__name__,error_message=str(exc)[:1000],
          result_json=json.dumps({"status":"FAILED","error_code":type(exc).__name__,"message":"Audit failed; see run error details."}))
        return {"status":"FAILED","error_code":type(exc).__name__}
async def process_due_monthly_runs():
    month=_month();due=store.due_profiles(month);outcomes=[]
    for profile in due:
        rid=store.create_run(profile,"monthly",month)
        if rid:outcomes.append(await execute_continuous_run(profile,rid,"monthly"))
    return {"month":month,"profiles_due":len(due),"runs_started":len(outcomes),"outcomes":outcomes}
