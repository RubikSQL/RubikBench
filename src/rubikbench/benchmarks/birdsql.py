"""BirdSQL (MINIDEV) benchmark setup."""

import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Any, List

import click

DEFAULT_DATA_DIR = Path("./data/BirdSQL")

GOOGLE_DRIVE_FILE_ID = "13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG"
ZIP_FILENAME = "minidev_0703.zip"
ZIP_INNER_PREFIX = "minidev/MINIDEV/"

CORRECTIONS_DRIVE_ID = "1iWlYVknwK5wGli5lnwg4stvNzMogjhwj"
CORRECTIONS_FILENAME = "bird_minidev_corrections.json"

RAW_QUERIES_FILE = "mini_dev_sqlite.json"
RAW_DATABASES_DIR = "dev_databases"
BENCHMARK_NAME = "BirdSQL"


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


def _write_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def resolve_db(data_dir: Path, db_name: str) -> Path:
    return data_dir / "databases" / f"{db_name}.sqlite"


def _download_and_extract(download_dir: Path, raw_dir: Path, *, force: bool = False, remove_zip: bool = False) -> None:
    marker = raw_dir / RAW_QUERIES_FILE
    if marker.exists() and not force:
        click.echo(click.style(f"  ✓ Raw data already present at {raw_dir}", fg="green"))
        return
    download_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = download_dir / ZIP_FILENAME
    if not zip_path.exists() or force:
        try:
            import gdown
        except ImportError:
            click.echo(click.style("✗ gdown required: pip install gdown", fg="red"))
            raise SystemExit(1)
        click.echo("  Downloading BirdSQL MINIDEV from Google Drive...")
        gdown.download(id=GOOGLE_DRIVE_FILE_ID, output=str(zip_path), quiet=False)
    else:
        click.echo(f"  Using cached ZIP: {zip_path}")
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
        zip_path.unlink(missing_ok=True)


def _download_corrections(download_dir: Path, *, force: bool = False) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    dest = download_dir / CORRECTIONS_FILENAME
    if dest.exists() and not force:
        click.echo(click.style(f"  ✓ Corrections already present: {dest}", fg="green"))
        return dest
    try:
        import gdown
    except ImportError:
        click.echo(click.style("✗ gdown required: pip install gdown", fg="red"))
        raise SystemExit(1)
    click.echo("  Downloading BirdSQL corrections...")
    gdown.download(id=CORRECTIONS_DRIVE_ID, output=str(dest), quiet=False)
    click.echo(click.style("  ✓ Corrections downloaded", fg="green"))
    return dest


def _apply_corrections(raw_queries: List[Dict[str, Any]], corrections_path: Path) -> List[Dict[str, Any]]:
    with open(corrections_path, "r", encoding="utf-8") as f:
        corrections: List[Dict[str, Any]] = json.load(f)
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


def _copy_databases(raw_dir: Path, databases_dir: Path) -> int:
    src_root = raw_dir / RAW_DATABASES_DIR
    if not src_root.exists():
        return 0
    databases_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for db_dir in sorted(src_root.iterdir()):
        if not db_dir.is_dir():
            continue
        src_file = db_dir / f"{db_dir.name}.sqlite"
        if not src_file.exists():
            continue
        dest_file = databases_dir / f"{db_dir.name}.sqlite"
        if not dest_file.exists() or dest_file.stat().st_size != src_file.stat().st_size:
            shutil.copy2(src_file, dest_file)
        count += 1
    return count


def _process_queries(raw_dir, queries_dir, corrections_path=None, no_corrections=False):
    src = raw_dir / RAW_QUERIES_FILE
    if not src.exists():
        raise FileNotFoundError(f"Raw queries not found: {src}")
    with open(src, "r", encoding="utf-8") as f:
        raw: List[Dict[str, Any]] = json.load(f)
    if corrections_path and corrections_path.exists() and not no_corrections:
        raw = _apply_corrections(raw, corrections_path)
    else:
        click.echo(f"  Using original queries ({len(raw)} total, corrections skipped)")
    click.echo(f"  Converting {len(raw)} queries...")
    converted = [_convert_query(q, i) for i, q in enumerate(raw)]
    by_db: Dict[str, List[Dict[str, Any]]] = {}
    for q in converted:
        by_db.setdefault(q["metadata"]["db_id"], []).append(q)
    queries_dir.mkdir(parents=True, exist_ok=True)
    _write_json(queries_dir / "BirdSQL.json", converted)
    click.echo(f"  Wrote {len(converted)} queries -> {queries_dir / 'BirdSQL.json'}")
    for db_id, qs in sorted(by_db.items()):
        _write_json(queries_dir / f"{db_id}.json", qs)
        click.echo(f"  Wrote {len(qs):>3d} queries -> {queries_dir / db_id}.json")


def setup(data_dir: Path, *, force: bool = False, remove_zip: bool = False, no_corrections: bool = False) -> None:
    click.echo("Setting up BirdSQL (MINIDEV) benchmark...")
    click.echo(f"  Data directory: {data_dir}")
    download_dir = data_dir / "download"
    raw_dir = data_dir / "raw"
    databases_dir = data_dir / "databases"
    queries_dir = data_dir / "queries"
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
