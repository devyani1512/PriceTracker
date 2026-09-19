"""DATABASE_URL parsing — the failure mode that broke the first Render deploy."""

from __future__ import annotations

import pytest

from app.utils.dsn import is_pooler_host, parse_database_url

_POOLER = "postgresql://postgres.abcdefgh:secret@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
_TRANSACTION = "postgresql://postgres.abcdefgh:secret@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
_DIRECT = "postgresql://postgres.abcdefgh:secret@db.abcdefgh.supabase.co:5432/postgres"


def test_parses_normal_url():
    cfg = parse_database_url(_POOLER)
    assert cfg["NAME"] == "postgres"
    assert cfg["USER"] == "postgres.abcdefgh"
    assert cfg["PASSWORD"] == "secret"
    assert cfg["HOST"] == "aws-0-ap-southeast-1.pooler.supabase.com"
    assert cfg["PORT"] == "5432"


def test_normalises_postgres_scheme():
    cfg = parse_database_url("postgres://u:p@localhost:5432/db")
    assert cfg["HOST"] == "localhost"
    assert cfg["NAME"] == "db"


def test_strips_surrounding_quotes():
    cfg = parse_database_url(f'"{_POOLER}"')
    assert cfg["HOST"] == "aws-0-ap-southeast-1.pooler.supabase.com"


def test_percent_encoded_password_is_decoded():
    cfg = parse_database_url("postgresql://u:p%40ss%5Bw%5D@localhost:5432/db")
    assert cfg["PASSWORD"] == "p@ss[w]"


def test_placeholder_raises_actionable_error():
    with pytest.raises(ValueError, match="YOUR-PASSWORD"):
        parse_database_url(
            "postgresql://postgres.abc:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
        )


def test_unencoded_brackets_raise_percent_encoding_hint():
    with pytest.raises(ValueError, match="percent-encoded"):
        parse_database_url("postgresql://u:pa[ss]@localhost:5432/db")


def test_missing_host_raises():
    with pytest.raises(ValueError, match="no host"):
        parse_database_url("postgresql:///justadb")


def test_pooler_disables_persistence_and_prepared_statements():
    cfg = parse_database_url(_TRANSACTION)
    assert cfg["CONN_MAX_AGE"] == 0
    assert cfg["CONN_HEALTH_CHECKS"] is True
    assert cfg["OPTIONS"]["prepare_threshold"] is None


def test_direct_connection_keeps_reuse_and_default_prepares():
    cfg = parse_database_url(_DIRECT)
    assert cfg["CONN_MAX_AGE"] == 60
    assert "prepare_threshold" not in cfg["OPTIONS"]


def test_env_can_override_conn_max_age(monkeypatch):
    monkeypatch.setenv("DB_CONN_MAX_AGE", "15")
    assert parse_database_url(_TRANSACTION)["CONN_MAX_AGE"] == 15
    assert parse_database_url(_DIRECT)["CONN_MAX_AGE"] == 15


def test_is_pooler_host():
    assert is_pooler_host("aws-0-ap-southeast-1.pooler.supabase.com", "5432")
    assert is_pooler_host("localhost", "6543")
    assert not is_pooler_host("db.abcdefgh.supabase.co", "5432")
