"""
예측 모델 및 카테고리 판매수량 - 파이차트용 데이터 로직
- arima_model.joblib (ARIMA)를 사용한 2025년 판매 수량 예측.
- 2020~2024 연도별 판매 수량·합계 및 2025 예측: get_sales_quantity_forecast()
- 도시/스토어/국가/대륙별 카테고리 판매 수량: 2020~2024 기준.
- 데이터 소스: 모델 서버 공통 로더 (SQL 01~10 또는 CSV) ↔ 대시보드 연동
"""

import sys
import pandas as pd
from pathlib import Path

# 프로젝트 루트 기준 경로 (ajjk1)
BASE = Path(__file__).resolve().parent.parent.parent
_MODEL_SERVER = Path(__file__).resolve().parent.parent
ARIMA_MODEL_PATH = _MODEL_SERVER / "prediction model" / "arima_model.joblib"
if not ARIMA_MODEL_PATH.exists():
    ARIMA_MODEL_PATH = Path(__file__).resolve().parent / "arima_model.joblib"

# 모델 서버 공통 데이터 로더 (SQL ↔ 대시보드 동일 소스)
if str(_MODEL_SERVER) not in sys.path:
    sys.path.insert(0, str(_MODEL_SERVER))
try:
    from load_sales_data import load_sales_dataframe, QUANTITY_UNIT
except ImportError:
    def load_sales_dataframe():
        return None
    QUANTITY_UNIT = "대"
    def load_sales_dataframe():
        return None

_arima_model_cache = None


def _norm_text(v) -> str:
    """SQL/CSV 로드 값의 앞뒤 따옴표/공백 정규화."""
    if v is None:
        return ""
    try:
        s = str(v).strip()
    except Exception:
        return ""
    # 한 겹의 감싼 따옴표 제거: 'Spain' 또는 "Spain"
    if len(s) >= 2 and ((s[0] == "'" and s[-1] == "'") or (s[0] == '"' and s[-1] == '"')):
        s = s[1:-1].strip()
    return s


def load_arima_model():
    """ARIMA 예측모델 로드 (선택적). 한 번 로드 후 캐시 재사용."""
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


def get_city_category_pie_data():
    """
    2020~2024년 각 도시별 카테고리별 판매 수량.
    ARIMA 예측모델(arima_model.joblib)과 동일 기간 데이터. 파이차트용.
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return None
    if "sale_date" not in df.columns or "City" not in df.columns or "category_name" not in df.columns or "quantity" not in df.columns:
        return None
    # 지역/카테고리 표기 통일 (따옴표 잔존/공백 제거)
    df = df.copy()
    df["City"] = df["City"].map(_norm_text)
    df["category_name"] = df["category_name"].map(_norm_text)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    agg = df.groupby(["City", "year", "category_name"])["quantity"].sum().reset_index()
    result = []
    for _, row in agg.iterrows():
        result.append({
            "city": _norm_text(row["City"]),
            "year": int(row["year"]),
            "category": _norm_text(row["category_name"]),
            "quantity": int(row["quantity"]),
        })
    return result


def get_city_category_pie_response():
    """
    파이차트 API용 응답 딕셔너리 반환.
    FastAPI 엔드포인트에서 호출.
    """
    arima_model = load_arima_model()
    data = get_city_category_pie_data()
    if data is None:
        return {"data": [], "model_loaded": arima_model is not None}
    return {"data": data, "model_loaded": arima_model is not None}


def get_sale_id_pie_data():
    """
    sale_id별 파이차트 데이터.
    각 sale_id의 total_sales 기준 Top 15.
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return None
    if "sale_id" not in df.columns or "total_sales" not in df.columns:
        return None
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    top = df.nlargest(15, "total_sales").copy()
    if "Product_Name" in top.columns:
        top["label"] = top.apply(
            lambda r: f"{r['sale_id']} ({str(r.get('Product_Name', ''))[:18]})" if pd.notna(r.get("Product_Name")) and str(r.get("Product_Name", "")).strip() else str(r["sale_id"]),
            axis=1,
        )
    else:
        top["label"] = top["sale_id"].astype(str)
    result = [
        {"sale_id": str(row["sale_id"]), "product": str(row.get("Product_Name", "") or ""), "total_sales": int(round(float(row["total_sales"]), 0)), "label": row["label"]}
        for _, row in top.iterrows()
    ]
    return result


def get_sale_id_pie_response():
    """sale_id별 파이차트 API 응답"""
    data = get_sale_id_pie_data()
    if data is None:
        return {"data": []}
    return {"data": data}


def _linear_predict(years: list, values: list, target_year: int) -> float:
    """
    단순 선형 회귀: values = a * years + b
    target_year 에서의 예측값 반환.
    """
    n = len(years)
    if n < 2:
        return float(values[0]) if values else 0.0
    sum_x = sum(years)
    sum_y = sum(values)
    sum_xy = sum(x * y for x, y in zip(years, values))
    sum_xx = sum(x * x for x in years)
    denom = n * sum_xx - sum_x * sum_x
    if abs(denom) < 1e-10:
        return sum_y / n
    a = (n * sum_xy - sum_x * sum_y) / denom
    b = (sum_y - a * sum_x) / n
    return a * target_year + b


def get_sales_quantity_forecast():
    """
    2020~2024년 연도별 판매 수량 실적 + 합계, 및 2025년 예측.
    arima_model.joblib (ARIMA) 사용, 없거나 실패 시 선형 추세 폴백.
    FastAPI GET /api/sales-quantity-forecast 에서 사용.
    반환: {
        "basis_years": [2020, 2021, ...],
        "yearly_quantity": [{"year": 2020, "quantity": n}, ...],
        "total_quantity_2020_2024": int,
        "predicted_quantity_2025": int,
        "method": "arima" | "linear_trend"
    }
    """
    empty = {
        "basis_years": [],
        "yearly_quantity": [],
        "total_quantity_2020_2024": 0,
        "predicted_quantity_2025": 0,
        "predicted_2025_by_category": [],
        "year_2025_label": "25년 예상 판매 수량",
        "method": "linear_trend",
    }
    df = load_sales_dataframe()
    if df is None or df.empty:
        return empty
    if "sale_date" not in df.columns or "quantity" not in df.columns:
        return empty
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    agg = df.groupby("year")["quantity"].sum().reset_index()
    years = agg["year"].astype(int).tolist()
    quantities = agg["quantity"].astype(int).tolist()
    total_2020_2024 = sum(quantities)
    yearly_list = [{"year": int(y), "quantity": int(q)} for y, q in zip(years, quantities)]
    if not years or not quantities:
        return {
            "basis_years": list(range(2020, 2025)),
            "yearly_quantity": [],
            "total_quantity_2020_2024": 0,
            "predicted_quantity_2025": 0,
            "predicted_2025_by_category": [],
            "year_2025_label": "25년 예상 판매 수량",
            "method": "linear_trend",
        }
    # 1) ARIMA 모델로 2025 예측 시도 (arima_model.joblib 사양)
    predicted_2025 = None
    method = "linear_trend"
    arima_model = load_arima_model()
    if arima_model is not None:
        try:
            # statsmodels ARIMAResults.forecast(steps=1) 또는 유사 API
            if hasattr(arima_model, "forecast"):
                fc = arima_model.forecast(steps=1)
                pred_val = float(fc[0]) if hasattr(fc, "__getitem__") else float(fc)
                predicted_2025 = max(0, int(round(pred_val)))
                method = "arima"
            elif hasattr(arima_model, "get_forecast"):
                fc = arima_model.get_forecast(steps=1)
                pred_val = float(fc.predicted_mean.iloc[0]) if hasattr(fc, "predicted_mean") else None
                if pred_val is not None:
                    predicted_2025 = max(0, int(round(pred_val)))
                    method = "arima"
        except Exception:
            pass
    # 2) ARIMA 미사용/실패 시 선형 추세 폴백
    if predicted_2025 is None:
        pred_2025 = _linear_predict(years, quantities, 2025)
        predicted_2025 = max(0, int(round(pred_2025)))

    # 3) 25년 예상 판매 수량 카테고리별 비율 적용 (2020~2024 전체 비율로 배분)
    predicted_2025_by_category = []
    if "category_name" in df.columns and predicted_2025 > 0:
        cat_agg = df.groupby("category_name")["quantity"].sum()
        total_cat = cat_agg.sum()
        if total_cat and total_cat > 0:
            for cat, q in cat_agg.items():
                ratio = float(q) / float(total_cat)
                predicted_2025_by_category.append({
                    "category": _norm_text(cat),
                    "quantity": max(0, int(round(predicted_2025 * ratio))),
                })
            predicted_2025_by_category = [x for x in predicted_2025_by_category if x["quantity"] > 0]

    return {
        "basis_years": sorted(years),
        "yearly_quantity": yearly_list,
        "total_quantity_2020_2024": total_2020_2024,
        "predicted_quantity_2025": predicted_2025,
        "predicted_2025_by_category": predicted_2025_by_category,
        "year_2025_label": "25년 예상 판매 수량",
        "method": method,
    }


def get_2025_predicted_sales_quantity():
    """
    25년 예상 판매 수량 (단일 값).
    get_sales_quantity_forecast()의 predicted_quantity_2025와 동일.
    ARIMA 또는 선형 추세로 산출.
    """
    data = get_sales_quantity_forecast()
    return data.get("predicted_quantity_2025", 0)


def get_predicted_demand_by_product(continent=None, country=None, store_id=None, city=None):
    """
    product_id별 2020~2024년 실적 수량 + 2025년 예측 수량.
    선택 지역 지정 시 해당 지역만 집계. 수요 대시보드 상품별 수량 테이블용.
    반환: [
        {"product_id": str, "product_name": str, "category": str, "quantity_2020": int, ..., "predicted_quantity": int},
        ...
    ]
    """
    forecast = get_sales_quantity_forecast()
    total_pred = forecast.get("predicted_quantity_2025", 0) or 0
    df = load_sales_dataframe()
    if df is None or df.empty:
        return []
    if "product_id" not in df.columns or "quantity" not in df.columns:
        return []
    date_col = "sale_date" if "sale_date" in df.columns else ("Sale_Date" if "Sale_Date" in df.columns else None)
    if date_col is None:
        return []
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["_year"] = pd.to_datetime(df[date_col], errors="coerce").dt.year
    df = df[df["_year"].between(2020, 2024)]

    # 선택 지역으로 필터 (수요 대시보드 연동)
    if continent or country or store_id or city:
        df = _filter_df_by_region(df, continent=continent, country=country, store_id=store_id, city=city)
        if df is None or df.empty:
            return []

    pname_col = "product_name" if "product_name" in df.columns else ("Product_Name" if "Product_Name" in df.columns else None)
    cat_col = "category_name" if "category_name" in df.columns else None
    launch_col = "launch_date" if "launch_date" in df.columns else ("Launch_Date" if "Launch_Date" in df.columns else None)
    pid_to_name = {}
    pid_to_category = {}
    pid_to_launch_year = {}
    if pname_col:
        for _, r in df[["product_id", pname_col]].drop_duplicates("product_id").iterrows():
            pid_to_name[str(r["product_id"]).strip()] = _norm_text(r[pname_col]) or str(r["product_id"]).strip()
    if cat_col:
        for _, r in df[["product_id", cat_col]].drop_duplicates("product_id").iterrows():
            pid_to_category[str(r["product_id"]).strip()] = _norm_text(str(r[cat_col]).strip()) or ""
    if launch_col:
        for _, r in df[["product_id", launch_col]].drop_duplicates("product_id").iterrows():
            try:
                val = r[launch_col]
                if pd.isna(val) or val is None or str(val).strip() == "":
                    pid_to_launch_year[str(r["product_id"]).strip()] = 2020
                else:
                    dt = pd.to_datetime(val, errors="coerce")
                    if pd.notna(dt):
                        pid_to_launch_year[str(r["product_id"]).strip()] = int(dt.year)
                    else:
                        pid_to_launch_year[str(r["product_id"]).strip()] = 2020
            except Exception:
                pid_to_launch_year[str(r["product_id"]).strip()] = 2020

    # 연도별 product_id별 수량 집계
    agg_by_year = df.groupby(["product_id", "_year"])["quantity"].sum().reset_index()
    agg_by_year = agg_by_year.rename(columns={"_year": "year"})
    total_q = agg_by_year["quantity"].sum()
    if total_q <= 0:
        return []

    # product_id별로 2020~2024 수량 수집
    by_product = {}
    for _, row in agg_by_year.iterrows():
        pid = str(row["product_id"]).strip()
        if pid not in by_product:
            pname = pid_to_name.get(pid, pid)
            cat = pid_to_category.get(pid, "")
            launch_year = pid_to_launch_year.get(pid, 2020)
            launch_year = max(2020, min(2025, launch_year))  # X축 표시용: 2020~2025 범위
            by_product[pid] = {
                "product_id": pid,
                "product_name": pname or pid,
                "category": cat,
                "launch_year": launch_year,
                "quantity_2020": 0, "quantity_2021": 0, "quantity_2022": 0,
                "quantity_2023": 0, "quantity_2024": 0,
                "predicted_quantity": 0,
            }
        try:
            y = int(float(row["year"]))
        except (TypeError, ValueError):
            continue
        if 2020 <= y <= 2024:
            by_product[pid][f"quantity_{y}"] = int(row["quantity"])

    # 2025 예측: 전체 비율로 배분
    for pid, rec in by_product.items():
        q_sum = rec["quantity_2020"] + rec["quantity_2021"] + rec["quantity_2022"] + rec["quantity_2023"] + rec["quantity_2024"]
        if total_q > 0 and total_pred > 0 and q_sum > 0:
            ratio = float(q_sum) / float(total_q)
            rec["predicted_quantity"] = max(0, int(round(total_pred * ratio)))

    # API 응답 시 quantity_2020~2024, predicted_quantity를 명시적으로 포함 (프론트엔드 대시보드 표시용)
    result = []
    for r in by_product.values():
        total = r["quantity_2020"] + r["quantity_2021"] + r["quantity_2022"] + r["quantity_2023"] + r["quantity_2024"] + r["predicted_quantity"]
        if total <= 0:
            continue
        out = {
            "product_id": r["product_id"],
            "product_name": r["product_name"],
            "category": r.get("category", ""),
            "launch_year": int(r.get("launch_year", 2020)),
            "quantity_2020": int(r["quantity_2020"]),
            "quantity_2021": int(r["quantity_2021"]),
            "quantity_2022": int(r["quantity_2022"]),
            "quantity_2023": int(r["quantity_2023"]),
            "quantity_2024": int(r["quantity_2024"]),
            "predicted_quantity": int(r["predicted_quantity"]),
        }
        result.append(out)
    return sorted(result, key=lambda x: -(x["predicted_quantity"] + x["quantity_2024"]))


def _norm_key(s: str) -> str:
    """대소문자 무시·공백 정리 (필터 매칭용)."""
    return (s or "").strip().lower()


def _filter_df_by_region(df, continent=None, country=None, store_id=None, city=None):
    """데이터프레임을 선택 지역(대륙/국가/스토어/도시)으로 필터링."""
    if df is None or df.empty:
        return df
    df = df.copy()
    if city:
        city_norm = _norm_text(str(city))
        city_key = _norm_key(str(city))
        if "City" in df.columns:
            mask = df["City"].astype(str).map(lambda x: _norm_text(x) == city_norm or _norm_key(x) == city_key)
            df = df[mask]
    if store_id:
        sid_norm = _norm_text(str(store_id))
        sid_key = _norm_key(str(store_id))
        if "store_id" in df.columns:
            mask = df["store_id"].astype(str).map(lambda x: _norm_text(x) == sid_norm or _norm_key(x) == sid_key)
            df = df[mask]
    if country:
        country_norm = _norm_text(str(country))
        country_key = _norm_key(str(country))
        if "Country" in df.columns:
            mask = df["Country"].astype(str).map(lambda x: _norm_text(x) == country_norm or _norm_key(x) == country_key)
            df = df[mask]
    if continent:
        continent_norm = _norm_text(str(continent))
        # COUNTRY_TO_CONTINENT는 아래 정의됨. continent별 소속 국가로 필터
        from_pred = (df["Country"].astype(str).map(_norm_text).map(
            lambda c: COUNTRY_TO_CONTINENT.get(c, "")
        ) == continent_norm) if "Country" in df.columns else pd.Series([True] * len(df))
        df = df[from_pred]
    return df


def get_predicted_demand_by_category(continent=None, country=None, store_id=None, city=None):
    """
    카테고리 테이블용: category_name별 2020~2024 실적 + 2025 예측 수량.
    수요 대시보드 카테고리별 수량 테이블의 데이터 소스.
    선택 지역(continent/country/store_id/city) 지정 시 해당 지역만 집계.

    반환: [
        {"category_id": str, "category": str, "quantity_2020": int, ..., "quantity_2024": int, "predicted_quantity": int},
        ...
    ]
    """
    forecast = get_sales_quantity_forecast()
    total_pred = forecast.get("predicted_quantity_2025", 0) or 0
    df = load_sales_dataframe()
    if df is None or df.empty:
        return []
    cat_col = "category_name" if "category_name" in df.columns else None
    if cat_col is None or "quantity" not in df.columns:
        return []
    date_col = "sale_date" if "sale_date" in df.columns else ("Sale_Date" if "Sale_Date" in df.columns else None)
    if date_col is None:
        return []
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["_year"] = pd.to_datetime(df[date_col], errors="coerce").dt.year
    df = df[df["_year"].between(2020, 2024)]

    # 선택 지역으로 필터 (수요 대시보드 연동)
    if continent or country or store_id or city:
        df = _filter_df_by_region(df, continent=continent, country=country, store_id=store_id, city=city)
        if df is None or df.empty:
            return []

    # category_name -> category_id 매핑 (대시보드 표시용)
    cat_to_id = {}
    if "category_id" in df.columns:
        for _, r in df[[cat_col, "category_id"]].drop_duplicates(cat_col).iterrows():
            cat_to_id[_norm_text(str(r[cat_col]).strip())] = str(r["category_id"]).strip() if pd.notna(r["category_id"]) else ""

    # 연도별 category_name별 수량 집계
    agg_by_year = df.groupby([cat_col, "_year"])["quantity"].sum().reset_index()
    agg_by_year = agg_by_year.rename(columns={"_year": "year"})
    total_q = agg_by_year["quantity"].sum()
    if total_q <= 0:
        return []

    by_category = {}
    for _, row in agg_by_year.iterrows():
        cat = _norm_text(str(row[cat_col]).strip()) or "Unknown"
        if cat not in by_category:
            by_category[cat] = {
                "category": cat,
                "quantity_2020": 0, "quantity_2021": 0, "quantity_2022": 0,
                "quantity_2023": 0, "quantity_2024": 0,
                "predicted_quantity": 0,
            }
        try:
            y = int(float(row["year"]))
        except (TypeError, ValueError):
            continue
        if 2020 <= y <= 2024:
            by_category[cat][f"quantity_{y}"] = int(row["quantity"])

    for cat, rec in by_category.items():
        q_sum = rec["quantity_2020"] + rec["quantity_2021"] + rec["quantity_2022"] + rec["quantity_2023"] + rec["quantity_2024"]
        if total_q > 0 and total_pred > 0 and q_sum > 0:
            ratio = float(q_sum) / float(total_q)
            rec["predicted_quantity"] = max(0, int(round(total_pred * ratio)))

    result = []
    for r in by_category.values():
        total = r["quantity_2020"] + r["quantity_2021"] + r["quantity_2022"] + r["quantity_2023"] + r["quantity_2024"] + r["predicted_quantity"]
        if total <= 0:
            continue
        result.append({
            "category_id": cat_to_id.get(r["category"], ""),
            "category": r["category"],
            "quantity_2020": int(r["quantity_2020"]),
            "quantity_2021": int(r["quantity_2021"]),
            "quantity_2022": int(r["quantity_2022"]),
            "quantity_2023": int(r["quantity_2023"]),
            "quantity_2024": int(r["quantity_2024"]),
            "predicted_quantity": int(r["predicted_quantity"]),
        })
    return sorted(result, key=lambda x: -(x["predicted_quantity"] + x["quantity_2024"]))


def get_category_demand_data(continent=None, country=None, store_id=None, city=None):
    """
    카테고리별 수요 데이터 통합 반환.
    API·대시보드에서 카테고리 수요 요약용으로 사용.

    반환: {
        "by_category": [{"category_id", "category", "quantity_2020", ..., "quantity_2024", "predicted_quantity"}, ...],
        "by_year_summary": [{"year": int, "total_quantity": int, "category_count": int}, ...],
        "total_2020_2024": int,
        "predicted_2025": int,
    }
    """
    rows = get_predicted_demand_by_category(
        continent=continent, country=country, store_id=store_id, city=city
    )
    if not rows:
        rows = get_predicted_demand_by_category() or []

    total_2020_2024 = 0
    predicted_2025 = 0
    by_year = {y: {"total": 0, "cats": set()} for y in range(2020, 2026)}

    for r in rows:
        for y in range(2020, 2025):
            q = int(r.get(f"quantity_{y}", 0) or 0)
            total_2020_2024 += q
            by_year[y]["total"] += q
            if q > 0:
                by_year[y]["cats"].add(r.get("category", ""))
        p = int(r.get("predicted_quantity", 0) or 0)
        predicted_2025 += p
        by_year[2025]["total"] += p
        if p > 0:
            by_year[2025]["cats"].add(r.get("category", ""))

    by_year_summary = [
        {
            "year": y,
            "total_quantity": by_year[y]["total"],
            "category_count": len(by_year[y]["cats"]),
        }
        for y in range(2020, 2026)
    ]

    return {
        "by_category": rows,
        "by_year_summary": by_year_summary,
        "total_2020_2024": total_2020_2024,
        "predicted_2025": predicted_2025,
    }


# 도시별 좌표 (경도lon, 위도lat) - store_id 매핑용
CITY_COORDS = {
    "Paris": (2.35, 48.85),
    "London": (-0.13, 51.51),
    "Dubai": (55.27, 25.2),
    "New York": (-74.01, 40.71),
    "Melbourne": (145.0, -37.8),
    "Tokyo": (139.69, 35.69),
    "Mexico City": (-99.13, 19.43),
    "Bangkok": (100.5, 13.75),
    "Singapore": (103.85, 1.29),
    "Seoul": (126.98, 37.57),
    "Beijing": (116.41, 39.9),
    "Chicago": (-87.63, 41.88),
    "Los Angeles": (-118.24, 34.05),
    "Toronto": (-79.38, 43.65),
    "Shanghai": (121.47, 31.23),
    "Bogota": (-74.07, 4.71),
    "San Francisco": (-122.42, 37.77),
    "Vienna": (16.37, 48.21),
    "Amsterdam": (4.9, 52.37),
    "Rome": (12.5, 41.9),
    "Berlin": (13.4, 52.52),
    "Taipei": (121.57, 25.04),
    "Abu Dhabi": (54.37, 24.45),
    "Munich": (11.58, 48.14),
    "Kyoto": (135.77, 35.01),
    "Honolulu": (-157.86, 21.31),
    "Montreal": (-73.57, 45.5),
    "Macau": (113.54, 22.19),
    "Cologne": (6.95, 50.94),
    "Costa Mesa": (-117.92, 33.64),
    "Glendale": (-118.25, 34.14),
    "Portland": (-122.68, 45.52),
    "Bondi": (151.27, -33.89),
    "Brisbane": (153.03, -27.47),
    "Cheltenham": (174.95, -36.87),
    "Burnaby": (-122.96, 49.25),
    "Cupertino": (-122.03, 37.32),
    "Brooklyn": (-73.94, 40.68),
    "Philadelphia": (-75.17, 39.95),
    "Milan": (9.19, 45.46),
    "Barcelona": (2.17, 41.39),
    "Fukuoka": (130.4, 33.59),
    "Kumamoto": (130.69, 32.79),
    "Chengdu": (104.07, 30.67),
    "Ottawa": (-75.69, 45.42),
    "Hong Kong": (114.17, 22.28),
    "Sydney": (151.21, -33.87),
}


def _strip_apple_prefix(s: str) -> str:
    """스토어명에서 공통 접두사 'Apple '/ '애플 ' 제거"""
    if not s or not isinstance(s, str):
        return s
    t = s.strip()
    if t.lower().startswith("apple "):
        return t[6:].strip()  # "Apple " 제거
    if t.startswith("애플 "):
        return t[3:].strip()  # "애플 " 제거
    return t


# 스토어명 영문 → 한글 (Apple/애플 제외, 대시보드: 한글(영문) 형식)
STORE_NAME_KO = {
    "Apple Kyoto": "교토",
    "Apple Gangnam": "강남",
    "Apple Park Visitor Center": "파크 방문자 센터",
    "Apple Grand Central": "그랜드 센트럴",
    "Apple SoHo": "소호",
    "Apple Covent Garden": "코벤트 가든",
    "Apple Regent Street": "리젠트 스트리트",
    "Apple Brompton Road": "브롬프턴 로드",
    "Apple Beverly Center": "베버리 센터",
    "Apple Michigan Avenue": "미시건 애비뉴",
    "Apple Downtown Brooklyn": "다운타운 브루클린",
    "Apple Eaton Centre": "이턴 센터",
    "Apple Rideau Centre": "리도 센터",
    "Apple South Coast Plaza": "사우스코스트 플라자",
    "Apple Dubai Mall": "두바이 몰",
    "Apple Mall of the Emirates": "에미리츠 몰",
    "Apple Yas Mall": "야스 몰",
    "Apple Marunouchi": "마루노우치",
    "Apple Shinjuku": "신주쿠",
    "Apple Omotesando": "오모테산도",
    "Apple Fukuoka": "후쿠오카",
    "Apple Nanjing East": "난징동",
    "Apple Taikoo Li": "타이쿠 리",
    "Apple Taipei 101": "타이페이 101",
    "Apple Jewel Changi Airport": "주얼 창이 공항",
    "Apple Orchard Road": "오차드 로드",
    "Apple Iconsiam": "아이콘시암",
    "Apple Santa Fe": "산타페",
    "Apple Antara": "안타라",
    "Apple Parque La Colina": "파르케 라 콜리나",
    "Apple Andino": "안디노",
    "Apple Passeig de Gracia": "파세이그 데 그라시아",
    "Apple Piazza Liberty": "피아자 리베르타",
    "Apple Kurfuerstendamm": "쿠어푸르스텐담",
    "Apple Rosenstrasse": "로젠슈트라세",
    "Apple Bondi": "본디",
    "Apple Chadstone": "채드스톤",
    "Apple Sydney": "시드니",
    "Apple Ala Moana": "알라 모아나",
}


def get_store_markers():
    """
    지도 표시용 매장 마커 목록.
    store_id, store_name, store_name_ko, city, country, lon, lat
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return []
    if "store_id" not in df.columns or "City" not in df.columns or "Country" not in df.columns:
        return []
    store_name_col = "store_name" if "store_name" in df.columns else ("Store_Name" if "Store_Name" in df.columns else None)
    cols = ["store_id", "City", "Country"]
    if store_name_col:
        cols.append(store_name_col)
    stores = df[cols].drop_duplicates("store_id")
    result = []
    city_count = {}
    for _, row in stores.iterrows():
        city = _norm_text(row["City"])
        country = _norm_text(row["Country"])
        lon, lat = CITY_COORDS.get(city, (0, 0))
        idx = city_count.get(city, 0)
        city_count[city] = idx + 1
        offset_lon = (idx % 3 - 1) * 0.12 if idx > 0 else 0
        offset_lat = (idx // 3) * 0.08 if idx > 0 else 0
        store_name_raw = _norm_text(str(row.get(store_name_col, ""))) if store_name_col else ""
        store_name = _strip_apple_prefix(store_name_raw)
        store_name_ko = STORE_NAME_KO.get(store_name_raw, _strip_apple_prefix(store_name_raw)) if store_name_raw else ""
        result.append({
            "store_id": _norm_text(row["store_id"]),
            "store_name": store_name,
            "store_name_ko": store_name_ko,
            "city": city,
            "country": country,
            "lon": lon + offset_lon,
            "lat": lat + offset_lat,
        })
    return result


def get_store_category_pie_data(store_id: str):
    """
    매장(store_id)별 카테고리별 판매 수량 연도별 (2020~2024) - 파이차트용.
    반환: {"data_by_year": {2020: [...], 2021: [...], ...}}
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return None
    if "store_id" not in df.columns or "category_name" not in df.columns or "quantity" not in df.columns or "sale_date" not in df.columns:
        return None
    sid = _norm_text(store_id)
    df = df[df["store_id"].astype(str).map(_norm_text) == sid]
    if df.empty:
        return {"data_by_year": {y: [] for y in range(2020, 2025)}}
    df = df.copy()
    df["category_name"] = df["category_name"].map(_norm_text)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    agg = df.groupby(["year", "category_name"])["quantity"].sum().reset_index()
    data_by_year = {}
    for y in range(2020, 2025):
        sub = agg[agg["year"] == y]
        data_by_year[y] = [{"category": _norm_text(row["category_name"]), "quantity": int(row["quantity"])} for _, row in sub.iterrows()]
    return {"data_by_year": data_by_year}


def get_store_category_pie_response(store_id: str):
    """매장별 카테고리 파이차트 API 응답 (연도별)"""
    data = get_store_category_pie_data(store_id)
    if data is None:
        return {"data_by_year": {y: [] for y in range(2020, 2025)}}
    return data


def get_store_product_quantity_barchart_data():
    """
    각 스토어별 product_id별 판매 수량 - 바차트용.
    2020~2024 합산. 반환: [ { store_id, city, products: [ { product_id, product_name, quantity }, ... ] }, ... ]
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return []
    if "store_id" not in df.columns or "product_id" not in df.columns or "quantity" not in df.columns or "sale_date" not in df.columns:
        return []
    if "City" not in df.columns:
        return []
    # 지역/ID 표기 통일
    df = df.copy()
    df["store_id"] = df["store_id"].map(_norm_text)
    df["City"] = df["City"].map(_norm_text)
    df["_pid"] = df["product_id"].map(_norm_text)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    agg = df.groupby(["store_id", "City", "_pid"])["quantity"].sum().reset_index()
    product_names = df.groupby("_pid")["Product_Name"].first() if "Product_Name" in df.columns else None
    result = []
    for (store_id, city), group in agg.groupby(["store_id", "City"]):
        products = []
        for _, row in group.iterrows():
            pid = _norm_text(row["_pid"])
            pname = product_names.get(pid) if product_names is not None else None
            pname = str(pname).strip() if pd.notna(pname) and str(pname).strip() else pid
            products.append({
                "product_id": pid,
                "product_name": pname,
                "quantity": int(row["quantity"]),
            })
        products = [p for p in products if p["quantity"] > 0]
        products.sort(key=lambda x: -x["quantity"])
        result.append({
            "store_id": _norm_text(store_id),
            "city": _norm_text(city) if pd.notna(city) else "",
            "products": products,
        })
    result.sort(key=lambda x: x["store_id"])
    return result


def get_country_category_pie_data(country: str):
    """
    국가(Country)별 카테고리별 판매 수량 연도별 (2020~2024) - 파이차트용.
    반환: {"data_by_year": {2020: [...], 2021: [...], ...}}
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return None
    if "Country" not in df.columns or "category_name" not in df.columns or "quantity" not in df.columns or "sale_date" not in df.columns:
        return None
    country_norm = _norm_text(country)
    df = df[df["Country"].astype(str).map(_norm_text) == country_norm]
    if df.empty:
        return {"data_by_year": {y: [] for y in range(2020, 2025)}}
    df = df.copy()
    df["category_name"] = df["category_name"].map(_norm_text)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    agg = df.groupby(["year", "category_name"])["quantity"].sum().reset_index()
    data_by_year = {}
    for y in range(2020, 2025):
        sub = agg[agg["year"] == y]
        data_by_year[y] = [{"category": _norm_text(row["category_name"]), "quantity": int(row["quantity"])} for _, row in sub.iterrows()]
    return {"data_by_year": data_by_year}


def get_country_category_pie_response(country: str):
    """국가별 카테고리 파이차트 API 응답 (연도별)"""
    data = get_country_category_pie_data(country)
    if data is None:
        return {"data_by_year": {y: [] for y in range(2020, 2025)}}
    return data


def get_country_stores_pie_data(country: str):
    """
    국가에 속한 스토어별 카테고리 파이차트 데이터 (2020~2024).
    반환: [{"store_id": "ST-10", "city": "...", "data": [{"category": "...", "quantity": n}, ...]}, ...]
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return None
    if "Country" not in df.columns or "store_id" not in df.columns or "category_name" not in df.columns or "quantity" not in df.columns or "sale_date" not in df.columns:
        return None
    country_norm = _norm_text(country)
    df = df[df["Country"].astype(str).map(_norm_text) == country_norm]
    if df.empty:
        return []
    df = df.copy()
    df["store_id"] = df["store_id"].map(_norm_text)
    df["City"] = df["City"].map(_norm_text) if "City" in df.columns else df.get("City")
    df["category_name"] = df["category_name"].map(_norm_text)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    if "City" not in df.columns:
        return []
    agg = df.groupby(["store_id", "City", "category_name"])["quantity"].sum().reset_index()
    result = []
    for (store_id, city), group in agg.groupby(["store_id", "City"]):
        data = [{"category": _norm_text(row["category_name"]), "quantity": int(row["quantity"])} for _, row in group.iterrows()]
        result.append({
            "store_id": _norm_text(store_id),
            "city": _norm_text(city) if pd.notna(city) else "",
            "data": data,
        })
    return result


def get_country_stores_pie_response(country: str):
    """국가별 스토어 파이차트 API 응답"""
    data = get_country_stores_pie_data(country)
    return {"data": data if data is not None else []}


# 국가 -> 대륙 매핑 (6대주)
COUNTRY_TO_CONTINENT = {
    "United States": "North America",
    "Canada": "North America",
    "Mexico": "North America",
    "Colombia": "South America",
    "United Kingdom": "Europe",
    "France": "Europe",
    "Germany": "Europe",
    "Austria": "Europe",
    "Spain": "Europe",
    "Italy": "Europe",
    "Netherlands": "Europe",
    "China": "Asia",
    "Japan": "Asia",
    "South Korea": "Asia",
    "Taiwan": "Asia",
    "Singapore": "Asia",
    "Thailand": "Asia",
    "UAE": "Asia",
    "Australia": "Oceania",
}


def get_continent_category_pie_data():
    """
    6대주(대륙)별 카테고리별 판매 수량 연도별 (2020~2024) - 파이차트용.
    반환: [{"continent": "Asia", "continent_ko": "아시아", "lon", "lat", "data_by_year": {2020: [...], ...}}, ...]
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return None
    if "Country" not in df.columns or "category_name" not in df.columns or "quantity" not in df.columns or "sale_date" not in df.columns:
        return None
    df = df.copy()
    df["_country_norm"] = df["Country"].astype(str).map(_norm_text)
    df["category_name"] = df["category_name"].map(_norm_text)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    df["continent"] = df["_country_norm"].map(lambda c: COUNTRY_TO_CONTINENT.get(c, "Other"))
    df = df[df["continent"] != "Other"]
    if df.empty:
        return []
    CONTINENT_CENTERS = {
        "North America": (-100, 45),
        "South America": (-60, -15),
        "Europe": (15, 50),
        "Asia": (100, 34),
        "Africa": (20, 0),
        "Oceania": (135, -25),
    }
    CONTINENT_KO = {
        "North America": "북미",
        "South America": "남미",
        "Europe": "유럽",
        "Asia": "아시아",
        "Africa": "아프리카",
        "Oceania": "오세아니아",
    }
    agg = df.groupby(["continent", "year", "category_name"])["quantity"].sum().reset_index()
    result = []
    for continent in agg["continent"].unique():
        sub = agg[agg["continent"] == continent]
        data_by_year = {}
        for y in range(2020, 2025):
            sub_y = sub[sub["year"] == y]
            data_by_year[y] = [{"category": _norm_text(row["category_name"]), "quantity": int(row["quantity"])} for _, row in sub_y.iterrows()]
        # 전체 합산 data (마커/하위호환용)
        data_agg = sub.groupby("category_name")["quantity"].sum().reset_index()
        data = [{"category": _norm_text(row["category_name"]), "quantity": int(row["quantity"])} for _, row in data_agg.iterrows()]
        lon, lat = CONTINENT_CENTERS.get(continent, (0, 0))
        result.append({
            "continent": continent,
            "continent_ko": CONTINENT_KO.get(continent, continent),
            "lon": lon,
            "lat": lat,
            "data": data,
            "data_by_year": data_by_year,
        })
    return result


def get_continent_category_pie_response():
    """6대주별 카테고리 파이차트 API 응답 (연도별)"""
    data = get_continent_category_pie_data()
    return {"data": data if data is not None else []}


# 대륙별 소속 국가 목록
CONTINENT_COUNTRIES = {
    "North America": ["United States", "Canada", "Mexico"],
    "South America": ["Colombia"],
    "Europe": ["United Kingdom", "France", "Germany", "Austria", "Spain", "Italy", "Netherlands"],
    "Asia": ["China", "Japan", "South Korea", "Taiwan", "Singapore", "Thailand", "UAE"],
    "Africa": [],
    "Oceania": ["Australia"],
}

# 국가명 한글
COUNTRY_KO = {
    "United States": "미국",
    "Canada": "캐나다",
    "Mexico": "멕시코",
    "Colombia": "콜롬비아",
    "United Kingdom": "영국",
    "France": "프랑스",
    "Germany": "독일",
    "Austria": "오스트리아",
    "Spain": "스페인",
    "Italy": "이탈리아",
    "Netherlands": "네덜란드",
    "China": "중국",
    "Japan": "일본",
    "South Korea": "한국",
    "Taiwan": "대만",
    "Singapore": "싱가포르",
    "Thailand": "태국",
    "UAE": "아랍에미리트",
    "Australia": "호주",
}


def get_continent_countries_pie_data(continent: str):
    """
    대륙에 속한 국가별 카테고리 파이차트 데이터 (2020~2024).
    반환: [{"country": "China", "country_ko": "중국", "data": [{"category": "...", "quantity": n}, ...]}, ...]
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return None
    countries = CONTINENT_COUNTRIES.get(continent, [])
    if not countries:
        return []
    if "Country" not in df.columns or "category_name" not in df.columns or "quantity" not in df.columns or "sale_date" not in df.columns:
        return None
    df = df.copy()
    df["_country_norm"] = df["Country"].astype(str).map(_norm_text)
    df["category_name"] = df["category_name"].map(_norm_text)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    df["year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df[df["year"].between(2020, 2024)]
    df = df[df["_country_norm"].isin(countries)]
    if df.empty:
        return []
    agg = df.groupby(["_country_norm", "category_name"])["quantity"].sum().reset_index()
    result = []
    for country in countries:
        sub = agg[agg["_country_norm"] == country]
        if sub.empty:
            continue
        data = [{"category": _norm_text(row["category_name"]), "quantity": int(row["quantity"])} for _, row in sub.iterrows()]
        result.append({
            "country": _norm_text(country),
            "country_ko": COUNTRY_KO.get(country, country),
            "data": data,
        })
    return result


def get_continent_countries_pie_response(continent: str):
    """대륙별 국가 파이차트 API 응답"""
    data = get_continent_countries_pie_data(continent)
    return {"data": data if data is not None else []}


# =============================================================================
# 수요 대시보드 (Demand Dashboard) - 로직 수정은 여기서
# =============================================================================
def get_demand_dashboard_data(
    continent: str = None,
    country: str = None,
    store_id: str = None,
    city: str = None,
    year: int = 2024,
):
    """
    수요 대시보드용 통합 데이터.
    선택된 지역(대륙/국가/스토어/도시)과 연도에 따른 수요(판매 수량) 데이터를 반환.
    프론트엔드는 GET /api/demand-dashboard?continent=...&country=...&store_id=...&city=...&year=2024 로 호출.

    반환:
        {
            "total_demand": int,           # 선택 지역·연도 총 수요(수량)
            "category_demand": [{"category": str, "quantity": int}, ...],
            "product_demand_2025": [{"product_id", "product_name", "predicted_quantity"}, ...],
            "yearly_quantity": [{"year": int, "quantity": int}, ...],  # 전체 연도별 (선택 지역 무관)
            "overall_quantity_by_year": int | None,  # 선택 연도 전체 수량 (지역 선택 시 0이면 대체용)
        }
    """
    result = {
        "total_demand": 0,
        "category_demand": [],
        "category_demand_2025": [],  # 카테고리별 2020~2024 실적 + 2025 예측 (상품별 수량과 동일 형식)
        "product_demand_2025": [],
        "yearly_quantity": [],
        "overall_quantity_by_year": None,
        "quantity_unit": QUANTITY_UNIT,  # 수량 단위 (가격탄력성 데이터 준비용)
    }

    # 1) 선택 지역·연도별 카테고리 수요
    category_rows = []
    if continent:
        cont_data = get_continent_category_pie_data()
        if cont_data:
            for c in cont_data:
                if _norm_text(str(c.get("continent", ""))) == _norm_text(str(continent)):
                    by_year = c.get("data_by_year") or {}
                    category_rows = by_year.get(year, []) or c.get("data", [])
                    break
    elif country:
        country_data = get_country_category_pie_data(_norm_text(str(country)))
        if country_data:
            by_year = country_data.get("data_by_year") or {}
            category_rows = by_year.get(year, [])
    elif store_id:
        store_data = get_store_category_pie_data(_norm_text(str(store_id)))
        if store_data:
            by_year = store_data.get("data_by_year") or {}
            category_rows = by_year.get(year, [])
    elif city:
        city_data = get_city_category_pie_data()
        if city_data:
            city_norm = _norm_text(str(city))
            filtered = [r for r in city_data if _norm_text(str(r.get("city", ""))) == city_norm and r.get("year") == year]
            cat_map = {}
            for r in filtered:
                cat = _norm_text(r.get("category", ""))
                qty = int(r.get("quantity", 0) or 0)
                cat_map[cat] = cat_map.get(cat, 0) + qty
            category_rows = [{"category": k, "quantity": v} for k, v in cat_map.items() if v > 0]

    # 지역 미선택 시 전역 카테고리별 수요 폴백 (category_demand_2025에서 선택 연도 수량 사용)
    if not category_rows:
        try:
            cat_global = get_predicted_demand_by_category() or []
            year_col = f"quantity_{year}" if 2020 <= year <= 2024 else "predicted_quantity"
            for r in cat_global:
                qty = int(r.get(year_col, 0) or 0)
                if qty > 0:
                    category_rows.append({"category": r.get("category", ""), "quantity": qty})
        except Exception:
            pass

    result["category_demand"] = [r for r in category_rows if isinstance(r, dict) and (r.get("quantity") or 0) > 0]
    result["total_demand"] = sum(r.get("quantity", 0) or 0 for r in result["category_demand"])

    # 2) 카테고리 테이블: category별 2020~2024 실적 + 2025 예측 (선택 지역 반영)
    try:
        result["category_demand_2025"] = get_predicted_demand_by_category(
            continent=continent, country=country, store_id=store_id, city=city
        ) or []
        # 지역 필터 시 데이터 없으면 전역 폴백 (대시보드에 항상 표시)
        if not result["category_demand_2025"] and (continent or country or store_id or city):
            result["category_demand_2025"] = get_predicted_demand_by_category() or []
    except Exception:
        result["category_demand_2025"] = []

    # 3) product_id별 2025년 예측 수요 (선택 지역 반영, 없으면 전역 폴백)
    try:
        result["product_demand_2025"] = get_predicted_demand_by_product(
            continent=continent, country=country, store_id=store_id, city=city
        ) or []
        if not result["product_demand_2025"] and (continent or country or store_id or city):
            result["product_demand_2025"] = get_predicted_demand_by_product() or []
    except Exception:
        result["product_demand_2025"] = []

    # 4) 전체 연도별 수량 (forecast)
    try:
        forecast = get_sales_quantity_forecast()
        result["yearly_quantity"] = forecast.get("yearly_quantity") or []
        row = next((r for r in result["yearly_quantity"] if r.get("year") == year), None)
        result["overall_quantity_by_year"] = int(row["quantity"]) if row and isinstance(row.get("quantity"), (int, float)) else None
    except Exception:
        result["yearly_quantity"] = []
        result["overall_quantity_by_year"] = None

    return result
