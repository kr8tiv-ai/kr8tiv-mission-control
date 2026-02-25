from __future__ import annotations

from app.api.board_onboarding import _build_onboarding_recommendation


def test_onboarding_qa_generates_persona_and_ability_recommendation() -> None:
    recommendation = _build_onboarding_recommendation(
        {
            "status": "complete",
            "deployment_mode": "team",
            "lead_agent": {
                "identity_profile": {
                    "role": "CMO",
                }
            },
        }
    )

    assert recommendation is not None
    assert recommendation.deployment_mode == "team"
    assert recommendation.persona_preset_key == "business-cmo"
    assert "mission_control_tasks" in recommendation.ability_bundle
    assert "orchestrator" in recommendation.ability_bundle


def test_personalized_flow_defaults_voice_and_uplay_chromium_capability() -> None:
    recommendation = _build_onboarding_recommendation(
        {
            "status": "complete",
            "deployment_mode": "individual",
            "lead_agent": {
                "identity_profile": {
                    "role": "Companion",
                }
            },
        }
    )

    assert recommendation is not None
    assert recommendation.deployment_mode == "individual"
    assert recommendation.persona_preset_key == "individual-companion"
    assert recommendation.voice_enabled is True
    assert "voice" in recommendation.ability_bundle
    assert "uplay_chromium" in recommendation.ability_bundle
