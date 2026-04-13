"""
RubikBench benchmark setup.

Downloads the RubikBench DuckDB database and its lightweight query metadata.
"""

import shutil
import zipfile
from typing import Any, Dict, List

import click

from ahvn.utils.basic.file_utils import delete_dir, delete_file, exists_file, touch_dir
from ahvn.utils.basic.path_utils import pj
from ahvn.utils.basic.serialize_utils import load_json, save_json

from ._verify import verify_checksum

# ── Constants ────────────────────────────────────────────────────────────────
DEFAULT_DATA_DIR = pj("./data", "RubikBench")
DEFAULT_DB_NAME = "RubikBench.duckdb"
# Canonical queries file in the repository root (version-controlled)
REPO_QUERIES_PATH = pj("./queries", "RubikBench.json")
HF_DATASET_ID = "Magolor/RubikBench"
HF_QUERIES_PATH = pj("queries", "RubikBench.json")
HF_QUERY_TAGS_PATH = pj("queries", "query_tags.yaml")

JSON_INDENT = 4
BENCHMARK_NAME = "RubikBench"
DATABASE_NAME = "RubikBench"

# ── Expected checksums (MD5) ────────────────────────────────────────────────
# Set to None to skip verification.  Update after each data release.
EXPECTED_ZIP_MD5 = None  # TODO: compute after next HF upload
EXPECTED_QUERIES_MD5 = "ada81fc524667aa4567a660fc918bba5"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_json(path: str, data: Any) -> None:
    save_json(data, path, indent=JSON_INDENT)


def _inject_fields(queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prepend ``benchmark`` and ``database`` keys to every query."""
    out: List[Dict[str, Any]] = []
    for q in queries:
        new_q: Dict[str, Any] = {
            "benchmark": BENCHMARK_NAME,
            "database": DATABASE_NAME,
        }
        new_q.update(q)
        out.append(new_q)
    return out


def resolve_db(data_dir: str, db_name: str) -> str:
    """Return the path to a database file inside *data_dir*/databases/."""
    return pj(data_dir, "databases", f"{db_name}.duckdb")


def _download_hf_file(data_dir: str, filename: str, *, force: bool = False) -> str:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        click.echo(click.style("✗ huggingface_hub required. Install with: pip install huggingface_hub", fg="red"))
        raise SystemExit(1)

    return hf_hub_download(
        repo_id=HF_DATASET_ID,
        repo_type="dataset",
        filename=filename,
        local_dir=data_dir,
        force_download=force,
    )


def _prepare_queries(data_dir: str, *, force: bool = False) -> str:
    queries_dir = pj(data_dir, "queries")
    dest_queries = pj(queries_dir, "RubikBench.json")

    if exists_file(REPO_QUERIES_PATH):
        raw_queries = load_json(REPO_QUERIES_PATH, strict=True)
        source = REPO_QUERIES_PATH
    else:
        if force or not exists_file(dest_queries):
            click.echo("  Downloading query metadata from HuggingFace...")
            source = _download_hf_file(data_dir, HF_QUERIES_PATH, force=force)
            try:
                _download_hf_file(data_dir, HF_QUERY_TAGS_PATH, force=force)
            except Exception as e:
                click.echo(click.style(f"  ! Failed to download query_tags.yaml: {e}", fg="yellow"))
        else:
            source = dest_queries
        raw_queries = load_json(dest_queries, strict=True)

    if not isinstance(raw_queries, list):
        raise TypeError(f"Expected a query list in {source}, got {type(raw_queries).__name__}.")

    if raw_queries and raw_queries[0].get("benchmark") and raw_queries[0].get("database"):
        enriched = raw_queries
    else:
        enriched = _inject_fields(raw_queries)

    _write_json(dest_queries, enriched)
    click.echo(f"  Wrote {len(enriched)} queries → {dest_queries}")

    # Verify queries integrity when the expected checksum matches the enriched
    # version (i.e. queries already had benchmark/database fields).
    if raw_queries is enriched:
        verify_checksum(dest_queries, EXPECTED_QUERIES_MD5, label="RubikBench.json")

    return dest_queries


# ── Setup ────────────────────────────────────────────────────────────────────


def setup(data_dir: str, *, force: bool = False, remove_zip: bool = False) -> None:
    """
    Download and extract the RubikBench DuckDB database.

    Directory layout after setup::

        data_dir/
        ├── download/                 # ZIP archive (removable)
        ├── databases/
        │   └── RubikBench.duckdb
        └── queries/
            └── RubikBench.json       # with benchmark / database fields

    Args:
        data_dir: Directory to store the data (e.g. ``./data/RubikBench``).
        force: Re-download even if the database already exists.
        remove_zip: Delete the ZIP archive after extraction.
    """
    databases_dir = pj(data_dir, "databases")
    download_dir = pj(data_dir, "download")
    db_path = pj(databases_dir, DEFAULT_DB_NAME)
    zip_path = pj(download_dir, f"{DEFAULT_DB_NAME}.zip")

    click.echo("Setting up RubikBench database...")
    click.echo(f"  Data directory: {data_dir}")

    touch_dir(databases_dir)
    touch_dir(download_dir)
    touch_dir(pj(data_dir, "queries"))

    # ── Download & extract database ──────────────────────────────────────
    if exists_file(db_path) and not force:
        click.echo(click.style(f"✓ Database already exists at {db_path}", fg="green"))
        click.echo("  Use --force to re-download")
    else:
        # Resume from cached ZIP?
        if exists_file(zip_path) and not force:
            click.echo(f"  Found existing zip file: {zip_path}")
            if not click.confirm("  Use existing zip file?", default=True):
                force = True

        # Download
        if force or not exists_file(zip_path):
            click.echo("  Downloading from HuggingFace: Magolor/RubikBench")
            try:
                downloaded = _download_hf_file(download_dir, f"{DEFAULT_DB_NAME}.zip", force=force)
                if downloaded != zip_path:
                    shutil.move(downloaded, zip_path)
                click.echo(f"  Downloaded to: {zip_path}")
            except Exception as e:
                click.echo(click.style(f"✗ Download failed: {e}", fg="red"))
                raise SystemExit(1)

        # Verify download integrity
        if not verify_checksum(zip_path, EXPECTED_ZIP_MD5, label=f"{DEFAULT_DB_NAME}.zip"):
            click.echo(click.style("  ✗ ZIP checksum verification failed. Re-run with --force.", fg="red"))
            raise SystemExit(1)

        # Extract into databases/
        click.echo(f"  Extracting: {zip_path}")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(databases_dir)
            click.echo(click.style("  ✓ Extraction complete", fg="green"))
        except Exception as e:
            click.echo(click.style(f"✗ Extraction failed: {e}", fg="red"))
            raise SystemExit(1)

        # Cleanup
        if remove_zip:
            delete_file(zip_path)
            delete_dir(download_dir)
            click.echo(f"  Removed zip file: {zip_path}")

    # ── Prepare queries ──────────────────────────────────────────────────
    dest_queries = _prepare_queries(data_dir, force=force)

    # ── Verify ───────────────────────────────────────────────────────────
    try:
        from ahvn.utils.db import Database

        db = Database(provider="duckdb", database=db_path)
        tables = db.db_tabs()
        db.close()
        click.echo(click.style("\n✓ RubikBench setup complete!", fg="green", bold=True))
        click.echo(f"  Database: {db_path}")
        click.echo(f"  Tables:   {len(tables)}")
        click.echo(f"  Queries:  {dest_queries}")
    except Exception as e:
        click.echo(click.style(f"\n✗ Verification failed: {e}", fg="red"))
        raise SystemExit(1)
