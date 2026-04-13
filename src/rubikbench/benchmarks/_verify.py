"""Download verification helpers."""

import hashlib
import os
from typing import Optional

import click


def md5_file(path: str) -> str:
    """Compute the MD5 hex digest of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_checksum(path: str, expected_md5: Optional[str], *, label: str = "") -> bool:
    """Verify a file's MD5 checksum.

    Args:
        path: Path to the file to verify.
        expected_md5: Expected MD5 hex digest. If ``None``, skip verification.
        label: Human-readable label for messages (defaults to the path).

    Returns:
        ``True`` if the checksum matches or was skipped, ``False`` otherwise.
    """
    if expected_md5 is None:
        return True
    label = label or path
    if not os.path.isfile(path):
        click.echo(click.style(f"  ✗ File not found for checksum: {label}", fg="red"))
        return False
    actual = md5_file(path)
    if actual != expected_md5:
        click.echo(click.style(
            f"  ✗ Checksum mismatch for {label}: expected {expected_md5}, got {actual}",
            fg="red",
        ))
        return False
    click.echo(click.style(f"  ✓ Checksum OK: {label}", fg="green"))
    return True


def file_size_matches(src: str, dest: str) -> bool:
    """Return True if both files exist and have the same size."""
    try:
        return os.path.getsize(src) == os.path.getsize(dest)
    except OSError:
        return False
