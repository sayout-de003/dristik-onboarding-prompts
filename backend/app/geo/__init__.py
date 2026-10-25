"""
GEO domain package exports.

Exports are loaded lazily so importing a focused GEO submodule (for example,
the readiness scorer or benchmark metrics) does not eagerly import every agent,
report renderer, provider adapter and presentation dependency. This also reduces
circular-import risk and makes focused unit tests substantially lighter.
"""
from __future__ import annotations

from importlib import import_module
from typing import Dict, Tuple

_EXPORTS: Dict[str, Tuple[str, str]] = {
    "GeoPillar": ("app.geo.pillar", "GeoPillar"),
    "GEO_SPECIALISTS": ("app.geo.pillar", "GEO_SPECIALISTS"),
    "build_geo_agents": ("app.geo.pillar", "build_geo_agents"),
    "citation_catalog": ("app.geo.citation_models", "citation_catalog"),
    "active_engine_names": ("app.geo.citation_models", "active_engine_names"),
    "unqueried_surfaces": ("app.geo.citation_models", "unqueried_surfaces"),
    "GeoReadinessAgent": ("app.geo.agents", "GeoReadinessAgent"),
    "AiSearchCitationAgent": ("app.geo.agents", "AiSearchCitationAgent"),
    "PerEngineEvaluatorAgent": ("app.geo.agents", "PerEngineEvaluatorAgent"),
    "InformationGainAgent": ("app.geo.agents", "InformationGainAgent"),
    "geo_pipeline_runner": ("app.geo.pipeline_runner", "geo_pipeline_runner"),
    "FIXED_PROMPT_SET": ("app.geo.pipeline_runner", "FIXED_PROMPT_SET"),
    "geo_pipeline_store": ("app.geo.pipeline_store", "geo_pipeline_store"),
    "GeoSnapshotSummary": ("app.geo.pipeline_store", "GeoSnapshotSummary"),
    "GeoSnapshotDetail": ("app.geo.pipeline_store", "GeoSnapshotDetail"),
    "geo_citation_gap_engine": ("app.geo.citation_gap", "geo_citation_gap_engine"),
    "CausalCitationGapReport": ("app.geo.citation_gap", "CausalCitationGapReport"),
    "benchmark_generator": ("app.geo.benchmark_generator", "benchmark_generator"),
    "BenchmarkSuite": ("app.geo.benchmark_generator", "BenchmarkSuite"),
    "benchmark_runner": ("app.geo.benchmark_runner", "benchmark_runner"),
    "ShareOfModelMetric": ("app.geo.benchmark_runner", "ShareOfModelMetric"),
    "EvaluatedQueryRun": ("app.geo.benchmark_runner", "EvaluatedQueryRun"),
    "crawler_log_analyzer": ("app.geo.crawler_logs", "crawler_log_analyzer"),
    "CrawlerLogAnalysis": ("app.geo.crawler_logs", "CrawlerLogAnalysis"),
    "geo_sentiment_engine": ("app.geo.sentiment_engine", "geo_sentiment_engine"),
    "HallucinationAuditReport": ("app.geo.sentiment_engine", "HallucinationAuditReport"),
    "CompleteGeoReportGenerator": ("app.geo.reporting.geo_report_generator", "CompleteGeoReportGenerator"),
    "render_geo_audit_book": ("app.geo.reporting.geo_audit_book", "render_geo_audit_book"),
    "geo_cover_figure": ("app.geo.reporting.geo_audit_book", "geo_cover_figure"),
    "calculate_geo_readiness": ("app.geo.scoring", "calculate_geo_readiness"),
    "GeoMetricsCalculator": ("app.geo.scoring", "GeoMetricsCalculator"),
    "DynamicQuestionSandboxEngine": ("app.geo.dynamic_sandbox", "DynamicQuestionSandboxEngine"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Load a public GEO export only when a caller requests it."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
