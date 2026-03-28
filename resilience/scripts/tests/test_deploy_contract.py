from pathlib import Path


def test_deploy_script_requires_expected_env_vars() -> None:
    script = Path("scripts/deploy_openclaw_stack.sh").read_text(encoding="utf-8")
    for key in ["VPS_HOST", "VPS_USER", "VPS_SSH_KEY", "DEPLOY_ROOT"]:
        assert key in script


def test_workflow_contains_required_production_dispatch_controls() -> None:
    workflow = Path(
        ".github/workflows/deploy-openclaw-production.yml"
    ).read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "environment: production" in workflow
    assert "post-deploy healthcheck" in workflow.lower()

