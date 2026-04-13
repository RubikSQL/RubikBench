"""
KaggleDBQA benchmark setup.

Downloads the KaggleDBQA dataset databases from Google Drive and queries
from the GitHub repository, then converts queries into the unified
RubikBench JSON format.

Reference:
    Lee, Chia-Hsuan, Oleksandr Polozov, and Matthew Richardson.
    "KaggleDBQA: Realistic Evaluation of Text-to-SQL Parsers."
    ACL 2021.  https://aclanthology.org/2021.acl-long.176
"""

import shutil
import zipfile
from typing import Dict, Any, List

import click

from ahvn.utils.basic.file_utils import enum_files, exists_dir, exists_file, touch_dir
from ahvn.utils.basic.path_utils import get_file_basename, pj
from ahvn.utils.basic.serialize_utils import load_json, save_json

from ._verify import file_size_matches, verify_checksum

# ── Constants ────────────────────────────────────────────────────────────────
DEFAULT_DATA_DIR = pj("./data", "KaggleDBQA")

GOOGLE_DRIVE_FILE_ID = "1YM3ZK-yyUflnUKWNuduVZxGdwEnQr77c"
ZIP_FILENAME = "KaggleDBQA_databases.zip"

GITHUB_RAW_BASE = "https://raw.githubusercontent.com/Chia-Hsuan-Lee/KaggleDBQA/main"

DATABASE_IDS = [
    "GeoNuclearData",
    "GreaterManchesterCrime",
    "Pesticide",
    "StudentMathScore",
    "TheHistoryofBaseball",
    "USWildFires",
    "WhatCDHipHop",
    "WorldSoccerDataBase",
]

JSON_INDENT = 4
BENCHMARK_NAME = "KaggleDBQA"

# Download checksums (MD5) – set to None to skip verification
EXPECTED_ZIP_MD5 = "020955541d4d3e642704424dfea34a0c"


# ── Query conversion ─────────────────────────────────────────────────────────


def _convert_query(raw: Dict[str, Any], idx: int) -> Dict[str, Any]:
    """Convert a single KaggleDBQA query to the unified format."""
    db_id = raw.get("db_id", "")

    return {
        "benchmark": BENCHMARK_NAME,
        "database": db_id or None,
        "id": f"Q{idx:05d}",
        "question": raw.get("question", ""),
        "context": {
            "query_time": None,
            "user_profile": {
                "occupation": None,
                "caliber": None,
                "currency": None,
                "region": {},
                "department": {},
                "preferences": [],
            },
        },
        "schema": None,
        "dialect": "sqlite",
        "sql": raw.get("query", ""),
        "metadata": {
            "difficulty": "unknown",
            "query_tags": [],
            "order-relevant": None,
            "verified": False,
            "db_id": db_id,
        },
    }


def _write_json(path: str, data: Any) -> None:
    save_json(data, path, indent=JSON_INDENT)


def resolve_db(data_dir: str, db_name: str) -> str:
    """Return the path to a database file inside *data_dir*/databases/."""
    return pj(data_dir, "databases", f"{db_name}.sqlite")


# ── Download & extract databases ─────────────────────────────────────────────


def _download_databases(
    download_dir: str,
    raw_dir: str,
    *,
    force: bool = False,
    remove_zip: bool = False,
) -> None:
    """Download the databases ZIP from Google Drive and extract."""
    marker = pj(raw_dir, "databases")

    if exists_dir(marker) and not force:
        click.echo(click.style(f"✓ Raw database data already present at {raw_dir}", fg="green"))
        click.echo("  Use --force to re-download")
        return

    touch_dir(download_dir)
    touch_dir(raw_dir)

    zip_path = pj(download_dir, ZIP_FILENAME)

    # Download
    if force or not exists_file(zip_path):
        try:
            import gdown
        except ImportError:
            click.echo(click.style("✗ gdown required. Install with: pip install gdown", fg="red"))
            raise SystemExit(1)

        click.echo("  Downloading KaggleDBQA databases from Google Drive...")
        gdown.download(id=GOOGLE_DRIVE_FILE_ID, output=str(zip_path), quiet=False)
    else:
        click.echo(f"  Using cached ZIP: {zip_path}")

    if not verify_checksum(zip_path, EXPECTED_ZIP_MD5, label=ZIP_FILENAME):
        click.echo(click.style("  ✗ ZIP checksum failed. Re-run with --force.", fg="red"))
        raise SystemExit(1)

    # Extract
    click.echo(f"  Extracting to {raw_dir} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(raw_dir)

    click.echo(click.style("  ✓ Extraction complete", fg="green"))

    # Cleanup
    if remove_zip:
        from ahvn.utils.basic.file_utils import delete_file

        delete_file(zip_path)
        click.echo(f"  Removed ZIP: {zip_path}")


# ── Download queries from GitHub ─────────────────────────────────────────────


def _download_queries_from_github(raw_dir: str, *, force: bool = False) -> None:
    """Download example JSON files and tables JSON from the GitHub repo."""
    import urllib.request
    import urllib.error

    examples_dir = pj(raw_dir, "examples")
    touch_dir(examples_dir)

    # Download tables metadata
    tables_path = pj(raw_dir, "KaggleDBQA_tables.json")
    if force or not exists_file(tables_path):
        url = f"{GITHUB_RAW_BASE}/KaggleDBQA_tables.json"
        click.echo("  Downloading table metadata...")
        try:
            urllib.request.urlretrieve(url, str(tables_path))
        except urllib.error.URLError as e:
            click.echo(click.style(f"  ✗ Failed to download {url}: {e}", fg="red"))

    # Download per-database example files (combined + test + fewshot)
    for db_id in DATABASE_IDS:
        for suffix in ("", "_test", "_fewshot"):
            fname = f"{db_id}{suffix}.json"
            dest = pj(examples_dir, fname)
            if exists_file(dest) and not force:
                continue
            url = f"{GITHUB_RAW_BASE}/examples/{fname}"
            try:
                urllib.request.urlretrieve(url, str(dest))
                click.echo(f"  Downloaded: {fname}")
            except urllib.error.URLError as e:
                click.echo(click.style(f"  ✗ Failed: {fname} ({e})", fg="yellow"))

    click.echo(click.style("  ✓ Query download complete", fg="green"))


# ── Copy databases ───────────────────────────────────────────────────────────


def _copy_databases(raw_dir: str, databases_dir: str) -> int:
    """Copy .sqlite files from raw/ to databases/ flat structure.

    The ZIP may contain databases in subdirectories like
    ``databases/DB_NAME/DB_NAME.sqlite`` or just ``databases/DB_NAME.sqlite``.
    We normalise them into a flat ``databases/{DB_NAME}.sqlite`` layout.
    """
    touch_dir(databases_dir)
    count = 0

    # Look for sqlite files recursively in raw_dir
    for sqlite_file in enum_files(raw_dir, ext="sqlite", abs=True):
        db_name = get_file_basename(sqlite_file, ext=False)
        dest = pj(databases_dir, f"{db_name}.sqlite")
        if not exists_file(dest) or not file_size_matches(sqlite_file, dest):
            shutil.copy2(sqlite_file, dest)
        count += 1

    return count


# ── Process queries ──────────────────────────────────────────────────────────


def _process_queries(raw_dir: str, queries_dir: str) -> None:
    """Read raw example queries and write unified JSON files."""
    examples_dir = pj(raw_dir, "examples")
    if not exists_dir(examples_dir):
        raise FileNotFoundError(f"Examples directory not found: {examples_dir}")

    touch_dir(queries_dir)

    all_queries: List[Dict[str, Any]] = []
    global_idx = 1  # Start IDs at Q00001

    for db_id in DATABASE_IDS:
        db_queries: List[Dict[str, Any]] = []

        # Only include test-split queries in the evaluation set.
        # Fewshot queries are kept as separate per-db files for prompting.
        fpath = pj(examples_dir, f"{db_id}_test.json")
        if exists_file(fpath):
            raw_list: List[Dict[str, Any]] = load_json(fpath, strict=True)
            for raw in raw_list:
                q = _convert_query(raw, global_idx)
                q["metadata"]["split"] = "test"
                db_queries.append(q)
                global_idx += 1

        if db_queries:
            # Per-database file (test only)
            p = pj(queries_dir, f"{db_id}.json")
            _write_json(p, db_queries)
            click.echo(f"  Wrote {len(db_queries):>3d} queries → {p}")
            all_queries.extend(db_queries)

        # Also write fewshot queries as a separate file (not included in main eval set)
        fewshot_path = pj(examples_dir, f"{db_id}_fewshot.json")
        if exists_file(fewshot_path):
            fewshot_raw: List[Dict[str, Any]] = load_json(fewshot_path, strict=True)
            fewshot_queries = []
            for raw in fewshot_raw:
                q = _convert_query(raw, 0)  # ID doesn't matter for fewshot
                q["id"] = f"F{len(fewshot_queries) + 1:05d}"
                q["metadata"]["split"] = "fewshot"
                fewshot_queries.append(q)
            if fewshot_queries:
                fp = pj(queries_dir, f"{db_id}_fewshot.json")
                _write_json(fp, fewshot_queries)
                click.echo(f"  Wrote {len(fewshot_queries):>3d} fewshot → {fp}")

    # Combined file
    combined = pj(queries_dir, "KaggleDBQA.json")
    _write_json(combined, all_queries)
    click.echo(f"  Wrote {len(all_queries)} queries → {combined}")


# ── Public entry point ───────────────────────────────────────────────────────


def setup(data_dir: str, *, force: bool = False, remove_zip: bool = False) -> None:
    """
    Download, extract, and prepare KaggleDBQA.

    Directory layout after setup::

        data_dir/
        ├── download/           # ZIP archive (removable)
        ├── raw/                # extracted databases + GitHub JSON files
        │   ├── databases/
        │   ├── examples/
        │   └── KaggleDBQA_tables.json
        ├── databases/          # flat copies of .sqlite files
        │   ├── GeoNuclearData.sqlite
        │   └── ...
        └── queries/            # unified query files
            ├── KaggleDBQA.json
            ├── GeoNuclearData.json
            └── ...

    Args:
        data_dir: Root directory for KaggleDBQA data (e.g. ``./data/KaggleDBQA``).
        force: Re-download / re-process even if files exist.
        remove_zip: Delete the ZIP (and download/) after extraction.
    """
    click.echo("Setting up KaggleDBQA benchmark...")
    click.echo(f"  Data directory: {data_dir}")

    download_dir = pj(data_dir, "download")
    raw_dir = pj(data_dir, "raw")
    databases_dir = pj(data_dir, "databases")
    queries_dir = pj(data_dir, "queries")

    _download_databases(download_dir, raw_dir, force=force, remove_zip=remove_zip)
    _download_queries_from_github(raw_dir, force=force)

    # Copy sqlite files into databases/
    db_count = _copy_databases(raw_dir, databases_dir)
    click.echo(f"  Copied {db_count} databases → {databases_dir}")

    _process_queries(raw_dir, queries_dir)

    click.echo(click.style("\n✓ KaggleDBQA setup complete!", fg="green", bold=True))
    click.echo(f"  Databases: {db_count} SQLite files in {databases_dir}")
    click.echo(f"  Queries:   {queries_dir}")
