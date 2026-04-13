"""BirdSQL (MINIDEV) benchmark setup."""

import shutil
import zipfile
from typing import Dict, Any, List

import click

from ahvn.utils.basic.file_utils import exists_dir, exists_file, list_dirs, touch_dir
from ahvn.utils.basic.path_utils import get_file_basename, pj
from ahvn.utils.basic.serialize_utils import load_json, save_json

from ._verify import file_size_matches, verify_checksum

DEFAULT_DATA_DIR = pj("./data", "BirdSQL")

GOOGLE_DRIVE_FILE_ID = "13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG"
ZIP_FILENAME = "minidev_0703.zip"
ZIP_INNER_PREFIX = "minidev/MINIDEV/"

CORRECTIONS_DRIVE_ID = "1iWlYVknwK5wGli5lnwg4stvNzMogjhwj"
CORRECTIONS_FILENAME = "bird_minidev_corrections.json"

RAW_QUERIES_FILE = "mini_dev_sqlite.json"
RAW_DATABASES_DIR = "dev_databases"
BENCHMARK_NAME = "BirdSQL"

# ── Expected checksums (MD5) ────────────────────────────────────────────────
EXPECTED_ZIP_MD5 = "d229472fcd8115c6408f88eb29ff95c9"
EXPECTED_CORRECTIONS_MD5 = "ed4a8ef44ecdb749a9f29c0861268d66"


def _convert_query(raw: Dict[str, Any], idx: int) -> Dict[str, Any]:
    evidence = (raw.get("evidence") or "").strip()
    db_id = raw.get("db_id", "")
    qid = raw.get("question_id", idx)
    try:
        qid_num = int(qid)
    except (ValueError, TypeError):
        qid_num = idx
    return {
        "benchmark": BENCHMARK_NAME,
        "database": db_id or None,
        "id": f"Q{qid_num:05d}",
        "question": raw.get("question", ""),
        "context": {
            "query_time": None,
            "user_profile": {
                "occupation": None,
                "caliber": None,
                "currency": None,
                "region": {},
                "department": {},
                "preferences": [evidence] if evidence else [],
            },
        },
        "schema": None,
        "dialect": "sqlite",
        "sql": raw.get("SQL", ""),
        "metadata": {
            "difficulty": (raw.get("difficulty") or "unknown").lower(),
            "query_tags": [],
            "order-relevant": None,
            "verified": False,
            "db_id": db_id,
        },
    }


def _write_json(path: str, data: Any) -> None:
    save_json(data, path, indent=4)


def resolve_db(data_dir: str, db_name: str) -> str:
    return pj(data_dir, "databases", f"{db_name}.sqlite")


def _download_and_extract(download_dir: str, raw_dir: str, *, force: bool = False, remove_zip: bool = False) -> None:
    marker = pj(raw_dir, RAW_QUERIES_FILE)
    if exists_file(marker) and not force:
        click.echo(click.style(f"  ✓ Raw data already present at {raw_dir}", fg="green"))
        return
    touch_dir(download_dir)
    touch_dir(raw_dir)
    zip_path = pj(download_dir, ZIP_FILENAME)
    if force or not exists_file(zip_path):
        try:
            import gdown
        except ImportError:
            click.echo(click.style("✗ gdown required: pip install gdown", fg="red"))
            raise SystemExit(1)
        click.echo("  Downloading BirdSQL MINIDEV from Google Drive...")
        gdown.download(id=GOOGLE_DRIVE_FILE_ID, output=str(zip_path), quiet=False)
    else:
        click.echo(f"  Using cached ZIP: {zip_path}")
    # Verify download integrity
    if not verify_checksum(zip_path, EXPECTED_ZIP_MD5, label=ZIP_FILENAME):
        click.echo(click.style("  ✗ ZIP checksum failed. Re-run with --force.", fg="red"))
        raise SystemExit(1)
    click.echo(f"  Extracting to {raw_dir} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if not info.filename.startswith(ZIP_INNER_PREFIX):
                continue
            rel = info.filename[len(ZIP_INNER_PREFIX) :]
            if not rel:
                continue
            info.filename = rel
            zf.extract(info, raw_dir)
    click.echo(click.style("  ✓ Extraction complete", fg="green"))
    if remove_zip:
        from ahvn.utils.basic.file_utils import delete_file

        delete_file(zip_path)


def _download_corrections(download_dir: str, *, force: bool = False) -> str:
    touch_dir(download_dir)
    dest = pj(download_dir, CORRECTIONS_FILENAME)
    if exists_file(dest) and not force:
        click.echo(click.style(f"  ✓ Corrections already present: {dest}", fg="green"))
        return dest
    try:
        import gdown
    except ImportError:
        click.echo(click.style("✗ gdown required: pip install gdown", fg="red"))
        raise SystemExit(1)
    click.echo("  Downloading BirdSQL corrections...")
    gdown.download(id=CORRECTIONS_DRIVE_ID, output=str(dest), quiet=False)
    if not verify_checksum(dest, EXPECTED_CORRECTIONS_MD5, label=CORRECTIONS_FILENAME):
        click.echo(click.style("  ✗ Corrections checksum failed. Re-run with --force.", fg="red"))
        raise SystemExit(1)
    click.echo(click.style("  ✓ Corrections downloaded", fg="green"))
    return dest


def _apply_corrections(raw_queries: List[Dict[str, Any]], corrections_path: str) -> List[Dict[str, Any]]:
    corrections: List[Dict[str, Any]] = load_json(corrections_path, strict=True)
    corr_by_id = {c["question_id"]: c for c in corrections}
    result = []
    for q in raw_queries:
        qid = q.get("question_id")
        if qid in corr_by_id:
            c = corr_by_id[qid]
            merged = dict(q)
            merged["question"] = c.get("question", q.get("question", ""))
            merged["SQL"] = c.get("SQL", q.get("SQL", ""))
            merged["evidence"] = c.get("evidence", q.get("evidence", ""))
            merged["difficulty"] = c.get("difficulty", q.get("difficulty", "unknown"))
            result.append(merged)
    click.echo(f"  Applied corrections: {len(corrections)} corrected, {len(raw_queries) - len(result)} dropped")
    return result


def _copy_databases(raw_dir: str, databases_dir: str) -> int:
    src_root = pj(raw_dir, RAW_DATABASES_DIR)
    if not exists_dir(src_root):
        return 0
    touch_dir(databases_dir)
    count = 0
    for db_dir in list_dirs(src_root, abs=True):
        db_name = get_file_basename(db_dir)
        src_file = pj(db_dir, f"{db_name}.sqlite")
        if not exists_file(src_file):
            continue
        dest_file = pj(databases_dir, f"{db_name}.sqlite")
        if not exists_file(dest_file) or not file_size_matches(src_file, dest_file):
            shutil.copy2(src_file, dest_file)
        count += 1
    return count


def _process_queries(raw_dir, queries_dir, corrections_path=None, no_corrections=False):
    src = pj(raw_dir, RAW_QUERIES_FILE)
    if not exists_file(src):
        raise FileNotFoundError(f"Raw queries not found: {src}")
    raw: List[Dict[str, Any]] = load_json(src, strict=True)
    if corrections_path and exists_file(corrections_path) and not no_corrections:
        raw = _apply_corrections(raw, corrections_path)
    else:
        click.echo(f"  Using original queries ({len(raw)} total, corrections skipped)")
    click.echo(f"  Converting {len(raw)} queries...")
    converted = [_convert_query(q, i) for i, q in enumerate(raw)]
    by_db: Dict[str, List[Dict[str, Any]]] = {}
    for q in converted:
        by_db.setdefault(q["metadata"]["db_id"], []).append(q)
    touch_dir(queries_dir)
    combined_path = pj(queries_dir, "BirdSQL.json")
    _write_json(combined_path, converted)
    click.echo(f"  Wrote {len(converted)} queries -> {combined_path}")
    for db_id, qs in sorted(by_db.items()):
        db_queries_path = pj(queries_dir, f"{db_id}.json")
        _write_json(db_queries_path, qs)
        click.echo(f"  Wrote {len(qs):>3d} queries -> {db_queries_path}")


def setup(data_dir: str, *, force: bool = False, remove_zip: bool = False, no_corrections: bool = False) -> None:
    click.echo("Setting up BirdSQL (MINIDEV) benchmark...")
    click.echo(f"  Data directory: {data_dir}")
    download_dir = pj(data_dir, "download")
    raw_dir = pj(data_dir, "raw")
    databases_dir = pj(data_dir, "databases")
    queries_dir = pj(data_dir, "queries")
    _download_and_extract(download_dir, raw_dir, force=force, remove_zip=remove_zip)
    corrections_path = None
    if not no_corrections:
        corrections_path = _download_corrections(download_dir, force=force)
    db_count = _copy_databases(raw_dir, databases_dir)
    click.echo(f"  Copied {db_count} databases -> {databases_dir}")
    _process_queries(raw_dir, queries_dir, corrections_path=corrections_path, no_corrections=no_corrections)
    click.echo(click.style("\n✓ BirdSQL setup complete!", fg="green", bold=True))
    click.echo(f"  Databases: {db_count} SQLite files in {databases_dir}")
    click.echo(f"  Queries:   {queries_dir}")
