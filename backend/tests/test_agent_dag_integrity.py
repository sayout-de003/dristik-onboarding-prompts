from types import SimpleNamespace

import pytest

from app.orchestration.agent_pool import topological_waves
from app.orchestration.runtime.registry import SPECIALIST_AGENTS_V3


def test_registered_agent_dag_has_no_missing_dependencies_or_cycles():
    waves = topological_waves(SPECIALIST_AGENTS_V3)
    positions = {agent_id: wave_index for wave_index, wave in enumerate(waves) for agent_id in wave}
    assert set(positions) == set(SPECIALIST_AGENTS_V3)
    for agent_id, definition in SPECIALIST_AGENTS_V3.items():
        for dependency in definition.dependencies or []:
            assert positions[dependency] < positions[agent_id]


def test_unknown_dependency_fails_closed():
    definitions = {
        "agent.a": SimpleNamespace(dependencies=["agent.missing"]),
    }
    with pytest.raises(ValueError, match="not registered"):
        topological_waves(definitions)


def test_dependency_cycle_fails_closed_instead_of_running_last_wave():
    definitions = {
        "agent.a": SimpleNamespace(dependencies=["agent.b"]),
        "agent.b": SimpleNamespace(dependencies=["agent.a"]),
    }
    with pytest.raises(ValueError, match="dependency cycle"):
        topological_waves(definitions)
