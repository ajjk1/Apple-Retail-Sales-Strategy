"""
엣지 케이스·검증 엄격 테스트.
- 잘못된/빈 파라미터, POST body 검증, 한글/영문 혼용 필터 등.
"""
import pytest
from fastapi.testclient import TestClient


def test_safety_stock_inventory_list_empty_filter(client: TestClient) -> None:
    r = client.get("/api/safety-stock-inventory-list?status_filter=")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_safety_stock_inventory_list_multiple_filters(client: TestClient) -> None:
    r = client.get("/api/safety-stock-inventory-list?status_filter=Danger,Overstock")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_safety_stock_forecast_chart_empty_product(client: TestClient) -> None:
    r = client.get("/api/safety-stock-forecast-chart?product_name=")
    assert r.status_code == 200
    data = r.json()
    assert "product_name" in data
    assert "chart_data" in data


def test_safety_stock_sales_by_store_period_empty_category(client: TestClient) -> None:
    r = client.get("/api/safety-stock-sales-by-store-period")
    assert r.status_code == 200
    data = r.json()
    assert "category" in data
    assert isinstance(data.get("data", []), list)


def test_inventory_comments_post_missing_body(client: TestClient) -> None:
    r = client.post("/api/inventory-comments", json={})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is False
    assert "error" in data


def test_inventory_comments_post_missing_comment(client: TestClient) -> None:
    r = client.post("/api/inventory-comments", json={"store_name": "Test Store"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is False


def test_inventory_comments_post_valid(client: TestClient) -> None:
    r = client.post(
        "/api/inventory-comments",
        json={"store_name": "Test Store Edge", "comment": "테스트 코멘트", "author": "pytest"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "comments" in data
    assert isinstance(data["comments"], list)


def test_store_recommendations_with_store_id(client: TestClient) -> None:
    r = client.get("/api/store-recommendations/1")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_store_sales_forecast_with_store_id(client: TestClient) -> None:
    r = client.get("/api/store-sales-forecast/1")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_demand_dashboard_with_query_params(client: TestClient) -> None:
    r = client.get("/api/demand-dashboard?store_id=1&year=2024")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_sales_by_store_quarterly_returns_200(client: TestClient) -> None:
    r = client.get("/api/sales-by-store-quarterly")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


def test_region_category_pivot_returns_200(client: TestClient) -> None:
    r = client.get("/api/region-category-pivot")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


def test_inventory_critical_alerts_returns_200(client: TestClient) -> None:
    r = client.get("/api/inventory-critical-alerts")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "critical_count" in data
    assert "critical_items" in data
    assert isinstance(data["critical_items"], list)


def test_inventory_critical_alerts_limit_param(client: TestClient) -> None:
    r = client.get("/api/inventory-critical-alerts?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "critical_items" in data
    assert isinstance(data["critical_items"], list)
    assert len(data["critical_items"]) <= 5
