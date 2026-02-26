"""
매출·추천 관련 API 엄격 테스트.
- /api/sales-summary, /api/store-list, /api/data-source 등 보조 엔드포인트 검증.
"""
import pytest
from fastapi.testclient import TestClient


def test_sales_summary_returns_200(client: TestClient) -> None:
    r = client.get("/api/sales-summary")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_store_list_returns_200(client: TestClient) -> None:
    r = client.get("/api/store-list")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) or isinstance(data, dict)
    if isinstance(data, dict) and "stores" in data:
        assert isinstance(data["stores"], list)


def test_recommendation_summary_returns_200(client: TestClient) -> None:
    r = client.get("/api/recommendation-summary")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_demand_dashboard_returns_200(client: TestClient) -> None:
    r = client.get("/api/demand-dashboard")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_last_updated_returns_200(client: TestClient) -> None:
    r = client.get("/api/last-updated")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict) or isinstance(data, str)


def test_root_returns_200(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200


def test_api_health_page_returns_200(client: TestClient) -> None:
    r = client.get("/api/health/page")
    assert r.status_code == 200
    assert "text/html" in (r.headers.get("content-type") or "")
