# tests/unit/test_probe.py
from datetime import date

from tax_bracket_ingest.scraper.probe import check_page_freshness

REVISION_DIV = '<div class="pup-content-revision">Page Last Reviewed or Updated: {text}</div>'


def _page(revision_html: str) -> str:
    return f"<html><body>{revision_html}</body></html>"


def test_returns_date_for_well_formed_revision_marker():
    html = _page(REVISION_DIV.format(text="15-Jun-2024"))

    assert check_page_freshness(html) == date(2024, 6, 15)


def test_returns_none_when_revision_div_is_absent():
    html = "<html><body><p>No revision marker here.</p></body></html>"

    assert check_page_freshness(html) is None


def test_returns_none_when_prefix_text_is_missing():
    html = _page("Last changed: 15-Jun-2024")

    assert check_page_freshness(html) is None


def test_returns_none_when_date_format_is_unrecognized():
    # IRS changing "01-Jan-2024" to an ISO date is exactly the kind of drift
    # that must fail closed rather than silently produce no date.
    html = _page(REVISION_DIV.format(text="2024-06-15"))

    assert check_page_freshness(html) is None


def test_returns_none_when_revision_text_is_empty():
    html = _page(REVISION_DIV.format(text=""))

    assert check_page_freshness(html) is None
