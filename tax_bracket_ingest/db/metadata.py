
import os
from datetime import date, datetime, timezone
from typing import Optional

import psycopg


def get_last_seen_date() -> Optional[date]:
    """
    Get the most recent last_seen_page_update from the ingest_metadata table.

    Connects using the DATABASE_URL environment variable.

    Returns:
        date: The last seen page update date, or None if the table is empty.
    """
    database_url = os.environ["DATABASE_URL"]
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_seen_page_update FROM ingest_metadata"
            )
            row = cur.fetchone()
    return row[0] if row else None

def update_ingest_metadata(last_seen_date: Optional[date]) -> None:
    """
    Update the ingest_metadata table with the provided last_seen_date and the current timestamp.

    Connects using the DATABASE_URL environment variable.

    Args:
        last_seen_date (date): The date to set as the last seen page update.
        freshness_state (str): The freshness state of the data.
    """
    database_url = os.environ["DATABASE_URL"]
    
    last_ingested_at = datetime.now(timezone.utc)
    
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO ingest_metadata (id, last_seen_page_update, last_ingested_at, ingest_run_count, ingest_skip_count) 
                VALUES (1, %s, %s, 1, 0)
                ON CONFLICT (id) DO UPDATE SET 
                    last_seen_page_update = EXCLUDED.last_seen_page_update,
                    last_ingested_at = EXCLUDED.last_ingested_at,
                    ingest_run_count = EXCLUDED.ingest_run_count + ingest_metadata.ingest_run_count,
                    ingest_skip_count = EXCLUDED.ingest_skip_count + ingest_metadata.ingest_skip_count""",
                (last_seen_date, last_ingested_at)
            )
            conn.commit()

def update_skip_count() -> None:
    """
    Increment the ingest_skip_count in the ingest_metadata table by 1.

    Connects using the DATABASE_URL environment variable.
    """
    database_url = os.environ["DATABASE_URL"]
    
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE ingest_metadata 
                SET ingest_skip_count = ingest_skip_count + 1
                WHERE id = 1"""
            )
            conn.commit()