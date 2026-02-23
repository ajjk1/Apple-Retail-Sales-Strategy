"""
안전재고 대시보드 백엔드 데이터 (Inventory Optimization.ipynb 연동)
- 모델 서버 공통 로더(SQL 01~10 또는 CSV)로 판매 데이터 로드 후,
  Safety_Stock / Inventory / Status / Frozen_Money 산출 (대시보드와 동일 데이터 소스)

================================================================================
[안전재고 대시보드 개발 가이드]
- 안전재고 대시보드 관련 **모든 로직·집계·데이터 형식**은 **이 파일(Inventory Optimization.py)** 에만 둡니다.
- 백엔드(main.py)는 이 모듈의 함수만 호출하고, 비즈니스 로직 추가/변경은 여기서만 수행합니다.
- 추가/변경 시 위 규칙을 따르고, 변경 이력은 이 주석 블록에 기록해 주세요.

----------------------------------------------------------------------
[Inventory Action Center] — 이 대시보드 전용 로직은 본 파일에만 둡니다.
----------------------------------------------------------------------
UI: 메인 대시보드(3000) → "안전재고" 진입 시 오버레이 "Inventory Action Center"
    현황 파악(Monitoring) · 조치 기록(Action Logging) · Risk KPIs · 상세 재고 테이블 · 관리자 코멘트

  UI 구역                              | 본 파일 함수                          | API (main.py)
  -------------------------------------|----------------------------------------|------------------------------------------
  상단 Risk KPIs (총 잠긴 돈, Danger/Overstock 수, 예상 매출) | get_kpi_summary()              | GET /api/safety-stock-kpi
  재고 상태별 건수 (파이/요약)         | get_safety_stock_summary()             | GET /api/safety-stock
  상세 재고 테이블 (제품·현재고·안전재고·상태·잠긴 돈) | get_inventory_list(status_filter) | GET /api/safety-stock-inventory-list
  수요 예측 & 적정 재고 차트           | get_demand_forecast_chart_data()       | GET /api/safety-stock-forecast-chart
  카테고리별 상점·분기 판매 / 상품별   | get_sales_by_store_six_month(), get_sales_by_product() | GET /api/safety-stock-sales-by-store-period, ...-by-product
  실시간 재고 경고 (Health_Index < 70)  | get_inventory_critical_alerts()       | GET /api/inventory-critical-alerts

  신규 Action Center 기능 추가 시: 위와 같이 이 파일에 함수를 추가한 뒤 main.py 에서 라우트만 등록.

----------------------------------------------------------------------
[안전재고 대시보드 · Inventory Optimization.py 연동 맵]
----------------------------------------------------------------------
프론트엔드: web-development/frontend/app/page.tsx (메인 대시보드 → 안전재고 오버레이)
백엔드 API: web-development/backend/main.py 가 이 파일의 함수를 import하여 사용.

  API 엔드포인트                    | Inventory Optimization.py 함수           | 용도
  ---------------------------------|------------------------------------------|------------------------------------------
  GET /api/safety-stock             | get_safety_stock_summary()                | 재고 상태별 건수 (Danger/Normal/Overstock)
  GET /api/safety-stock-forecast-chart | get_demand_forecast_chart_data()     | 수요 예측 & 적정 재고 (예측: arima_model.joblib)
  GET /api/safety-stock-sales-by-store-period | get_sales_by_store_six_month(category) | 카테고리별 상점·6개월 구간 판매 수량
  GET /api/safety-stock-kpi         | get_kpi_summary()                         | [Action Center] KPI: 동결자금, Danger/Overstock, 예상 매출
  GET /api/safety-stock-inventory-list | get_inventory_list(status_filter)   | [Action Center] 재고 리스트(상품별, Frozen_Money 내림차순)
  GET /api/inventory-critical-alerts | get_inventory_critical_alerts()         | [3.4.4] 실시간 재고·예측 신뢰도 경고 (Health_Index < 70)

  데이터 소스: SQL 전용 — load_sales_dataframe() (load_sales_data.py → 01.data/*.sql).
  모델: arima_model.joblib 전용 (03.prediction model/arima_model.joblib). Prophet/CSV 미사용.
  새 함수 추가 시: backend/main.py 에 getattr(_inv_module, "함수명", None) 등록 후 새 라우트 추가.
----------------------------------------------------------------------
변경 이력:
  - 수요 예측: arima_model.joblib(ARIMA)만 사용, 2020년부터 분기별(quarter) 집계 및 6분기 예측.
  - 상점별 3개월(분기) 판매, 상품별 판매, 대륙/국가/상점 필터, store_countries 연동.
  - inventory_Optimization_F_logic.py 통합: get_kpi_summary, get_inventory_list 추가.
  - 데이터 소스: SQL 전용(load_sales_dataframe → 01.data/*.sql). 모델: arima_model.joblib 전용.
  - [Inventory Action Center] 전용 로직은 본 파일에만 두고, UI↔API↔함수 매핑 문서화.
----------------------------------------------------------------------
"""

import sys
import time
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any

_MODEL_SERVER = Path(__file__).resolve().parent.parent
if str(_MODEL_SERVER) not in sys.path:
    sys.path.insert(0, str(_MODEL_SERVER))
try:
    from load_sales_data import load_sales_dataframe
except ImportError:
    def load_sales_dataframe():
        return None

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
DEFAULT_PRODUCT = "MacBook Pro 16-inch"
START_QUARTER = pd.Period("2020Q1", freq="Q")  # 분기 차트 시작
FORECAST_QUARTERS = 6
FORECAST_CACHE_TTL_SEC = 300

# 수요 예측: arima_model.joblib (ARIMA만 사용)
ARIMA_MODEL_PATH = _MODEL_SERVER / "03.prediction model" / "arima_model.joblib"
if not ARIMA_MODEL_PATH.exists():
    ARIMA_MODEL_PATH = _MODEL_SERVER / "prediction model" / "arima_model.joblib"
_arima_model_cache: Any = None


def load_arima_model():
    """
    ARIMA 예측모델(arima_model.joblib) 로드. 한 번 로드 후 캐시 재사용.
    
    [로직 상세]
    - 모델 파일은 최초 1회만 로드하여 메모리 캐시(_arima_model_cache)에 저장
    - 이후 API 호출 시마다 파일을 다시 읽지 않아 속도 최적화
    - 데이터 소스: SQL (load_sales_dataframe) → 파일 재읽기 없이 메모리에서 처리
    """
    global _arima_model_cache
    if not ARIMA_MODEL_PATH.exists():
        return None
    if _arima_model_cache is not None:
        return _arima_model_cache
    try:
        import joblib
        _arima_model_cache = joblib.load(ARIMA_MODEL_PATH)
        return _arima_model_cache
    except Exception:
        return None


# 수요 예측 차트 (ARIMA) 결과 TTL 캐시
_cache_forecast_chart: dict | None = None
_cache_forecast_chart_time: float = 0.0

# 6대주 (대륙 필터 하부 카테고리 순서)
_SIX_CONTINENTS = ["Africa", "Asia", "Europe", "North America", "Oceania", "South America"]

# 국가(country) → 대륙 (상점별 3개월 필터용, 데이터에 있는 모든 국가 포함)
_COUNTRY_TO_CONTINENT = {
    "United States": "North America", "Canada": "North America", "Mexico": "North America",
    "United Kingdom": "Europe", "France": "Europe", "Germany": "Europe", "Austria": "Europe",
    "Italy": "Europe", "Spain": "Europe", "Netherlands": "Europe", "Switzerland": "Europe",
    "Japan": "Asia", "China": "Asia", "South Korea": "Asia", "Singapore": "Asia",
    "Hong Kong": "Asia", "Macau": "Asia", "India": "Asia", "Thailand": "Asia",
    "Taiwan": "Asia", "UAE": "Asia",
    "Australia": "Oceania", "New Zealand": "Oceania",
    "Colombia": "South America", "Brazil": "South America", "Argentina": "South America",
}


def run_inventory_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """
    노트북(Inventory Optimization.ipynb)과 동일한 로직:
    Safety_Stock 산출 → Inventory 시뮬레이션 → Status 진단 → Frozen_Money.
    """
    if df is None or df.empty:
        return df
    df = df.copy()

    # 기존 분석 컬럼 제거
    cols_to_remove = [
        "Inventory",
        "Frozen_Money",
        "Safety_Stock",
        "Safety_Stock_x",
        "Safety_Stock_y",
        "Status",
        "Simulated_Sales",
        "Recovered_Money",
    ]
    df = df.drop(columns=[c for c in cols_to_remove if c in df.columns])

    if "Product_Name" not in df.columns or "quantity" not in df.columns:
        return df

    # quantity 숫자화
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)

    # [Step 1] 제품별 안전 재고
    product_stats = (
        df.groupby("Product_Name")["quantity"]
        .agg(["mean", "std"])
        .reset_index()
    )
    product_stats.fillna(0, inplace=True)
    np.random.seed(99)
    noise_factor = np.random.uniform(0.8, 1.5, size=len(product_stats))
    base_safety = product_stats["mean"] + 2 * product_stats["std"]
    product_stats["Safety_Stock"] = np.ceil(base_safety * noise_factor).astype(int)
    df = df.merge(
        product_stats[["Product_Name", "Safety_Stock"]],
        on="Product_Name",
        how="left",
    )

    # [Step 2–3] 재고 수준 생성 및 과잉 재고 타겟
    np.random.seed(42)
    df["Inventory"] = (
        df["Safety_Stock"] + df["quantity"] + np.random.randint(0, 5, size=len(df))
    )
    target_products = [
        "MacBook Pro 16-inch",
        "Mac Studio",
        "Apple Watch Ultra",
        "iPad Pro 12.9-inch",
        "iMac 24-inch",
    ]
    mask_over = df["Product_Name"].isin(target_products)
    df.loc[mask_over, "Inventory"] = df.loc[mask_over, "Safety_Stock"] * 4

    # [Step 4] Status, Frozen_Money
    conditions = [
        df["Inventory"] < df["Safety_Stock"],
        df["Inventory"] > df["Safety_Stock"] * 3,
        df["Inventory"] >= df["Safety_Stock"],
    ]
    choices = ["Danger", "Overstock", "Normal"]
    df["Status"] = np.select(conditions, choices, default="Normal")

    if "price" in df.columns:
        price = pd.to_numeric(df["price"], errors="coerce").fillna(0)
        df["Frozen_Money"] = ((df["Inventory"] - df["quantity"]) * price).clip(lower=0)
    else:
        df["Frozen_Money"] = 0

    return df


def get_safety_stock_summary():
    """
    [Inventory Action Center] 재고 상태(Status)별 건수 및 총 건수.
    안전재고 대시보드·Inventory Optimization.ipynb와 동일한 파이프라인 실행 후 집계.
    반환: {"statuses": [{"status": "상태명", "count": 건수}, ...], "total_count": 총건수}
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {"statuses": [], "total_count": 0}
    df = run_inventory_pipeline(df)
    if df is None or df.empty or "Status" not in df.columns:
        return {"statuses": [], "total_count": 0}
    status_counts = df["Status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    statuses = [
        {
            "status": str(row["status"]).strip() if pd.notna(row["status"]) else "",
            "count": int(row["count"]),
        }
        for _, row in status_counts.iterrows()
    ]
    total_count = sum(s["count"] for s in statuses)
    return {"statuses": statuses, "total_count": total_count}


def get_kpi_summary(target_product: str | None = None):
    """
    [Inventory Action Center] 상단 Risk KPIs용 (총 잠긴 돈, Danger/Overstock 수, 예상 매출).
    안전재고 대시보드 상단 KPI(헤더 카드)용.
    
    [로직 상세]
    1. 데이터 로딩: SQL 파일(01.data/*.sql)에서 load_sales_dataframe()로 로드
       - 메모리 캐싱으로 API 호출 시마다 파일 재읽기 없음 (속도 최적화)
    
    2. 재고 지표 집계:
       - total_frozen_money: 파이프라인에서 Frozen_Money 합계
       - danger_count: Status='Danger' 건수
       - overstock_count: Status='Overstock' 건수
    
    3. 예측(ARIMA):
       - arima_model.joblib로 전체 2025년 예측 (1스텝)
       - 최근 4분기 전체 판매량 대비 대상 상품 비중 계산
       - 상품별 예측 수량 = 전체 예측 × 상품 비중 ÷ 6분기
    
    4. 예상 매출 계산:
       - 예상 매출 = (ARIMA 예측 수량) × 제품 단가
       - 별도의 매출 예측 모델 없이 가볍고 직관적인 지표 제공
    
    [충돌 방지]
    - 모든 로직은 이 모듈 내부로 격리되어 있어 다른 모델/로직과 변수명 충돌 없음
    
    데이터 소스: SQL(load_sales_dataframe). 모델: arima_model.joblib 전용.
    """
    product = (target_product or "").strip() or DEFAULT_PRODUCT
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {
            "total_frozen_money": 0.0,
            "danger_count": 0,
            "overstock_count": 0,
            "predicted_demand": 0,
            "expected_revenue": 0.0,
        }
    df = run_inventory_pipeline(df)
    if df is None or df.empty:
        return {
            "total_frozen_money": 0.0,
            "danger_count": 0,
            "overstock_count": 0,
            "predicted_demand": 0,
            "expected_revenue": 0.0,
        }
    total_frozen = float(df["Frozen_Money"].sum()) if "Frozen_Money" in df.columns else 0.0
    danger_count = int((df["Status"] == "Danger").sum()) if "Status" in df.columns else 0
    overstock_count = int((df["Status"] == "Overstock").sum()) if "Status" in df.columns else 0

    predicted_demand = 0
    expected_revenue = 0.0
    arima_model = load_arima_model()
    if arima_model is not None and "sale_date" in df.columns and "quantity" in df.columns:
        try:
            if hasattr(arima_model, "forecast"):
                fc = arima_model.forecast(steps=1)
                total_2025 = float(fc[0]) if hasattr(fc, "__getitem__") else float(fc)
            elif hasattr(arima_model, "get_forecast"):
                fc = arima_model.get_forecast(steps=1)
                total_2025 = float(fc.predicted_mean.iloc[0])
            else:
                total_2025 = 0.0
            total_2025 = max(0.0, total_2025)
            d = df.copy()
            d["sale_date"] = pd.to_datetime(d["sale_date"], errors="coerce")
            d = d.dropna(subset=["sale_date"])
            d["quarter"] = d["sale_date"].dt.to_period("Q")
            d["quantity"] = pd.to_numeric(d["quantity"], errors="coerce").fillna(0)
            split_quarter = d["sale_date"].max().to_period("Q")
            last_4_end = split_quarter
            last_4_start = last_4_end - 3
            total_4 = d[(d["quarter"] >= last_4_start) & (d["quarter"] <= last_4_end)].groupby("quarter")["quantity"].sum().sum()
            product_df = d[d["Product_Name"].astype(str).str.strip() == product]
            product_4 = product_df[(product_df["quarter"] >= last_4_start) & (product_df["quarter"] <= last_4_end)].groupby("quarter")["quantity"].sum().sum() if not product_df.empty else 0.0
            share = float(product_4) / float(total_4) if total_4 and total_4 > 0 else 0.0
            product_2025 = total_2025 * share
            predicted_demand = int(round(product_2025 / float(FORECAST_QUARTERS)))
            if "price" in df.columns:
                target_price = df[df["Product_Name"].astype(str).str.strip() == product]["price"]
                target_price = pd.to_numeric(target_price, errors="coerce").fillna(0)
                price_val = float(target_price.iloc[0]) if len(target_price) else 0.0
                expected_revenue = predicted_demand * price_val
        except Exception:
            pass
    return {
        "total_frozen_money": total_frozen,
        "danger_count": danger_count,
        "overstock_count": overstock_count,
        "predicted_demand": predicted_demand,
        "expected_revenue": expected_revenue,
    }


def get_inventory_list(status_filter: list | None = None):
    """
    [Inventory Action Center] 상세 재고 테이블용 (제품명·현재고·안전재고·상태·잠긴 돈).
    안전재고 대시보드 하단 재고 리스트(테이블)용.
    
    [로직 상세]
    - 데이터 소스: SQL(load_sales_dataframe) → 메모리 캐싱으로 빠른 처리
    - Product_Name 기준 집계 (중복 제거)
    - 정렬: Frozen_Money 내림차순 (리스크 높은 순서)
    - 필터: status_filter 지정 시 해당 Status만 반환 (예: ["Danger","Overstock"])
    - 색상 구분: 프론트엔드에서 Danger=빨강, Overstock=주황 표시
    
    데이터 소스: SQL(load_sales_dataframe).
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return []
    df = run_inventory_pipeline(df)
    if df is None or df.empty or "Product_Name" not in df.columns:
        return []
    need = ["Product_Name", "Inventory", "Safety_Stock", "Status", "Frozen_Money"]
    if not all(c in df.columns for c in need):
        return []
    if status_filter:
        df = df[df["Status"].isin(status_filter)]
    if df.empty:
        return []
    agg = df.groupby("Product_Name", as_index=False).agg(
        Inventory=("Inventory", "first"),
        Safety_Stock=("Safety_Stock", "first"),
        Status=("Status", "first"),
        Frozen_Money=("Frozen_Money", "sum"),
    )
    if "price" in df.columns:
        price_first = df.groupby("Product_Name")["price"].first()
        agg["price"] = agg["Product_Name"].map(price_first)
    else:
        agg["price"] = 0.0
    agg = agg.sort_values(by="Frozen_Money", ascending=False).reset_index(drop=True)
    agg = agg.fillna(0)
    return agg[["Product_Name", "Inventory", "Safety_Stock", "Status", "Frozen_Money", "price"]].to_dict(orient="records")


def get_inventory_critical_alerts(limit: int = 50):
    """
    [3.4.4 실시간 재고 및 예측 신뢰도 경고]
    - 안전 재고 대비 현재 재고 비율(Health_Index) 계산: (Inventory / Safety_Stock) * 100
    - Health_Index < 70 인 항목을 품절 위기(Critical)로 분류
    반환: {"critical_count": int, "critical_items": [{"Store_Name", "Product_Name", "Health_Index", "Inventory", "Safety_Stock"}, ...]}
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {"critical_count": 0, "critical_items": []}
    df = run_inventory_pipeline(df)
    if df is None or df.empty or "Product_Name" not in df.columns or "Inventory" not in df.columns or "Safety_Stock" not in df.columns:
        return {"critical_count": 0, "critical_items": []}
    safety = pd.to_numeric(df["Safety_Stock"], errors="coerce").fillna(0)
    inv = pd.to_numeric(df["Inventory"], errors="coerce").fillna(0)
    df = df.copy()
    df["Health_Index"] = np.where(safety > 0, (inv / safety) * 100.0, 0.0)
    critical = df[df["Health_Index"] < 70].copy()
    if critical.empty:
        return {"critical_count": 0, "critical_items": []}
    store_col = "Store_Name" if "Store_Name" in critical.columns else ("store_name" if "store_name" in critical.columns else None)
    cols = ["Product_Name", "Health_Index", "Inventory", "Safety_Stock"]
    if store_col:
        cols = [store_col] + cols
    for c in cols:
        if c not in critical.columns:
            critical[c] = "" if c == store_col else 0
    critical = critical[cols].drop_duplicates().sort_values("Health_Index")
    critical_count = int(critical.shape[0])
    critical = critical.head(limit)
    critical_items = []
    for _, row in critical.iterrows():
        item = {
            "Product_Name": str(row["Product_Name"]).strip() if pd.notna(row["Product_Name"]) else "",
            "Health_Index": round(float(row["Health_Index"]), 1),
            "Inventory": int(round(float(row["Inventory"]), 0)),
            "Safety_Stock": int(round(float(row["Safety_Stock"]), 0)),
        }
        if store_col:
            item["Store_Name"] = str(row[store_col]).strip() if pd.notna(row[store_col]) else ""
        critical_items.append(item)
    return {"critical_count": critical_count, "critical_items": critical_items}


def get_inventory_health_for_recommendation():
    """
    [4.1.1 유저 맞춤형 추천 엔진] 재고 기반 가중치용.
    - 상품별 Health_Index (재고 건전성) 반환. 재고가 많을수록 추천 점수 가산용.
    반환: [{"product_name": str, "health_index": float}, ...]
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return []
    df = run_inventory_pipeline(df)
    if df is None or df.empty or "Product_Name" not in df.columns or "Inventory" not in df.columns or "Safety_Stock" not in df.columns:
        return []
    safety = pd.to_numeric(df["Safety_Stock"], errors="coerce").fillna(0)
    inv = pd.to_numeric(df["Inventory"], errors="coerce").fillna(0)
    df = df.copy()
    df["Health_Index"] = np.where(safety > 0, (inv / safety) * 100.0, 0.0)
    agg = df.groupby("Product_Name", as_index=False)["Health_Index"].first()
    return [
        {"product_name": str(row["Product_Name"]).strip() if pd.notna(row["Product_Name"]) else "", "health_index": round(float(row["Health_Index"]), 1)}
        for _, row in agg.iterrows()
    ]


def _quarter_label(q) -> str:
    """Period('Q') → '2020-Q1' 형식."""
    return f"{q.year}-Q{q.quarter}"


def _get_forecast_chart_data_with_arima(df: pd.DataFrame, target_product: str, train_df: pd.DataFrame, quarterly_actual: pd.Series, split_quarter) -> list | None:
    """
    arima_model.joblib으로 전체 2025 예측 후 상품 비중 적용해 6분기 분배.
    성공 시 chart_data(과거 실적은 호출측에서 채움)의 예측 구간 리스트 반환, 실패 시 None.
    """
    arima_model = load_arima_model()
    if arima_model is None:
        return None
    try:
        if hasattr(arima_model, "forecast"):
            fc = arima_model.forecast(steps=1)
            total_2025 = float(fc[0]) if hasattr(fc, "__getitem__") else float(fc)
        elif hasattr(arima_model, "get_forecast"):
            fc = arima_model.get_forecast(steps=1)
            total_2025 = float(fc.predicted_mean.iloc[0])
        else:
            return None
    except Exception:
        return None
    total_2025 = max(0.0, total_2025)
    df = df.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    df = df.dropna(subset=["sale_date"])
    df["quarter"] = df["sale_date"].dt.to_period("Q")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    # 최근 4분기 전체 vs 해당 상품 비중
    last_4_end = split_quarter
    last_4_start = last_4_end - 3
    total_4 = df[(df["quarter"] >= last_4_start) & (df["quarter"] <= last_4_end)].groupby("quarter")["quantity"].sum().sum()
    product_4 = quarterly_actual[(quarterly_actual.index >= last_4_start) & (quarterly_actual.index <= last_4_end)].sum() if not quarterly_actual.empty else 0.0
    share = float(product_4) / float(total_4) if total_4 and total_4 > 0 else 0.0
    product_2025 = total_2025 * share
    # 다음 6분기: 균등 배분 (연간 예측을 6분기에)
    forecast_list = []
    for i in range(1, FORECAST_QUARTERS + 1):
        q = split_quarter + i
        yhat = product_2025 / float(FORECAST_QUARTERS)
        yhat = max(0.0, yhat)
        yhat_lower = max(0.0, yhat * 0.85)
        yhat_upper = yhat * 1.15
        sales_label = f"예측 판매량: {int(round(yhat)):,}대 (ARIMA)"
        stock_label = f"권장 재고: {int(round(yhat_upper)):,}대 (상한선 기준)"
        message = "적정 재고 유지"
        # 예측 구간 타겟: Store stock quantity는 yhat의 95%~130% 중간값(1.125)으로 설정
        store_stock = round(yhat * 1.125, 2)
        forecast_list.append({
            "month": _quarter_label(q),
            "yhat": round(yhat, 2),
            "yhat_lower": round(yhat_lower, 2),
            "yhat_upper": round(yhat_upper, 2),
            "store_stock_quantity": store_stock,
            "insight": {"sales_label": sales_label, "stock_label": stock_label, "message": message},
        })
    return forecast_list


def get_demand_forecast_chart_data(product_name: str | None = None):
    """
    수요 예측 & 적정 재고 그래프(대시보드 메인 차트)용 데이터.
    예측 모델: arima_model.joblib (ARIMA)만 사용. 미사용/실패 시 폴백은 백엔드 main.py.
    product_name이 있으면 해당 상품 기준, 없으면 기본 상품(MacBook Pro 16-inch). 기본만 TTL 캐시.
    반환: {
      "product_name": str,
      "chart_data": [{"month", "yhat", "yhat_lower", "yhat_upper", "insight": {...}}, ...]
    }
    """
    global _cache_forecast_chart, _cache_forecast_chart_time
    target_product = (product_name or "").strip() or DEFAULT_PRODUCT
    use_cache = not (product_name or "").strip()
    now = time.time()
    if use_cache and _cache_forecast_chart is not None and (now - _cache_forecast_chart_time) < FORECAST_CACHE_TTL_SEC:
        return _cache_forecast_chart

    df = load_sales_dataframe()
    if df is None or df.empty or "Product_Name" not in df.columns or "quantity" not in df.columns or "sale_date" not in df.columns:
        return {"product_name": target_product, "chart_data": []}
    df = df.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    df = df.dropna(subset=["sale_date"])
    agg_cols = ["quantity"]
    if "store_stock_quantity" in df.columns:
        agg_cols.append("store_stock_quantity")
    train_df = (
        df[df["Product_Name"] == target_product]
        .groupby("sale_date")[agg_cols]
        .sum()
        .reset_index()
    )
    train_df.columns = ["ds", "y"] + (["store_stock"] if "store_stock_quantity" in df.columns else [])
    if len(train_df) < 2:
        return {"product_name": target_product, "chart_data": []}

    train_df["quarter"] = train_df["ds"].dt.to_period("Q")
    quarterly_actual = train_df.groupby("quarter")["y"].sum().sort_index()
    quarterly_store = train_df.groupby("quarter")["store_stock"].sum().sort_index() if "store_stock" in train_df.columns else None
    split_quarter = train_df["ds"].max().to_period("Q")

    # 2020년부터 현재(split_quarter)까지 분기별 실적
    chart_data = []
    if not quarterly_actual.empty:
        for q in quarterly_actual.index:
            if q < START_QUARTER or q > split_quarter:
                continue
            actual = float(quarterly_actual.loc[q])
            row = {
                "month": _quarter_label(q),
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

    # 1) ARIMA(arima_model.joblib)로 6분기 예측 시도
    arima_forecast = _get_forecast_chart_data_with_arima(df, target_product, train_df, quarterly_actual, split_quarter)
    if arima_forecast is not None:
        chart_data.extend(arima_forecast)
        result = {"product_name": target_product, "chart_data": chart_data}
        if use_cache:
            _cache_forecast_chart = result
            _cache_forecast_chart_time = time.time()
        return result

    # ARIMA만 사용. 실패 시 과거 실적만 반환 → 백엔드 main.py 폴백이 예측 생성
    return {"product_name": target_product, "chart_data": chart_data or []}


def get_sales_by_store_six_month(category: str, continent: str | None = None, country: str | None = None, store_name: str | None = None):
    """
    안전재고 대시보드: 카테고리 선택 시 재고 상태 카드에 표시할
    상점(Store)별·sale_date 기준 3개월(분기) 구간 판매 수량. 대륙/국가/상점 필터 지원.
    반환: {
      "category": str,
      "periods": [...],
      "data": [...],
      "store_names": [...],
      "filter_options": { "continents": [...], "countries": [...], "stores": [...] }
    }
    """
    def _norm(s):
        return (str(s).strip() if s is not None and str(s).strip() else "(Unknown)")

    _empty_opts = {"continents": [], "countries": [], "stores": []}
    empty_out = {"category": category if (category and str(category).strip()) else "", "periods": [], "data": [], "store_names": [], "store_continents": {}, "filter_options": _empty_opts}
    if not (category and str(category).strip()):
        return empty_out
    category = str(category).strip()
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {"category": category, "periods": [], "data": [], "store_names": [], "store_continents": {}, "filter_options": _empty_opts}
    need = ["sale_date", "quantity", "Store_Name", "category_name"]
    if not all(c in df.columns for c in need):
        return {"category": category, "periods": [], "data": [], "store_names": [], "store_continents": {}, "filter_options": _empty_opts}
    df = df.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    df = df.dropna(subset=["sale_date"])
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df = df[df["category_name"].astype(str).str.strip().str.lower() == category.lower()]
    if df.empty:
        return {"category": category, "periods": [], "data": [], "store_names": [], "store_continents": {}, "filter_options": _empty_opts}

    # Country/Continent (대륙 필터용)
    if "Country" in df.columns:
        df["_country"] = df["Country"].astype(str).str.strip()
        df["continent"] = df["_country"].map(lambda c: _COUNTRY_TO_CONTINENT.get(c, "Other"))
    else:
        df["_country"] = ""
        df["continent"] = "Other"

    # 필터 옵션: 대륙=6대주(데이터 있는 것만), 국가=country 필드, 상점=store_name(Store_Name)
    present_continents = set(df["continent"].dropna().astype(str).unique().tolist())
    continents_ordered = [c for c in _SIX_CONTINENTS if c in present_continents]
    if "Other" in present_continents:
        continents_ordered.append("Other")
    filter_options = {
        "continents": continents_ordered,
        "countries": sorted(df["_country"].dropna().astype(str).replace("", pd.NA).dropna().unique().tolist()),
        "stores": sorted({_norm(s) for s in df["Store_Name"].unique()}),
    }
    # 상점별 국가 매핑 (프론트엔드에서 국가 선택 시 상점 목록 필터용)
    store_countries = {}
    for store in filter_options["stores"]:
        sub = df[df["Store_Name"].apply(_norm) == store]
        if not sub.empty and "_country" in sub.columns:
            val = sub.iloc[0]["_country"]
            store_countries[store] = str(val).strip() if pd.notna(val) else ""
        else:
            store_countries[store] = ""

    # 대륙/국가/상점 필터 적용
    if continent and str(continent).strip():
        df = df[df["continent"].astype(str).str.strip() == str(continent).strip()]
    if country and str(country).strip():
        df = df[df["_country"].astype(str).str.strip() == str(country).strip()]
    if store_name and str(store_name).strip():
        df = df[df["Store_Name"].apply(_norm) == str(store_name).strip()]

    if df.empty:
        return {"category": category, "periods": [], "data": [], "store_names": [], "store_continents": {}, "store_countries": store_countries, "filter_options": filter_options}

    # 3개월(분기) 구간 집계
    df["year"] = df["sale_date"].dt.year
    df["quarter"] = (df["sale_date"].dt.month - 1) // 3 + 1
    df["period_label"] = df["year"].astype(str) + " " + df["quarter"].astype(str) + "분기"
    agg = df.groupby(["period_label", "Store_Name"])["quantity"].sum().reset_index()
    periods_ordered = sorted(agg["period_label"].unique(), key=lambda p: (int(p.split()[0]), int(p.split()[1].replace("분기", ""))))
    store_names = sorted({_norm(s) for s in agg["Store_Name"].unique()})
    # 상점별 대륙 매핑 (하부 카테고리/범례에 대륙 표시용)
    store_continents = {}
    for store in store_names:
        sub = df[df["Store_Name"].apply(_norm) == store]
        if not sub.empty:
            store_continents[store] = str(sub.iloc[0]["continent"]).strip() if pd.notna(sub.iloc[0]["continent"]) else ""
        else:
            store_continents[store] = ""

    rows = []
    for p in periods_ordered:
        row = {"period": p}
        sub = agg[agg["period_label"] == p]
        for store in store_names:
            q = sub[sub["Store_Name"].apply(_norm) == store]["quantity"].sum()
            row[store] = int(q)
        rows.append(row)
    return {
        "category": category,
        "periods": periods_ordered,
        "data": rows,
        "store_names": store_names,
        "store_continents": store_continents,
        "store_countries": store_countries,
        "filter_options": filter_options,
    }


def get_sales_by_product(
    category: str,
    continent: str | None = None,
    country: str | None = None,
    store_name: str | None = None,
    period: str | None = None,
):
    """
    안전재고 대시보드: 동일 필터(카테고리/대륙/국가/상점) 기준으로
    product_id·product_name 별 판매 수량 집계. period 지정 시 해당 분기만 집계.
    반환: { "category": str, "period": str|None, "products": [ {"product_id", "product_name", "quantity"}, ... ] }
    """
    def _norm(s):
        return (str(s).strip() if s is not None and str(s).strip() else "(Unknown)")

    if not (category and str(category).strip()):
        return {"category": category or "", "period": period, "products": []}
    category = str(category).strip()
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {"category": category, "period": period, "products": []}
    need = ["sale_date", "quantity", "category_name", "Store_Name"]
    if not all(c in df.columns for c in need):
        return {"category": category, "period": period, "products": []}
    product_col = "Product_Name" if "Product_Name" in df.columns else ("product_name" if "product_name" in df.columns else None)
    if product_col is None:
        return {"category": category, "period": period, "products": []}
    df = df.copy()
    df["sale_date"] = pd.to_datetime(df["sale_date"], errors="coerce")
    df = df.dropna(subset=["sale_date"])
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df = df[df["category_name"].astype(str).str.strip().str.lower() == category.lower()]
    if df.empty:
        return {"category": category, "period": period, "products": []}

    if "Country" in df.columns:
        df["_country"] = df["Country"].astype(str).str.strip()
        df["continent"] = df["_country"].map(lambda c: _COUNTRY_TO_CONTINENT.get(c, "Other"))
    else:
        df["_country"] = ""
        df["continent"] = "Other"

    if continent and str(continent).strip():
        df = df[df["continent"].astype(str).str.strip() == str(continent).strip()]
    if country and str(country).strip():
        df = df[df["_country"].astype(str).str.strip() == str(country).strip()]
    if store_name and str(store_name).strip():
        df = df[df["Store_Name"].apply(_norm) == str(store_name).strip()]

    if period and str(period).strip():
        df["year"] = df["sale_date"].dt.year
        df["quarter"] = (df["sale_date"].dt.month - 1) // 3 + 1
        df["period_label"] = df["year"].astype(str) + " " + df["quarter"].astype(str) + "분기"
        df = df[df["period_label"].astype(str).str.strip() == str(period).strip()]

    if df.empty:
        return {"category": category, "period": period, "products": []}

    id_col = "product_id" if "product_id" in df.columns else None
    if id_col:
        agg = df.groupby([id_col, product_col])["quantity"].sum().reset_index()
        agg.columns = ["product_id", "product_name", "quantity"]
    else:
        agg = df.groupby(product_col)["quantity"].sum().reset_index()
        agg.columns = ["product_name", "quantity"]
        agg["product_id"] = ""

    agg["quantity"] = agg["quantity"].astype(int)
    agg = agg.sort_values("quantity", ascending=False).reset_index(drop=True)
    products = []
    for _, row in agg.iterrows():
        products.append({
            "product_id": str(row.get("product_id", "")).strip(),
            "product_name": str(row.get("product_name", "")).strip(),
            "quantity": int(row["quantity"]),
        })
    return {"category": category, "period": period, "products": products}


if __name__ == "__main__":
    summary = get_safety_stock_summary()
    print(f"재고 상태 총 건수: {summary['total_count']:,}")
    print("\n--- 재고 상태별 건수 ---")
    for s in summary["statuses"]:
        print(f"  {s['status']}: {s['count']:,}")
