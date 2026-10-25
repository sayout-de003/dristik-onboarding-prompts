import pytest
from pydantic import ValidationError

from app.core.config import Settings, validate_production_configuration


SECURE_PRODUCTION = {
    "ENVIRONMENT": "production",
    "DEBUG": False,
    "AUTH_SECRET": "r" * 64,
    "SYSTEM_ADMIN_PASSWORD": "a-unique-long-production-admin-password",
    "FRONTEND_URL": "https://dristik.ai",
    "SSRF_PROTECTION_ENABLED": True,
    "ALLOW_PAYMENT_TEST_MOCKS": False,
    "PRODUCTION_DATA_INTEGRITY_MODE": True,
}


def test_valid_production_configuration_passes():
    validate_production_configuration(Settings(**SECURE_PRODUCTION))


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"DEBUG": True}, "DEBUG=True"),
        ({"AUTH_SECRET": "dristik-dev-secret-change-me"}, "weak AUTH_SECRET"),
        ({"FRONTEND_URL": "http://dristik.ai"}, "must use HTTPS"),
        ({"SSRF_PROTECTION_ENABLED": False}, "SSRF_PROTECTION_ENABLED"),
        ({"ALLOW_PAYMENT_TEST_MOCKS": True}, "ALLOW_PAYMENT_TEST_MOCKS"),
        ({"PRODUCTION_DATA_INTEGRITY_MODE": False}, "PRODUCTION_DATA_INTEGRITY_MODE"),
    ],
)
def test_unsafe_production_configuration_fails_closed(override, message):
    config = {**SECURE_PRODUCTION, **override}
    with pytest.raises(RuntimeError, match=message):
        validate_production_configuration(Settings(**config))


def test_crawl_concurrency_has_a_hard_upper_bound():
    with pytest.raises(ValidationError):
        Settings(CRAWL_CONCURRENCY=21)
