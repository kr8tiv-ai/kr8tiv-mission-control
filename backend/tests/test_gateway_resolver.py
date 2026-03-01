from __future__ import annotations

from types import SimpleNamespace

from app.services.openclaw.gateway_resolver import (
    gateway_client_config,
    optional_gateway_client_config,
)


def test_gateway_client_config_derives_origin_from_ws_url() -> None:
    gateway = SimpleNamespace(url="ws://76.13.106.100:48650", token="  secret-token  ")

    cfg = gateway_client_config(gateway)  # type: ignore[arg-type]

    assert cfg.url == "ws://76.13.106.100:48650"
    assert cfg.token == "secret-token"
    assert cfg.origin == "http://76.13.106.100:48650"


def test_optional_gateway_client_config_derives_origin_from_wss_url() -> None:
    gateway = SimpleNamespace(url="wss://gateway.example/ws", token="")

    cfg = optional_gateway_client_config(gateway)  # type: ignore[arg-type]

    assert cfg is not None
    assert cfg.origin == "https://gateway.example"


def test_optional_gateway_client_config_returns_none_without_url() -> None:
    gateway = SimpleNamespace(url="  ", token="secret-token")

    assert optional_gateway_client_config(gateway) is None  # type: ignore[arg-type]
