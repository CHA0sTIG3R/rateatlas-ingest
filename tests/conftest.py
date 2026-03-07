# tests/conftest.py
import json
from pathlib import Path
from moto import mock_aws
import pytest
import pandas as pd
import boto3

from tax_bracket_ingest import run_ingest
import tax_bracket_ingest.scraper.fetch as fetch_mod

TEST_DATA = Path(__file__).parent / "data"

class DummyResponse:
    def __init__(self, status_code=200, content=b"dummy content", headers=None, json_body=None):
        self.status_code = status_code
        self.content = content
        self._headers = headers or {"Content-Type": "text/plain"}
        self._json_body = json_body

    @property
    def headers(self):
        return self._headers

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def json(self):
        if self._json_body is not None:
            return self._json_body
        return json.loads(self.text)

    def raise_for_status(self):
        # This method is intentionally left empty because DummyResponse always simulates a successful response (status_code 200).
        pass

@pytest.fixture(scope="session")
def test_data_dir():
    """Path to tests/data"""
    return TEST_DATA

@pytest.fixture
def sample_page_html(test_data_dir):
    return (test_data_dir / "sample_page.html").read_bytes()
    
@pytest.fixture
def sample_table_html(sample_page_html):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(sample_page_html.decode('utf-8'), 'html.parser')
    table = soup.find('table')
    return str(table) if table else None

@pytest.fixture
def sample_raw_csv(test_data_dir):
    return pd.read_csv(test_data_dir / "sample_raw.csv")

@pytest.fixture
def sample_normalized_df(test_data_dir):
    return pd.read_csv(test_data_dir / "sample_normalized.csv")

@pytest.fixture
def sample_normalized_csv_bytes(test_data_dir):
    return (test_data_dir / "sample_normalized.csv").read_bytes()

@pytest.fixture(autouse=True)
def stub_out_fetch(monkeypatch, sample_page_html):
    monkeypatch.setattr(fetch_mod, "fetch", lambda url: sample_page_html)
    monkeypatch.setattr(run_ingest, "fetch_irs_data", lambda: sample_page_html)

@pytest.fixture
def moto_s3_client():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        yield s3

@pytest.fixture(autouse=True)
def aws_credentials_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_KEY", "history.csv")
    monkeypatch.setenv("AWS_ACCOUNT_ID", "123456789012")
    monkeypatch.setenv("DRY_RUN", "0")
    monkeypatch.setenv("ENABLE_BACKEND_PUSH", "0")
    yield
    
@pytest.fixture(autouse=True)
def backend_url(monkeypatch):
    """Ensure BACKEND_URL is set for both unit and integration tests."""
    monkeypatch.setenv("BACKEND_URL", "http://fake-backend")
    yield
    
@pytest.fixture
def dummy_response():
    """Returns a dummy response object with a 200 status code."""
    return DummyResponse()
