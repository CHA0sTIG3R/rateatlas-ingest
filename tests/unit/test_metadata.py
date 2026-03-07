# tests/unit/test_metadata.py
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from tax_bracket_ingest.db.metadata import get_last_seen_date, update_ingest_metadata


@pytest.fixture(autouse=True)
def db_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")


@pytest.fixture
def mock_connect(monkeypatch):
    mock_cur = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    monkeypatch.setattr("tax_bracket_ingest.db.metadata.psycopg.connect", lambda url: mock_conn)
    return mock_conn, mock_cur


class TestGetLastSeenDate:
    def test_returns_date_when_row_exists(self, mock_connect):
        _, mock_cur = mock_connect
        expected = date(2024, 1, 15)
        mock_cur.fetchone.return_value = (expected,)

        assert get_last_seen_date() == expected

    def test_returns_none_when_table_empty(self, mock_connect):
        _, mock_cur = mock_connect
        mock_cur.fetchone.return_value = None

        assert get_last_seen_date() is None

    def test_raises_when_database_url_missing(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL")

        with pytest.raises(KeyError):
            get_last_seen_date()

    def test_queries_most_recent_row(self, mock_connect):
        _, mock_cur = mock_connect
        mock_cur.fetchone.return_value = (date(2024, 1, 15),)

        get_last_seen_date()

        sql = mock_cur.execute.call_args[0][0]
        assert "ORDER BY last_ingested_at DESC" in sql
        assert "LIMIT 1" in sql


class TestUpdateIngestMetadata:
    def test_executes_upsert_with_correct_params(self, mock_connect):
        _, mock_cur = mock_connect
        last_seen = date(2024, 1, 15)

        update_ingest_metadata(last_seen, "FRESH")

        mock_cur.execute.assert_called_once()
        _, params = mock_cur.execute.call_args[0]
        assert params[0] == last_seen
        assert isinstance(params[1], datetime) and params[1].tzinfo is not None
        assert params[2] == "FRESH"

    def test_commits_transaction(self, mock_connect):
        mock_conn, _ = mock_connect

        update_ingest_metadata(date(2024, 1, 15), "STALE")

        mock_conn.commit.assert_called_once()

    def test_stale_freshness_state(self, mock_connect):
        _, mock_cur = mock_connect

        update_ingest_metadata(date(2024, 1, 15), "STALE")

        _, params = mock_cur.execute.call_args[0]
        assert params[2] == "STALE"

    def test_raises_when_database_url_missing(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL")

        with pytest.raises(KeyError):
            update_ingest_metadata(date(2024, 1, 15), "FRESH")
