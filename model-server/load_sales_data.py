"""
모델 서버 공통 판매 데이터 로더.

- 로컬: 01.data/*.sql 우선 → 02.Database for dashboard 폴백 → CSV
- 배포(Hugging Face 등): 환경 변수 USE_DASHBOARD_SQL=1 설정 시 02.Database for dashboard 우선 사용.
  → 대용량 01.data SQL 업로드 없이 경량 SQL만으로 배포 가능.

모든 모델(예측, 매출, 재고, 추천)이 동일한 데이터 소스를 사용하도록 load_sales_dataframe() 하나로 통일.
- 수량 단위: QUANTITY_UNIT (가격탄력성 등 데이터 준비용)
"""

from __future__ import annotations

import os
import re
import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_MODEL_SERVER = Path(__file__).resolve().parent
_CACHE_DF: Optional[pd.DataFrame] = None

# 수량 단위 (가격탄력성 등 데이터 준비용)
QUANTITY_UNIT = "대"

# 배포 시 02.Database for dashboard 우선 사용 (Hugging Face 등에서 설정)
def _use_dashboard_sql_first() -> bool:
    v = os.environ.get("USE_DASHBOARD_SQL", "").strip().lower()
    return v in ("1", "true", "yes", "on")


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
    """현재 데이터가 어디서 로드되는지 반환. 배포(USE_DASHBOARD_SQL=1)면 02 우선, 아니면 01.data 우선."""
    data_dir_01 = _MODEL_SERVER / "01.data"
    dashboard_dir = _MODEL_SERVER / "02.Database for dashboard"
    use_dashboard_first = _use_dashboard_sql_first()

    if use_dashboard_first:
        sql_files = sorted(dashboard_dir.glob("*.sql")) if dashboard_dir.exists() else []
        sql_dir = dashboard_dir
        if not sql_files:
            sql_files = sorted(data_dir_01.glob("*.sql")) if data_dir_01.exists() else []
            sql_dir = data_dir_01 if sql_files else dashboard_dir
    else:
        sql_files = sorted(data_dir_01.glob("*.sql")) if data_dir_01.exists() else []
        sql_dir = data_dir_01
        if not sql_files:
            sql_files = sorted(dashboard_dir.glob("*.sql")) if dashboard_dir.exists() else []
            sql_dir = dashboard_dir if sql_files else data_dir_01

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

    # 로컬: 01.data 우선. 배포(USE_DASHBOARD_SQL=1): 02.Database for dashboard 우선.
    data_dir_01 = _MODEL_SERVER / "01.data"
    dashboard_dir = _MODEL_SERVER / "02.Database for dashboard"
    use_dashboard_first = _use_dashboard_sql_first()

    if use_dashboard_first:
        sql_files = sorted(dashboard_dir.glob("*.sql")) if dashboard_dir.exists() else []
        sql_dir = dashboard_dir
        if not sql_files:
            sql_files = sorted(data_dir_01.glob("*.sql")) if data_dir_01.exists() else []
            sql_dir = data_dir_01 if sql_files else dashboard_dir
    else:
        sql_files = sorted(data_dir_01.glob("*.sql")) if data_dir_01.exists() else []
        sql_dir = data_dir_01
        if not sql_files:
            sql_files = sorted(dashboard_dir.glob("*.sql")) if dashboard_dir.exists() else []
            sql_dir = dashboard_dir if sql_files else data_dir_01

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
        dashboard_dir = _MODEL_SERVER / "02.Database for dashboard"
        print(
            f"[load_sales_data] 데이터 없음. 시도 경로: "
            f"01.data={data_dir_01.exists()}, "
            f"02.Database for dashboard={dashboard_dir.exists()}, "
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

