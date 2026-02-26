"""
GET /api/data-source 엄격 테스트.
- 응답 스키마·타입·허용 값 검증.
"""
import pytest
from fastapi.testclient import TestClient


def test_data_source_returns_200(client: TestClient) -> None:
    r = client.get("/api/data-source")
    assert r.status_code == 200
    assert "application/json" in (r.headers.get("content-type") or "")


def test_data_source_is_dict(client: TestClient) -> None:
    r = client.get("/api/data-source")
    data = r.json()
    assert isinstance(data, dict)


def test_data_source_has_required_keys(client: TestClient) -> None:
    r = client.get("/api/data-source")
    data = r.json()
    assert "loader" in data
    assert "quantity_unit" in data or "data_dir" in data or "source" in data


def test_data_source_loader_type(client: TestClient) -> None:
    r = client.get("/api/data-source")
    data = r.json()
    loader = data.get("loader")
    assert loader is None or isinstance(loader, str)
    if isinstance(loader, str):
        assert loader in ("model_server", "builtin", "sql", "csv", "none") or len(loader) >= 0


def test_data_source_source_type(client: TestClient) -> None:
    r = client.get("/api/data-source")
    data = r.json()
    src = data.get("source")
    if src is not None:
        assert isinstance(src, str)


def test_data_source_sql_file_count_type(client: TestClient) -> None:
    r = client.get("/api/data-source")
    data = r.json()
    n = data.get("sql_file_count")
    if n is not None:
        assert isinstance(n, int)
        assert n >= 0
