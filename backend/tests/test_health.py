"""Health probes and the shared error envelope."""

from __future__ import annotations

from typing import Any


def test_liveness_reports_service_metadata(client: Any) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_touches_the_database(client: Any) -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"


def test_unknown_route_uses_the_shared_error_envelope(client: Any) -> None:
    """Starlette answers unmatched routes itself; it must still match our shape."""
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_rejected_method_uses_the_shared_error_envelope(client: Any) -> None:
    response = client.request("DELETE", "/api/v1/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
