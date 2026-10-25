"""Smoke tests for the real application import graph.

Compilation alone does not execute imports and therefore cannot detect stale
package paths left behind by module moves.
"""
import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "app.crawl.crawler",
        "app.orchestration.agent_pool",
        "app.orchestration.team_orchestrator",
        "app.orchestration.orchestrator",
        "app.api.routes.audits.analyses",
    ],
)
def test_critical_audit_runtime_modules_import(module_name):
    importlib.import_module(module_name)
