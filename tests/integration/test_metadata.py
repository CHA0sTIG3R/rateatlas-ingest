# tests/integration/test_metadata.py
import os
from datetime import date, datetime, timezone

import pytest

from tax_bracket_ingest.db.metadata import get_last_seen_date, update_ingest_metadata

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db_conn():
    """
    Yields a real psycopg connection and creates/tears down the ingest_metadata table.
    Skips the entire module if DATABASE_URL is not set.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set — skipping DB integration tests")

    import psycopg

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ingest_metadata (
                    id                      SERIAL PRIMARY KEY,
                    last_seen_page_update   DATE NOT NULL,
                    last_ingested_at        TIMESTAMPTZ NOT NULL,
                    freshness_state         VARCHAR(10) NOT NULL
                        CHECK (freshness_state IN ('FRESH', 'STALE'))
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

    def test_returns_most_recent_date(self, db_conn):
        older = date(2023, 1, 1)
        newer = date(2024, 6, 15)

        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ingest_metadata (id, last_seen_page_update, last_ingested_at, freshness_state) VALUES (%s, %s, %s, %s)",
                (1, older, datetime(2023, 1, 1, tzinfo=timezone.utc), "STALE"),
            )
            cur.execute(
                "INSERT INTO ingest_metadata (id, last_seen_page_update, last_ingested_at, freshness_state) VALUES (%s, %s, %s, %s)",
                (2, newer, datetime(2024, 6, 15, tzinfo=timezone.utc), "FRESH"),
            )
        db_conn.commit()

        assert get_last_seen_date() == newer


class TestUpdateIngestMetadata:
    def test_inserts_row_on_first_call(self, db_conn):
        update_ingest_metadata(date(2024, 1, 15), "FRESH")

        with db_conn.cursor() as cur:
            cur.execute("SELECT last_seen_page_update, freshness_state FROM ingest_metadata WHERE id = 1")
            row = cur.fetchone()

        assert row is not None
        assert row[0] == date(2024, 1, 15)
        assert row[1] == "FRESH"

    def test_upserts_on_second_call(self, db_conn):
        update_ingest_metadata(date(2024, 1, 15), "FRESH")
        update_ingest_metadata(date(2025, 3, 1), "STALE")

        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*), last_seen_page_update, freshness_state FROM ingest_metadata GROUP BY last_seen_page_update, freshness_state")
            rows = cur.fetchall()

        assert len(rows) == 1
        assert rows[0][1] == date(2025, 3, 1)
        assert rows[0][2] == "STALE"

    def test_last_ingested_at_is_timezone_aware(self, db_conn):
        update_ingest_metadata(date(2024, 1, 15), "FRESH")

        with db_conn.cursor() as cur:
            cur.execute("SELECT last_ingested_at FROM ingest_metadata WHERE id = 1")
            row = cur.fetchone()

        assert row[0].tzinfo is not None

    def test_roundtrip_with_get_last_seen_date(self):
        expected = date(2025, 6, 1)
        update_ingest_metadata(expected, "FRESH")

        assert get_last_seen_date() == expected
