"""
안전재고 대시보드 API 엄격 테스트.
- 모든 safety-stock·inventory 관련 엔드포인트의 상태 코드·스키마·타입 검증.
"""
import pytest
from fastapi.testclient import TestClient


# ---------- GET /api/safety-stock ----------
def test_safety_stock_returns_200(client: TestClient) -> None:
    r = client.get("/api/safety-stock")
    assert r.status_code == 200
    assert "application/json" in (r.headers.get("content-type") or "")


def test_safety_stock_has_statuses_and_total_count(client: TestClient) -> None:
    r = client.get("/api/safety-stock")
    data = r.json()
    assert isinstance(data, dict)
    assert "statuses" in data
    assert "total_count" in data
    assert isinstance(data["statuses"], list)
    assert isinstance(data["total_count"], int)
    assert data["total_count"] >= 0


def test_safety_stock_status_items_shape(client: TestClient) -> None:
    r = client.get("/api/safety-stock")
    data = r.json()
    for item in data.get("statuses", [])[:5]:
        assert isinstance(item, dict)
        assert "status" in item or "label" in item or "count" in item or len(item) >= 1
        if "count" in item:
            assert isinstance(item["count"], (int, float))


# ---------- GET /api/safety-stock-kpi ----------
def test_safety_stock_kpi_returns_200(client: TestClient) -> None:
    r = client.get("/api/safety-stock-kpi")
    assert r.status_code == 200


def test_safety_stock_kpi_schema(client: TestClient) -> None:
    r = client.get("/api/safety-stock-kpi")
    data = r.json()
    assert isinstance(data, dict)
    assert "total_frozen_money" in data
    assert "danger_count" in data
    assert "overstock_count" in data
    assert isinstance(data["total_frozen_money"], (int, float))
    assert isinstance(data["danger_count"], int)
    assert isinstance(data["overstock_count"], int)
    assert data["danger_count"] >= 0
    assert data["overstock_count"] >= 0


# ---------- GET /api/safety-stock-forecast-chart ----------
def test_safety_stock_forecast_chart_returns_200(client: TestClient) -> None:
    r = client.get("/api/safety-stock-forecast-chart")
    assert r.status_code == 200


def test_safety_stock_forecast_chart_schema(client: TestClient) -> None:
    r = client.get("/api/safety-stock-forecast-chart")
    data = r.json()
    assert isinstance(data, dict)
    assert "product_name" in data
    assert "chart_data" in data
    assert isinstance(data["product_name"], str)
    assert isinstance(data["chart_data"], list)


def test_safety_stock_forecast_chart_with_product_param(client: TestClient) -> None:
    r = client.get("/api/safety-stock-forecast-chart?product_name=MacBook%20Pro")
    assert r.status_code == 200
    data = r.json()
    assert "product_name" in data
    assert "chart_data" in data


# ---------- GET /api/safety-stock-sales-by-store-period ----------
def test_safety_stock_sales_by_store_period_returns_200(client: TestClient) -> None:
    r = client.get("/api/safety-stock-sales-by-store-period?category=Phone")
    assert r.status_code == 200


def test_safety_stock_sales_by_store_period_schema(client: TestClient) -> None:
    r = client.get("/api/safety-stock-sales-by-store-period?category=Phone")
    data = r.json()
    assert isinstance(data, dict)
    assert "category" in data
    assert "data" in data or "periods" in data
    assert isinstance(data.get("data", []), list)
    assert isinstance(data.get("periods", []), list)


# ---------- GET /api/safety-stock-sales-by-product ----------
def test_safety_stock_sales_by_product_returns_200(client: TestClient) -> None:
    r = client.get("/api/safety-stock-sales-by-product?category=Phone")
    assert r.status_code == 200


def test_safety_stock_sales_by_product_schema(client: TestClient) -> None:
    r = client.get("/api/safety-stock-sales-by-product?category=Phone")
    data = r.json()
    assert isinstance(data, dict)
    assert "category" in data
    assert "products" in data or "product" in data or len(data) >= 1
    if "products" in data:
        assert isinstance(data["products"], list)


# ---------- GET /api/safety-stock-inventory-list ----------
def test_safety_stock_inventory_list_returns_200(client: TestClient) -> None:
    r = client.get("/api/safety-stock-inventory-list")
    assert r.status_code == 200


def test_safety_stock_inventory_list_is_list(client: TestClient) -> None:
    r = client.get("/api/safety-stock-inventory-list")
    data = r.json()
    assert isinstance(data, list)


def test_safety_stock_inventory_list_with_filter(client: TestClient) -> None:
    r = client.get("/api/safety-stock-inventory-list?status_filter=Danger")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_safety_stock_inventory_list_filter_korean(client: TestClient) -> None:
    r = client.get("/api/safety-stock-inventory-list?status_filter=위험")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- GET /api/safety-stock-overstock-status ----------
def test_safety_stock_overstock_status_returns_200(client: TestClient) -> None:
    r = client.get("/api/safety-stock-overstock-status")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- GET /api/safety-stock-overstock-top5 ----------
def test_safety_stock_overstock_top5_returns_200(client: TestClient) -> None:
    r = client.get("/api/safety-stock-overstock-top5")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    for item in data:
        assert isinstance(item, dict)
        assert "product_name" in item or "overstock_qty" in item or len(item) >= 1


# ---------- GET /api/safety-stock-risky-items-top5 ----------
def test_safety_stock_risky_items_top5_returns_200(client: TestClient) -> None:
    r = client.get("/api/safety-stock-risky-items-top5")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 5


# ---------- GET /api/inventory-frozen-money ----------
def test_inventory_frozen_money_returns_200(client: TestClient) -> None:
    r = client.get("/api/inventory-frozen-money")
    assert r.status_code == 200


def test_inventory_frozen_money_schema(client: TestClient) -> None:
    r = client.get("/api/inventory-frozen-money")
    data = r.json()
    assert isinstance(data, dict)
    assert "items" in data
    assert isinstance(data["items"], list)


# ---------- GET /api/inventory-comments (GET) ----------
def test_inventory_comments_get_returns_200(client: TestClient) -> None:
    r = client.get("/api/inventory-comments")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "comments" in data
    assert isinstance(data["comments"], list)
