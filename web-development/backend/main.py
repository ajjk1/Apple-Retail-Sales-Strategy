"""
Apple Retail API — Hugging Face Spaces 백엔드 + Vercel 프론트 연동

[1] 모듈화
- prediction model, Sales analysis, Inventory Optimization, Real-time dashboard 는 모두
  load_sales_data.py 의 load_sales_dataframe() 만 참조하여 데이터를 읽습니다.
- main.py 는 위 모듈들을 importlib 로 동적 로드한 뒤, 각 모듈의 함수를 FastAPI 라우트에서 호출합니다.

[2] Main 통합
- FastAPI(uvicorn) 로 서버 구동. 각 분석 모델의 결과를 반환하는 API 엔드포인트를 제공합니다.
- /api/apple-data, /api/city-category-pie, /api/sales-summary, /api/safety-stock 등
  모든 엔드포인트는 main.py 에서 해당 모듈 함수를 호출하여 JSON 응답을 반환합니다.

[3] CORS 설정
- Vercel 도메인(https://apple-retail-sales-strategy-k1kp94g4f-ajjk1.vercel.app/ 등)에서
  브라우저가 이 API에 접근할 수 있도록 CORSMiddleware 로 allow_origins·allow_origin_regex 설정.
- allow_credentials, allow_methods, allow_headers 도 허용하여 프론트-백 연동이 가능하도록 합니다.

[4] Hugging Face Spaces 실행
- Dockerfile 에서 uvicorn main:app --host 0.0.0.0 --port 7860 으로 기동합니다.
- 0.0.0.0 바인딩으로 외부에서 Space URL 로 접근 가능합니다.
"""

from fastapi import FastAPI, Request  # FastAPI 프레임워크를 불러옵니다.
from fastapi.middleware.cors import CORSMiddleware  # 다른 도메인(Next.js)의 접속을 허용하기 위해 불러옵니다.
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import HTMLResponse
import pandas as pd
from pathlib import Path
import importlib.util
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import types
import sqlite3
import csv
import io
import re
from typing import Any, Dict, List, Optional

# FastAPI 애플리케이션 객체 생성 (제목: Apple Retail API)
app = FastAPI(title="Apple Retail API")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MODEL_SERVER = _PROJECT_ROOT / "model-server"

# 한글 → 영문 매핑 (대시보드 한글 인식용)
_COUNTRY_KO_TO_EN = {
    "미국": "United States",
    "캐나다": "Canada",
    "멕시코": "Mexico",
    "콜롬비아": "Colombia",
    "영국": "United Kingdom",
    "프랑스": "France",
    "독일": "Germany",
    "오스트리아": "Austria",
    "스페인": "Spain",
    "이탈리아": "Italy",
    "네덜란드": "Netherlands",
    "중국": "China",
    "일본": "Japan",
    "한국": "South Korea",
    "대만": "Taiwan",
    "싱가포르": "Singapore",
    "태국": "Thailand",
    "아랍에미리트": "UAE",
    "호주": "Australia",
}
_CONTINENT_KO_TO_EN = {
    "북미": "North America",
    "남미": "South America",
    "유럽": "Europe",
    "아시아": "Asia",
    "중동": "Middle East",
    "오세아니아": "Oceania",
}


def _resolve_country_to_en(term: str) -> str:
    """한글 또는 영문 국가명 → 영문 (API 쿼리용)"""
    t = (term or "").strip()
    if not t:
        return t
    if t in _COUNTRY_KO_TO_EN:
        return _COUNTRY_KO_TO_EN[t]
    # 영문 변형 (Korea → South Korea 등)
    if t.lower() == "korea":
        return "South Korea"
    return t


def _resolve_continent_to_en(term: str) -> str:
    """한글 또는 영문 대륙명 → 영문 (API 쿼리용)"""
    t = (term or "").strip()
    if not t:
        return t
    return _CONTINENT_KO_TO_EN.get(t, t)

def _model_path(*candidates: str):
    """모델 서버 내 파일 경로 (폴더명 02.prediction model 등 지원)."""
    for name in candidates:
        p = _MODEL_SERVER / name
        if p.exists():
            return p
    return _MODEL_SERVER / candidates[0]


# -----------------------------
# [모듈 로드 순서] 1 → 2 → 3 → 4 → 5 (변경 금지. Real-time은 load_sales_data 이후 로드되어야 함)
# 1) load_sales_data  2) prediction model  3) Sales analysis  4) Inventory Optimization  5) Real-time dashboard
# -----------------------------
# 1) 모델 서버 load_sales_data.py 실행 → 연동 (우선)
#    - model-server/load_sales_data.py 가 있으면 로드하여 load_sales_dataframe, get_data_source_info 사용
#    - 대시보드 표시 데이터는 이 로더를 통해 01.data(SQL/CSV)에서 로드
# 2) 파일 없거나 실패 시 main.py 내장 로더 사용 (폴백)
# -----------------------------
_load_sales_data_file = _MODEL_SERVER / "load_sales_data.py"
load_sales_dataframe = None  # type: ignore
get_data_source_info = None  # type: ignore
_ld_module_obj = None

if _load_sales_data_file.exists():
    try:
        if str(_MODEL_SERVER) not in sys.path:
            sys.path.insert(0, str(_MODEL_SERVER))
        _ld_spec = importlib.util.spec_from_file_location("load_sales_data", _load_sales_data_file)
        _ld_module_obj = importlib.util.module_from_spec(_ld_spec)
        _ld_spec.loader.exec_module(_ld_module_obj)
        load_sales_dataframe = getattr(_ld_module_obj, "load_sales_dataframe", None)
        get_data_source_info = getattr(_ld_module_obj, "get_data_source_info", None)
        if load_sales_dataframe is not None:
            sys.modules["load_sales_data"] = _ld_module_obj
    except Exception as e:
        print(f"[Apple Retail API] load_sales_data.py 로드 실패: {e}")
        load_sales_dataframe = None
        get_data_source_info = None
        _ld_module_obj = None

# 내장 로더 (load_sales_data.py 미사용 시 또는 보조)
# -----------------------------

_LS_DATA_DIR: Optional[Path] = None
_LS_SQL_FILES: Optional[list[Path]] = None
_LS_CSV_CANDIDATES: Optional[list[Path]] = None
_ls_cache_df: Optional[pd.DataFrame] = None
_ls_cache_mtime: float = 0.0


def _ls_strip_wrapping_quotes(v):
    """문자열 양끝의 ' 또는 \" 를 제거하고 공백을 정리."""
    if v is None:
        return v
    if not isinstance(v, str):
        return v
    t = v.strip()
    if len(t) >= 2 and ((t[0] == "'" and t[-1] == "'") or (t[0] == '"' and t[-1] == '"')):
        t = t[1:-1].strip()
    return t


def _ls_normalize_text_columns(df: pd.DataFrame) -> pd.DataFrame:
    """SQL/CSV 로드 결과로 생길 수 있는 따옴표 포함 문자열을 정규화."""
    if df is None or df.empty:
        return df
    df = df.copy()
    obj_cols = df.select_dtypes(include=["object"]).columns
    for c in obj_cols:
        try:
            df[c] = df[c].map(_ls_strip_wrapping_quotes)
        except Exception:
            continue
    return df


def _ls_get_data_dir() -> Path: # 데이터 파일이 저장된 폴더 경로를 반환합니다.
    # 독립된 if문: 전역 변수를 호출하여 기존에 설정된 경로가 있는지 확인합니다.
    global _LS_DATA_DIR # 전역 변수 _LS_DATA_DIR을 사용합니다.
    
    # 독립된 if문: 이미 경로가 설정되어 있다면 중복 계산 없이 즉시 반환합니다.
    if _LS_DATA_DIR is not None: # 설정된 값이 존재한다면
        return _LS_DATA_DIR # 해당 경로를 그대로 반환합니다.

    # 독립된 if문: 현재 사용자님의 폴더 구조인 '01.data' 경로를 생성합니다.
    # 이미지 좌측 탐색기에 있는 "01.data" 폴더 이름을 정확히 입력합니다.
    target_path = _MODEL_SERVER / "01.data" # 루트 폴더 아래의 01.data 폴더를 가리킵니다.
    
    # 독립된 if문: 해당 폴더가 실제로 존재하는지 확인 후 변수에 할당합니다.
    if target_path.exists(): # 폴더가 존재한다면
        _LS_DATA_DIR = target_path # 해당 폴더를 데이터 디렉토리로 확정합니다.

    # 독립된 if문: 만약 폴더가 없다면 안전을 위해 루트(/code)를 기본값으로 설정합니다.
    if _LS_DATA_DIR is None: # 위에서 할당되지 않았다면
        _LS_DATA_DIR = _MODEL_SERVER # 루트 경로를 할당합니다.
        
    # 독립된 if문: 최종적으로 결정된 경로를 반환합니다.
    return _LS_DATA_DIR # 확정된 경로를 반환합니다.


def _ls_get_sql_files() -> list[Path]:
    """Apple_Retail_Sales_Dataset_Modified_01.sql ~ _10.sql 목록."""
    global _LS_SQL_FILES
    if _LS_SQL_FILES is not None:
        return _LS_SQL_FILES
    d = _ls_get_data_dir()
    _LS_SQL_FILES = [d / f"Apple_Retail_Sales_Dataset_Modified_{i:02d}.sql" for i in range(1, 11)]
    return _LS_SQL_FILES


def _ls_get_csv_candidates() -> list[Path]:
    """CSV 폴백 후보 경로."""
    global _LS_CSV_CANDIDATES
    if _LS_CSV_CANDIDATES is not None:
        return _LS_CSV_CANDIDATES
    d = _ls_get_data_dir()
    base = _MODEL_SERVER.parent
    _LS_CSV_CANDIDATES = [
        d / "Apple_Retail_Sales_Dataset_Modified.csv",
        d / "data_02_inventory_final.csv",
        base / "web-development" / "data_02_inventory_final.csv",
    ]
    return _LS_CSV_CANDIDATES


def _ls_parse_insert_values(content: str):
    """INSERT INTO sales_data (...) VALUES (row1), (row2), ... 에서 row 리스트 추출 (14컬럼)."""
    match = re.search(
        r"INSERT\s+INTO\s+sales_data\s+\([^)]+\)\s+VALUES\s+(.+)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return []
    values_part = match.group(1).strip().rstrip(");").strip()
    if not values_part:
        return []
    parts = re.split(r"\)\s*,\s*\(", values_part)
    rows = []
    for part in parts:
        part = part.strip().strip("()")
        if not part:
            continue
        try:
            reader = csv.reader(io.StringIO(part), quotechar="'", doublequote=True, skipinitialspace=True)
            row = next(reader)
            if len(row) >= 14:
                rows.append(tuple(row[:14]))
        except Exception:
            continue
    return rows


def _ls_source_mtime() -> float:
    """SQL 또는 CSV 최신 수정 시각."""
    mtimes: list[float] = []
    for p in _ls_get_sql_files():
        if p.exists():
            mtimes.append(p.stat().st_mtime)
    for p in _ls_get_csv_candidates():
        if p.exists():
            mtimes.append(p.stat().st_mtime)
    return max(mtimes, default=0.0)


def _ls_load_sales_dataframe(force_reload: bool = False) -> Optional[pd.DataFrame]:
    """
    [내장 폴백] SQL(01~10) 우선 로드, 없거나 비면 CSV 폴백.
    반환 DataFrame 컬럼:
    sale_id, sale_date, store_id, product_id, quantity, product_name,
    category_id, launch_date, price, category_name, store_name, city->City, country->Country,
    store_name->Store_Name, product_name->Product_Name, total_sales.
    """
    global _ls_cache_df, _ls_cache_mtime
    mtime = _ls_source_mtime()
    if not force_reload and mtime > 0 and _ls_cache_df is not None and _ls_cache_mtime == mtime:
        return _ls_cache_df.copy()
    _ls_cache_mtime = mtime

    cols = "sale_id,sale_date,store_id,product_id,quantity,product_name,category_id,launch_date,price,category_name,store_name,city,country,total_sales"
    sql_files = _ls_get_sql_files()

    # 1) SQL 로드 (in-memory sqlite)
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE sales_data (
            sale_id TEXT, sale_date TEXT, store_id TEXT, product_id TEXT, quantity INTEGER,
            product_name TEXT, category_id TEXT, launch_date TEXT, price REAL,
            category_name TEXT, store_name TEXT, city TEXT, country TEXT, total_sales REAL
        );
        """
    )
    placeholders = ",".join("?" * 14)
    insert_sql = f"INSERT INTO sales_data ({cols}) VALUES ({placeholders})"
    for path in sql_files:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            rows = _ls_parse_insert_values(text)
            if rows:
                conn.executemany(insert_sql, rows)
        except Exception:
            continue

    try:
        df = pd.read_sql("SELECT * FROM sales_data", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()

    if not df.empty:
        df.rename(
            columns={
                "city": "City",
                "country": "Country",
                "store_name": "Store_Name",
                "product_name": "Product_Name",
            },
            inplace=True,
        )
        df = _ls_normalize_text_columns(df)
        _ls_cache_df = df
        return df.copy()

    # 2) CSV 폴백
    _ls_cache_df = None
    for path in _ls_get_csv_candidates():
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df is None or df.empty:
            continue
        rename = {}
        for c in df.columns:
            if c == "product_name":
                rename[c] = "Product_Name"
            elif c == "city":
                rename[c] = "City"
            elif c == "country":
                rename[c] = "Country"
            elif c == "store_name":
                rename[c] = "Store_Name"
        if rename:
            df.rename(columns=rename, inplace=True)
        df = _ls_normalize_text_columns(df)
        _ls_cache_df = df
        return df.copy()

    return None


def _ls_get_data_source_info() -> Dict[str, Any]:
    """[내장 폴백] 대시보드 표시용: 현재 데이터 소스 정보."""
    d = _ls_get_data_dir()
    sql_files = _ls_get_sql_files()
    has_sql = any(p.exists() for p in sql_files)
    csv_path = next((p for p in _ls_get_csv_candidates() if p.exists()), None)
    return {
        "data_dir": str(d),
        "source": "sql" if has_sql else ("csv" if csv_path else "none"),
        "sql_file_count": sum(1 for p in sql_files if p.exists()),
        "csv_path": str(csv_path) if csv_path else None,
        "quantity_unit": "대",  # 수량 단위 (가격탄력성 데이터 준비용)
    }


# 모델 서버 파일 미사용 시: 내장 로더를 전역으로 지정 후 sys.modules 주입
if load_sales_dataframe is None:
    load_sales_dataframe = _ls_load_sales_dataframe
    get_data_source_info = _ls_get_data_source_info
if "load_sales_data" not in sys.modules or sys.modules["load_sales_data"] is None:
    _load_sales_data_shim = types.ModuleType("load_sales_data")
    _load_sales_data_shim.load_sales_dataframe = load_sales_dataframe
    _load_sales_data_shim.get_data_source_info = get_data_source_info
    sys.modules["load_sales_data"] = _load_sales_data_shim


# prediction model.py 로드 (수요 대시보드 · 파이차트 · 2025 수량 예측 연동)
# - get_sales_quantity_forecast: 2020~2024 기준 2025년 예측 판매 수량
# - get_predicted_demand_by_product: product_id별 2025년 예측 수요
get_city_category_pie_response = None
get_sale_id_pie_response = None
get_store_markers = None
get_store_category_pie_response = None
get_country_category_pie_response = None
get_country_stores_pie_response = None
get_continent_category_pie_response = None
get_continent_countries_pie_response = None
get_sales_quantity_forecast = None
get_predicted_demand_by_product = None
get_store_product_quantity_barchart_data = None
get_demand_dashboard_data = None
_prediction_model_file = _model_path("02.prediction model", "03.prediction model", "prediction model") / "prediction model.py"
if _prediction_model_file.exists():
    try:
        _spec = importlib.util.spec_from_file_location("prediction_model", _prediction_model_file)
        _pred_module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_pred_module)
        get_city_category_pie_response = _pred_module.get_city_category_pie_response
        get_sale_id_pie_response = getattr(_pred_module, "get_sale_id_pie_response", None)
        get_store_markers = getattr(_pred_module, "get_store_markers", None)
        get_store_category_pie_response = getattr(_pred_module, "get_store_category_pie_response", None)
        get_country_category_pie_response = getattr(_pred_module, "get_country_category_pie_response", None)
        get_country_stores_pie_response = getattr(_pred_module, "get_country_stores_pie_response", None)
        get_continent_category_pie_response = getattr(_pred_module, "get_continent_category_pie_response", None)
        get_continent_countries_pie_response = getattr(_pred_module, "get_continent_countries_pie_response", None)
        get_sales_quantity_forecast = getattr(_pred_module, "get_sales_quantity_forecast", None)
        get_predicted_demand_by_product = getattr(_pred_module, "get_predicted_demand_by_product", None)
        get_store_product_quantity_barchart_data = getattr(_pred_module, "get_store_product_quantity_barchart_data", None)
        get_demand_dashboard_data = getattr(_pred_module, "get_demand_dashboard_data", None)
    except Exception as e:
        print(f"[Apple Retail API] prediction model.py 로드 실패: {e}")

# Sales analysis.py 로드 (매출 박스 · 매출 대시보드, SQL 연동)
get_store_sales_summary = None
get_sales_box_value = None
get_sales_by_country_category = None
get_sales_by_store = None
get_sales_by_store_by_year = None
get_sales_by_store_quarterly = None
get_sales_by_store_quarterly_by_category = None
get_store_performance_grade = None
try: # 모듈 로드를 시도합니다.
    # 독립된 if문: 파일 경로가 유효한지 확인합니다.
    _sales_analysis_file = _model_path("04.Sales analysis") / "Sales analysis.py"
    if _sales_analysis_file.exists(): # 경로가 설정되어 있다면
        
        # [해결] 첫 번째는 별칭, 두 번째는 실제 파일 경로(_sales_analysis_file)를 넣어야 식이 완성됩니다.
        _spec_sales = importlib.util.spec_from_file_location("sales_analysis", _sales_analysis_file)  # 주소 정보를 추가했습니다.
        
        # 독립된 if문: 설계도(spec)가 성공적으로 만들어졌을 때만 다음 단계를 진행합니다.
        if _spec_sales is not None: # 설계도가 존재한다면
            _sales_module = importlib.util.module_from_spec(_spec_sales) # 모듈 객체를 생성합니다.
            _spec_sales.loader.exec_module(_sales_module) # 모듈 내용을 실제로 실행합니다.
            
            # 독립된 if문: 로드된 모듈에서 '일꾼(함수)'들을 하나씩 꺼내옵니다.
            get_store_sales_summary = getattr(_sales_module, "get_store_sales_summary", None)
            get_sales_box_value = getattr(_sales_module, "get_sales_box_value", None)
            get_sales_by_country_category = getattr(_sales_module, "get_sales_by_country_category", None)
            get_sales_by_store = getattr(_sales_module, "get_sales_by_store", None)
            get_sales_by_store_by_year = getattr(_sales_module, "get_sales_by_store_by_year", None)
            get_sales_by_store_quarterly = getattr(_sales_module, "get_sales_by_store_quarterly", None)
            get_sales_by_store_quarterly_by_category = getattr(_sales_module, "get_sales_by_store_quarterly_by_category", None)
            get_store_performance_grade = getattr(_sales_module, "get_store_performance_grade", None)
except Exception as e: # 독립된 if문: 만약 위 과정에서 에러가 나면 실행됩니다.
    print(f"[오류 발생] 매출 분석 파일 로드 실패: {e}") # 에러 메시지를 출력합니다.

# Inventory Optimization.py 로드 (안전재고 대시보드 연동)
# - get_safety_stock_summary: 재고 상태별 건수 (Status: Danger/Normal/Overstock)
# - get_demand_forecast_chart_data: 수요 예측 & 적정 재고 메인 차트
get_safety_stock_summary = None
get_demand_forecast_chart_data = None
get_sales_by_store_six_month = None
get_sales_by_product = None
get_kpi_summary = None
get_inventory_list = None
get_inventory_critical_alerts = None
get_inventory_health_for_recommendation = None
_inventory_file = _model_path("04.Sales analysis", "05.Inventory Optimization", "Inventory Optimization") / "Inventory Optimization.py"
if _inventory_file.exists():
    try:
        _spec_inv = importlib.util.spec_from_file_location("inventory_optimization", _inventory_file)
        _inv_module = importlib.util.module_from_spec(_spec_inv)
        _spec_inv.loader.exec_module(_inv_module)
        get_safety_stock_summary = getattr(_inv_module, "get_safety_stock_summary", None)
        get_demand_forecast_chart_data = getattr(_inv_module, "get_demand_forecast_chart_data", None)
        get_sales_by_store_six_month = getattr(_inv_module, "get_sales_by_store_six_month", None)
        get_sales_by_product = getattr(_inv_module, "get_sales_by_product", None)
        get_kpi_summary = getattr(_inv_module, "get_kpi_summary", None)
        get_inventory_list = getattr(_inv_module, "get_inventory_list", None)
        get_inventory_critical_alerts = getattr(_inv_module, "get_inventory_critical_alerts", None)
        get_inventory_health_for_recommendation = getattr(_inv_module, "get_inventory_health_for_recommendation", None)
    except Exception as e:
        print(f"[Apple Retail API] Inventory Optimization.py 로드 실패: {e}")

# -----------------------------------------------------------------------------
# Real-time execution and performance dashboard.py 로드 (추천·성장 전략 대시보드)
# 로드 순서: 1) load_sales_data → 2) prediction → 3) Sales analysis → 4) Inventory → 5) Real-time
# Real-time은 반드시 load_sales_data 이후에 로드됨. 로드 후 load_sales_dataframe을 주입해 동일 데이터 소스 보장.
# -----------------------------------------------------------------------------
get_recommendation_summary = None
get_store_recommendations = None
get_sales_forecast_chart_data = None
get_store_list_from_realtime = None
get_store_performance_grade_from_realtime = None
get_region_category_pivot_from_realtime = None
get_price_demand_correlation_from_realtime = None
get_user_personalized_recommendations_from_realtime = None
get_collab_filter_with_inventory_boost_from_realtime = None
get_customer_journey_funnel_from_realtime = None
get_funnel_stage_weight_from_realtime = None
_realtime_file = _model_path(
    "05.Real-time execution and performance dashboard",
    "06.Real-time execution and performance dashboard",
    "Real-time execution and performance dashboard",
) / "Real-time execution and performance dashboard.py"
if _realtime_file.exists():
    try:
        _spec_rt = importlib.util.spec_from_file_location("realtime_dashboard", _realtime_file)
        _rt_module = importlib.util.module_from_spec(_spec_rt)
        _spec_rt.loader.exec_module(_rt_module)
        # 성장 전략 대시보드: 동일한 load_sales_dataframe 사용 보장 (주입 순서: exec_module 직후)
        if load_sales_dataframe is not None:
            setattr(_rt_module, "load_sales_dataframe", load_sales_dataframe)
        # Real-time 제공 함수 등록 (순서 무관, getattr만 수행)
        get_recommendation_summary = getattr(_rt_module, "get_recommendation_summary", None)
        get_store_recommendations = getattr(_rt_module, "get_store_recommendations", None)
        get_sales_forecast_chart_data = getattr(_rt_module, "get_sales_forecast_chart_data", None)
        get_store_list_from_realtime = getattr(_rt_module, "get_store_list", None)
        get_store_performance_grade_from_realtime = getattr(_rt_module, "get_store_performance_grade", None)
        get_region_category_pivot_from_realtime = getattr(_rt_module, "get_region_category_pivot", None)
        get_price_demand_correlation_from_realtime = getattr(_rt_module, "get_price_demand_correlation", None)
        get_user_personalized_recommendations_from_realtime = getattr(_rt_module, "get_user_personalized_recommendations", None)
        get_collab_filter_with_inventory_boost_from_realtime = getattr(_rt_module, "get_collab_filter_with_inventory_boost", None)
        get_customer_journey_funnel_from_realtime = getattr(_rt_module, "get_customer_journey_funnel", None)
        get_funnel_stage_weight_from_realtime = getattr(_rt_module, "get_funnel_stage_weight", None)
    except Exception as e:
        print(f"[Apple Retail API] Real-time execution and performance dashboard.py 로드 실패: {e}")


def _run_integration_report():
    """
    모델 서버 연동 진단.
    - startup 시 자동 호출. 서버 없이 진단만: python main.py --integration-check
    """
    sep = "=" * 60
    print(sep)
    print("모델 서버 연동 진단")
    print(sep)
    # Hugging Face Docker: CWD=/app/web-development/backend, _PROJECT_ROOT=/app
    if _PROJECT_ROOT.resolve() == Path("/app"):
        print("[Hugging Face Docker 환경] _PROJECT_ROOT=/app")
    print(f"프로젝트 루트: {_PROJECT_ROOT}")
    print(f"MODEL_SERVER:  {_MODEL_SERVER}")
    print(f"존재 여부:     {_MODEL_SERVER.exists()}")
    print()

    # [1] load_sales_data
    ld_file = _MODEL_SERVER / "load_sales_data.py"
    print("[1] load_sales_data.py")
    print(f"    경로: {ld_file}")
    print(f"    존재: {ld_file.exists()}")
    if not ld_file.exists():
        print("    >>> 파일 없음 - 내장 로더 사용 예정")
    else:
        loader = "model_server" if _ld_module_obj is not None and load_sales_dataframe is not None else "builtin"
        print(f"    load_sales_dataframe: {'OK' if load_sales_dataframe else 'None'}")
        print(f"    get_data_source_info: {'OK' if get_data_source_info else 'None'}")
        if get_data_source_info is not None:
            try:
                info = get_data_source_info()
                print(f"    데이터 소스: {info.get('source', '?')}")
                print(f"    SQL 파일 수: {info.get('sql_file_count', 0)}")
                print(f"    data_dir: {(info.get('data_dir') or '')[:80]}...")
            except Exception as e:
                print(f"    >>> get_data_source_info 오류: {e}")
        # 데이터프레임은 기동 시 로드하지 않음 (HF 등 메모리 제한 환경 OOM 방지). 첫 API 요청 시 지연 로드.
        if load_sales_dataframe is not None:
            print(f"    load_sales_dataframe: 지연 로드 (첫 요청 시 로드)")
    print()

    # [2] 01.data SQL
    sql_dir = _MODEL_SERVER / "01.data"
    print("[2] 데이터 디렉터리 (01.data)")
    print(f"    경로: {sql_dir}")
    print(f"    존재: {sql_dir.exists()}")
    if sql_dir.exists():
        sqls = sorted(sql_dir.glob("*.sql"))
        expected = [f"Apple_Retail_Sales_Dataset_Modified_{i:02d}.sql" for i in range(1, 11)]
        missing = [n for n in expected if not (sql_dir / n).exists()]
        print(f"    SQL 파일: {len(sqls)}개 (기대: 01~10)")
        for f in sqls[:3]:
            print(f"      - {f.name}")
        if len(sqls) > 3:
            print(f"      ... 외 {len(sqls)-3}개")
        if missing:
            print(f"    >>> 누락 파일: {missing}")
        else:
            print(f"    >>> 01~10 전부 존재 (SQL 연동 정상)")
    print()

    # [3] prediction model
    pred_dir = _model_path("02.prediction model", "03.prediction model", "prediction model")
    pred_file = pred_dir / "prediction model.py"
    print("[3] prediction model")
    print(f"    경로: {pred_file}")
    print(f"    존재: {pred_file.exists()}")
    if pred_file.exists():
        pred_ok = get_store_markers is not None and get_continent_category_pie_response is not None
        print(f"    get_demand_dashboard_data: {'OK' if get_demand_dashboard_data else 'None'}")
        print(f"    지도/대륙 파이: {'로드됨' if pred_ok else '미로드'}")
    print()

    # [4~6] Sales, Inventory, Real-time
    modules = [
        ("04.Sales analysis", "Sales analysis", "Sales analysis.py"),
        ("05.Inventory Optimization", "Inventory Optimization", "Inventory Optimization.py"),
        ("06.Real-time execution and performance dashboard", "Real-time execution and performance dashboard", "Real-time execution and performance dashboard.py"),
    ]
    for folder_alt, folder_name, fname in modules:
        p = _MODEL_SERVER / folder_alt / fname
        if not p.exists():
            p = _MODEL_SERVER / folder_name / fname
        print(f"[4~6] {fname}: {'존재' if p.exists() else '없음'} - {p}")
    print()
    print(sep)
    print("진단 완료. 문제가 있으면 위 로그를 확인하세요.")
    print(sep)


@app.on_event("startup")
def _log_data_loader_status():
    """기동 시 연동 진단 실행."""
    _run_integration_report()


# 안전재고 수요 예측 차트 기본 상품명 (Inventory Optimization과 동일)
SAFETY_STOCK_DEFAULT_PRODUCT = "MacBook Pro 16-inch"


def _fallback_safety_stock_forecast_chart(target_product: str | None = None):
    """
    ARIMA 미사용/실패 등으로 get_demand_forecast_chart_data()가 빈 chart_data를 반환할 때의 폴백.
    - 2020년부터 분기별 실적 + 최근 분기 추세로 6분기 예측. 반환 스키마는 chart_data와 동일(month 키에 '2020-Q1' 형식).
    """
    target = (target_product or "").strip() or SAFETY_STOCK_DEFAULT_PRODUCT
    if load_sales_dataframe is None:
        return {"product_name": target, "chart_data": []}
    df = load_sales_dataframe()
    if df is None or getattr(df, "empty", True):
        return {"product_name": target, "chart_data": []}

    prod_col = "Product_Name" if "Product_Name" in df.columns else ("product_name" if "product_name" in df.columns else None)
    if prod_col is None or "sale_date" not in df.columns or "quantity" not in df.columns:
        return {"product_name": target, "chart_data": []}

    use_cols = [prod_col, "sale_date", "quantity"]
    if "store_stock_quantity" in df.columns:
        use_cols.append("store_stock_quantity")
    sdf = df[use_cols].copy()
    sdf[prod_col] = sdf[prod_col].astype(str).str.strip()
    sdf = sdf[sdf[prod_col] == target]
    if sdf.empty:
        return {"product_name": target, "chart_data": []}

    sdf["sale_date"] = pd.to_datetime(sdf["sale_date"], errors="coerce")
    sdf = sdf.dropna(subset=["sale_date"])
    if sdf.empty:
        return {"product_name": target, "chart_data": []}

    sdf["quantity"] = pd.to_numeric(sdf["quantity"], errors="coerce").fillna(0)
    if "store_stock_quantity" in sdf.columns:
        sdf["store_stock_quantity"] = pd.to_numeric(sdf["store_stock_quantity"], errors="coerce").fillna(0)
    sdf["quarter"] = sdf["sale_date"].dt.to_period("Q")
    quarterly = sdf.groupby("quarter")["quantity"].sum().sort_index()
    quarterly_store = sdf.groupby("quarter")["store_stock_quantity"].sum().sort_index() if "store_stock_quantity" in sdf.columns else None
    if len(quarterly) < 2:
        return {"product_name": target, "chart_data": []}

    start_quarter = pd.Period("2020Q1", freq="Q")
    split_quarter = quarterly.index.max()
    if split_quarter < start_quarter:
        return {"product_name": target, "chart_data": []}

    # 최근 4분기 추세
    recent = quarterly.tail(4)
    last = float(recent.iloc[-1])
    prev = float(recent.iloc[-2]) if len(recent) >= 2 else last
    growth = 0.0 if prev <= 0 else (last - prev) / prev
    growth = max(-0.25, min(0.25, growth))
    base_level = last

    def q_label(q):
        return f"{q.year}-Q{q.quarter}"

    chart_data = []
    for q in quarterly.index:
        if q < start_quarter or q > split_quarter:
            continue
        actual = float(quarterly.loc[q])
        row = {
            "month": q_label(q),
            "yhat": round(actual, 2),
            "yhat_lower": round(actual, 2),
            "yhat_upper": round(actual, 2),
            "insight": {
                "sales_label": f"판매 실적: {int(round(actual)):,}대",
                "stock_label": "당분기 재고 기준 (실적)",
                "message": "과거 실적",
            },
        }
        if quarterly_store is not None and q in quarterly_store.index:
            row["store_stock_quantity"] = round(float(quarterly_store.loc[q]), 2)
        chart_data.append(row)
    for i in range(1, 7):
        q = split_quarter + i
        yhat = max(0.0, base_level * ((1.0 + growth) ** i))
        yhat_lower = max(0.0, yhat * 0.85)
        yhat_upper = yhat * 1.15
        sales_label = f"예측 판매량: {int(round(yhat)):,}대"
        stock_label = f"권장 재고: {int(round(yhat_upper)):,}대 (상한선 기준)"
        message = "적정 재고 유지"
        if i == 1 and growth > 0.07:
            message = "수요 증가 추세 — 선제적 발주 권장"
        elif i == 1 and growth < -0.07:
            message = "수요 감소 추세 — 재고 과잉 주의"
        chart_data.append({
            "month": q_label(q),
            "yhat": round(float(yhat), 2),
            "yhat_lower": round(float(yhat_lower), 2),
            "yhat_upper": round(float(yhat_upper), 2),
            "store_stock_quantity": round(yhat * 1.125, 2),
            "insight": {"sales_label": sales_label, "stock_label": stock_label, "message": message},
        })

    return {"product_name": target, "chart_data": chart_data, "method": "fallback_ma_trend"}

# CORS: 브라우저 보안 정책. Vercel 프론트에서 이 API 호출 시 도메인 허용 (독립된 if문으로 미들웨어 등록)
if True:
    # allow_origins: 허용할 Origin 목록 (정확히 일치하는 도메인)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
            "http://localhost:3003",
            "http://127.0.0.1:3003",
            "http://localhost:3004",
            "http://127.0.0.1:3004",
            "http://192.168.0.43:3000",
            "http://192.168.0.43:3001",
            "https://apple-retail-sales-strategy.vercel.app",
            "https://apple-retail-sales-strategy-k1kp94g4f-ajjk1.vercel.app",
            "null",
        ],
        # allow_origin_regex: *.vercel.app 및 192.168.x.x 로컬 네트워크
        allow_origin_regex=r"https://.*\.vercel\.app|http://192\.168\.\d+\.\d+:\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
# 응답 압축 (JSON/텍스트 등 대용량 응답 전송 최적화)
app.add_middleware(GZipMiddleware, minimum_size=500)

# 마지막 업데이트 날짜 캐시 (실시간 연동용)
_cached_last_updated: Optional[str] = None


def _today_kst() -> str:
    """KST(한국 표준시) 기준 오늘 날짜 (YY_MM_DD, 예: 26_02_19)."""
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%y_%m_%d")


def _compute_last_updated(df: Optional[pd.DataFrame]) -> str:
    """데이터프레임에서 최신 sale_date 추출, 없으면 KST 오늘 날짜."""
    if df is None or df.empty:
        return _today_kst()
    col = None
    for c in ("sale_date", "Sale_Date"):
        if c in df.columns:
            col = c
            break
    if col is None:
        return _today_kst()
    try:
        ts = pd.to_datetime(df[col], errors="coerce").max()
        if pd.notna(ts):
            return pd.Timestamp(ts).strftime("%Y-%m-%d")
    except Exception:
        pass
    return _today_kst()


def load_retail_data():
    """
    리테일 데이터를 로드해 요약 통계를 반환합니다.
    모델 서버 데이터(load_sales_dataframe)를 우선 사용하고,
    없거나 컬럼이 부족하면 CSV 폴백으로 동일 형식 반환.
    """
    global _cached_last_updated
    df = None
    if load_sales_dataframe is not None:
        try:
            df = load_sales_dataframe()
        except Exception:
            df = None

    if df is not None and not df.empty:
        # total_sales 컬럼이 없으면 quantity * price 로 계산
        if "total_sales" not in df.columns:
            q = pd.to_numeric(df.get("quantity", 0), errors="coerce").fillna(0)
            p = pd.to_numeric(df.get("price", 0), errors="coerce").fillna(0)
            df = df.copy()
            df["total_sales"] = q * p
        else:
            df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)

        cat_col = "category_name" if "category_name" in df.columns else None
        country_col = "Country" if "Country" in df.columns else ("country" if "country" in df.columns else None)
        product_col = "Product_Name" if "Product_Name" in df.columns else ("product_name" if "product_name" in df.columns else None)
        if cat_col and country_col and product_col:
            total_sales = float(df["total_sales"].sum())
            total_transactions = len(df)
            avg_order_value = total_sales / total_transactions if total_transactions > 0 else 0
            by_category = (
                df.groupby(cat_col)["total_sales"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            sales_by_category = [
                {"category": row[cat_col], "sales": round(float(row["total_sales"]), 0)}
                for _, row in by_category.iterrows()
            ]
            by_country = (
                df.groupby(country_col)["total_sales"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            sales_by_country = [
                {"country": row[country_col], "sales": round(float(row["total_sales"]), 0)}
                for _, row in by_country.iterrows()
            ]
            by_product = (
                df.groupby(product_col)["total_sales"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .reset_index()
            )
            top_products = [
                {"product": row[product_col], "sales": round(float(row["total_sales"]), 0)}
                for _, row in by_product.iterrows()
            ]
            inventory_status = []
            if get_safety_stock_summary is not None:
                try:
                    safety = get_safety_stock_summary()
                    if isinstance(safety, dict) and safety.get("statuses"):
                        inventory_status = [
                            {"status": s.get("status", ""), "count": int(s.get("count", 0))}
                            for s in safety["statuses"]
                        ]
                except Exception:
                    pass
            _cached_last_updated = _compute_last_updated(df)
            return {
                "title": "Apple 리테일 재고 전략 현황",
                "status": "정상",
                "last_updated": _cached_last_updated,
                "summary": {
                    "total_sales": round(total_sales, 2),
                    "total_transactions": total_transactions,
                    "avg_order_value": round(avg_order_value, 2),
                },
                "sales_by_category": sales_by_category,
                "sales_by_country": sales_by_country,
                "top_products": top_products,
                "inventory_status": inventory_status,
            }
        df = None

    # CSV 폴백 (모델 서버 데이터 없거나 컬럼 부족 시)
    base = Path(__file__).parent.parent.parent
    csv_candidates = [
        base / "model-server" / "data" / "Apple_Retail_Sales_Dataset_Modified.csv",
        base / "model-server" / "data" / "data_01.csv",
        base / "model-server" / "01.data" / "data_02_inventory_final.csv",
        Path(__file__).parent.parent / "data_02_inventory_final.csv",
    ]
    csv_path = next((p for p in csv_candidates if p.exists()), None)
    if csv_path is None:
        return None
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return None
    required = ["total_sales", "category_name", "Country", "Product_Name"]
    if not all(col in df.columns for col in required):
        return None
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    total_sales = float(df["total_sales"].sum())
    total_transactions = len(df)
    avg_order_value = total_sales / total_transactions if total_transactions > 0 else 0
    by_category = (
        df.groupby("category_name")["total_sales"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    sales_by_category = [
        {"category": row["category_name"], "sales": round(float(row["total_sales"]), 0)}
        for _, row in by_category.iterrows()
    ]
    by_country = (
        df.groupby("Country")["total_sales"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    sales_by_country = [
        {"country": row["Country"], "sales": round(float(row["total_sales"]), 0)}
        for _, row in by_country.iterrows()
    ]
    by_product = (
        df.groupby("Product_Name")["total_sales"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .reset_index()
    )
    top_products = [
        {"product": row["Product_Name"], "sales": round(float(row["total_sales"]), 0)}
        for _, row in by_product.iterrows()
    ]
    inventory_status = []
    if "Status" in df.columns:
        status_counts = df["Status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        inventory_status = [
            {"status": row["status"], "count": int(row["count"])}
            for _, row in status_counts.iterrows()
        ]
    _cached_last_updated = _compute_last_updated(df)
    return {
        "title": "Apple 리테일 재고 전략 현황",
        "status": "정상",
        "last_updated": _cached_last_updated,
        "summary": {
            "total_sales": round(total_sales, 2),
            "total_transactions": total_transactions,
            "avg_order_value": round(avg_order_value, 2),
        },
        "sales_by_category": sales_by_category,
        "sales_by_country": sales_by_country,
        "top_products": top_products,
        "inventory_status": inventory_status,
    }


# Vercel 대시보드 URL (HF Space 방문 시 "대시보드 보기" 링크용)
_DASHBOARD_VERCEL_URL = "https://apple-retail-sales-strategy-k1kp94g4f-ajjk1.vercel.app"


@app.get("/")
def root(request: Request):
    """루트 접속 시 API 안내. 브라우저는 HTML(대시보드 링크), API 클라이언트는 JSON."""
    base = str(request.base_url).rstrip("/")
    data = {
        "service": "apple-retail-api",
        "docs": "/docs",
        "health": "/api/health",
        "apple_data": "/api/apple-data",
        "dashboard": _DASHBOARD_VERCEL_URL,
        "message": f"API 문서: {base}/docs  |  상태: {base}/api/health  |  대시보드: {_DASHBOARD_VERCEL_URL}",
    }
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" in accept:
        html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Apple Retail API</title>
<style>body{{font-family:system-ui,sans-serif;max-width:560px;margin:2rem auto;padding:0 1rem;}} a{{color:#0066cc;}} .btn{{display:inline-block;margin:0.5rem 0.5rem 0 0;padding:0.6rem 1.2rem;background:#0066cc;color:#fff;text-decoration:none;border-radius:8px;}} .btn:hover{{opacity:.9;}} ul{{line-height:1.8;}}</style></head>
<body>
<h1>Apple Retail Sales Strategy API</h1>
<p><strong>대시보드 보기 (데이터·지도·차트)</strong></p>
<p><a href="{_DASHBOARD_VERCEL_URL}" class="btn" target="_blank" rel="noopener">Vercel 대시보드 열기</a></p>
<p>API 안내:</p>
<ul>
<li><a href="{base}/docs" target="_blank">API 문서 (Swagger)</a></li>
<li><a href="{base}/api/health" target="_blank">상태 확인</a></li>
<li><a href="{base}/api/apple-data" target="_blank">예측 데이터 (JSON)</a></li>
</ul>
<p style="color:#666;font-size:0.9rem;">JSON 응답이 필요하면 Accept: application/json 으로 요청하세요.</p>
</body></html>"""
        return HTMLResponse(html)
    return data


@app.get("/health")
def health_check():
    """서버 상태 확인용 엔드포인트"""
    return {"status": "ok", "service": "apple-retail-api"}


@app.get("/api/health")
def api_health_check(request: Request):
    """대시보드 연동 확인용. 브라우저 접속 시 HTML로 상태 표시, API 호출 시 JSON 반환."""
    data = {"status": "ok", "service": "apple-retail-api"}
    accept = request.headers.get("accept", "") or ""
    if "text/html" in accept:
        html = f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><title>API 상태</title>
<style>body{{font-family:system-ui;max-width:480px;margin:2rem auto;padding:1.5rem;background:#f5f5f7;}} .card{{background:#fff;border-radius:12px;padding:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.08);}} h1{{font-size:1.25rem;color:#1d1d1f;margin:0 0 1rem;}} .row{{display:flex;justify-content:space-between;padding:0.5rem 0;border-bottom:1px solid #eee;}} .key{{color:#6e6e73;}} .val{{font-weight:600;color:#10b981;}} a{{color:#0071e3;}}</style>
</head>
<body><div class="card">
<h1>Apple Retail API 상태</h1>
<div class="row"><span class="key">상태</span><span class="val">{data["status"]}</span></div>
<div class="row"><span class="key">서비스</span><span>{data["service"]}</span></div>
<div class="row"><span class="key">API 문서</span><a href="/docs" target="_blank">/docs</a></div>
<div class="row"><span class="key">대시보드</span><a href="http://localhost:3000" target="_blank">localhost:3000</a></div>
</div></body></html>"""
        return HTMLResponse(html)
    return data


@app.get("/api/health/page", response_class=HTMLResponse)
def api_health_page():
    """브라우저에서 API 상태를 보기 위한 HTML 전용 페이지 (항상 HTML 반환)."""
    html = """<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><title>API 상태</title>
<style>body{font-family:system-ui;max-width:480px;margin:2rem auto;padding:1.5rem;background:#f5f5f7;} .card{background:#fff;border-radius:12px;padding:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.08);} h1{font-size:1.25rem;color:#1d1d1f;margin:0 0 1rem;} .row{display:flex;justify-content:space-between;padding:0.5rem 0;border-bottom:1px solid #eee;} .key{color:#6e6e73;} .val{font-weight:600;color:#10b981;} a{color:#0071e3;}</style>
</head>
<body><div class="card">
<h1>Apple Retail API 상태</h1>
<div class="row"><span class="key">상태</span><span class="val">ok</span></div>
<div class="row"><span class="key">서비스</span><span>apple-retail-api</span></div>
<div class="row"><span class="key">API 문서</span><a href="/docs" target="_blank">/docs</a></div>
<div class="row"><span class="key">대시보드</span><a href="http://localhost:3000" target="_blank">localhost:3000</a></div>
</div></body></html>"""
    return HTMLResponse(html)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_html():
    """
    단일 HTML 대시보드 제공.
    - 프로젝트 루트(ajjk1)의 Apple_Retail_Sales.html을 그대로 반환합니다.
    - 로컬 파일(file://)로 열면 CORS로 API 호출이 막힐 수 있어, 이 경로로 여는 것을 권장합니다.
    """
    base = Path(__file__).resolve().parent.parent.parent  # 프로젝트 루트 (ajjk1)
    p = base / "Apple_Retail_Sales.html"
    if not p.exists():
        return HTMLResponse(
            "<h3>Apple_Retail_Sales.html 파일이 없습니다.</h3><p>프로젝트 루트(ajjk1)에 Apple_Retail_Sales.html을 생성해주세요.</p>",
            status_code=404,
        )
    try:
        return HTMLResponse(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return HTMLResponse("<h3>대시보드 파일을 읽을 수 없습니다.</h3>", status_code=500)


@app.get("/api/city-category-pie")
def get_city_category_pie():
    """2020~2023년 도시별 카테고리별 판매 수량 (파이차트용, prediction model 연동)"""
    if get_city_category_pie_response is None:
        return {"data": [], "model_loaded": False}
    try:
        return get_city_category_pie_response()
    except Exception as e:
        print(f"[Apple Retail API] get_city_category_pie 오류: {e}")
        return {"data": [], "model_loaded": False}


@app.get("/api/sale-id-pie")
def get_sale_id_pie():
    """sale_id별 매출 Top 15 파이차트"""
    if get_sale_id_pie_response is None:
        return {"data": []}
    return get_sale_id_pie_response()


@app.get("/api/store-markers")
def api_store_markers():
    """지도 표시용 매장 마커 (store_id, city, lon, lat)"""
    if get_store_markers is None:
        return {"data": []}
    try:
        raw = get_store_markers() or []
        cleaned = []
        for item in raw:
            if isinstance(item, dict):
                cleaned.append({
                    "store_id": item.get("store_id", ""),
                    "store_name": item.get("store_name", ""),
                    "store_name_ko": item.get("store_name_ko", ""),
                    "city": item.get("city", ""),
                    "country": item.get("country", ""),
                    "lon": item.get("lon", 0),
                    "lat": item.get("lat", 0),
                })
            else:
                cleaned.append(item)
        return {"data": cleaned}
    except Exception as e:
        print(f"[Apple Retail API] api_store_markers 오류: {e}")
        return {"data": []}


@app.get("/api/store-category-pie")
def api_store_category_pie(store_id: str = ""):
    """매장(store_id)별 카테고리 파이차트 데이터"""
    if get_store_category_pie_response is None or not store_id:
        return {"data": []}
    return get_store_category_pie_response(store_id)


@app.get("/api/country-category-pie")
def api_country_category_pie(country: str = ""):
    """국가별 카테고리 파이차트 데이터 (2020~2023) (한글/영문 모두 인식)"""
    if get_country_category_pie_response is None or not country:
        return {"data": []}
    country_en = _resolve_country_to_en(country)
    return get_country_category_pie_response(country_en)


@app.get("/api/country-stores-pie")
def api_country_stores_pie(country: str = ""):
    """국가별 스토어 파이차트 데이터 (2020~2023) (한글/영문 모두 인식)"""
    if get_country_stores_pie_response is None or not country:
        return {"data": []}
    country_en = _resolve_country_to_en(country)
    # store_name 제거: store_id로 통일
    resp = get_country_stores_pie_response(country_en) or {"data": []}
    data = resp.get("data", []) if isinstance(resp, dict) else []
    if isinstance(data, list):
        data = [{k: v for k, v in d.items() if k != "store_name"} if isinstance(d, dict) else d for d in data]
    return {"data": data}


@app.get("/api/continent-category-pie")
def api_continent_category_pie():
    """6대주별 카테고리 파이차트 데이터 (2020~2023)"""
    if get_continent_category_pie_response is None:
        return {"data": []}
    try:
        return get_continent_category_pie_response()
    except Exception as e:
        print(f"[Apple Retail API] api_continent_category_pie 오류: {e}")
        return {"data": []}


@app.get("/api/continent-countries-pie")
def api_continent_countries_pie(continent: str = ""):
    """대륙별 국가 파이차트 데이터 (2020~2023) (한글/영문 모두 인식)"""
    if get_continent_countries_pie_response is None or not continent:
        return {"data": []}
    continent_en = _resolve_continent_to_en(continent)
    return get_continent_countries_pie_response(continent_en)


@app.get("/api/sales-summary")
def api_sales_summary():
    """매출 대시보드용: 전체 합계, 스토어 수, 연도별 매출(2025 예상 포함), Top 스토어 목록 (Sales analysis.py 연동)"""
    fallback = {"total_sum": 0, "store_count": 0, "sales_by_year": [], "predicted_sales_2025": 0, "forecast_method": "linear_trend", "stores": [], "top_stores": [], "sales_by_country": [], "sales_by_city": [], "sales_by_store": [], "sales_by_store_by_year": []}
    if get_store_sales_summary is None:
        return fallback
    try:
        summary = get_store_sales_summary() or fallback
        if isinstance(summary, dict):
            for key in ("stores", "top_stores"):
                items = summary.get(key, [])
                if isinstance(items, list):
                    summary[key] = [{k: v for k, v in d.items() if k != "store_name"} if isinstance(d, dict) else d for d in items]
        return summary
    except Exception as e:
        print(f"[Apple Retail API] api_sales_summary 오류: {e}")
        return fallback


@app.get("/api/store-performance-grade")
def api_store_performance_grade():
    """[3.4.1] 매장 등급 및 달성률 분석. 성장 전략 대시보드용 — Real-time 모듈 우선, 없으면 Sales analysis 폴백."""
    if get_store_performance_grade_from_realtime is not None:
        try:
            return get_store_performance_grade_from_realtime()
        except Exception as e:
            print(f"[Apple Retail API] api_store_performance_grade (realtime) 오류: {e}")
    if get_store_performance_grade is None:
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": 0}
    try:
        return get_store_performance_grade()
    except Exception as e:
        print(f"[Apple Retail API] api_store_performance_grade 오류: {e}")
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": 0}


@app.get("/api/region-category-pivot")
def api_region_category_pivot(country: Optional[str] = None):
    """[3.4.2] 지역별 카테고리 매출 피봇. country 지정 시 해당 국가 카테고리 점유율(파이 차트용) 포함."""
    if get_region_category_pivot_from_realtime is None:
        return {"countries": [], "categories": [], "pivot_rows": [], "category_share": []}
    try:
        return get_region_category_pivot_from_realtime(country=country)
    except Exception as e:
        print(f"[Apple Retail API] api_region_category_pivot 오류: {e}")
        return {"countries": [], "categories": [], "pivot_rows": [], "category_share": []}


@app.get("/api/price-demand-correlation")
def api_price_demand_correlation(product_name: Optional[str] = None):
    """[3.4.3] 가격-수요 상관관계 및 인사이트. product_name 지정 시 해당 제품 상관계수·스캐터 데이터 반환."""
    if get_price_demand_correlation_from_realtime is None:
        return {"product_name": "", "correlation": None, "insight": "데이터 없음", "scatter_data": [], "available_products": []}
    try:
        return get_price_demand_correlation_from_realtime(product_name=product_name)
    except Exception as e:
        print(f"[Apple Retail API] api_price_demand_correlation 오류: {e}")
        return {"product_name": "", "correlation": None, "insight": "오류", "scatter_data": [], "available_products": []}


@app.get("/api/sales-box")
def api_sales_box():
    """매출 박스용: 메인 페이지에 표시할 전체 매출 합계 (Sales analysis.py 연동)"""
    if get_sales_box_value is None:
        return {"value": 0}
    try:
        return {"value": get_sales_box_value()}
    except Exception as e:
        print(f"[Apple Retail API] api_sales_box 오류: {e}")
        return {"value": 0}


@app.get("/api/sales-by-country-category")
def api_sales_by_country_category(country: str = ""):
    """국가별 카테고리별 매출 (한글/영문 모두 인식)"""
    if get_sales_by_country_category is None or not country.strip():
        return {"categories": []}
    try:
        country_en = _resolve_country_to_en(country.strip())
        result = get_sales_by_country_category(country_en)
        return {"categories": result if isinstance(result, list) else []}
    except Exception as e:
        print(f"[Apple Retail API] api_sales_by_country_category 오류: {e}")
        return {"categories": []}


@app.get("/api/sales-by-store")
def api_sales_by_store(country: str = ""):
    """국가별 Store_Name 연간/연도별 매출 (대륙 차트에서 국가 클릭 시 Store_Name 카드용)"""
    fallback = {"sales_by_store": [], "sales_by_store_by_year": []}
    if get_sales_by_store is None or get_sales_by_store_by_year is None or not country.strip():
        return fallback
    try:
        country_en = _resolve_country_to_en(country.strip())
        by_store = get_sales_by_store(country_en)
        by_year = get_sales_by_store_by_year(country_en)
        return {"sales_by_store": by_store if isinstance(by_store, list) else [], "sales_by_store_by_year": by_year if isinstance(by_year, list) else []}
    except Exception as e:
        print(f"[Apple Retail API] api_sales_by_store 오류: {e}")
        return fallback


@app.get("/api/sales-by-store-quarterly")
def api_sales_by_store_quarterly(store_name: str = "", country: str = ""):
    """특정 스토어의 3개월 단위 매출 (스캐터·라인 차트용)"""
    if get_sales_by_store_quarterly is None or not store_name.strip():
        return {"quarterly": []}
    try:
        country_en = _resolve_country_to_en(country.strip()) if country.strip() else None
        result = get_sales_by_store_quarterly(store_name.strip(), country_en)
        return {"quarterly": result if isinstance(result, list) else []}
    except Exception as e:
        print(f"[Apple Retail API] api_sales_by_store_quarterly 오류: {e}")
        return {"quarterly": []}


@app.get("/api/sales-by-store-quarterly-by-category")
def api_sales_by_store_quarterly_by_category(store_name: str = "", country: str = ""):
    """특정 스토어의 카테고리별 3개월 단위 매출 (카테고리별 분기 추이 차트용)"""
    if get_sales_by_store_quarterly_by_category is None or not store_name.strip():
        return {"quarterly_by_category": []}
    try:
        country_en = _resolve_country_to_en(country.strip()) if country.strip() else None
        result = get_sales_by_store_quarterly_by_category(store_name.strip(), country_en)
        return {"quarterly_by_category": result if isinstance(result, list) else []}
    except Exception as e:
        print(f"[Apple Retail API] api_sales_by_store_quarterly_by_category 오류: {e}")
        return {"quarterly_by_category": []}


@app.get("/api/data-source")
def api_data_source():
    """모델 서버 데이터 소스 정보 (load_sales_data.py 실행 후 01.data SQL/CSV 연동, 대시보드와 동일 소스)"""
    fallback = {"data_dir": "", "source": "none", "sql_file_count": 0, "csv_path": None, "loader": "none", "quantity_unit": "대"}
    if get_data_source_info is None:
        return fallback
    try:
        out = dict(get_data_source_info())
        out["loader"] = "model_server" if _ld_module_obj is not None else "builtin"
        return out
    except Exception as e:
        print(f"[Apple Retail API] api_data_source 오류: {e}")
        return fallback


@app.get("/api/safety-stock")
def api_safety_stock():
    """안전재고 대시보드용: 재고 상태별 건수 (Inventory Optimization.py 연동)"""
    if get_safety_stock_summary is None:
        return {"statuses": [], "total_count": 0}
    return get_safety_stock_summary()


@app.get("/api/safety-stock-forecast-chart")
def api_safety_stock_forecast_chart(product_name: str | None = None):
    """안전재고 대시보드 메인 차트: 수요 예측 & 적정 재고 (ARIMA, 2020년부터 분기별). product_name 지정 시 해당 상품 기준."""
    if get_demand_forecast_chart_data is None:
        return {"product_name": (product_name or "").strip() or SAFETY_STOCK_DEFAULT_PRODUCT, "chart_data": []}
    try:
        data = get_demand_forecast_chart_data(product_name=product_name) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("product_name", (product_name or "").strip() or SAFETY_STOCK_DEFAULT_PRODUCT)
    data.setdefault("chart_data", [])

    requested_name = (product_name or "").strip()
    if requested_name:
        data = {**data, "product_name": requested_name}

    # ARIMA 미사용/실패 등으로 chart_data가 비거나, 2025년 예측 구간이 없으면 폴백으로 과거 실적 + 2025 예측 채움
    chart_list = data.get("chart_data") or []
    has_2025 = any((str(p.get("month") or "").startswith("2025") for p in chart_list))
    if not chart_list or not has_2025:
        try:
            fb = _fallback_safety_stock_forecast_chart(data.get("product_name") or product_name)
            if fb.get("chart_data"):
                data = {**fb, "product_name": requested_name or fb.get("product_name") or SAFETY_STOCK_DEFAULT_PRODUCT}
                chart_list = data.get("chart_data") or []
        except Exception:
            pass

    # 2025년 분기 예측을 수요 대시보드의 2025 예측 수량으로 통일 (그래프에 동일 값 표시)
    display_product = (data.get("product_name") or "").strip() or SAFETY_STOCK_DEFAULT_PRODUCT
    pred_2025_total = 0
    pred_2025_product = None
    try:
        if get_sales_quantity_forecast is not None:
            fc = get_sales_quantity_forecast()
            if isinstance(fc, dict):
                pred_2025_total = int(fc.get("predicted_quantity_2025") or 0)
        if get_predicted_demand_by_product is not None:
            product_list = get_predicted_demand_by_product() or []
            for p in product_list:
                if not isinstance(p, dict):
                    continue
                pname = (p.get("product_name") or p.get("Product_Name") or "").strip()
                if pname and pname == display_product:
                    pred_2025_product = int(p.get("predicted_quantity") or 0)
                    break
    except Exception:
        pass
    # 상품 지정 시 해당 상품 예측만 사용(없으면 0), 미지정(기본) 시 해당 기본 상품 또는 전체 예측 사용
    pred_2025 = pred_2025_product if pred_2025_product is not None else (0 if requested_name else pred_2025_total)
    per_quarter = pred_2025 / 4.0 if pred_2025 else 0.0
    yhat_q = max(0.0, per_quarter)
    yhat_lower_q = max(0.0, yhat_q * 0.85)
    yhat_upper_q = yhat_q * 1.15
    store_stock_q = round(yhat_q * 1.125, 2)
    quarters_2025 = [
        {"month": "2025-Q1", "yhat": round(yhat_q, 2), "yhat_lower": round(yhat_lower_q, 2), "yhat_upper": round(yhat_upper_q, 2), "store_stock_quantity": store_stock_q, "insight": {"sales_label": f"2025년 예측(수요 대시보드): {int(round(yhat_q)):,}대/분기", "stock_label": f"권장 재고: {int(round(yhat_upper_q)):,}대 (상한선)", "message": "수요 대시보드 2025 예측 반영"}},
        {"month": "2025-Q2", "yhat": round(yhat_q, 2), "yhat_lower": round(yhat_lower_q, 2), "yhat_upper": round(yhat_upper_q, 2), "store_stock_quantity": store_stock_q, "insight": {"sales_label": f"2025년 예측(수요 대시보드): {int(round(yhat_q)):,}대/분기", "stock_label": f"권장 재고: {int(round(yhat_upper_q)):,}대 (상한선)", "message": "수요 대시보드 2025 예측 반영"}},
        {"month": "2025-Q3", "yhat": round(yhat_q, 2), "yhat_lower": round(yhat_lower_q, 2), "yhat_upper": round(yhat_upper_q, 2), "store_stock_quantity": store_stock_q, "insight": {"sales_label": f"2025년 예측(수요 대시보드): {int(round(yhat_q)):,}대/분기", "stock_label": f"권장 재고: {int(round(yhat_upper_q)):,}대 (상한선)", "message": "수요 대시보드 2025 예측 반영"}},
        {"month": "2025-Q4", "yhat": round(yhat_q, 2), "yhat_lower": round(yhat_lower_q, 2), "yhat_upper": round(yhat_upper_q, 2), "store_stock_quantity": store_stock_q, "insight": {"sales_label": f"2025년 예측(수요 대시보드): {int(round(yhat_q)):,}대/분기", "stock_label": f"권장 재고: {int(round(yhat_upper_q)):,}대 (상한선)", "message": "수요 대시보드 2025 예측 반영"}},
    ]
    # 기존 2025 분기 제거 후 수요 대시보드 2025 예측으로 교체
    chart_list = [p for p in chart_list if not (str(p.get("month") or "").startswith("2025"))]
    chart_list.extend(quarters_2025)
    # 26년도 1·2분기 제거 (그래프는 2025-Q4까지 표시)
    chart_list = [p for p in chart_list if not (str(p.get("month") or "").startswith("2026"))]
    chart_list.sort(key=lambda p: (str(p.get("month") or "")))
    data["chart_data"] = chart_list
    return data


@app.get("/api/safety-stock-sales-by-store-period")
def api_safety_stock_sales_by_store_period(
    category: str = "",
    continent: str | None = None,
    country: str | None = None,
    store_name: str | None = None,
):
    """안전재고 대시보드: 카테고리별 상점·6개월 구간 판매 수량 (대륙/국가/상점 필터)"""
    if get_sales_by_store_six_month is None:
        return {"category": category, "periods": [], "data": [], "store_names": [], "filter_options": {"continents": [], "countries": [], "stores": []}}
    return get_sales_by_store_six_month(category, continent=continent or None, country=country or None, store_name=store_name or None)


@app.get("/api/safety-stock-sales-by-product")
def api_safety_stock_sales_by_product(
    category: str = "",
    continent: str | None = None,
    country: str | None = None,
    store_name: str | None = None,
    period: str | None = None,
):
    """안전재고 대시보드: 동일 필터 기준 product_id·product_name 별 판매 수량 (period=분기 선택 시 해당 기간만)"""
    if get_sales_by_product is None:
        return {"category": category, "period": period, "products": []}
    return get_sales_by_product(category, continent=continent or None, country=country or None, store_name=store_name or None, period=period or None)


@app.get("/api/safety-stock-kpi")
def api_safety_stock_kpi():
    """Inventory Action Center: 총 잠긴 돈, 위험 품목 수, 과잉 품목 수 (Risk KPIs)"""
    if get_kpi_summary is None:
        return {"total_frozen_money": 0.0, "danger_count": 0, "overstock_count": 0, "predicted_demand": 0, "expected_revenue": 0.0}
    return get_kpi_summary()


@app.get("/api/safety-stock-inventory-list")
def api_safety_stock_inventory_list(status_filter: str | None = None):
    """Inventory Action Center: 상세 재고 테이블 (Status별 필터: Danger, Overstock 등)"""
    if get_inventory_list is None:
        return []
    filters = None
    if status_filter and status_filter.strip():
        filters = [s.strip() for s in status_filter.split(",") if s.strip()]
    return get_inventory_list(status_filter=filters)


@app.get("/api/inventory-critical-alerts")
def api_inventory_critical_alerts(limit: int = 50):
    """[3.4.4] 실시간 재고·예측 신뢰도 경고. Health_Index(안전재고 대비 현재 재고 비율) < 70 인 품절 위기 항목."""
    if get_inventory_critical_alerts is None:
        return {"critical_count": 0, "critical_items": []}
    try:
        return get_inventory_critical_alerts(limit=min(max(1, limit), 200))
    except Exception as e:
        print(f"[Apple Retail API] api_inventory_critical_alerts 오류: {e}")
        return {"critical_count": 0, "critical_items": []}


# 관리자 코멘트 저장 경로 (comments.csv)
_INVENTORY_COMMENTS_PATH = Path(__file__).resolve().parent / "data" / "inventory_comments.csv"


def _ensure_comments_dir():
    _INVENTORY_COMMENTS_PATH.parent.mkdir(parents=True, exist_ok=True)


def _read_inventory_comments() -> list:
    """comments.csv 읽기. product_name, comment, author, created_at"""
    if not _INVENTORY_COMMENTS_PATH.exists():
        return []
    out = []
    try:
        with open(_INVENTORY_COMMENTS_PATH, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                out.append({
                    "product_name": row.get("product_name", "").strip(),
                    "comment": row.get("comment", "").strip(),
                    "author": row.get("author", "").strip(),
                    "created_at": row.get("created_at", "").strip(),
                })
    except Exception:
        pass
    return out


def _append_inventory_comment(product_name: str, comment: str, author: str = "") -> None:
    """한 줄 추가 (product_name, comment, author, created_at)"""
    _ensure_comments_dir()
    created = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M")
    row = {"product_name": product_name, "comment": comment, "author": author or "관리자", "created_at": created}
    file_exists = _INVENTORY_COMMENTS_PATH.exists()
    with open(_INVENTORY_COMMENTS_PATH, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["product_name", "comment", "author", "created_at"])
        if not file_exists:
            w.writeheader()
        w.writerow(row)


@app.get("/api/inventory-comments")
def api_inventory_comments():
    """Inventory Action Center: 관리자 코멘트 목록 (product_name, comment, author, created_at)"""
    return {"comments": _read_inventory_comments()}


@app.post("/api/inventory-comments")
async def api_inventory_comments_post(request: Request):
    """Inventory Action Center: 코멘트 추가 (body: product_name, comment, author?)"""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    product_name = (body.get("product_name") or "").strip()
    comment = (body.get("comment") or "").strip()
    author = (body.get("author") or "").strip()
    if not product_name or not comment:
        return {"ok": False, "error": "product_name and comment are required"}
    _append_inventory_comment(product_name, comment, author)
    return {"ok": True, "comments": _read_inventory_comments()}


@app.get("/api/quick-status")
def api_quick_status():
    """경량 연동 상태 (스모크 테스트 없이 즉시 반환, 대시보드 연동 표시용)"""
    data_source = get_data_source_info() if callable(get_data_source_info) else {"source": "none", "sql_file_count": 0}
    return {
        "data_source": data_source,
        "modules_loaded": {
            "load_sales_data": load_sales_dataframe is not None and get_data_source_info is not None,
            "prediction_model": callable(get_demand_dashboard_data),
            "sales_analysis": callable(get_store_sales_summary),
            "inventory_optimization": callable(get_safety_stock_summary),
            "realtime_dashboard": callable(get_recommendation_summary),
        },
    }


@app.get("/api/integration-status")
def api_integration_status():
    """01.data~05 모듈 연동 상태 요약 (로딩 여부 + 핵심 API 호출 가능 여부)"""
    def _safe_call(fn, default=None):
        try:
            return fn() if callable(fn) else default
        except Exception:
            return default

    data_source = _safe_call(get_data_source_info, {"data_dir": "", "source": "none", "sql_file_count": 0, "csv_path": None})
    # 가벼운 스모크: 너무 무거운 데이터는 길이만 확인
    forecast = _safe_call(get_sales_quantity_forecast, None)
    sales_summary = _safe_call(get_store_sales_summary, None)
    safety_stock = _safe_call(get_safety_stock_summary, None)
    recommend = _safe_call(get_recommendation_summary, None)

    return {
        "data_source": data_source,
        "modules_loaded": {
            "load_sales_data": load_sales_dataframe is not None and get_data_source_info is not None,
            "prediction_model": callable(get_demand_dashboard_data),
            "sales_analysis": callable(get_store_sales_summary),
            "inventory_optimization": callable(get_safety_stock_summary),
            "realtime_dashboard": callable(get_recommendation_summary),
        },
        "functions_available": {
            "get_sales_quantity_forecast": callable(get_sales_quantity_forecast),
            "get_predicted_demand_by_product": callable(get_predicted_demand_by_product),
            "get_demand_dashboard_data": callable(get_demand_dashboard_data),
            "get_city_category_pie_response": callable(get_city_category_pie_response),
            "get_store_markers": callable(get_store_markers),
            "get_store_sales_summary": callable(get_store_sales_summary),
            "get_safety_stock_summary": callable(get_safety_stock_summary),
            "get_demand_forecast_chart_data": callable(get_demand_forecast_chart_data),
            "get_recommendation_summary": callable(get_recommendation_summary),
        },
        "smoke": {
            "forecast_total_quantity_2020_2024": (forecast or {}).get("total_quantity_2020_2024") if isinstance(forecast, dict) else None,
            "sales_store_count": (sales_summary or {}).get("store_count") if isinstance(sales_summary, dict) else None,
            "safety_stock_total_count": (safety_stock or {}).get("total_count") if isinstance(safety_stock, dict) else None,
            "recommendation_top_products_len": len((recommend or {}).get("top_products", [])) if isinstance(recommend, dict) else None,
        },
        "server_time": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/api/recommendation-summary")
def api_recommendation_summary():
    """추천 시스템 대시보드용: 추천 상품·카테고리 (Real-time execution and performance dashboard 연동)"""
    fallback = {"top_products": [], "top_categories": []}
    if get_recommendation_summary is None:
        return fallback
    try:
        return get_recommendation_summary()
    except Exception as e:
        print(f"[Apple Retail API] api_recommendation_summary 오류: {e}")
        return fallback


@app.get("/api/store-sales-forecast/{store_id}")
def api_store_sales_forecast(store_id: str, days: int = 30):
    """
    매출 예측 시계열: 일별 실측 + 향후 30일 예측 및 신뢰 구간.
    sale_date resample('D') + 선형 회귀 예측.
    """
    fallback = {"actual": [], "predicted": [], "store_id": store_id}
    if get_sales_forecast_chart_data is None:
        return fallback
    try:
        return get_sales_forecast_chart_data(store_id, forecast_days=max(1, min(90, days)))
    except Exception as e:
        print(f"[Apple Retail API] api_store_sales_forecast 오류: {e}")
        return fallback


@app.get("/api/store-recommendations/{store_id}")
def api_store_recommendations(store_id: str):
    """
    특정 store_id에 대한 4가지 추천 모델 결과 반환.
    - 연관 분석 (Association): Lift 기반 병행 구매 추천
    - 유사 상점 (CF): Cosine Similarity 기반 유사 상점의 베스트셀러
    - 잠재 수요 (SVD/MF): 행렬 분해 기반 예상 판매량
    - 트렌드 분석: 최근 판매 증가율 기반
    """
    fallback = {
        "store_id": store_id,
        "store_summary": {"total_sales": 0, "product_count": 0, "store_name": ""},
        "association": [],
        "similar_store": [],
        "latent_demand": [],
        "trend": []
    }
    if get_store_recommendations is None:
        return fallback
    try:
        return get_store_recommendations(store_id)
    except Exception as e:
        print(f"[Apple Retail API] api_store_recommendations 오류: {e}")
        return fallback


@app.get("/api/store-list")
def api_store_list():
    """성장 전략 대시보드용: 상점 목록 (store_id, store_name). Real-time 모듈 우선, 0건이면 load_sales_dataframe 폴백."""
    if get_store_list_from_realtime is not None:
        try:
            out = get_store_list_from_realtime()
            n = len(out.get("stores") or [])
            if n > 0:
                print(f"[Apple Retail API] api_store_list: realtime 반환 상점 {n}건")
                return out
            print("[Apple Retail API] api_store_list: realtime 반환 상점 0건 → load_sales_dataframe 폴백 시도")
        except Exception as e:
            print(f"[Apple Retail API] api_store_list (realtime) 오류: {e}")
            import traceback
            traceback.print_exc()
    if load_sales_dataframe is None:
        print("[Apple Retail API] api_store_list: load_sales_dataframe is None")
        return {"stores": []}
    try:
        df = load_sales_dataframe()
        if df is None or df.empty:
            print("[Apple Retail API] api_store_list: df is None or empty")
            return {"stores": []}
        store_id_col = "store_id" if "store_id" in df.columns else None
        if store_id_col is None:
            print(f"[Apple Retail API] api_store_list: store_id 컬럼 없음. 컬럼: {list(df.columns)[:10]}")
            return {"stores": []}
        store_name_col = "Store_Name" if "Store_Name" in df.columns else ("store_name" if "store_name" in df.columns else None)
        stores = df[store_id_col].astype(str).str.strip().unique().tolist()
        store_names = {}
        if store_name_col:
            for sid in stores:
                sub = df[df[store_id_col].astype(str).str.strip() == sid]
                if not sub.empty:
                    name = sub[store_name_col].iloc[0]
                    store_names[sid] = str(name).strip() if pd.notna(name) else sid
                else:
                    store_names[sid] = sid
        else:
            store_names = {sid: sid for sid in stores}
        sorted_stores = sorted(stores, key=lambda x: (x.upper(), x))
        result = {
            "stores": [{"store_id": s, "store_name": store_names.get(s, s)} for s in sorted_stores]
        }
        n = len(result["stores"])
        print(f"[Apple Retail API] api_store_list: 폴백 반환 상점 {n}건 (store_id 컬럼={store_id_col}, store_name 컬럼={store_name_col})")
        if n > 0:
            print(f"[Apple Retail API] api_store_list: 첫 상점 예시 - {result['stores'][0]}")
        return result
    except Exception as e:
        print(f"[Apple Retail API] api_store_list 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"stores": []}


@app.get("/api/user-personalized-recommendations")
def api_user_personalized_recommendations(store_id: Optional[str] = None):
    """
    [4.1.1 유저(상점) 맞춤형 추천] 재고 건전성(Health_Index) + 상점 판매 이력(카테고리) 기반 상위 3개 상품.
    - store_id 미지정 시 빈 결과 반환.
    - 응답: user_id, recommendations[{ rank, product_id, reason }], top_3, user_history_categories
    """
    fallback = {"user_id": 1025, "user_identifier": store_id or "", "recommendations": [], "top_3": [], "user_history_categories": [], "performance_simulation": {"lift_rate": 1.15, "expected_sales_increase_pct": 15.0, "insight": "추천 시스템 도입 시 예상 매출 증대 효과: 15.0%", "projected_scores": []}}
    if not store_id or get_inventory_health_for_recommendation is None or get_user_personalized_recommendations_from_realtime is None:
        return fallback
    try:
        inventory_health = get_inventory_health_for_recommendation()
        return get_user_personalized_recommendations_from_realtime(store_id.strip(), inventory_health)
    except Exception as e:
        print(f"[Apple Retail API] api_user_personalized_recommendations 오류: {e}")
        return fallback


@app.get("/api/collab-filter-recommendations")
def api_collab_filter_recommendations(store_id: Optional[str] = None):
    """
    [4.1.1 유저(상점) 기반 협업 필터링 및 재고 가중치 결합]
    - 유사 상점 5곳 구매 패턴 평균(base_score) × 재고 가산(Health_Index>=120 → boost 1.2).
    """
    fallback = {"target_store": store_id or "", "top_recommendations": []}
    if not store_id or get_inventory_health_for_recommendation is None or get_collab_filter_with_inventory_boost_from_realtime is None:
        return fallback
    try:
        inventory_health = get_inventory_health_for_recommendation()
        return get_collab_filter_with_inventory_boost_from_realtime(store_id.strip(), inventory_health)
    except Exception as e:
        print(f"[Apple Retail API] api_collab_filter_recommendations 오류: {e}")
        return fallback


# [4.3.2] 추천 시스템 피드백 루프: 로그 저장 디렉터리
_FEEDBACK_LOG_DIR = Path(__file__).resolve().parent / "logs"


@app.post("/api/recommendation-feedback")
async def api_recommendation_feedback(request: Request):
    """
    [4.3.2 추천 시스템 피드백 루프 시뮬레이션]
    - body: { "store_id": str (optional), "user_id": int (optional), "feedback": { "Product_Name": 0|1, ... } }
    - 1: 클릭, 0: 무시. 클릭된 제품을 다음 학습 시 가중치 강화 대상으로 저장.
    """
    try:
        body = await request.json()
        if body is None:
            body = {}
        feedback = body.get("feedback") or {}
        store_id = body.get("store_id") or ""
        user_id = body.get("user_id")
        clicked_items = [k for k, v in feedback.items() if v == 1]
        _FEEDBACK_LOG_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        log_path = _FEEDBACK_LOG_DIR / f"feedback_{date_str}.json"
        import json
        entry = {"ts": datetime.utcnow().isoformat() + "Z", "store_id": store_id, "user_id": user_id, "feedback": feedback, "clicked_items": clicked_items}
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = [data]
            data.append(entry)
        else:
            data = [entry]
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {
            "clicked_items": clicked_items,
            "message": "피드백 수집 완료",
            "log_path": str(log_path),
        }
    except Exception as e:
        print(f"[Apple Retail API] api_recommendation_feedback 오류: {e}")
        return {"clicked_items": [], "message": "피드백 저장 실패", "log_path": ""}


@app.get("/api/customer-journey-funnel")
def api_customer_journey_funnel():
    """[4.4.1 고객 여정 단계별 수치 분석] 퍼널 단계별 유저 수·전환율·병목 구간."""
    fallback = {"stages": [], "overall_cvr": 0.0, "drop_off": []}
    if get_customer_journey_funnel_from_realtime is None:
        return fallback
    try:
        return get_customer_journey_funnel_from_realtime()
    except Exception as e:
        print(f"[Apple Retail API] api_customer_journey_funnel 오류: {e}")
        return fallback


@app.get("/api/funnel-stage-weight")
def api_funnel_stage_weight(stage: Optional[str] = None):
    """[4.4.2 퍼널 위치에 따른 가중치 동적 할당] 단계별 추천 가중치·전략. stage 미지정 시 전체 반환."""
    fallback = {"stages": []} if not stage else {"current_stage": stage, "recommendation_weight": 1.0, "strategy": "기본 가중치 적용"}
    if get_funnel_stage_weight_from_realtime is None:
        return fallback
    try:
        return get_funnel_stage_weight_from_realtime(stage)
    except Exception as e:
        print(f"[Apple Retail API] api_funnel_stage_weight 오류: {e}")
        return fallback


@app.get("/api/sales-quantity-forecast")
def api_sales_quantity_forecast():
    """수요 대시보드용: 2020~2024 기준 2025년 판매 수량 예측 (prediction model.py 연동)"""
    fallback = {
        "basis_years": [],
        "yearly_quantity": [],
        "total_quantity_2020_2024": 0,
        "predicted_quantity_2025": 0,
        "predicted_2025_by_category": [],
        "method": "linear_trend",
    }
    if get_sales_quantity_forecast is None:
        return fallback
    try:
        return get_sales_quantity_forecast()
    except Exception as e:
        print(f"[Apple Retail API] api_sales_quantity_forecast 오류: {e}")
        return fallback


@app.get("/api/predicted-demand-by-product")
def api_predicted_demand_by_product():
    """수요 대시보드용: product_id별 2025년 예측 수요 (prediction model.py 연동)"""
    if get_predicted_demand_by_product is None:
        return {"data": []}
    data = get_predicted_demand_by_product() or []
    data = _enrich_product_demand_with_category(data)
    return {"data": data}


_PRODUCT_CATEGORY_MAP_CACHE: Optional[Dict[str, str]] = None


def _get_product_category_map() -> Dict[str, str]:
    """product_id -> category_name 매핑 (캐시)."""
    global _PRODUCT_CATEGORY_MAP_CACHE
    if _PRODUCT_CATEGORY_MAP_CACHE is not None:
        return _PRODUCT_CATEGORY_MAP_CACHE
    out: Dict[str, str] = {}
    df = None
    # 내장 로더 우선 (경로 확실)
    try:
        df = _ls_load_sales_dataframe()
    except Exception:
        pass
    if df is None or df.empty:
        try:
            df = load_sales_dataframe()
        except Exception:
            pass
    if df is not None and not df.empty and "product_id" in df.columns:
        cat_col = "category_name" if "category_name" in df.columns else None
        if cat_col:
            try:
                for _, r in df[["product_id", cat_col]].drop_duplicates("product_id").iterrows():
                    out[str(r["product_id"]).strip()] = _norm_category(r[cat_col])
            except Exception:
                pass
    _PRODUCT_CATEGORY_MAP_CACHE = out
    return out


def _norm_category(v) -> str:
    """카테고리 문자열 정규화 (따옴표·공백 제거)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).strip()
    if len(s) >= 2 and s[0] in ("'", '"') and s[-1] == s[0]:
        s = s[1:-1].strip()
    return s


def _enrich_product_demand_with_category(products: list) -> list:
    """product_demand_2025에 category가 없거나 비어 있으면 매핑 추가."""
    if not products:
        return products
    needs_enrich = any(
        isinstance(p, dict) and not (str(p.get("category") or "").strip())
        for p in products
    )
    if not needs_enrich:
        return products
    pid_to_cat = _get_product_category_map()
    if not pid_to_cat:
        return products
    for p in products:
        if not isinstance(p, dict):
            continue
        if not (str(p.get("category") or "").strip()):
            pid = str(p.get("product_id", "")).strip()
            cat = pid_to_cat.get(pid, "")
            if cat:
                p["category"] = cat
    return products


@app.get("/api/demand-dashboard")
def api_demand_dashboard(
    continent: Optional[str] = None,
    country: Optional[str] = None,
    store_id: Optional[str] = None,
    city: Optional[str] = None,
    year: int = 2024,
):
    """수요 대시보드용: 선택 지역·연도별 통합 수요 데이터 (prediction model.py get_demand_dashboard_data 연동)"""
    if get_demand_dashboard_data is None:
        return {
            "total_demand": 0,
            "category_demand": [],
            "category_demand_2025": [],
            "product_demand_2025": [],
            "yearly_quantity": [],
            "overall_quantity_by_year": None,
        }
    try:
        country_en = _resolve_country_to_en(country) if country else None
        result = get_demand_dashboard_data(
            continent=continent or None,
            country=country_en or country,
            store_id=store_id or None,
            city=city or None,
            year=year,
        )
        # product_demand_2025에 category 보강 (항상 적용)
        if result and isinstance(result.get("product_demand_2025"), list):
            pid_to_cat = _get_product_category_map()
            new_list = []
            for p in result["product_demand_2025"]:
                if not isinstance(p, dict):
                    new_list.append(p)
                    continue
                pid = str(p.get("product_id", "")).strip()
                cat = pid_to_cat.get(pid, (p.get("category") or ""))
                new_list.append({**p, "category": cat})
            result["product_demand_2025"] = new_list
        return result
    except Exception as e:
        print(f"[Apple Retail API] api_demand_dashboard 오류: {e}")
        return {
            "total_demand": 0,
            "category_demand": [],
            "category_demand_2025": [],
            "product_demand_2025": [],
            "yearly_quantity": [],
            "overall_quantity_by_year": None,
        }


@app.get("/api/store-product-quantity-barchart")
def api_store_product_quantity_barchart():
    """각 스토어별 product_id별 판매 수량 (2020~2024 합산) - 바차트용"""
    if get_store_product_quantity_barchart_data is None:
        return {"data": []}
    # store_name 제거: store_id로 통일
    raw = get_store_product_quantity_barchart_data() or []
    if isinstance(raw, list):
        raw = [{k: v for k, v in d.items() if k != "store_name"} if isinstance(d, dict) else d for d in raw]
    return {"data": raw}


def _apple_data_fallback():
    """데이터 로드 실패 시 동일 형식으로 폴백 반환 (대시보드 오류 방지)."""
    fallback_date = _today_kst()
    return {
        "title": "Apple 리테일 재고 전략 현황",
        "status": "데이터 파일 없음",
        "last_updated": fallback_date,
        "summary": {},
        "sales_by_category": [],
        "sales_by_country": [],
        "top_products": [],
        "inventory_status": [],
    }


@app.get("/api/last-updated")
def api_last_updated():
    """마지막 업데이트 날짜 (실시간 연동용, 경량 폴링)."""
    global _cached_last_updated
    if _cached_last_updated:
        return {"last_updated": _cached_last_updated}
    # 캐시 없으면 load_retail_data 한 번 호출하여 채움
    try:
        result = load_retail_data()
        if result and result.get("last_updated"):
            return {"last_updated": result["last_updated"]}
    except Exception:
        pass
    return {"last_updated": _today_kst()}


@app.get("/api/apple-data")  # 프론트엔드에서 호출할 주소를 정의합니다.
def get_apple_data():
    try:
        result = load_retail_data()
        if result is None:
            return _apple_data_fallback()
        return result
    except Exception as e:
        print(f"[Apple Retail API] get_apple_data 오류: {e}")
        return _apple_data_fallback()


# 연동 진단만 실행 후 종료 (서버 기동 없음): python main.py --integration-check
if __name__ == "__main__":
    if "--integration-check" in sys.argv:
        _run_integration_report()
        sys.exit(0)
