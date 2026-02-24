"""
매출 박스 · 매출 대시보드 백엔드 데이터
- 모델 서버 SQL 파일(01~10) 우선, 없으면 CSV 기반 스토어별 total_sales 집계
- FastAPI /api/sales-summary, /api/sales-box 에서 사용 (대시보드와 동일 데이터 소스)

================================================================================
[매출대시보드 개발 가이드]
- 매출대시보드 관련 로직 수정은 이 파일(Sales analysis.py)에 반영합니다.
- 추가/변경 시 위 규칙을 따르고, 변경 이력을 이 주석 블록에 기록해 주세요.
[변경이력] get_sales_by_city() 추가 - 도시별 연간 매출 (지역별 매출 바차트용)
[변경이력] get_sales_by_store() 추가 - Store_Name별 연간 매출 (매장별 바차트용)
[변경이력] get_sales_by_store_by_year() 추가 - Store_Name별 연도별 매출 (연도별 그룹 바차트용)
[변경이력] Apple 공통 접두사 제거 (_strip_apple_prefix) - Store_Name 표시 시 "Apple "/"애플 " 삭제
[변경이력] get_sales_by_store_quarterly() 추가 - 특정 스토어 3개월 단위 매출 (스캐터·라인 차트용)
[변경이력] get_sales_by_store_quarterly_by_category() 추가 - 특정 스토어 카테고리별 3개월 단위 매출 (카테고리별 분기 추이 차트용)
[변경이력] get_store_performance_grade() 추가 - [3.4.1] 매장 등급 및 달성률 분석 (목표 대비 달성률, S/A/C 등급, 등급 분포)
================================================================================

----------------------------------------------------------------------
[매출 대시보드 · Sales analysis.py 연동 맵] (수정 시 참고)
----------------------------------------------------------------------
프론트엔드: web-development/frontend/app/sales/page.tsx (매출 대시보드)
백엔드 API: web-development/backend/main.py 가 이 파일의 함수를 import하여 사용.

  API 엔드포인트                    | Sales analysis.py 함수              | 용도
  ---------------------------------|--------------------------------------|------------------------------------------
  GET /api/sales-summary            | get_store_sales_summary()            | 전체 합계, 연도별 매출, Top스토어, 국가/도시/매장별
  GET /api/sales-box                | get_sales_box_value()               | 메인 페이지 매출 박스 숫자
  GET /api/sales-by-country-category| get_sales_by_country_category(country)| 국가 선택 시 카테고리별 매출
  GET /api/sales-by-store           | get_sales_by_store(country)         | 국가 선택 시 매장별 바차트
                                   | get_sales_by_store_by_year(country)  | 매장별 연도별 (동일 응답)
  GET /api/sales-by-store-quarterly| get_sales_by_store_quarterly(store, country)| 매장 클릭 시 분기별 스캐터·라인
  GET /api/store-performance-grade  | get_store_performance_grade()            | [3.4.1] 매장 등급·달성률·등급 분포(파이 차트)

  데이터 소스: _get_df() → load_sales_dataframe (model-server/load_sales_data.py) → SQL(01~10) 또는 CSV.
  새 함수 추가 시: backend/main.py 에서 getattr(_sales_module, "함수명", None) 등록 후 새 라우트 추가.
----------------------------------------------------------------------

[모듈화] 본 파일은 load_sales_data.py 만 참조하여 데이터를 읽습니다.
- _get_df() 가 load_sales_dataframe() 을 호출 → SQL(01.data / 02.Database for dashboard) 또는 CSV.
- 독립된 if문: Import 성공/실패 분리 처리.
----------------------------------------------------------------------
"""

import re
import sys
import importlib.util
import pandas as pd
from pathlib import Path

# 모델 서버 루트 (load_sales_data.py 위치)
_MODEL_SERVER = Path(__file__).resolve().parent.parent
if str(_MODEL_SERVER) not in sys.path:
    sys.path.insert(0, str(_MODEL_SERVER))
# load_sales_data 참조 (실패 시 _load_sales_dataframe=None, 독립된 if문으로 분기)
_load_sales_dataframe = None
try:
    from load_sales_data import load_sales_dataframe as _load_sales_dataframe
except ImportError:
    _load_sales_dataframe = None

# 예측 모델(ARIMA) 로드 - 2025년 매출 예상에 사용
_get_sales_quantity_forecast = None
_pred_path = _MODEL_SERVER / "03.prediction model" / "prediction model.py"
if _pred_path.exists():
    try:
        _spec = importlib.util.spec_from_file_location("prediction_model", _pred_path)
        _pred_mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_pred_mod)
        _get_sales_quantity_forecast = getattr(_pred_mod, "get_sales_quantity_forecast", None)
    except Exception:
        pass


def _get_df():
    """SQL 우선, 없으면 None."""
    if _load_sales_dataframe is None:
        return None
    return _load_sales_dataframe()


def _strip_apple_prefix(s: str) -> str:
    """스토어명에서 공통 접두사 'Apple '/ '애플 ' 제거"""
    if not s or not isinstance(s, str):
        return s
    t = s.strip()
    if t.lower().startswith("apple "):
        return t[6:].strip()
    if t.startswith("애플 "):
        return t[3:].strip()
    return t


def _strip_apple_store_prefix(s: str) -> str:
    """스토어명에서 'Apple Store ' 또는 'Apple ' 제거 (분기별 매칭용). 'Apple Store SoHo' → 'SoHo'."""
    if not s or not isinstance(s, str):
        return s
    t = s.strip()
    if t.lower().startswith("apple store "):
        return t[12:].strip()
    if t.lower().startswith("apple "):
        return t[6:].strip()
    if t.startswith("애플 "):
        return t[3:].strip()
    return t


def get_store_sales_amounts():
    """
    스토어별 판매 금액 (2020~2024). 모델 서버 SQL(01~10) 또는 CSV와 연동.
    반환: [{"store_id": "ST-10", "city": "...", "country": "...", "total_sales": n}, ...]
    """
    df = _get_df()
    if df is None or df.empty:
        return []
    if "store_id" not in df.columns or "total_sales" not in df.columns:
        return []
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    if "City" not in df.columns or "Country" not in df.columns:
        return []
    # store_name은 UI/API에서 store_id로 통일 (응답에서 제거)
    agg = df.groupby(["store_id", "City", "Country"]).agg(
        total_sales=("total_sales", "sum")
    ).reset_index()
    result = []
    for _, row in agg.iterrows():
        result.append({
            "store_id": str(row["store_id"]).strip(),
            "city": str(row["City"]).strip() if pd.notna(row["City"]) else "",
            "country": str(row["Country"]).strip() if pd.notna(row["Country"]) else "",
            "total_sales": int(round(float(row["total_sales"]), 0)),
        })
    return result


def get_store_sales_by_year(store_id: str = None):
    """
    스토어별 연도별 판매 금액. 모델 서버 SQL/CSV와 연동.
    store_id가 없으면 전체 스토어, 있으면 스토어만.
    반환: [{"store_id": "ST-10", "city": "...", "country": "...", "year": 2023, "total_sales": n}, ...]
    """
    df = _get_df()
    if df is None or df.empty:
        return []
    if "store_id" not in df.columns or "total_sales" not in df.columns:
        return []
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    if store_id:
        df = df[df["store_id"].astype(str).str.strip() == str(store_id).strip()]
    if df.empty:
        return []
    if "City" not in df.columns or "Country" not in df.columns:
        return []
    agg = df.groupby(["store_id", "City", "Country", "year"]).agg(
        total_sales=("total_sales", "sum")
    ).reset_index()
    result = []
    for _, row in agg.iterrows():
        result.append({
            "store_id": str(row["store_id"]).strip(),
            "city": str(row["City"]).strip() if pd.notna(row["City"]) else "",
            "country": str(row["Country"]).strip() if pd.notna(row["Country"]) else "",
            "year": int(row["year"]),
            "total_sales": int(round(float(row["total_sales"]), 0)),
        })
    return result


def get_sales_by_store(country: str = None):
    """
    Store_Name별 연간 매출 (2020~2024). Store_Name 기준 집계.
    country 지정 시 해당 국가 스토어만.
    반환: [{"store_name": "Apple Store Paris", "total_sales": n}, ...]
    """
    df = _get_df()
    if df is None or df.empty:
        return []
    if "store_id" not in df.columns or "total_sales" not in df.columns:
        return []
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    if country and "Country" in df.columns:
        df = df[df["Country"].astype(str).str.strip() == str(country).strip()]
    if df.empty:
        return []
    name_col = "Store_Name" if "Store_Name" in df.columns else ("store_name" if "store_name" in df.columns else None)
    group_col = name_col if name_col else "store_id"
    agg = df.groupby(group_col).agg(total_sales=("total_sales", "sum")).reset_index()
    result = [
        {"store_name": _strip_apple_prefix(str(row[group_col]).strip()) or "(미지정)", "total_sales": int(round(float(row["total_sales"]), 0))}
        for _, row in agg.iterrows()
    ]
    result.sort(key=lambda x: -x["total_sales"])
    return result[:50]


def get_sales_by_store_by_year(country: str = None):
    """
    Store_Name별 연도별 매출 (2020~2024). country 지정 시 해당 국가 스토어만.
    반환: [{"store_name": "Apple Store Paris", "year": 2023, "total_sales": n}, ...]
    """
    df = _get_df()
    if df is None or df.empty:
        return []
    if "store_id" not in df.columns or "total_sales" not in df.columns:
        return []
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    if country and "Country" in df.columns:
        df = df[df["Country"].astype(str).str.strip() == str(country).strip()]
    if df.empty:
        return []
    name_col = "Store_Name" if "Store_Name" in df.columns else ("store_name" if "store_name" in df.columns else None)
    group_col = name_col if name_col else "store_id"
    agg = df.groupby([group_col, "year"]).agg(total_sales=("total_sales", "sum")).reset_index()
    result = [
        {"store_name": _strip_apple_prefix(str(row[group_col]).strip()) or "(미지정)", "year": int(row["year"]), "total_sales": int(round(float(row["total_sales"]), 0))}
        for _, row in agg.iterrows()
    ]
    # Top 15 stores by total sales (for chart readability)
    by_store = {}
    for r in result:
        by_store[r["store_name"]] = by_store.get(r["store_name"], 0) + r["total_sales"]
    top_stores = sorted(by_store.keys(), key=lambda k: -by_store[k])[:15]
    return [r for r in result if r["store_name"] in top_stores]


def _normalize_store_name_for_match(s: str) -> str:
    """매칭 시 공백 정규화: '소호 (SoHo)' ↔ '소호(SoHo)' 호환."""
    if not s or not isinstance(s, str):
        return ""
    t = re.sub(r"\s*\(\s*", "(", re.sub(r"\s*\)\s*", ")", s.strip()))
    return t


def _extract_store_name_for_match(store_name: str) -> list:
    """API로 전달된 store_name에서 매칭에 사용할 후보 목록 생성. '소호(SoHo)' → ['SoHo', '소호(SoHo)'], 'Apple SoHo', 'Store SoHo' 포함."""
    s = (store_name or "").strip()
    if not s:
        return []
    candidates = [s]
    # 공백 포함/미포함 변형 (괄호 주변)
    norm = _normalize_store_name_for_match(s)
    if norm and norm not in candidates:
        candidates.append(norm)
    # 괄호 안 영문 추출: "소호(SoHo)" → "SoHo"
    if "(" in s and ")" in s:
        m = re.search(r"\(([^)]+)\)", s)
        if m:
            inner = m.group(1).strip()
            if inner and inner not in candidates:
                candidates.insert(0, inner)
    # "Apple SoHo", "Apple Store SoHo" 형태도 후보에 추가 (DB에 저장 형태와 매칭)
    if not s.lower().startswith("apple "):
        if "Apple " + s not in candidates:
            candidates.append("Apple " + s)
        if not s.lower().startswith("store "):
            if "Store " + s not in candidates:
                candidates.append("Store " + s)
    # Centre/Center 철자 변형 (e.g. Rideau Centre ↔ Rideau Center)
    if "Centre" in s:
        alt = s.replace("Centre", "Center")
        if alt not in candidates:
            candidates.append(alt)
    if "Center" in s:
        alt = s.replace("Center", "Centre")
        if alt not in candidates:
            candidates.append(alt)
    return candidates


def get_sales_by_store_quarterly(store_name: str, country: str = None):
    """
    특정 스토어의 3개월 단위 매출 (2020~2024).
    store_name: _strip_apple_prefix 적용된 스토어명 또는 "소호(SoHo)" 형식
    country: 국가 필터 (선택)
    반환: [{"period": "2020-Q1", "year": 2020, "quarter": 1, "total_sales": n}, ...]
    """
    df = _get_df()
    if df is None or df.empty:
        return []
    date_col = "sale_date" if "sale_date" in df.columns else ("Sale_Date" if "Sale_Date" in df.columns else None)
    if not date_col or "total_sales" not in df.columns:
        return []
    store_name = (store_name or "").strip()
    if not store_name:
        return []
    candidates = _extract_store_name_for_match(store_name)
    if not candidates:
        return []
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["_sale_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["_sale_date"])
    df["year"] = df["_sale_date"].dt.year
    df["quarter"] = df["_sale_date"].dt.quarter
    df = df[df["year"].between(2020, 2024)]
    if country and "Country" in df.columns:
        country_str = str(country).strip().lower()
        df = df[df["Country"].astype(str).str.strip().str.lower() == country_str]
    name_col = "Store_Name" if "Store_Name" in df.columns else ("store_name" if "store_name" in df.columns else None)
    if not name_col:
        return []
    # store_name 매칭: raw, strip Apple/Apple Store, 공백 정규화, 대소문자 무시
    def _match(n):
        r = str(n).strip() if pd.notna(n) else ""
        if not r:
            return False
        stripped = _strip_apple_prefix(r)
        stripped_store = _strip_apple_store_prefix(r)
        r_norm = _normalize_store_name_for_match(r)
        stripped_norm = _normalize_store_name_for_match(stripped)
        stripped_store_norm = _normalize_store_name_for_match(stripped_store)
        for c in candidates:
            c_norm = _normalize_store_name_for_match(c)
            # 정확 일치
            if r == c or stripped == c or stripped_store == c:
                return True
            # 정규화 후 일치
            if r_norm == c_norm or stripped_norm == c_norm or stripped_store_norm == c_norm:
                return True
            # 대소문자 무시 (소호(SoHo) ↔ Apple SoHo 등)
            if r_norm.lower() == c_norm.lower() or stripped_norm.lower() == c_norm.lower() or stripped_store_norm.lower() == c_norm.lower():
                return True
            # 후보가 DB 스토어명에 포함된 경우 (e.g. Union Square ↔ Apple Store Union Square)
            if c and (c in r or c in stripped or c in stripped_store):
                return True
            if c_norm and (c_norm in r_norm or c_norm in stripped_norm or c_norm in stripped_store_norm):
                return True
        return False

    df = df[df[name_col].apply(_match)]
    if df.empty:
        return []
    agg = df.groupby(["year", "quarter"]).agg(total_sales=("total_sales", "sum")).reset_index()
    result = []
    for _, row in agg.iterrows():
        y, q = int(row["year"]), int(row["quarter"])
        result.append({
            "period": f"{y}-Q{q}",
            "year": y,
            "quarter": q,
            "total_sales": int(round(float(row["total_sales"]), 0)),
        })
    result.sort(key=lambda x: (x["year"], x["quarter"]))
    return result


def get_sales_by_store_quarterly_by_category(store_name: str, country: str = None):
    """
    특정 스토어의 카테고리별 3개월 단위 매출 (2020~2024).
    store_name, country: get_sales_by_store_quarterly 와 동일.
    반환: [{"period": "2020-Q1", "year": 2020, "quarter": 1, "category": "iPhone", "total_sales": n}, ...]
    - 카테고리 컬럼이 없으면 분기별 합계를 "(전체)" 한 개 카테고리로 반환 (그래프가 보이도록 폴백)
    """
    df = _get_df()
    if df is None or df.empty:
        return []
    date_col = "sale_date" if "sale_date" in df.columns else ("Sale_Date" if "Sale_Date" in df.columns else None)
    if not date_col or "total_sales" not in df.columns:
        return []
    # 데이터 컬럼: category_name, category_id (SQL/load_sales_data 기준)
    cat_col = "category_name" if "category_name" in df.columns else ("category_id" if "category_id" in df.columns else ("Category" if "Category" in df.columns else ("category" if "category" in df.columns else None)))
    store_name = (store_name or "").strip()
    if not store_name:
        return []
    candidates = _extract_store_name_for_match(store_name)
    if not candidates:
        return []
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["_sale_date"] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=["_sale_date"])
    df["year"] = df["_sale_date"].dt.year
    df["quarter"] = df["_sale_date"].dt.quarter
    df = df[df["year"].between(2020, 2024)]
    if country and "Country" in df.columns:
        country_str = str(country).strip().lower()
        df = df[df["Country"].astype(str).str.strip().str.lower() == country_str]
    name_col = "Store_Name" if "Store_Name" in df.columns else ("store_name" if "store_name" in df.columns else None)
    if not name_col:
        return []

    def _match_store(n):
        r = str(n).strip() if pd.notna(n) else ""
        if not r:
            return False
        stripped = _strip_apple_prefix(r)
        stripped_store = _strip_apple_store_prefix(r)
        r_norm = _normalize_store_name_for_match(r)
        stripped_norm = _normalize_store_name_for_match(stripped)
        stripped_store_norm = _normalize_store_name_for_match(stripped_store)
        for c in candidates:
            c_norm = _normalize_store_name_for_match(c)
            if r == c or stripped == c or stripped_store == c:
                return True
            if r_norm == c_norm or stripped_norm == c_norm or stripped_store_norm == c_norm:
                return True
            if r_norm.lower() == c_norm.lower() or stripped_norm.lower() == c_norm.lower() or stripped_store_norm.lower() == c_norm.lower():
                return True
            if c and (c in r or c in stripped or c in stripped_store):
                return True
            if c_norm and (c_norm in r_norm or c_norm in stripped_norm or c_norm in stripped_store_norm):
                return True
        return False

    df = df[df[name_col].apply(_match_store)]
    if df.empty:
        return []

    if not cat_col:
        # 카테고리 컬럼 없음: 분기별 합계만 "(전체)" 로 반환 (그래프 표시용 폴백)
        agg = df.groupby(["year", "quarter"]).agg(total_sales=("total_sales", "sum")).reset_index()
        result = []
        for _, row in agg.iterrows():
            y, q = int(row["year"]), int(row["quarter"])
            result.append({
                "period": f"{y}-Q{q}",
                "year": y,
                "quarter": q,
                "category": "(전체)",
                "total_sales": int(round(float(row["total_sales"]), 0)),
            })
        result.sort(key=lambda x: (x["year"], x["quarter"]))
        return result

    df[cat_col] = df[cat_col].astype(str).str.strip().replace("", "(미분류)")
    agg = df.groupby(["year", "quarter", cat_col]).agg(total_sales=("total_sales", "sum")).reset_index()
    result = []
    for _, row in agg.iterrows():
        y, q = int(row["year"]), int(row["quarter"])
        result.append({
            "period": f"{y}-Q{q}",
            "year": y,
            "quarter": q,
            "category": str(row[cat_col]).strip() or "(미분류)",
            "total_sales": int(round(float(row["total_sales"]), 0)),
        })
    result.sort(key=lambda x: (x["year"], x["quarter"], x["category"]))
    return result


def get_sales_by_city():
    """
    도시별 연간 매출 (2020~2024). City+Country 기준 집계.
    반환: [{"city": "Paris", "country": "France", "total_sales": n}, ...]
    - FastAPI GET /api/sales-summary 응답의 sales_by_city에 사용
    - 매출대시보드 지역(국가)별 매출 → 도시별 바차트
    """
    stores = get_store_sales_amounts()
    if not stores:
        return []
    by_city = {}
    for row in stores:
        city = str(row.get("city", "")).strip() or ""
        country = str(row.get("country", "")).strip() or ""
        if not city and not country:
            continue
        key = (city or "(미지정)", country or "(미지정)")
        by_city[key] = by_city.get(key, 0) + int(row.get("total_sales", 0) or 0)
    return [
        {"city": k[0], "country": k[1], "total_sales": int(v)}
        for k, v in sorted(by_city.items(), key=lambda x: -x[1])
    ]


def get_sales_by_country():
    """
    국가별 전체 매출 (2020~2024). 모든 스토어 기준 집계 (제한 없음).
    반환: [{"country": "United States", "total_sales": n}, ...]
    - FastAPI GET /api/sales-summary 응답의 sales_by_country에 사용
    """
    stores = get_store_sales_amounts()
    if not stores:
        return []
    by_country = {}
    for row in stores:
        c = str(row.get("country", "")).strip() or ""
        if c:
            by_country[c] = by_country.get(c, 0) + int(row.get("total_sales", 0) or 0)
    return [
        {"country": c, "total_sales": int(s)}
        for c, s in sorted(by_country.items(), key=lambda x: -x[1])
    ]


def get_sales_by_country_category(country: str = None):
    """
    국가별 카테고리별 매출 (2020~2024).
    - country가 없으면: [{"country": "...", "total_sales": n}, ...] (국가 목록)
    - country가 있으면: [{"category": "...", "total_sales": n}, ...] (해당 국가의 카테고리별 매출)
    """
    df = _get_df()
    if df is None or df.empty or "total_sales" not in df.columns or "Country" not in df.columns:
        return []
    # 데이터 컬럼: category_name, category_id
    cat_col = "category_name" if "category_name" in df.columns else ("category_id" if "category_id" in df.columns else None)
    if not cat_col:
        return []
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    df["Country"] = df["Country"].astype(str).str.strip()
    df[cat_col] = df[cat_col].astype(str).str.strip()

    if country:
        country_str = str(country).strip()
        sub = df[df["Country"] == country_str]
        if sub.empty:
            return []
        agg = sub.groupby(cat_col)["total_sales"].sum().reset_index()
        return [
            {"category": str(row[cat_col]).strip() or "(미분류)", "total_sales": int(round(float(row["total_sales"]), 0))}
            for _, row in agg.iterrows()
        ]
    # 전체 국가별 매출 (카테고리 집계용)
    agg = df.groupby("Country")["total_sales"].sum().reset_index()
    return [
        {"country": str(row["Country"]).strip(), "total_sales": int(round(float(row["total_sales"]), 0))}
        for _, row in agg.iterrows()
        if str(row["Country"]).strip()
    ]


def get_sales_by_year():
    """
    연도별 전체 매출 (2020~2024). 모델 서버 SQL/CSV와 연동.
    반환: [{"year": 2020, "total_sales": n}, {"year": 2021, "total_sales": n}, ...]
    - FastAPI GET /api/sales-summary 응답의 sales_by_year에 사용
    """
    by_year = get_store_sales_by_year()
    if not by_year:
        return [{"year": y, "total_sales": 0} for y in range(2020, 2025)]
    agg = {}
    for row in by_year:
        y = row["year"]
        agg[y] = agg.get(y, 0) + row["total_sales"]
    return [{"year": y, "total_sales": int(agg.get(y, 0))} for y in range(2020, 2025)]


def _linear_predict_sales(years, sales_list, target_year):
    """선형 추세로 target_year 매출 예측."""
    if not years or not sales_list or len(years) != len(sales_list):
        return 0.0
    n = len(years)
    sum_x = sum(years)
    sum_y = sum(sales_list)
    sum_xy = sum(y * s for y, s in zip(years, sales_list))
    sum_xx = sum(y * y for y in years)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return sum_y / n
    a = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - a * sum_x) / n
    return a * target_year + b


def get_predicted_sales_2025():
    """
    예측 모델(ARIMA)을 이용한 2025년 매출 예상.
    - prediction model의 predicted_quantity_2025 × (전체 매출/전체 수량) 비율로 환산
    - 예측 모델 미사용 시 연도별 매출 선형 추세로 예측
    반환: {"predicted_sales_2025": int, "method": "arima" | "linear_trend"}
    """
    sales_by_year = get_sales_by_year()
    total_sales = sum(s["total_sales"] for s in sales_by_year)
    years = [s["year"] for s in sales_by_year]
    sales_list = [s["total_sales"] for s in sales_by_year]

    # 1) 예측 모델로 2025 수량 예측 → 매출 환산
    if _get_sales_quantity_forecast is not None:
        try:
            fc = _get_sales_quantity_forecast()
            pred_qty = fc.get("predicted_quantity_2025", 0) or 0
            total_qty = fc.get("total_quantity_2020_2024", 0) or 0
            if pred_qty > 0 and total_qty > 0 and total_sales > 0:
                avg_price = total_sales / total_qty
                pred_sales = max(0, int(round(pred_qty * avg_price)))
                return {"predicted_sales_2025": pred_sales, "method": fc.get("method", "arima")}
        except Exception:
            pass

    # 2) 선형 추세 폴백
    pred = _linear_predict_sales(years, sales_list, 2025)
    return {"predicted_sales_2025": max(0, int(round(pred))), "method": "linear_trend"}


def get_store_performance_grade():
    """
    [3.4.1 매장 등급 및 달성률 분석]
    - 매장별 총 매출 집계 (Country, Store_Name)
    - 연간 예측(2025)을 기반으로 매장당 목표 배분 후 달성률 산출
    - 성과 등급: S(>=100%), A(80%~100%), C(기본)
    반환: {
        "store_performance": [{"country", "store_name", "total_sales", "achievement_rate", "grade", "target_annual"}, ...],
        "grade_distribution": [{"grade": "S", "count": n, "pct": float}, ...],  # 파이 차트용
        "annual_forecast_revenue": int
    }
    """
    df = _get_df()
    if df is None or df.empty or "total_sales" not in df.columns:
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": 0}
    forecast = get_predicted_sales_2025()
    annual_forecast_revenue = forecast.get("predicted_sales_2025", 0) or 0
    if annual_forecast_revenue <= 0:
        annual_forecast_revenue = df["total_sales"].sum()  # 폴백: 실적 합계를 목표로

    country_col = "Country" if "Country" in df.columns else None
    name_col = "Store_Name" if "Store_Name" in df.columns else ("store_name" if "store_name" in df.columns else None)
    if not name_col:
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": int(annual_forecast_revenue)}
    group_cols = [name_col]
    if country_col:
        group_cols.insert(0, country_col)

    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    store_perf = df.groupby(group_cols)["total_sales"].sum().reset_index()
    if store_perf.empty:
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": int(annual_forecast_revenue)}

    n_stores = store_perf[name_col].nunique()
    if n_stores <= 0:
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": int(annual_forecast_revenue)}
    # 매장당 연간 목표 (연간 예측 / 매장 수) → 달성률 = (매장 실적 / 목표) * 100
    target_annual = (annual_forecast_revenue / 12) / n_stores * 12 if n_stores else 0
    if target_annual <= 0:
        target_annual = 1.0
    store_perf["target_annual"] = target_annual
    store_perf["Achievement_Rate"] = (store_perf["total_sales"] / target_annual) * 100.0
    store_perf["Grade"] = "C"
    store_perf.loc[store_perf["Achievement_Rate"] >= 100, "Grade"] = "S"
    store_perf.loc[(store_perf["Achievement_Rate"] >= 80) & (store_perf["Achievement_Rate"] < 100), "Grade"] = "A"

    store_performance = []
    for _, row in store_perf.iterrows():
        store_performance.append({
            "country": str(row[country_col]).strip() if country_col and pd.notna(row.get(country_col)) else "",
            "store_name": _strip_apple_prefix(str(row[name_col]).strip()) if pd.notna(row[name_col]) else "",
            "total_sales": int(round(float(row["total_sales"]), 0)),
            "target_annual": int(round(float(row["target_annual"]), 0)),
            "achievement_rate": round(float(row["Achievement_Rate"]), 1),
            "grade": str(row["Grade"]).strip(),
        })

    grade_counts = store_perf["Grade"].value_counts()
    total = len(store_perf)
    grade_distribution = [
        {"grade": g, "count": int(grade_counts.get(g, 0)), "pct": round((grade_counts.get(g, 0) / total) * 100.0, 1)}
        for g in ("S", "A", "C")
    ]

    return {
        "store_performance": store_performance,
        "grade_distribution": grade_distribution,
        "annual_forecast_revenue": int(annual_forecast_revenue),
    }


def get_store_sales_summary():
    """
    매출 대시보드용: 전체 요약, 연도별 매출(2020~2024 + 2025 예상), 스토어별 판매 금액 Top N
    반환: {"total_sum": 전체합계, "store_count": 스토어수, "sales_by_year": [...], "predicted_sales_2025": int, "forecast_method": str, "stores": [...], "top_stores": [...]}
    - FastAPI GET /api/sales-summary 응답에 그대로 사용
    """
    stores = get_store_sales_amounts()
    sales_by_year = get_sales_by_year()
    forecast_2025 = get_predicted_sales_2025()
    pred_sales = forecast_2025.get("predicted_sales_2025", 0)
    forecast_method = forecast_2025.get("method", "linear_trend")
    # sales_by_year에 2025 예상 추가
    sales_by_year_with_2025 = sales_by_year + [{"year": 2025, "total_sales": pred_sales, "is_forecast": True}]
    sales_by_country = get_sales_by_country()
    if not stores:
        return {
            "total_sum": 0,
            "store_count": 0,
            "sales_by_year": sales_by_year_with_2025,
            "predicted_sales_2025": pred_sales,
            "forecast_method": forecast_method,
            "stores": [],
            "top_stores": [],
            "sales_by_country": sales_by_country,
            "sales_by_city": [],
            "sales_by_store": [],
            "sales_by_store_by_year": [],
        }
    total_sum = sum(s["total_sales"] for s in stores)
    sorted_stores = sorted(stores, key=lambda x: x["total_sales"], reverse=True)
    sales_by_city = get_sales_by_city()
    sales_by_store = get_sales_by_store()
    sales_by_store_by_year = get_sales_by_store_by_year()
    return {
        "total_sum": total_sum,
        "store_count": len(stores),
        "sales_by_year": sales_by_year_with_2025,
        "predicted_sales_2025": pred_sales,
        "forecast_method": forecast_method,
        "stores": sorted_stores,
        "top_stores": sorted_stores[:20],
        "sales_by_country": sales_by_country,
        "sales_by_city": sales_by_city,
        "sales_by_store": sales_by_store,
        "sales_by_store_by_year": sales_by_store_by_year,
    }


def get_sales_box_value():
    """
    메인 페이지 매출 박스에 표시할 값 (2020~2024 전체 매출 합계)
    반환: int (전체 합계, 데이터 없으면 0)
    - FastAPI GET /api/sales-box 응답에 사용 가능
    """
    summary = get_store_sales_summary()
    return summary["total_sum"]


if __name__ == "__main__":
    summary = get_store_sales_summary()
    print(f"전체 판매 금액: {summary['total_sum']:,}원")
    print(f"스토어 수: {summary['store_count']}")
    print("\n--- Top 10 스토어별 판매 금액 ---")
    for i, s in enumerate(summary["top_stores"][:10], 1):
        print(f"{i}. {s['store_id']} ({s['city']}) : {s['total_sales']:,}")
