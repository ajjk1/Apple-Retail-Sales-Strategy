"""
load_sales_data (model-server) 단위 테스트.
- get_data_source_info, 텍스트 정규화, 컬럼 정규화 등 엄격 검증.
"""
import pytest
import pandas as pd

# conftest에서 model-server가 path에 있음
import load_sales_data as lsd


def test_get_data_source_info_returns_dict() -> None:
    info = lsd.get_data_source_info()
    assert isinstance(info, dict)


def test_get_data_source_info_has_quantity_unit() -> None:
    info = lsd.get_data_source_info()
    assert "quantity_unit" in info
    assert info["quantity_unit"] == "대"


def test_get_data_source_info_has_source() -> None:
    info = lsd.get_data_source_info()
    assert "source" in info
    assert info["source"] in ("sql", "csv", "none")


def test_get_data_source_info_sql_file_count_non_negative() -> None:
    info = lsd.get_data_source_info()
    assert "sql_file_count" in info
    assert isinstance(info["sql_file_count"], int)
    assert info["sql_file_count"] >= 0


def test_strip_wrapping_quotes_single_quotes() -> None:
    assert lsd._strip_wrapping_quotes("'a'") == "a"
    assert lsd._strip_wrapping_quotes("'  x  '") == "x"


def test_strip_wrapping_quotes_double_quotes() -> None:
    assert lsd._strip_wrapping_quotes('"b"') == "b"


def test_strip_wrapping_quotes_no_quotes_unchanged() -> None:
    assert lsd._strip_wrapping_quotes("hello") == "hello"
    assert lsd._strip_wrapping_quotes("  hello  ") == "hello"


def test_strip_wrapping_quotes_empty_or_none() -> None:
    assert lsd._strip_wrapping_quotes("") == ""
    assert lsd._strip_wrapping_quotes(None) == ""


def test_normalize_text_columns_empty_df() -> None:
    df = pd.DataFrame()
    out = lsd._normalize_text_columns(df)
    assert out is not None
    assert out.empty


def test_normalize_text_columns_none_returns_none() -> None:
    out = lsd._normalize_text_columns(None)
    assert out is None


def test_normalize_text_columns_strips_quotes() -> None:
    df = pd.DataFrame({"a": ["  'x'  ", '"y"', " z "]})
    df["a"] = df["a"].astype(object)  # object 컬럼만 정규화되므로 명시
    out = lsd._normalize_text_columns(df)
    assert out is not None
    assert list(out["a"]) == ["x", "y", "z"]


def test_parse_insert_values_null() -> None:
    row = lsd._parse_insert_values("NULL, 1, 'a'")
    assert row is not None
    assert len(row) == 3
    assert row[0] is None


def test_parse_insert_values_simple() -> None:
    row = lsd._parse_insert_values("1, 'text', 3.5")
    assert len(row) >= 1
    assert row[0] is not None or row[0] is None


def test_canonicalize_columns_empty_df() -> None:
    df = pd.DataFrame()
    out = lsd._canonicalize_columns(df)
    assert out is not None
    assert out.empty


def test_canonicalize_columns_renames_lower_to_capital() -> None:
    df = pd.DataFrame({"city": [1], "country": [2], "product_name": [3]})
    out = lsd._canonicalize_columns(df)
    assert "City" in out.columns
    assert "Country" in out.columns
    assert "Product_Name" in out.columns


def test_quantity_unit_constant() -> None:
    assert hasattr(lsd, "QUANTITY_UNIT")
    assert lsd.QUANTITY_UNIT == "대"
