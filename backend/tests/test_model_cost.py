"""Cost follows the provider and model that ran, or the rate the operator set."""
from app.inference.pricing import (
    extract_anthropic_cost,
    extract_gemini_cost,
    extract_groq_cost,
    extract_openai_cost,
    extract_openrouter_cost,
    extract_provider_cost,
    extract_together_cost,
    parse_operator_rates,
    price_call,
    provider_billed_usd,
)
from app.inference.telemetry import TelemetryTracker


def test_list_price_uses_the_model_that_ran():
    haiku = price_call(
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        input_tokens=1_000_000,
        output_tokens=200_000,
    )
    groq = price_call(
        provider="groq",
        model="openai/gpt-oss-20b",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert haiku.basis == "list_price"
    assert haiku.cost_usd == 2.0  # $1 input + $5 * 0.2 output
    assert haiku.is_actual is False
    assert groq.basis == "list_price"
    assert groq.cost_usd == 0.375  # $0.075 + $0.30
    assert groq.is_actual is False


def _clear_rates(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.LLM_MODEL_PRICES", None)
    monkeypatch.setattr("app.core.config.settings.LLM_COST_INPUT_PER_MILLION", None)
    monkeypatch.setattr("app.core.config.settings.LLM_COST_OUTPUT_PER_MILLION", None)


def test_reasoning_flag_does_not_reprice_another_model(monkeypatch):
    _clear_rates(monkeypatch)
    tracker = TelemetryTracker()
    tracker.record_call(
        input_tokens=1_000_000,
        output_tokens=0,
        latency_ms=10,
        capability="synthesizer",
        is_reasoning=True,
        model="claude-haiku-4-5-20251001",
        provider="anthropic",
    )
    data = tracker.get_data()
    assert data.estimated_cost_usd == 1.0
    assert data.cost_basis == "list_price"
    assert data.cost_complete is True
    assert data.models_used == ["anthropic/claude-haiku-4-5-20251001"]
    assert data.agent_calls[0].cost_usd == 1.0


def test_unknown_model_is_unpriced(monkeypatch):
    _clear_rates(monkeypatch)
    tracker = TelemetryTracker()
    tracker.record_call(
        input_tokens=500,
        output_tokens=100,
        latency_ms=4,
        capability="business_icp",
        model="some-new-model",
        provider="openrouter",
    )
    data = tracker.get_data()
    assert data.estimated_cost_usd == 0.0
    assert data.cost_complete is False
    assert data.unpriced_calls == 1
    assert data.cost_basis == "unpriced"
    assert data.agent_calls[0].cost_usd is None


def test_openrouter_gpt4o_is_not_priced_as_openai():
    quote = price_call(
        provider="openrouter",
        model="openai/gpt-4o",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert quote.basis == "unpriced"
    assert quote.cost_usd is None
    assert quote.is_actual is False


def test_provider_bill_wins_over_list_and_operator_rates():
    rates = parse_operator_rates(
        '{"anthropic/claude-haiku-4-5-20251001": {"input": 9, "output": 9}}'
    )
    quote = price_call(
        provider="anthropic",
        model="claude-haiku-4-5-20251001",
        input_tokens=1_000_000,
        output_tokens=0,
        provider_cost_usd=0.0042,
        operator_rates=rates,
        blanket_input_per_million=3,
        blanket_output_per_million=15,
    )
    assert quote.basis == "provider_billed"
    assert quote.cost_usd == 0.0042
    assert quote.is_actual is True


def test_operator_model_rate_overrides_list_price():
    rates = parse_operator_rates(
        '{"groq/openai/gpt-oss-120b": {"input": 0.2, "output": 0.8}}'
    )
    quote = price_call(
        provider="groq",
        model="openai/gpt-oss-120b",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        operator_rates=rates,
        blanket_input_per_million=9,
        blanket_output_per_million=9,
    )
    assert quote.basis == "operator_rate"
    assert quote.cost_usd == 1.0
    assert quote.is_actual is False


def test_blanket_rate_prices_whatever_model_ran():
    quote = price_call(
        provider="moonshot",
        model="moonshot-v1-8k",
        input_tokens=2_000_000,
        output_tokens=500_000,
        blanket_input_per_million=0.5,
        blanket_output_per_million=2.0,
    )
    assert quote.basis == "operator_rate"
    assert quote.cost_usd == 2.0
    assert quote.is_actual is False


def test_tracker_sums_each_models_own_price(monkeypatch):
    _clear_rates(monkeypatch)
    tracker = TelemetryTracker()
    tracker.record_call(1_000_000, 0, 1, "a", model="claude-haiku-4-5-20251001", provider="claude")
    tracker.record_call(1_000_000, 1_000_000, 1, "b", model="openai/gpt-oss-20b", provider="groq", provider_cost_usd=0.01)
    data = tracker.get_data()
    assert data.agent_calls[0].provider == "anthropic"
    assert data.agent_calls[0].cost_basis == "list_price"
    assert data.agent_calls[0].is_actual is False
    assert data.agent_calls[0].actual_cost_usd is None
    assert data.agent_calls[0].calculated_cost_usd == 1.0
    assert data.agent_calls[1].cost_basis == "provider_billed"
    assert data.agent_calls[1].is_actual is True
    assert data.agent_calls[1].actual_cost_usd == 0.01
    assert data.agent_calls[1].calculated_cost_usd is None
    assert data.estimated_cost_usd == 1.01
    assert data.actual_cost_usd == 0.01
    assert data.calculated_cost_usd == 1.0
    assert data.has_actual_costs is True
    assert data.all_costs_actual is False
    assert data.cost_basis == "mixed"
    assert data.cost_complete is True
    assert data.models_used == [
        "anthropic/claude-haiku-4-5-20251001",
        "groq/openai/gpt-oss-20b",
    ]


def test_known_plus_unknown_keeps_the_known_dollars(monkeypatch):
    _clear_rates(monkeypatch)
    tracker = TelemetryTracker()
    tracker.record_call(1_000_000, 0, 1, "a", model="gemini-2.0-flash", provider="google")
    tracker.record_call(100, 100, 1, "b", model="qwen/qwen3.6-27b", provider="groq")
    data = tracker.get_data()
    assert data.agent_calls[0].provider == "gemini"
    assert data.agent_calls[0].cost_usd == 0.1
    assert data.agent_calls[0].is_actual is False
    assert data.agent_calls[1].is_actual is False
    assert data.estimated_cost_usd == 0.1
    assert data.actual_cost_usd == 0.0
    assert data.calculated_cost_usd == 0.1
    assert data.has_actual_costs is False
    assert data.all_costs_actual is False
    assert data.unpriced_calls == 1
    assert data.cost_complete is False
    assert data.cost_basis == "mixed"


def test_tracker_uses_the_rate_you_configured(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.LLM_MODEL_PRICES", None)
    monkeypatch.setattr("app.core.config.settings.LLM_COST_INPUT_PER_MILLION", 1.0)
    monkeypatch.setattr("app.core.config.settings.LLM_COST_OUTPUT_PER_MILLION", 2.0)
    tracker = TelemetryTracker()
    tracker.record_call(1_000_000, 1_000_000, 1, "a", model="any-model", provider="custom")
    data = tracker.get_data()
    assert data.estimated_cost_usd == 3.0
    assert data.cost_basis == "operator_rate"
    assert data.agent_calls[0].is_actual is False
    assert data.cost_complete is True
    assert data.models_used == ["custom/any-model"]


def test_provider_billed_usd_reads_openrouter_usage():
    assert provider_billed_usd({"cost": 0.0125, "prompt_tokens": 10}) == 0.0125
    assert provider_billed_usd({"cost_details": {"upstream_inference_cost": 0.2}}) == 0.2
    assert provider_billed_usd({"prompt_tokens": 10}) is None
    assert provider_billed_usd({"cost": -1}) is None


def test_operator_prices_accept_nested_and_pipe_keys():
    rates = parse_operator_rates(
        '{"anthropic": {"claude-sonnet-4-6": {"input": 3, "output": 15}},'
        '"xai|grok-2-latest": {"input": 2, "output": 10}}'
    )
    sonnet = price_call(
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=0,
        operator_rates=rates,
    )
    grok = price_call(
        provider="xai",
        model="grok-2-latest",
        input_tokens=0,
        output_tokens=1_000_000,
        operator_rates=rates,
    )
    assert sonnet.cost_usd == 3.0
    assert sonnet.is_actual is False
    assert grok.cost_usd == 10.0
    assert grok.is_actual is False


def test_price_quote_is_actual_distinction():
    # provider_billed -> True
    billed = price_call(
        provider="openrouter",
        model="deepseek/deepseek-r1",
        input_tokens=1000,
        output_tokens=100,
        provider_cost_usd=0.0035,
    )
    assert billed.basis == "provider_billed"
    assert billed.is_actual is True
    assert billed.cost_usd == 0.0035

    # operator_rate -> False
    configured = price_call(
        provider="groq",
        model="custom-groq",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        blanket_input_per_million=1.0,
        blanket_output_per_million=2.0,
    )
    assert configured.basis == "operator_rate"
    assert configured.is_actual is False

    # list_price -> False
    listed = price_call(
        provider="anthropic",
        model="claude-3-5-sonnet",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert listed.basis == "list_price"
    assert listed.is_actual is False

    # unpriced -> False
    unpriced = price_call(
        provider="groq",
        model="completely-unrecognized-model",
        input_tokens=1000,
        output_tokens=1000,
    )
    assert unpriced.basis == "unpriced"
    assert unpriced.is_actual is False
    assert unpriced.cost_usd is None


def test_provider_cost_extractors():
    # OpenRouter
    assert extract_openrouter_cost({"usage": {"cost": 0.005}}) == 0.005
    assert extract_openrouter_cost({"usage": {"cost_details": {"upstream_inference_cost": 0.015}}}) == 0.015
    assert extract_openrouter_cost({"usage": {"prompt_tokens": 500}}) is None
    assert extract_openrouter_cost(None) is None

    # Providers returning usage tokens but no in-band dollar cost
    assert extract_openai_cost({"usage": {"prompt_tokens": 100, "completion_tokens": 50}}) is None
    assert extract_anthropic_cost({"usage": {"input_tokens": 100, "output_tokens": 50}}) is None
    assert extract_groq_cost({"usage": {"prompt_tokens": 100, "completion_tokens": 50}}) is None
    assert extract_gemini_cost({"usage": {"prompt_tokens": 100, "completion_tokens": 50}}) is None
    assert extract_together_cost({"usage": {"prompt_tokens": 100, "completion_tokens": 50}}) is None

    # Dispatcher
    assert extract_provider_cost("openrouter", {"usage": {"cost": 0.0025}}) == 0.0025
    assert extract_provider_cost("groq", {"usage": {"prompt_tokens": 100, "cost": 99.9}}) is None
    assert extract_provider_cost("anthropic", {"usage": {"input_tokens": 100}}) is None
    assert extract_provider_cost("openai", {"usage": {"prompt_tokens": 100}}) is None
    assert extract_provider_cost("gemini", {"usage": {"prompt_tokens": 100}}) is None
    assert extract_provider_cost("together", {"usage": {"prompt_tokens": 100}}) is None


def test_telemetry_live_summary_actual_split(monkeypatch):
    _clear_rates(monkeypatch)
    tracker = TelemetryTracker()
    tracker.record_call(
        input_tokens=1000,
        output_tokens=500,
        latency_ms=120,
        capability="synthesizer",
        model="deepseek/deepseek-r1",
        provider="openrouter",
        provider_cost_usd=0.014827,
    )
    summary = tracker.get_live_summary()
    assert summary["actual_cost_usd"] == 0.014827
    assert summary["calculated_cost_usd"] == 0.0
    assert summary["total_cost_usd"] == 0.014827
    assert summary["has_actual_costs"] is True
    assert summary["all_costs_actual"] is True


def test_stage_cost_tracking_accumulates_per_stage(monkeypatch):
    _clear_rates(monkeypatch)
    tracker = TelemetryTracker()
    
    # Stage 1: Crawl & Ingest
    tracker.set_active_stage("crawl_and_ingest", "Crawl & Ingestion")
    tracker.record_call(1_000_000, 0, 10, "crawl_summarizer", model="gemini-2.0-flash", provider="google")
    assert tracker.get_current_stage_cost() == 0.1
    
    # Stage 2: Specialist Execution
    tracker.set_active_stage("specialist_execution", "105-Agent Specialist DAG")
    tracker.record_call(1_000_000, 0, 15, "seo_specialist", model="claude-haiku-4-5-20251001", provider="anthropic")
    tracker.record_call(500, 200, 20, "geo_specialist", model="meta-llama/llama-3.3-70b-instruct", provider="openrouter", provider_cost_usd=0.0035)
    
    data = tracker.get_data()
    assert len(data.stage_costs) == 2
    assert "crawl_and_ingest" in data.stage_costs
    assert "specialist_execution" in data.stage_costs
    
    crawl_stage = data.stage_costs["crawl_and_ingest"]
    assert crawl_stage.calls_count == 1
    assert crawl_stage.input_tokens == 1_000_000
    assert crawl_stage.cost_usd == 0.1
    assert crawl_stage.models == ["gemini/gemini-2.0-flash"]
    
    spec_stage = data.stage_costs["specialist_execution"]
    assert spec_stage.calls_count == 2
    assert spec_stage.cost_usd == round(1.0 + 0.0035, 6)
    
    live_summary = tracker.get_live_summary()
    assert live_summary["active_stage"] == "specialist_execution"
    assert live_summary["active_stage_cost_usd"] == spec_stage.cost_usd
    assert live_summary["total_cost_usd"] == data.estimated_cost_usd
    assert len(live_summary["stage_costs"]) == 2

