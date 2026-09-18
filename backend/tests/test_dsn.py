"""DATABASE_URL parsing — the failure mode that broke the first Render deploy."""

from __future__ import annotations

import pytest

from app.utils.dsn import parse_database_url

_POOLER = "postgresql://postgres.abcdefgh:secret@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"


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
