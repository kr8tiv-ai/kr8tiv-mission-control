from __future__ import annotations

from app.services.skills_hot_ingest import ingest_skill


def test_invalid_skill_is_quarantined() -> None:
    result = ingest_skill({"name": "bad-skill", "risk_tier": "invalid"})
    assert result.status == "quarantined"
    assert result.metadata["ingest_status"] == "quarantined"


def test_valid_skill_is_accepted_with_checksum() -> None:
    result = ingest_skill({"name": "good-skill", "risk_tier": "low", "source_url": "https://a"})
    assert result.status == "accepted"
    assert result.metadata["ingest_status"] == "accepted"
    checksum = str(result.metadata["ingest_checksum"])
    assert len(checksum) == 64
