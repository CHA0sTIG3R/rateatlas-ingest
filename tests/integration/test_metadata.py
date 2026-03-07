# tests/integration/test_metadata.py
import os
from datetime import date, datetime, timezone

import psycopg
import pytest

from tax_bracket_ingest.db.metadata import get_last_seen_date, update_ingest_metadata

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db_conn():
    """
    Yields a real psycopg connection and creates/tears down the ingest_metadata table.
    Skips the entire module if DATABASE_URL is not set or the DB is unreachable.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set — skipping DB integration tests")

    try:
        conn = psycopg.connect(database_url)
    except psycopg.OperationalError as e:
        pytest.skip(f"DB unreachable — skipping DB integration tests: {e}")

    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ingest_metadata (
                    id                    INTEGER PRIMARY KEY DEFAULT 1,
                    last_seen_page_update DATE NOT NULL,
                    last_ingested_at      TIMESTAMPTZ NOT NULL
                )
            """)
        conn.commit()
        yield conn
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS ingest_metadata")
        conn.commit()


@pytest.fixture(autouse=True)
def clean_table(db_conn):
    """Truncate the table before each test for isolation."""
    with db_conn.cursor() as cur:
        cur.execute("TRUNCATE ingest_metadata RESTART IDENTITY")
    db_conn.commit()


class TestGetLastSeenDate:
    def test_returns_none_on_empty_table(self):
        assert get_last_seen_date() is None

    def test_returns_date_when_row_exists(self, db_conn):
        expected = date(2024, 6, 15)

        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingest_metadata (id, last_seen_page_update, last_ingested_at) VALUES (%s, %s, %s)",
                (1, expected, datetime(2024, 6, 15, tzinfo=timezone.utc)),
            )
        db_conn.commit()

        assert get_last_seen_date() == expected


class TestUpdateIngestMetadata:
    def test_inserts_row_on_first_call(self, db_conn):
        update_ingest_metadata(date(2024, 1, 15))

        with db_conn.cursor() as cur:
            cur.execute("SELECT last_seen_page_update FROM ingest_metadata WHERE id = 1")
            row = cur.fetchone()

        assert row is not None
        assert row[0] == date(2024, 1, 15)

    def test_upserts_on_second_call(self, db_conn):
        update_ingest_metadata(date(2024, 1, 15))
        update_ingest_metadata(date(2025, 3, 1))

        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), last_seen_page_update FROM ingest_metadata GROUP BY last_seen_page_update")
            rows = cur.fetchall()

        assert len(rows) == 1
        assert rows[0][1] == date(2025, 3, 1)

    def test_last_ingested_at_is_timezone_aware(self, db_conn):
        update_ingest_metadata(date(2024, 1, 15))

        with db_conn.cursor() as cur:
            cur.execute("SELECT last_ingested_at FROM ingest_metadata WHERE id = 1")
            row = cur.fetchone()

        assert row[0].tzinfo is not None

    def test_roundtrip_with_get_last_seen_date(self):
        expected = date(2025, 6, 1)
        update_ingest_metadata(expected)

        assert get_last_seen_date() == expected
