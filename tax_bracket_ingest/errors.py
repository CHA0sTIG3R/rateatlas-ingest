# tax_bracket_ingest/errors.py


class FreshnessSignalError(RuntimeError):
    """Raised when the IRS page's last-reviewed-or-updated date cannot be determined.

    Ingestion must stop before any backend, S3, or database mutation when this
    is raised — a missing or malformed signal is not the same as "unchanged".
    """
