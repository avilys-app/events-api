"""Configuration behavior that changes database connectivity."""

from app.core.config import Settings


def test_supabase_pooler_is_detected() -> None:
    settings = Settings(
        jwt_secret="test-secret",
        db_host="aws-1-eu-north-1.pooler.supabase.com",
    )

    assert settings.uses_supabase_pooler is True


def test_direct_postgres_is_not_treated_as_a_pooler() -> None:
    settings = Settings(jwt_secret="test-secret", db_host="localhost")

    assert settings.uses_supabase_pooler is False
