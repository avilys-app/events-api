"""Environment configuration and database connectivity settings."""

import pytest
from app.core.config import Settings
from app.core.database import supabase_pooler_connect_args
from pydantic import ValidationError


def test_supabase_pooler_is_detected() -> None:
    settings = Settings(
        jwt_secret="test-secret",
        db_host="aws-1-eu-north-1.pooler.supabase.com",
    )

    assert settings.uses_supabase_pooler is True


def test_direct_postgres_is_not_treated_as_a_pooler() -> None:
    settings = Settings(jwt_secret="test-secret", db_host="localhost")

    assert settings.uses_supabase_pooler is False


def test_supabase_pooler_disables_asyncpg_statement_caches() -> None:
    connect_args = supabase_pooler_connect_args()

    assert connect_args["statement_cache_size"] == 0
    assert connect_args["prepared_statement_cache_size"] == 0

    statement_name = connect_args["prepared_statement_name_func"]
    assert statement_name() != statement_name()


def test_long_event_threshold_defaults_to_six_months(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LONG_EVENT_THRESHOLD_MONTHS", raising=False)
    assert Settings(_env_file=None, jwt_secret="test-secret").long_event_threshold_months == 6


def test_long_event_threshold_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LONG_EVENT_THRESHOLD_MONTHS", "3")
    assert Settings(_env_file=None, jwt_secret="test-secret").long_event_threshold_months == 3


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "invalid"])
def test_long_event_threshold_requires_positive_integer(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("LONG_EVENT_THRESHOLD_MONTHS", value)
    with pytest.raises(ValidationError, match="long_event_threshold_months"):
        Settings(_env_file=None, jwt_secret="test-secret")
