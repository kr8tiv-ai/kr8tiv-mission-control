from scripts.watchdog_openclaw import classify_container_state


def test_unhealthy_state_triggers_restart_action() -> None:
    assert (
        classify_container_state(status="running", health="unhealthy")
        == "restart_container"
    )
