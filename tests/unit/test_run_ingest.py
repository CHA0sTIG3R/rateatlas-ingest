# tests/unit/test_run_ingest.py
from datetime import date
from unittest.mock import MagicMock

import pytest

import tax_bracket_ingest.run_ingest as ri
from tax_bracket_ingest.errors import FreshnessSignalError


@pytest.fixture
def main_deps(monkeypatch):
    """Isolate main()'s side-effecting collaborators so the three freshness
    paths (malformed signal / unchanged page / changed page) can be asserted
    deterministically, without touching S3, the backend, or a real DB.
    """
    monkeypatch.setattr(ri, "fetch_irs_data", lambda: b"<html></html>")
    monkeypatch.setattr(ri, "is_dry_run", lambda: True)
    monkeypatch.setattr(ri, "get_ingest_config", lambda: ri.IngestConfig(s3_bucket="bucket", s3_key="key"))
    monkeypatch.setattr(ri, "parse_irs_data", lambda html: {})
    monkeypatch.setattr(ri, "parse_irs_data_to_dataframe", lambda struct: MagicMock(name="raw_df"))
    monkeypatch.setattr(ri, "process_irs_dataframe", lambda df: MagicMock(name="curr_df"))

    deps = {
        "get_last_seen_date": MagicMock(name="get_last_seen_date"),
        "update_ingest_metadata": MagicMock(name="update_ingest_metadata"),
        "update_skip_count": MagicMock(name="update_skip_count"),
        "write_df_to_s3": MagicMock(name="write_df_to_s3"),
        "push_backend": MagicMock(name="_push_backend_if_enabled"),
    }
    monkeypatch.setattr(ri, "get_last_seen_date", deps["get_last_seen_date"])
    monkeypatch.setattr(ri, "update_ingest_metadata", deps["update_ingest_metadata"])
    monkeypatch.setattr(ri, "update_skip_count", deps["update_skip_count"])
    monkeypatch.setattr(ri, "write_df_to_s3", deps["write_df_to_s3"])
    monkeypatch.setattr(ri, "_push_backend_if_enabled", deps["push_backend"])
    return deps


def _assert_no_mutation(deps):
    deps["write_df_to_s3"].assert_not_called()
    deps["push_backend"].assert_not_called()
    deps["update_ingest_metadata"].assert_not_called()
    deps["update_skip_count"].assert_not_called()


class TestMainFreshnessContract:
    def test_malformed_or_missing_signal_fails_closed_before_any_mutation(self, main_deps, monkeypatch):
        monkeypatch.setattr(ri, "check_page_freshness", lambda html: None)

        with pytest.raises(FreshnessSignalError):
            ri.main()

        main_deps["get_last_seen_date"].assert_not_called()
        _assert_no_mutation(main_deps)

    def test_unchanged_page_skips_processing(self, main_deps, monkeypatch):
        seen = date(2024, 1, 15)
        monkeypatch.setattr(ri, "check_page_freshness", lambda html: seen)
        main_deps["get_last_seen_date"].return_value = seen

        ri.main()

        main_deps["update_skip_count"].assert_called_once()
        main_deps["write_df_to_s3"].assert_not_called()
        main_deps["push_backend"].assert_not_called()
        main_deps["update_ingest_metadata"].assert_not_called()

    def test_changed_page_processes_and_records_new_metadata(self, main_deps, monkeypatch):
        new_date = date(2025, 1, 15)
        monkeypatch.setattr(ri, "check_page_freshness", lambda html: new_date)
        main_deps["get_last_seen_date"].return_value = date(2024, 1, 15)

        ri.main()

        main_deps["write_df_to_s3"].assert_called_once()
        main_deps["push_backend"].assert_called_once()
        main_deps["update_ingest_metadata"].assert_called_once_with(new_date)
        main_deps["update_skip_count"].assert_not_called()
