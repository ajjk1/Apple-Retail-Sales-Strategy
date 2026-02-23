"""
모델 서버 공통 판매 데이터 로더.

- 데이터 소스: model-server/01.data/*.sql (Apple_Retail_Sales_Dataset_Modified_01~10.sql) 만 사용
- CSV 파일은 참고하지 않음 (SQL 전용)

모든 모델(02 예측, 03 매출, 04 재고, 05 추천)이 동일한 데이터 소스를 사용하도록
load_sales_dataframe() 하나로 통일합니다.

- 수량 단위: QUANTITY_UNIT (가격탄력성 등 데이터 준비용)
"""

from __future__ import annotations

from pathlib import Path
import re
import csv
import io
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_MODEL_SERVER = Path(__file__).resolve().parent
_CACHE_DF: Optional[pd.DataFrame] = None

# 수량 단위 (가격탄력성 등 데이터 준비용)
QUANTITY_UNIT = "대"


def _strip_wrapping_quotes(s: str) -> str:
    s = (s or "").strip()
    if len(s) >= 2 and ((s[0] == "'" and s[-1] == "'") or (s[0] == '"' and s[-1] == '"')):
        return s[1:-1].strip()
    return s


def _normalize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """모든 object 컬럼에 대해 앞뒤 따옴표/공백 정규화."""
    if df is None or df.empty:
        return df
    df = df.copy()
    obj_cols = [c for c in df.columns if df[c].dtype == "object"]
    for c in obj_cols:
        df[c] = (
            df[c]
            .astype(str)
            .map(_strip_wrapping_quotes)
            .str.strip()
            .replace({"None": "", "nan": "", "NaN": ""})
        )
    return df


def get_data_source_info() -> Dict[str, Any]:
    """현재 데이터가 어디서 로드되는지(02.Database for dashboard / 01.data SQL / CSV) 반환."""
    dashboard_dir = _MODEL_SERVER / "02.Database for dashboard"
    sql_files = sorted(dashboard_dir.glob("*.sql")) if dashboard_dir.exists() else []
    sql_dir = dashboard_dir if sql_files else (_MODEL_SERVER / "01.data")
    if not sql_files:
        sql_files = sorted(sql_dir.glob("*.sql")) if sql_dir.exists() else []

    csv_candidates = [
        _MODEL_SERVER / "data" / "Apple_Retail_Sales_Dataset_Modified.csv",
        _MODEL_SERVER / "data" / "data_01.csv",
        _MODEL_SERVER / "data_01.csv",
    ]
    csv_path = next((p for p in csv_candidates if p.exists()), None)

    base_info = {"quantity_unit": QUANTITY_UNIT}
    if sql_files:
        return {
            **base_info,
            "data_dir": str(sql_dir),
            "source": "sql",
            "sql_file_count": len(sql_files),
            "csv_path": str(csv_path) if csv_path else None,
        }
    if csv_path:
        return {
            **base_info,
            "data_dir": str(csv_path.parent),
            "source": "csv",
            "sql_file_count": 0,
            "csv_path": str(csv_path),
        }
    return {**base_info, "data_dir": "", "source": "none", "sql_file_count": 0, "csv_path": None}


def _parse_insert_values(tuple_text: str) -> List[Any]:
    """
    INSERT ... VALUES ( ... ) 의 괄호 안 텍스트를 CSV처럼 파싱.
    - quotechar: ' (SQL 문자열)
    - skipinitialspace: True (콤마 뒤 공백 처리)
    """
    reader = csv.reader(io.StringIO(tuple_text), quotechar="'", doublequote=True, skipinitialspace=True)
    row = next(reader, [])
    out: List[Any] = []
    for v in row:
        vv = v
        if vv is None:
            out.append(None)
            continue
        vv = str(vv).strip()
        if vv.upper() == "NULL":
            out.append(None)
            continue
        out.append(vv)
    return out


def _extract_insert_blocks(sql: str) -> List[Tuple[List[str], str]]:
    """
    SQL 문자열에서 INSERT 블록을 추출.
    반환: [(columns, values_blob_string), ...]
    """
    blocks: List[Tuple[List[str], str]] = []

    # INSERT INTO sales_data (a,b,c) VALUES ...;
    # values_blob는 다음 INSERT 또는 파일 끝까지.
    insert_re = re.compile(
        r"INSERT\s+INTO\s+sales_data\s*\((?P<cols>[^)]+)\)\s*VALUES\s*(?P<vals>.*?);",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for m in insert_re.finditer(sql):
        cols_raw = m.group("cols")
        cols = [c.strip().strip('"') for c in cols_raw.split(",")]
        vals = m.group("vals").strip()
        blocks.append((cols, vals))
    return blocks


def _iter_tuple_texts(values_blob: str):
    """
    VALUES 뒤에 오는 "(...),(...),(...)" blob에서 각 튜플의 내부 텍스트만 순회.
    - 문자열 따옴표(') 내부의 괄호/콤마는 무시.
    """
    in_quote = False
    start_idx = None
    i = 0
    while i < len(values_blob):
        ch = values_blob[i]
        if ch == "'":
            # SQL escape: '' -> 단일 따옴표
            if in_quote and i + 1 < len(values_blob) and values_blob[i + 1] == "'":
                i += 2
                continue
            in_quote = not in_quote
            i += 1
            continue

        if not in_quote:
            if ch == "(" and start_idx is None:
                start_idx = i + 1
            elif ch == ")" and start_idx is not None:
                yield values_blob[start_idx:i]
                start_idx = None
        i += 1


def _load_from_sql_files(sql_files: List[Path]) -> Optional[pd.DataFrame]:
    rows: List[List[Any]] = []
    cols_final: Optional[List[str]] = None

    for p in sql_files:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for cols, vals_blob in _extract_insert_blocks(text):
            cols_final = cols_final or cols
            for tup_text in _iter_tuple_texts(vals_blob):
                rows.append(_parse_insert_values(tup_text))

    if not rows or not cols_final:
        return None
    df = pd.DataFrame(rows, columns=cols_final)
    return df


def _canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    모델 코드들이 기대하는 컬럼명으로 정리.
    - City/Country/Product_Name (대문자) 지원
    - 나머지는 원본(lowercase) 유지
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    rename_map = {
        "city": "City",
        "country": "Country",
        "product_name": "Product_Name",
        "store_name": "Store_Name",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    return df


def load_sales_dataframe(force_reload: bool = False) -> Optional[pd.DataFrame]:
    """
    판매 데이터 DataFrame을 로드.
    - 최초 1회 로드 후 메모리 캐시
    """
    global _CACHE_DF
    if _CACHE_DF is not None and not force_reload:
        return _CACHE_DF

    # 배포용 경량 데이터 우선 (Hugging Face 등): 02.Database for dashboard
    dashboard_dir = _MODEL_SERVER / "02.Database for dashboard"
    sql_files = sorted(dashboard_dir.glob("*.sql")) if dashboard_dir.exists() else []
    if not sql_files:
        sql_dir = _MODEL_SERVER / "01.data"
        sql_files = sorted(sql_dir.glob("*.sql")) if sql_dir.exists() else []

    df: Optional[pd.DataFrame] = None
    if sql_files:
        df = _load_from_sql_files(sql_files)

    if df is None or df.empty:
        csv_candidates = [
            _MODEL_SERVER / "data" / "Apple_Retail_Sales_Dataset_Modified.csv",
            _MODEL_SERVER / "data" / "data_01.csv",
            _MODEL_SERVER / "data_01.csv",
        ]
        csv_path = next((p for p in csv_candidates if p.exists()), None)
        if csv_path is not None:
            try:
                df = pd.read_csv(csv_path)
            except Exception:
                df = None

    if df is None or getattr(df, "empty", True):
        # Hugging Face 등 배포 환경에서 원인 파악용 로그 (SQL/CSV 모두 없을 때)
        print(
            f"[load_sales_data] 데이터 없음. 시도 경로: "
            f"02.Database for dashboard={dashboard_dir.exists()}, "
            f"01.data={(_MODEL_SERVER / '01.data').exists()}, "
            f"sql_files={len(sql_files) if sql_files else 0}개"
        )
        _CACHE_DF = None
        return None

    df = _canonicalize_columns(df)
    df = _normalize_text_columns(df)

    # 숫자 컬럼은 가능한 범위 내에서 숫자화 (모델에서 다시 coerce 하더라도 안전)
    for col in ("quantity", "total_sales", "price"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # SQL INSERT에 없을 수 있음: quantity 기준 95%~130% 랜덤으로 Store stock quantity 생성
    if "store_stock_quantity" not in df.columns and "quantity" in df.columns:
        q = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
        rng = np.random.default_rng()
        df["store_stock_quantity"] = (q * (0.95 + rng.random(len(df)) * 0.35)).clip(lower=1).round().astype(int)

    _CACHE_DF = df
    return df

