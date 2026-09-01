"""Configuration behavior that changes database connectivity."""

from app.core.config import Settings
from app.core.database import supabase_pooler_connect_args


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
