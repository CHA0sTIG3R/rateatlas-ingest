# tax_bracket_ingest/run_ingest.py
from dotenv import load_dotenv
from typing import Optional
from dataclasses import dataclass
from functools import lru_cache

from tax_bracket_ingest.logging_config import setup_logging

load_dotenv()
setup_logging()

import logging
logger = logging.getLogger(__name__)

import os
from io import BytesIO

import boto3
import pandas as pd
import requests

from tax_bracket_ingest.scraper.fetch import fetch_irs_data
from tax_bracket_ingest.parser.parser import parse_irs_data, parse_irs_data_to_dataframe
from tax_bracket_ingest.parser.normalize import process_irs_dataframe


TRUTHY_ENV_VALUES = {"1", "true", "t", "yes", "y", "on"}


@dataclass(frozen=True)
class IngestConfig:
    s3_bucket: str
    s3_key: str


@lru_cache(maxsize=1)
def get_ingest_config() -> IngestConfig:
    bucket = os.getenv("S3_BUCKET")
    key = os.getenv("S3_KEY")
    missing = [name for name, value in (("S3_BUCKET", bucket), ("S3_KEY", key)) if not value]
    if missing:
        logger.error(
            "missing_env_vars",
            extra={
                "action": "Required S3 configuration missing",
                "missing": missing,
            },
        )
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    config = IngestConfig(s3_bucket=bucket, s3_key=key) # type: ignore
    logger.debug(
        "ingest_config_loaded",
        extra={
            "s3_bucket": config.s3_bucket,
            "s3_key": config.s3_key,
            "action": "Loaded ingest configuration from environment",
        },
    )
    return config


def get_env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in TRUTHY_ENV_VALUES

def is_dry_run() -> bool:
    return get_env_flag("DRY_RUN", default=True)

def should_push_backend() -> bool:
    return get_env_flag("ENABLE_BACKEND_PUSH", default=False)

    
def read_csv_from_s3(key: str, config: Optional[IngestConfig] = None) -> pd.DataFrame:
    if config is None:
        config = get_ingest_config()
    s3 = boto3.client("s3")
    logger.debug(
        "fetch_s3_object",
        extra={
            "s3_bucket": config.s3_bucket,
            "s3_key": key,
            "action": "Fetching CSV from S3",
        },
    )
    resp = s3.get_object(Bucket=config.s3_bucket, Key=key)
    return pd.read_csv(BytesIO(resp["Body"].read()))

def write_df_to_s3(df: pd.DataFrame, key: str, dry_run: Optional[bool] = None, config: Optional[IngestConfig] = None):
    if config is None:
        config = get_ingest_config()
    if dry_run is None:
        dry_run = is_dry_run()
    if dry_run:
        logger.info(
            "dry_run_skip_write_s3",
            extra={
                "rows": len(df),
                "s3_key": key,
                "action": "Skipped writing historical CSV to S3 in dry-run mode",
            },
        )
        return
    s3 = boto3.client("s3")
    buf = BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    s3.put_object(Bucket=config.s3_bucket, Key=key, Body=buf.getvalue())
    
def push_csv_to_backend(df: pd.DataFrame, dry_run: Optional[bool] = None):
    if dry_run is None:
        dry_run = is_dry_run()
    if dry_run:
        logger.info(
            "dry_run_skip_backend_push",
            extra={
                "rows": len(df),
                "action": "Skipped pushing current tax data to backend in dry-run mode",
            },
        )
        return "dry_run_skipped"
    csv_bytes = df.to_csv(index=False).encode('utf-8')
    backend_url = os.getenv("BACKEND_URL")
    if not backend_url:
        logger.warning(
            "backend_url_missing",
            extra={
                "rows": len(df),
                "action": "Skipped pushing current tax data because BACKEND_URL is unset",
            },
        )
        return "skipped_no_backend_url"
    url = backend_url + "/api/v1/tax/upload"
    headers = {
        "Content-Type": "text/csv", 
        "X-API-KEY": os.getenv("INGEST_API_KEY")
    }
    try:
        resp = requests.post(
            url,
            headers=headers,
            data=csv_bytes,
            timeout=30
        )
    except requests.RequestException:
        logger.exception(
            "backend_push_failed",
            extra={
                "rows": len(df),
                "backend_url": url,
                "action": "Failed to push current tax data to backend",
            },
        )
        return "failed_backend_push"
    content_type = resp.headers.get("Content-Type", "")
    response_text = resp.text
    log_extra = {
        "rows": len(df),
        "backend_url": url,
        "status_code": resp.status_code,
    }
    payload = None
    if "json" in content_type.lower():
        try:
            payload = resp.json()
        except ValueError:
            log_extra["response_text"] = response_text[:2048]
            logger.warning("backend_push_invalid_json", extra=log_extra)
        else:
            log_extra["response_json"] = payload
    else:
        log_extra["response_text"] = response_text[:2048]
    if not resp.ok:
        logger.error("backend_push_non_2xx", extra=log_extra)
        return "failed_backend_push"
    if isinstance(payload, dict):
        errors = payload.get("errors") or payload.get("error")
        if errors:
            log_extra["errors"] = errors
            logger.error("backend_push_error_payload", extra=log_extra)
            return "failed_backend_payload_errors"
    logger.info("backend_push_response", extra=log_extra)
    return response_text
    
    
def main():
    dry_run = is_dry_run()
    logger.info(
        "dry_run_configured",
        extra={
            "dry_run": dry_run,
            "action": "Resolved dry run setting from environment",
        },
    )

    config = get_ingest_config()

    if dry_run:
        logger.info(
            "dry_run_mode",
            extra={"action": "Running ingest process in dry-run mode"},
        )
    html = fetch_irs_data()
    
    raw_struct = parse_irs_data(html.decode('utf-8'))
    raw_df = parse_irs_data_to_dataframe(raw_struct)
    curr_df = process_irs_dataframe(raw_df)
    
    if dry_run:
        hist_df = curr_df
        logger.info(
            "dry_run_skip_history_fetch",
            extra={
                "rows": len(curr_df),
                "action": "Skipped fetching historical CSV from S3 in dry-run mode",
            },
        )
    else:
        prev_hist = read_csv_from_s3(config.s3_key, config=config)
        
        latest_year = prev_hist["Year"].max()
        recent_year_rows = prev_hist[prev_hist["Year"] == latest_year]

        # Compare and append only if new
        if not curr_df.equals(recent_year_rows):
            hist_df = pd.concat([curr_df, prev_hist], ignore_index=True)
            logger.info("append_new_data", extra={
                "year": latest_year,
                "rows_added": len(curr_df),
                "action": "Appending new data to historical CSV"
            })
        else:
            hist_df = prev_hist
            logger.info("skipping_append", extra={
                "year": latest_year,
                "rows": len(curr_df),
                "action": "No new data to append, skipping"
            })
    
    # Push to backend when enabled
    if should_push_backend():
        resp = push_csv_to_backend(curr_df, dry_run=dry_run)
        if not dry_run:
            logger.info("pushed_to_backend",  extra={
                "rows": len(curr_df),
                "response": resp,
                "action": "Pushed current tax data to backend"
            })
    else:
        logger.info(
            "backend_push_disabled",
            extra={
                "rows": len(curr_df),
                "action": "Backend push skipped because ENABLE_BACKEND_PUSH=0",
            },
        )
    
    # update S3
    write_df_to_s3(hist_df, config.s3_key, dry_run=dry_run, config=config)
    if not dry_run:
        logger.info("updated_s3",  extra={
            "s3_bucket": config.s3_bucket,
            "s3_key": config.s3_key,
            "rows": len(hist_df),
            "action": "Updated historical CSV in S3"
        })
    
    logger.info("ingest_complete", extra={"action": "Ingest process completed successfully"})

if __name__ == "__main__":
    logger.info("starting_ingest",  extra={"action": "Starting ingest process"})
    try:
        main()
    except Exception as e:
        logger.error("ingest_error", error=str(e), extra={"action": "Error during ingest process"}) # type: ignore
        raise
    finally:
        logger.info("ingest_finished", extra={"action": "Ingest process finished"})
