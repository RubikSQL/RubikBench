"""
RubikBench benchmark setup.

Downloads the RubikBench DuckDB database from HuggingFace.
"""

import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List

import click

# ── Constants ────────────────────────────────────────────────────────────────
DEFAULT_DATA_DIR = Path("./data/RubikBench")
DEFAULT_DB_NAME = "RubikBench.duckdb"
# Canonical queries file in the repository root (version-controlled)
REPO_QUERIES_PATH = Path("./queries/RubikBench.json")

JSON_INDENT = 4
BENCHMARK_NAME = "RubikBench"
DATABASE_NAME = "RubikBench"


# ── Helpers ──────────────────────────────────────────────────────────────────


def _write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=JSON_INDENT)


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


def resolve_db(data_dir: Path, db_name: str) -> Path:
    """Return the path to a database file inside *data_dir*/databases/."""
    return data_dir / "databases" / f"{db_name}.duckdb"


# ── Setup ────────────────────────────────────────────────────────────────────


def setup(data_dir: Path, *, force: bool = False, remove_zip: bool = False) -> None:
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
    databases_dir = data_dir / "databases"
    download_dir = data_dir / "download"
    queries_dir = data_dir / "queries"
    db_path = databases_dir / DEFAULT_DB_NAME
    zip_path = download_dir / f"{DEFAULT_DB_NAME}.zip"

    click.echo("Setting up RubikBench database...")
    click.echo(f"  Data directory: {data_dir}")

    databases_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    queries_dir.mkdir(parents=True, exist_ok=True)

    # ── Download & extract database ──────────────────────────────────────
    if db_path.exists() and not force:
        click.echo(click.style(f"✓ Database already exists at {db_path}", fg="green"))
        click.echo("  Use --force to re-download")
    else:
        # Resume from cached ZIP?
        if zip_path.exists() and not force:
            click.echo(f"  Found existing zip file: {zip_path}")
            if not click.confirm("  Use existing zip file?", default=True):
                force = True

        # Download
        if not zip_path.exists() or force:
            try:
                from huggingface_hub import hf_hub_download
            except ImportError:
                click.echo(click.style("✗ huggingface_hub required. Install with: pip install huggingface_hub", fg="red"))
                raise SystemExit(1)

            click.echo("  Downloading from HuggingFace: Magolor/RubikBench")
            try:
                downloaded = Path(
                    hf_hub_download(
                        repo_id="Magolor/RubikBench",
                        repo_type="dataset",
                        filename=f"{DEFAULT_DB_NAME}.zip",
                        local_dir=str(download_dir),
                    )
                )
                if downloaded != zip_path:
                    downloaded.rename(zip_path)
                click.echo(f"  Downloaded to: {zip_path}")
            except Exception as e:
                click.echo(click.style(f"✗ Download failed: {e}", fg="red"))
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
            zip_path.unlink(missing_ok=True)
            try:
                download_dir.rmdir()
            except OSError:
                pass
            click.echo(f"  Removed zip file: {zip_path}")

    # ── Prepare queries ──────────────────────────────────────────────────
    dest_queries = queries_dir / "RubikBench.json"
    if REPO_QUERIES_PATH.exists():
        with open(REPO_QUERIES_PATH, "r", encoding="utf-8") as f:
            raw_queries = json.load(f)
        enriched = _inject_fields(raw_queries)
        _write_json(dest_queries, enriched)
        click.echo(f"  Wrote {len(enriched)} queries → {dest_queries}")
    elif dest_queries.exists():
        click.echo(f"  Queries already at {dest_queries}")
    else:
        click.echo(click.style(f"✗ Source queries not found: {REPO_QUERIES_PATH}", fg="yellow"))

    # ── Verify ───────────────────────────────────────────────────────────
    try:
        from ahvn.utils.db import Database

        db = Database(provider="duckdb", database=str(db_path))
        tables = db.db_tabs()
        db.close()
        click.echo(click.style("\n✓ RubikBench setup complete!", fg="green", bold=True))
        click.echo(f"  Database: {db_path}")
        click.echo(f"  Tables:   {len(tables)}")
        click.echo(f"  Queries:  {dest_queries}")
    except Exception as e:
        click.echo(click.style(f"\n✗ Verification failed: {e}", fg="red"))
        raise SystemExit(1)
