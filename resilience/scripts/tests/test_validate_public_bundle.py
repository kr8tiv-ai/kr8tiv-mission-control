from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts.validate_public_bundle import extract_zip_safely


def test_extract_zip_safely_allows_normal_entries(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    destination = tmp_path / "out"
    destination.mkdir()

    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("docs/readme.txt", "ok")

    extract_zip_safely(archive, destination)

    assert (destination / "docs" / "readme.txt").exists()


def test_extract_zip_safely_blocks_zip_slip_entries(tmp_path: Path) -> None:
    archive = tmp_path / "bundle.zip"
    destination = tmp_path / "out"
    destination.mkdir()

    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "bad")

    with pytest.raises(ValueError):
        extract_zip_safely(archive, destination)
