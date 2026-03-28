from scripts.validate_capability_matrix import validate_matrix


def test_each_task_type_has_at_least_one_agent() -> None:
    errors = validate_matrix("config/agent-capability-matrix.yaml")
    assert errors == []

