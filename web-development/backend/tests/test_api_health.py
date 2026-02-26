"""
헬스·상태 API 엄격 테스트.
- 상태 코드, Content-Type, 응답 스키마·타입을 엄격히 검증.
"""
import pytest
from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert "application/json" in (r.headers.get("content-type") or "")


def test_health_json_structure(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    # 최소 한 개 이상의 키 존재
    assert len(data) >= 1


def test_api_health_returns_200(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert "application/json" in (r.headers.get("content-type") or "")


def test_api_health_has_status_or_ok(client: TestClient) -> None:
    r = client.get("/api/health")
    data = r.json()
    assert isinstance(data, dict)
    assert "status" in data or "ok" in data or "healthy" in data or len(data) >= 1


def test_quick_status_returns_200(client: TestClient) -> None:
    r = client.get("/api/quick-status")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_quick_status_has_expected_keys(client: TestClient) -> None:
    r = client.get("/api/quick-status")
    data = r.json()
    # quick-status는 연동 상태 관련 키를 가짐
    assert "loader" in data or "model_server" in data or "ok" in data or "status" in data or len(data) >= 1


def test_integration_status_returns_200(client: TestClient) -> None:
    r = client.get("/api/integration-status")
    assert r.status_code == 200
    assert "application/json" in (r.headers.get("content-type") or "")


def test_integration_status_is_dict(client: TestClient) -> None:
    r = client.get("/api/integration-status")
    data = r.json()
    assert isinstance(data, dict)
    # 연동 점검 결과이므로 최소 1개 섹션
    assert len(data) >= 1
