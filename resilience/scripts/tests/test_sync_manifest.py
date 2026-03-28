from pathlib import Path

import yaml


def test_manifest_references_existing_source_templates() -> None:
    manifest = yaml.safe_load(
        Path("config/template-manifest.yaml").read_text(encoding="utf-8")
    )
    for entry in manifest["templates"]:
        assert Path(entry["source"]).exists()
