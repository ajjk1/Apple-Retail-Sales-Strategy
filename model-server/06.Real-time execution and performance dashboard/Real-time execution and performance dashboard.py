"""
추천 시스템 대시보드 백엔드 데이터 (성장 전략 대시보드)
- 매출·판매 데이터 기반 추천 상품·카테고리 산출 (모델 서버 공통 로더 연동)
- FastAPI GET /api/recommendation-summary, /api/store-list, /api/store-recommendations 응답에 사용
- store_id 기반 4가지 추천 엔진 제공

데이터 소스:
- 실데이터: load_sales_dataframe() → SQL(01.data/*.sql). 상점 목록·추천·매출·피봇·상관관계 등은 모두 동일 SQL 기반.
- 예측 모델: arima_model.joblib 은 Inventory Optimization 등에서 사용. 본 모듈은 매출 시계열만 선형 추세 사용.
- 샘플/시뮬레이션 (대시보드에서 강조 표시): get_customer_journey_funnel() 퍼널 User_Count [10000,4500,1200,400],
  get_funnel_stage_weight() 단계별 가중치·전략, performance_simulation(Lift 1.15) 는 예시/가정 데이터.

제공 함수:
- get_store_list() : 성장 전략 대시보드용 상점 목록 (store_id, store_name) — 동일 데이터 소스 보장
- get_store_performance_grade() : [3.4.1] 매장 등급 및 달성률 분석 (목표 대비 달성률, S/A/C 등급, 등급 분포)
- get_region_category_pivot(country=None) : [3.4.2] 지역별 카테고리 매출 피봇 (국가×제품군 매출, 선택 국가 카테고리 점유율)
- get_price_demand_correlation(product_name=None) : [3.4.3] 가격-수요 상관관계 및 인사이트 (상관계수, 전략 문구, 스캐터 데이터)
- get_recommendation_summary() : 추천 대시보드용 Top 상품·Top 카테고리 (실시간 집계)
- get_store_recommendations(store_id) : 특정 상점의 4가지 추천 모델 결과
  - association_recommendations: 연관 분석 (Apriori, Lift)
  - similar_store_recommendations: 유사 상점 기반 (Cosine Similarity)
  - latent_demand_recommendations: 잠재 수요 (SVD/MF)
  - trend_recommendations: 트렌드 분석 (판매 증가율)
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

# [4.1.1] 유저(상점) 맞춤형 추천: inventory_health는 main.py에서 Inventory Optimization 결과를 넘겨받음

_MODEL_SERVER = Path(__file__).resolve().parent.parent
if str(_MODEL_SERVER) not in sys.path:
    sys.path.insert(0, str(_MODEL_SERVER))
try:
    from load_sales_data import load_sales_dataframe
except Exception:
    def load_sales_dataframe():
        return None


def get_recommendation_summary():
    """
    추천 시스템 대시보드용: 매출 기준 추천 상품(Top 15)·추천 카테고리(Top 10)
    반환: {
        "top_products": [{"product": "상품명", "sales": 매출, "rank": 순위}, ...],
        "top_categories": [{"category": "카테고리명", "sales": 매출, "rank": 순위}, ...],
    }
    - FastAPI GET /api/recommendation-summary 응답에 그대로 사용
    - 데이터 소스: load_sales_data (SQL 01~10 또는 CSV) ↔ 대시보드 동일
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {"top_products": [], "top_categories": []}

    # 컬럼명 통일 (load_sales_data는 Product_Name 등으로 rename함)
    product_col = "Product_Name" if "Product_Name" in df.columns else "product_name"
    if product_col not in df.columns:
        product_col = next((c for c in df.columns if "product" in c.lower()), None)
    cat_col = "category_name" if "category_name" in df.columns else next((c for c in df.columns if "category" in c.lower()), None)
    if "total_sales" not in df.columns:
        return {"top_products": [], "top_categories": []}

    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)

    # 추천 상품: 매출 Top 15
    top_products = []
    if product_col:
        by_product = (
            df.groupby(product_col)["total_sales"]
            .sum()
            .sort_values(ascending=False)
            .head(15)
            .reset_index()
        )
        for rank, (_, row) in enumerate(by_product.iterrows(), 1):
            top_products.append({
                "product": str(row[product_col]).strip() if pd.notna(row[product_col]) else "",
                "sales": int(round(float(row["total_sales"]), 0)),
                "rank": rank,
            })

    # 추천 카테고리: 매출 Top 10
    top_categories = []
    if cat_col:
        by_cat = (
            df.groupby(cat_col)["total_sales"]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        for rank, (_, row) in enumerate(by_cat.iterrows(), 1):
            top_categories.append({
                "category": str(row[cat_col]).strip() if pd.notna(row[cat_col]) else "",
                "sales": int(round(float(row["total_sales"]), 0)),
                "rank": rank,
            })

    return {"top_products": top_products, "top_categories": top_categories}


def get_store_list() -> Dict[str, List[Dict[str, str]]]:
    """
    성장 전략 대시보드용 상점 목록 반환. 추천·매출 예측과 동일한 load_sales_dataframe() 사용.
    반환: {"stores": [{"store_id": str, "store_name": str}, ...]} (store_id 기준 정렬)
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        print("[Real-time] get_store_list: df is None or empty")
        return {"stores": []}
    store_id_col = "store_id" if "store_id" in df.columns else None
    if not store_id_col:
        print(f"[Real-time] get_store_list: store_id 컬럼 없음. 컬럼: {list(df.columns)[:10]}")
        return {"stores": []}
    name_col = "Store_Name" if "Store_Name" in df.columns else ("store_name" if "store_name" in df.columns else None)
    stores = df[store_id_col].astype(str).str.strip().unique().tolist()
    store_names: Dict[str, str] = {}
    if name_col:
        for sid in stores:
            sub = df[df[store_id_col].astype(str).str.strip() == sid]
            if not sub.empty:
                val = sub[name_col].iloc[0]
                store_names[sid] = str(val).strip() if pd.notna(val) else sid
            else:
                store_names[sid] = sid
    else:
        store_names = {s: s for s in stores}
    sorted_stores = sorted(stores, key=lambda x: (x.upper(), x))
    result = {
        "stores": [{"store_id": s, "store_name": store_names.get(s, s)} for s in sorted_stores]
    }
    n = len(result["stores"])
    print(f"[Real-time] get_store_list: 반환 상점 {n}건 (store_id 컬럼={store_id_col}, store_name 컬럼={name_col})")
    if n > 0:
        print(f"[Real-time] get_store_list: 첫 상점 예시 - {result['stores'][0]}")
    return result


def _store_id_to_user_id(store_id: str) -> int:
    """store_id(예: ST-10) -> 숫자 user_id. 파싱 실패 시 1025 반환."""
    if not store_id:
        return 1025
    s = str(store_id).strip().upper()
    if s.startswith("ST-"):
        try:
            return int(s[3:].strip())
        except ValueError:
            pass
    try:
        return int("".join(c for c in s if c.isdigit()) or "1025")
    except ValueError:
        return 1025


def get_user_personalized_recommendations(
    store_id: str,
    inventory_health: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    [4.1.1 유저별(상점별) 상품 가중치 추천]
    - 상점(store_id)의 판매 이력(카테고리)을 구매 이력으로 간주.
    - 재고 건전성(Health_Index) 기반 점수 + 동일 카테고리 +50점.
    - inventory_health: Inventory Optimization.get_inventory_health_for_recommendation() 결과.
    반환: user_id, recommendations[{ rank, product_id, reason }], top_3, user_history_categories
    """
    _default_simulation = {"lift_rate": 1.15, "expected_sales_increase_pct": 15.0, "insight": "추천 시스템 도입 시 예상 매출 증대 효과: 15.0%", "projected_scores": [], "data_source": "simulation", "data_source_description": "시뮬레이션 (15% 상승 가정)."}
    empty_out = {
        "user_id": _store_id_to_user_id(store_id),
        "user_identifier": store_id,
        "recommendations": [],
        "top_3": [],
        "user_history_categories": [],
        "performance_simulation": _default_simulation,
    }
    df = load_sales_dataframe()
    if df is None or df.empty or not inventory_health:
        return empty_out

    store_id_col = "store_id" if "store_id" in df.columns else None
    cat_col = "category_name" if "category_name" in df.columns else next((c for c in df.columns if "category" in c.lower()), None)
    product_col = "Product_Name" if "Product_Name" in df.columns else "product_name"
    pid_col = "product_id" if "product_id" in df.columns else None

    product_to_id: Dict[str, str] = {}
    if pid_col and product_col and pid_col in df.columns:
        for _, row in df[[product_col, pid_col]].drop_duplicates(product_col).iterrows():
            p = str(row[product_col]).strip() if pd.notna(row[product_col]) else ""
            pid = str(row[pid_col]).strip() if pd.notna(row[pid_col]) else ""
            if p:
                product_to_id[p] = pid or p

    user_history = []
    if store_id_col and cat_col:
        sub = df[df[store_id_col].astype(str).str.strip() == str(store_id).strip()]
        if not sub.empty:
            user_history = sub[cat_col].dropna().astype(str).str.strip().unique().tolist()
            user_history = [c for c in user_history if c and c != "nan"]

    stock_weight = []
    for item in inventory_health:
        pn = (item.get("product_name") or "").strip()
        hi = float(item.get("health_index") or 0)
        score = hi * 0.1
        stock_weight.append({"Product_Name": pn, "Score": score})

    if not stock_weight:
        return {**empty_out, "user_history_categories": user_history}

    recommend_list = pd.DataFrame(stock_weight)
    product_to_cat = {}
    if product_col in df.columns and cat_col:
        for _, row in df[[product_col, cat_col]].drop_duplicates(product_col).iterrows():
            p = str(row[product_col]).strip() if pd.notna(row[product_col]) else ""
            c = str(row[cat_col]).strip() if pd.notna(row[cat_col]) else ""
            if p and c:
                product_to_cat[p] = c

    user_cats = set(c.strip().lower() for c in user_history) if user_history else set()
    if user_cats and not recommend_list.empty and product_to_cat:
        for idx in recommend_list.index:
            pn = str(recommend_list.at[idx, "Product_Name"]).strip()
            cat = product_to_cat.get(pn, "")
            if cat.strip().lower() in user_cats:
                recommend_list.at[idx, "Score"] = recommend_list.at[idx, "Score"] + 50.0

    final = recommend_list.sort_values(by="Score", ascending=False).head(3)
    top_3 = [
        {"product_name": str(row["Product_Name"]).strip(), "score": round(float(row["Score"]), 1)}
        for _, row in final.iterrows()
    ]
    recommendations = []
    for rank, (_, row) in enumerate(final.iterrows(), 1):
        pn = str(row["Product_Name"]).strip()
        product_id = product_to_id.get(pn, pn)
        cat = product_to_cat.get(pn, "")
        if user_cats and cat.strip().lower() in user_cats:
            reason = "구매 이력 기반 및 재고 충분"
        else:
            reason = "유사 유저 선호 제품" if rank >= 2 else "재고 충분"
        recommendations.append({"rank": rank, "product_id": product_id, "reason": reason})

    # [4.3 성과 지표 시뮬레이션: 추천 도입 후 재고 소진 속도] 기대 매출 증대 효과 (Lift 15% 가정)
    lift_rate = 1.15
    expected_pct = round((lift_rate * 100 - 100), 1)
    projected_scores = [round(float(row["Score"]) * lift_rate, 1) for _, row in final.iterrows()]
    performance_simulation = {
        "lift_rate": lift_rate,
        "expected_sales_increase_pct": expected_pct,
        "insight": f"추천 시스템 도입 시 예상 매출 증대 효과: {expected_pct}%",
        "projected_scores": projected_scores,
        "data_source": "simulation",
        "data_source_description": "시뮬레이션 (기존 판매량 대비 15% 상승 가정). 실제 효과는 A/B 테스트로 검증 필요.",
    }

    return {
        "user_id": _store_id_to_user_id(store_id),
        "user_identifier": store_id,
        "recommendations": recommendations,
        "top_3": top_3,
        "user_history_categories": user_history,
        "performance_simulation": performance_simulation,
    }


def get_collab_filter_with_inventory_boost(
    store_id: str,
    inventory_health: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    [4.1.1 유저(상점) 기반 협업 필터링 및 재고 가중치 결합]
    - store_id를 유저로 간주, store-item(quantity) 피벗 → 유저 간 코사인 유사도 → 유사 상점 상위 5명 구매 패턴 평균.
    - 재고 가중치: Health_Index >= 120(과잉 재고) 품목에 20% 가산점(boost=1.2), 나머지 1.0.
    - final_score = base_score * boost, 상위 3개 추천.
    반환: { "target_store": store_id, "top_recommendations": [{"product_name", "base_score", "boost", "final_score"}, ...] }
    """
    empty_out = {"target_store": store_id, "top_recommendations": []}
    df = load_sales_dataframe()
    if df is None or df.empty:
        return empty_out

    store_id_col = "store_id" if "store_id" in df.columns else None
    product_col = "Product_Name" if "Product_Name" in df.columns else "product_name"
    if not store_id_col or product_col not in df.columns:
        return empty_out

    df = df.copy()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    store_item = df.groupby([store_id_col, product_col])["quantity"].sum().reset_index()
    user_item_matrix = store_item.pivot_table(index=store_id_col, columns=product_col, values="quantity", aggfunc="sum").fillna(0)

    if store_id not in user_item_matrix.index or user_item_matrix.shape[0] < 2:
        return empty_out

    try:
        from sklearn.metrics.pairwise import cosine_similarity
        user_sim = cosine_similarity(user_item_matrix)
        user_sim_df = pd.DataFrame(user_sim, index=user_item_matrix.index, columns=user_item_matrix.index)
    except ImportError:
        def _cosine(a: np.ndarray, b: np.ndarray) -> float:
            dot = np.dot(a, b)
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            return (dot / (na * nb)) if (na > 0 and nb > 0) else 0.0
        mat = user_item_matrix.values
        n = len(mat)
        user_sim = np.array([[ _cosine(mat[i], mat[j]) for j in range(n)] for i in range(n)])
        user_sim_df = pd.DataFrame(user_sim, index=user_item_matrix.index, columns=user_item_matrix.index)

    target_store = str(store_id).strip()
    if target_store not in user_sim_df.index:
        return empty_out
    similar_stores = user_sim_df[target_store].sort_values(ascending=False)[1:6].index
    score_series = user_item_matrix.loc[similar_stores].mean()

    final_scores = score_series.to_frame(name="base_score")
    final_scores["boost"] = 1.0
    if inventory_health:
        boost_items = {
            (item.get("product_name") or "").strip()
            for item in inventory_health
            if float(item.get("health_index") or 0) >= 120
        }
        boost_items.discard("")
        if boost_items:
            final_scores.loc[final_scores.index.isin(boost_items), "boost"] = 1.2
    final_scores["final_score"] = final_scores["base_score"] * final_scores["boost"]

    top_df = final_scores.sort_values(by="final_score", ascending=False).head(3)
    top_recommendations = [
        {
            "product_name": str(pn).strip(),
            "base_score": round(float(row["base_score"]), 2),
            "boost": round(float(row["boost"]), 2),
            "final_score": round(float(row["final_score"]), 2),
        }
        for pn, row in top_df.iterrows()
    ]
    return {"target_store": store_id, "top_recommendations": top_recommendations}


def get_customer_journey_funnel() -> Dict[str, Any]:
    """
    [4.4.1 고객 여정 단계별 수치 분석]
    - 실제 환경에서는 로그 기반 단계별 Unique User 수 집계. 여기서는 샘플 퍼널 데이터로 로직 구현.
    - 단계별 전환율(Conversion_Rate) = 이전 단계 대비 다음 단계로 넘어간 비율(%).
    - 전체 대비 최종 전환율(Overall CVR) = 마지막 단계 / 첫 단계 * 100.
    - 전환율 40% 미만 구간을 병목(집중 개선 필요)으로 식별.
    반환: { "stages": [{"stage", "user_count", "conversion_rate"}], "overall_cvr": float, "drop_off": [{"stage", "conversion_rate"}] }
    """
    funnel_data = {
        "Stage": ["Main_Exposure", "Product_Click", "Add_to_Cart", "Purchase"],
        "User_Count": [10000, 4500, 1200, 400],
    }
    funnel_df = pd.DataFrame(funnel_data)
    funnel_df["Conversion_Rate"] = funnel_df["User_Count"].pct_change().add(1).fillna(1) * 100
    overall_cvr = (float(funnel_df.iloc[-1]["User_Count"]) / float(funnel_df.iloc[0]["User_Count"])) * 100
    drop_off_df = funnel_df[funnel_df["Conversion_Rate"] < 40]
    stages = [
        {"stage": str(row["Stage"]), "user_count": int(row["User_Count"]), "conversion_rate": round(float(row["Conversion_Rate"]), 2)}
        for _, row in funnel_df.iterrows()
    ]
    drop_off = [
        {"stage": str(row["Stage"]), "conversion_rate": round(float(row["Conversion_Rate"]), 2)}
        for _, row in drop_off_df.iterrows()
    ]
    return {
        "stages": stages,
        "overall_cvr": round(overall_cvr, 2),
        "drop_off": drop_off,
        "data_source": "sample",
        "data_source_description": "샘플 퍼널 데이터 (User_Count: 10000→4500→1200→400). 실제 환경에서는 로그 기반 단계별 Unique User 수 집계 필요.",
    }


# [4.4.2] 퍼널 단계별 추천 가중치·전략 (독립된 if문 로직)
_FUNNEL_STAGE_WEIGHTS = {
    "Main_Exposure": {"recommendation_weight": 1.2, "strategy": "대중적 인기 제품 중심 노출 가중치 부여"},
    "Product_Click": {"recommendation_weight": 1.0, "strategy": "클릭 이력 기반 유사 제품·카테고리 노출"},
    "Add_to_Cart": {"recommendation_weight": 1.5, "strategy": "장바구니 제품과 호환되는 액세서리 및 재고 최적화 품목 노출"},
    "Purchase": {"recommendation_weight": 1.0, "strategy": "구매 완료 후 액세서리·연관 상품 추천"},
}


def get_funnel_stage_weight(current_user_stage: Optional[str] = None) -> Dict[str, Any]:
    """
    [4.4.2 퍼널 위치에 따른 가중치 동적 할당]
    - current_user_stage가 없으면 전체 단계별 가중치·전략 반환.
    - 있으면 해당 단계의 recommendation_weight, strategy만 반환.
    """
    if current_user_stage is None or not str(current_user_stage).strip():
        return {
            "stages": [
                {"stage": k, "recommendation_weight": v["recommendation_weight"], "strategy": v["strategy"]}
                for k, v in _FUNNEL_STAGE_WEIGHTS.items()
            ],
            "data_source": "sample",
            "data_source_description": "예시 가중치·전략 (실제 환경에서는 A/B 테스트·로그 기반 튜닝 권장).",
        }
    stage_key = str(current_user_stage).strip()
    if stage_key in _FUNNEL_STAGE_WEIGHTS:
        rec = _FUNNEL_STAGE_WEIGHTS[stage_key]
        return {"current_stage": stage_key, "recommendation_weight": rec["recommendation_weight"], "strategy": rec["strategy"], "data_source": "sample"}
    return {"current_stage": stage_key, "recommendation_weight": 1.0, "strategy": "기본 가중치 적용", "data_source": "sample"}


def _strip_apple_prefix(s: str) -> str:
    """스토어명에서 'Apple ' / '애플 ' 접두사 제거 (표시용)."""
    if not s or not isinstance(s, str):
        return s
    t = str(s).strip()
    if t.lower().startswith("apple "):
        return t[6:].strip()
    if t.startswith("애플 "):
        return t[3:].strip()
    return t


def _annual_forecast_from_df(df: pd.DataFrame) -> float:
    """연도별 total_sales 집계 후 선형 추세로 2025년 예측. 실적 없으면 전체 합계 반환."""
    if df is None or df.empty or "total_sales" not in df.columns:
        return 0.0
    if "sale_date" not in df.columns:
        return float(df["total_sales"].sum())
    df = df.copy()
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    df["_year"] = pd.to_datetime(df["sale_date"], errors="coerce").dt.year
    df = df.dropna(subset=["_year"])
    by_year = df.groupby("_year")["total_sales"].sum()
    if by_year.empty or len(by_year) < 2:
        return float(by_year.sum()) if not by_year.empty else float(df["total_sales"].sum())
    years = sorted(by_year.index.astype(int).tolist())
    if 2025 in years:
        return float(by_year.get(2025, by_year.iloc[-1]))
    last_y = years[-1]
    first_y = years[0]
    slope = (float(by_year[last_y]) - float(by_year[first_y])) / (last_y - first_y) if (last_y - first_y) != 0 else 0.0
    pred_2025 = float(by_year[last_y]) + slope * (2025 - last_y)
    return max(0.0, pred_2025)


def get_store_performance_grade() -> Dict[str, Any]:
    """
    [3.4.1 매장 등급 및 달성률 분석] — 성장 전략 대시보드용.
    - 매장별 총 매출 집계 (Country, Store_Name)
    - 연간 예측(2025)을 기반으로 매장당 목표 배분 후 달성률 산출 (동일 데이터 소스: load_sales_dataframe)
    - 성과 등급: S(>=100%), A(80%~100%), C(기본)
    반환: {
        "store_performance": [{"country", "store_name", "total_sales", "achievement_rate", "grade", "target_annual"}, ...],
        "grade_distribution": [{"grade": "S", "count": n, "pct": float}, ...],
        "annual_forecast_revenue": int
    }
    """
    df = load_sales_dataframe()
    if df is None or df.empty or "total_sales" not in df.columns:
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": 0}

    annual_forecast_revenue = _annual_forecast_from_df(df)
    if annual_forecast_revenue <= 0:
        annual_forecast_revenue = float(df["total_sales"].sum())

    country_col = "Country" if "Country" in df.columns else None
    name_col = "Store_Name" if "Store_Name" in df.columns else ("store_name" if "store_name" in df.columns else None)
    if not name_col:
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": int(annual_forecast_revenue)}

    group_cols = [name_col]
    if country_col:
        group_cols.insert(0, country_col)

    df = df.copy()
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    store_perf = df.groupby(group_cols)["total_sales"].sum().reset_index()
    if store_perf.empty:
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": int(annual_forecast_revenue)}

    n_stores = store_perf[name_col].nunique()
    if n_stores <= 0:
        return {"store_performance": [], "grade_distribution": [], "annual_forecast_revenue": int(annual_forecast_revenue)}

    target_annual = annual_forecast_revenue / n_stores
    if target_annual <= 0:
        target_annual = 1.0
    store_perf["target_annual"] = target_annual
    store_perf["Achievement_Rate"] = (store_perf["total_sales"] / target_annual) * 100.0
    store_perf["Grade"] = "C"
    store_perf.loc[store_perf["Achievement_Rate"] >= 100, "Grade"] = "S"
    store_perf.loc[(store_perf["Achievement_Rate"] >= 80) & (store_perf["Achievement_Rate"] < 100), "Grade"] = "A"

    store_performance: List[Dict[str, Any]] = []
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


def get_region_category_pivot(country: Optional[str] = None) -> Dict[str, Any]:
    """
    [3.4.2 지역별 카테고리 매출 피봇 분석]
    - 국가(Country) × 제품군(category_name) 매출 피봇 테이블 생성
    - country 지정 시 해당 국가의 카테고리 점유율(파이 차트용) 반환
    반환: {
        "countries": [str],
        "categories": [str],
        "pivot_rows": [{"country": str, "total_sales": int, "by_category": {cat: sales}, ...}],
        "category_share": [{"category": str, "pct": float, "total_sales": int}, ...]  # country 지정 시만
    }
    """
    df = load_sales_dataframe()
    if df is None or df.empty or "total_sales" not in df.columns:
        return {"countries": [], "categories": [], "pivot_rows": [], "category_share": []}

    country_col = "Country" if "Country" in df.columns else ("country" if "country" in df.columns else None)
    cat_col = "category_name" if "category_name" in df.columns else next((c for c in df.columns if "category" in c.lower()), None)
    if not country_col or not cat_col:
        return {"countries": [], "categories": [], "pivot_rows": [], "category_share": []}

    df = df.copy()
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    pivot_table = df.pivot_table(
        index=country_col, columns=cat_col, values="total_sales", aggfunc="sum", fill_value=0
    )
    if pivot_table.empty:
        return {"countries": [], "categories": [], "pivot_rows": [], "category_share": []}

    countries = [str(x).strip() for x in pivot_table.index.tolist()]
    categories = [str(x).strip() for x in pivot_table.columns.tolist()]

    pivot_rows: List[Dict[str, Any]] = []
    for c in countries:
        row = pivot_table.loc[c] if c in pivot_table.index else pd.Series()
        by_cat = {str(k): int(round(float(v), 0)) for k, v in row.items()} if not row.empty else {}
        total = int(round(float(pivot_table.loc[c].sum() if c in pivot_table.index else 0), 0))
        pivot_rows.append({"country": c, "total_sales": total, "by_category": by_cat})

    out: Dict[str, Any] = {
        "countries": countries,
        "categories": categories,
        "pivot_rows": pivot_rows,
    }

    # 선택 국가의 카테고리 점유율 (파이 차트용)
    country_share: List[Dict[str, Any]] = []
    target_country = (country or "").strip()
    if target_country and target_country in pivot_table.index:
        series = pivot_table.loc[target_country]
        total = float(series.sum())
        if total > 0:
            for cat in series.index:
                val = float(series[cat])
                country_share.append({
                    "category": str(cat).strip(),
                    "total_sales": int(round(val, 0)),
                    "pct": round((val / total) * 100.0, 1),
                })
            country_share.sort(key=lambda x: -x["total_sales"])
    out["category_share"] = country_share
    return out


def get_price_demand_correlation(product_name: Optional[str] = None) -> Dict[str, Any]:
    """
    [3.4.3 가격-수요 상관관계 및 인사이트 도출]
    - 특정 제품의 price vs quantity 상관계수 산출
    - 인사이트: corr < -0.6 → 가격 민감도 높음 / else → 프리미엄 수요 안정
    반환: {
        "product_name": str,
        "correlation": float,
        "insight": str,
        "scatter_data": [{"price": float, "quantity": float}, ...],
        "available_products": [str, ...],
    }
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {"product_name": "", "correlation": None, "insight": "데이터 없음", "scatter_data": [], "available_products": []}

    product_col = "Product_Name" if "Product_Name" in df.columns else "product_name"
    price_col = "price" if "price" in df.columns else next((c for c in df.columns if c.lower() == "price"), None)
    qty_col = "quantity" if "quantity" in df.columns else next((c for c in df.columns if "quantity" in c.lower()), None)
    if not product_col or not price_col or not qty_col:
        return {"product_name": "", "correlation": None, "insight": "데이터 없음", "scatter_data": [], "available_products": []}

    # 제품 목록 (매출 상위 N개 등으로 제한 가능)
    products = df[product_col].dropna().astype(str).str.strip().unique().tolist()
    products = sorted([p for p in products if p])[:100]
    out: Dict[str, Any] = {
        "product_name": "",
        "correlation": None,
        "insight": "분석 중",
        "scatter_data": [],
        "available_products": products,
    }

    target_name = (product_name or "").strip() if product_name else None
    if not target_name and products:
        target_name = products[0]
    if not target_name:
        return out

    target_p = df[df[product_col].astype(str).str.strip() == target_name].copy()
    if target_p.empty:
        out["product_name"] = target_name
        out["insight"] = "해당 제품 데이터 없음"
        return out

    target_p[price_col] = pd.to_numeric(target_p[price_col], errors="coerce")
    target_p[qty_col] = pd.to_numeric(target_p[qty_col], errors="coerce")
    target_p = target_p.dropna(subset=[price_col, qty_col])
    if target_p.empty or len(target_p) < 2:
        out["product_name"] = target_name
        out["insight"] = "가격·수량 데이터 부족"
        return out

    corr_val = float(target_p[price_col].corr(target_p[qty_col]))
    if pd.isna(corr_val):
        corr_val = 0.0
        insight = "분석 중"
    elif corr_val < -0.6:
        insight = "가격 민감도가 매우 높음: 할인 시 폭발적 수요 예상"
    else:
        insight = "프리미엄 수요 안정적: 가격 유지 전략 권고"

    scatter_data = [
        {"price": round(float(row[price_col]), 2), "quantity": int(round(float(row[qty_col]), 0))}
        for _, row in target_p.iterrows()
    ][:500]

    out["product_name"] = target_name
    out["correlation"] = round(corr_val, 2)
    out["insight"] = insight
    out["scatter_data"] = scatter_data
    return out


def _get_top5_product_names(df: pd.DataFrame) -> List[str]:
    """
    추천 결과 없음 시 폴백용: 전체 매출 기준 상위 5개 품목명 리스트 반환.
    """
    if df is None or df.empty:
        return []
    product_col = "Product_Name" if "Product_Name" in df.columns else "product_name"
    if product_col not in df.columns:
        product_col = next((c for c in df.columns if "product" in c.lower()), None)
    if not product_col or "total_sales" not in df.columns:
        return []
    df = df.copy()
    df["total_sales"] = pd.to_numeric(df["total_sales"], errors="coerce").fillna(0)
    top = df.groupby(product_col)["total_sales"].sum().sort_values(ascending=False).head(5)
    return [str(name).strip() for name in top.index.tolist() if pd.notna(name) and str(name).strip()]


# ============================================================================
# 4가지 추천 엔진 구현
# ============================================================================

def _get_store_data(df: pd.DataFrame, store_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """특정 상점의 데이터와 전체 데이터 반환"""
    store_df = df[df["store_id"].astype(str).str.strip() == str(store_id).strip()].copy()
    return store_df, df.copy()


def association_recommendations(df: pd.DataFrame, store_id: str, top_n: int = 10) -> pd.DataFrame:
    """
    1) 연관 분석 (Association): 해당 상점의 Top 판매 제품과 Lift(향상도)가 높은 병행 구매 후보군 추천.
    
    구현:
    - 해당 상점의 Top 판매 제품 추출
    - 전체 데이터에서 해당 제품과 함께 구매된 제품들의 Lift 계산
    - Lift > 1.0인 제품 중 상점에 없는 제품 추천
    """
    store_df, all_df = _get_store_data(df, store_id)
    if store_df.empty:
        return pd.DataFrame(columns=["product_name", "lift", "confidence", "support", "reason"])
    
    # 상점의 Top 판매 제품 (상위 5개)
    product_col = "Product_Name" if "Product_Name" in store_df.columns else "product_name"
    if product_col not in store_df.columns:
        return pd.DataFrame(columns=["product_name", "lift", "confidence", "support", "reason"])
    
    store_df["quantity"] = pd.to_numeric(store_df["quantity"], errors="coerce").fillna(0)
    top_products = store_df.groupby(product_col)["quantity"].sum().sort_values(ascending=False).head(5).index.tolist()
    
    if not top_products:
        return pd.DataFrame(columns=["product_name", "lift", "confidence", "support", "reason"])
    
    # 상점에서 판매 중인 제품 목록
    store_products = set(store_df[product_col].unique())
    
    # 전체 데이터에서 거래 단위로 제품 그룹화 (sale_id 기준)
    sale_id_col = "sale_id" if "sale_id" in all_df.columns else None
    if sale_id_col is None:
        # sale_id가 없으면 날짜+상점+제품 조합으로 가상 거래 생성
        all_df["_transaction_id"] = all_df["sale_date"].astype(str) + "_" + all_df["store_id"].astype(str)
        sale_id_col = "_transaction_id"
    
    recommendations = []
    
    for top_product in top_products:
        # Top 제품을 구매한 거래들
        transactions_with_top = set(all_df[all_df[product_col] == top_product][sale_id_col].unique())
        total_transactions = len(all_df[sale_id_col].unique())
        
        if len(transactions_with_top) == 0 or total_transactions == 0:
            continue
        
        # Top 제품과 함께 구매된 제품들
        co_products = all_df[all_df[sale_id_col].isin(transactions_with_top)][product_col].value_counts()
        
        for co_product, co_count in co_products.items():
            if co_product == top_product or co_product in store_products:
                continue
            
            # Lift 계산: P(A and B) / (P(A) * P(B))
            p_a = len(transactions_with_top) / total_transactions  # Top 제품 구매 확률
            transactions_with_co = set(all_df[all_df[product_col] == co_product][sale_id_col].unique())
            p_b = len(transactions_with_co) / total_transactions  # Co 제품 구매 확률
            transactions_both = transactions_with_top & transactions_with_co
            p_ab = len(transactions_both) / total_transactions  # 함께 구매 확률
            
            if p_a > 0 and p_b > 0:
                lift = p_ab / (p_a * p_b)
                confidence = len(transactions_both) / len(transactions_with_top) if len(transactions_with_top) > 0 else 0
                support = len(transactions_both) / total_transactions
                
                if lift > 1.0:  # Lift > 1.0인 경우만 추천
                    recommendations.append({
                        "product_name": co_product,
                        "lift": round(lift, 3),
                        "confidence": round(confidence, 3),
                        "support": round(support, 3),
                        "reason": f"'{top_product}'와 함께 구매됨 (Lift: {lift:.2f})"
                    })
    
    if not recommendations:
        return pd.DataFrame(columns=["product_name", "lift", "confidence", "support", "reason"])
    
    result_df = pd.DataFrame(recommendations)
    result_df = result_df.sort_values("lift", ascending=False).head(top_n)
    return result_df


def similar_store_recommendations(df: pd.DataFrame, store_id: str, top_n: int = 10) -> pd.DataFrame:
    """
    2) 유사 상점 (CF): Cosine Similarity로 상점 간 유사도를 계산, 유사 상점의 베스트셀러 중 현재 상점에 없는 제품 추천.
    """
    store_df, all_df = _get_store_data(df, store_id)
    if store_df.empty:
        return pd.DataFrame(columns=["product_name", "similarity_score", "sales_in_similar_store", "reason"])
    
    product_col = "Product_Name" if "Product_Name" in all_df.columns else "product_name"
    if product_col not in all_df.columns:
        return pd.DataFrame(columns=["product_name", "similarity_score", "sales_in_similar_store", "reason"])
    
    # 상점별 제품 판매량 매트릭스 생성
    all_df["quantity"] = pd.to_numeric(all_df["quantity"], errors="coerce").fillna(0)
    store_product_matrix = all_df.groupby(["store_id", product_col])["quantity"].sum().reset_index()
    pivot_matrix = store_product_matrix.pivot_table(
        index="store_id", columns=product_col, values="quantity", fill_value=0
    )
    
    if store_id not in pivot_matrix.index:
        return pd.DataFrame(columns=["product_name", "similarity_score", "sales_in_similar_store", "reason"])
    
    # Cosine Similarity 계산
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        target_store_vector = pivot_matrix.loc[store_id].values.reshape(1, -1)
        similarities = cosine_similarity(target_store_vector, pivot_matrix.values)[0]
    except ImportError:
        # sklearn 없을 경우 수동 계산
        def cosine_sim(a, b):
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0
            return dot_product / (norm_a * norm_b)
        
        target_vector = pivot_matrix.loc[store_id].values
        similarities = np.array([cosine_sim(target_vector, pivot_matrix.iloc[i].values) for i in range(len(pivot_matrix))])
    
    # 유사도가 높은 상점들 (자기 자신 제외)
    similar_stores = []
    for idx, sim_score in enumerate(similarities):
        store_id_val = pivot_matrix.index[idx]
        if store_id_val != store_id and sim_score > 0.1:  # 최소 유사도 임계값
            similar_stores.append((store_id_val, sim_score))
    
    similar_stores.sort(key=lambda x: x[1], reverse=True)
    
    # 현재 상점의 제품 목록
    store_products = set(store_df[product_col].unique())
    
    # 유사 상점들의 베스트셀러 중 현재 상점에 없는 제품 추천
    recommendations = []
    seen_products = set()
    
    for similar_store_id, sim_score in similar_stores[:5]:  # 상위 5개 유사 상점
        similar_store_products = pivot_matrix.loc[similar_store_id]
        top_products = similar_store_products.nlargest(10).index.tolist()
        
        for product in top_products:
            if product not in store_products and product not in seen_products:
                sales_in_similar = int(similar_store_products[product])
                if sales_in_similar > 0:
                    recommendations.append({
                        "product_name": product,
                        "similarity_score": round(sim_score, 3),
                        "sales_in_similar_store": sales_in_similar,
                        "reason": f"유사 상점 '{similar_store_id}'의 베스트셀러 (유사도: {sim_score:.2f})"
                    })
                    seen_products.add(product)
    
    if not recommendations:
        return pd.DataFrame(columns=["product_name", "similarity_score", "sales_in_similar_store", "reason"])
    
    result_df = pd.DataFrame(recommendations)
    result_df = result_df.sort_values("similarity_score", ascending=False).head(top_n)
    return result_df


def latent_demand_recommendations(df: pd.DataFrame, store_id: str, top_n: int = 10) -> pd.DataFrame:
    """
    3) 잠재 수요 (SVD/MF): 전체 행렬을 학습하여 해당 상점의 예상 평점(판매량)이 높은 미취급 제품 추천.
    """
    store_df, all_df = _get_store_data(df, store_id)
    if store_df.empty:
        return pd.DataFrame(columns=["product_name", "predicted_sales", "reason"])
    
    product_col = "Product_Name" if "Product_Name" in all_df.columns else "product_name"
    if product_col not in all_df.columns:
        return pd.DataFrame(columns=["product_name", "predicted_sales", "reason"])
    
    all_df["quantity"] = pd.to_numeric(all_df["quantity"], errors="coerce").fillna(0)
    
    # 상점-제품 매트릭스 생성
    store_product_matrix = all_df.groupby(["store_id", product_col])["quantity"].sum().reset_index()
    pivot_matrix = store_product_matrix.pivot_table(
        index="store_id", columns=product_col, values="quantity", fill_value=0
    )
    
    if store_id not in pivot_matrix.index:
        return pd.DataFrame(columns=["product_name", "predicted_sales", "reason"])
    
    # SVD로 차원 축소 후 복원하여 예측
    try:
        from sklearn.decomposition import TruncatedSVD
        
        # SVD 적용 (차원 수는 min(상점 수, 제품 수, 50))
        n_components = min(50, len(pivot_matrix.index) - 1, len(pivot_matrix.columns) - 1)
        if n_components < 2:
            n_components = 2
        
        svd = TruncatedSVD(n_components=n_components, random_state=42)
        matrix_reduced = svd.fit_transform(pivot_matrix.values)
        matrix_reconstructed = svd.inverse_transform(matrix_reduced)
        
        # 재구성된 매트릭스에서 해당 상점의 예상 판매량
        store_idx = pivot_matrix.index.get_loc(store_id)
        predicted_sales = matrix_reconstructed[store_idx]
        
        # 현재 상점의 제품 목록
        store_products = set(store_df[product_col].unique())
        
        # 예상 판매량이 높은 미취급 제품 추천
        recommendations = []
        for idx, product in enumerate(pivot_matrix.columns):
            if product not in store_products:
                pred_value = max(0, predicted_sales[idx])
                if pred_value > 0:
                    recommendations.append({
                        "product_name": product,
                        "predicted_sales": round(pred_value, 2),
                        "reason": f"SVD 기반 예상 판매량: {pred_value:.1f}대"
                    })
        
        if not recommendations:
            return pd.DataFrame(columns=["product_name", "predicted_sales", "reason"])
        
        result_df = pd.DataFrame(recommendations)
        result_df = result_df.sort_values("predicted_sales", ascending=False).head(top_n)
        return result_df
        
    except Exception as e:
        # SVD 실패 시 간단한 평균 기반 추천
        store_products = set(store_df[product_col].unique())
        avg_sales = all_df.groupby(product_col)["quantity"].mean()
        
        recommendations = []
        for product, avg_qty in avg_sales.items():
            if product not in store_products and avg_qty > 0:
                recommendations.append({
                    "product_name": product,
                    "predicted_sales": round(avg_qty, 2),
                    "reason": f"전체 평균 판매량: {avg_qty:.1f}대 (SVD 실패 시 폴백)"
                })
        
        if not recommendations:
            return pd.DataFrame(columns=["product_name", "predicted_sales", "reason"])
        
        result_df = pd.DataFrame(recommendations)
        result_df = result_df.sort_values("predicted_sales", ascending=False).head(top_n)
        return result_df


def trend_recommendations(df: pd.DataFrame, store_id: str, top_n: int = 10) -> pd.DataFrame:
    """
    4) 트렌드 분석: 전체 상점 데이터 중 최근 판매 증가율이 높거나 특정 지역/전체 평균 대비 급상승 중인 제품 추천.
    """
    store_df, all_df = _get_store_data(df, store_id)
    if store_df.empty or "sale_date" not in all_df.columns:
        return pd.DataFrame(columns=["product_name", "growth_rate", "recent_sales", "reason"])
    
    product_col = "Product_Name" if "Product_Name" in all_df.columns else "product_name"
    if product_col not in all_df.columns:
        return pd.DataFrame(columns=["product_name", "growth_rate", "recent_sales", "reason"])
    
    all_df["sale_date"] = pd.to_datetime(all_df["sale_date"], errors="coerce")
    all_df = all_df.dropna(subset=["sale_date"])
    all_df["quantity"] = pd.to_numeric(all_df["quantity"], errors="coerce").fillna(0)
    
    # 최근 3개월과 그 이전 3개월 비교
    latest_date = all_df["sale_date"].max()
    period1_end = latest_date
    period1_start = latest_date - pd.Timedelta(days=90)
    period2_end = period1_start
    period2_start = period2_end - pd.Timedelta(days=90)
    
    period1_df = all_df[(all_df["sale_date"] >= period1_start) & (all_df["sale_date"] <= period1_end)]
    period2_df = all_df[(all_df["sale_date"] >= period2_start) & (all_df["sale_date"] < period2_end)]
    
    period1_sales = period1_df.groupby(product_col)["quantity"].sum()
    period2_sales = period2_df.groupby(product_col)["quantity"].sum()
    
    # 성장률 계산
    store_products = set(store_df[product_col].unique())
    recommendations = []
    
    for product in period1_sales.index:
        if product in store_products:
            continue
        
        recent = period1_sales.get(product, 0)
        previous = period2_sales.get(product, 0)
        
        if previous > 0:
            growth_rate = ((recent - previous) / previous) * 100
        elif recent > 0:
            growth_rate = 999  # 신규 제품
        else:
            continue
        
        if growth_rate > 20 or recent > period1_sales.quantile(0.75):  # 성장률 20% 이상 또는 상위 25%
            recommendations.append({
                "product_name": product,
                "growth_rate": round(growth_rate, 1),
                "recent_sales": int(recent),
                "reason": f"최근 3개월 판매 증가율: {growth_rate:.1f}% (이전 대비)"
            })
    
    if not recommendations:
        return pd.DataFrame(columns=["product_name", "growth_rate", "recent_sales", "reason"])
    
    result_df = pd.DataFrame(recommendations)
    result_df = result_df.sort_values("growth_rate", ascending=False).head(top_n)
    return result_df


# ============================================================================
# 매출 예측 시계열 (일별 resample + 30일 예측)
# ============================================================================

def _get_daily_sales_for_store(df: pd.DataFrame, store_id: str) -> pd.Series:
    """
    sale_date 기준 일별 매출 집계 (resample('D')).
    해당 store_id만 필터 후 일별 total_sales 합계.
    """
    store_df = df[df["store_id"].astype(str).str.strip() == str(store_id).strip()].copy()
    if store_df.empty or "sale_date" not in store_df.columns:
        return pd.Series(dtype=float)
    store_df["sale_date"] = pd.to_datetime(store_df["sale_date"], errors="coerce")
    store_df = store_df.dropna(subset=["sale_date"])
    if "total_sales" in store_df.columns:
        store_df["total_sales"] = pd.to_numeric(store_df["total_sales"], errors="coerce").fillna(0)
    else:
        # total_sales 없으면 quantity * price 로 계산
        q = pd.to_numeric(store_df.get("quantity", 0), errors="coerce").fillna(0)
        p = pd.to_numeric(store_df.get("price", 0), errors="coerce").fillna(0)
        store_df["total_sales"] = q * p
    store_df = store_df.set_index("sale_date")
    daily = store_df["total_sales"].resample("D").sum()
    return daily


def predict_sales(store_id: str, forecast_days: int = 30) -> Dict[str, Any]:
    """
    향후 forecast_days(기본 30)일 매출 예측.
    - 일별 매출을 resample('D')로 생성 후 선형 회귀로 추세 추정 (Prophet 없이).
    - 반환: actual (실측), predicted (예측), lower/upper (신뢰 구간).
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {"actual": [], "predicted": [], "store_id": store_id}
    
    daily = _get_daily_sales_for_store(df, store_id)
    if daily.empty or len(daily) < 2:
        return {"actual": [], "predicted": [], "store_id": store_id}
    
    # 실측: 날짜와 매출 리스트
    actual_list = [
        {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2)}
        for d, v in daily.items()
    ]
    
    # 선형 회귀: 일수(0,1,2,...) vs 매출
    try:
        from sklearn.linear_model import LinearRegression
    except ImportError:
        # sklearn 없으면 단순 평균으로 예측
        mean_sales = float(daily.mean())
        last_date = daily.index.max()
        predicted_list = []
        for i in range(1, forecast_days + 1):
            d = last_date + pd.Timedelta(days=i)
            predicted_list.append({
                "date": d.strftime("%Y-%m-%d"),
                "value": round(mean_sales, 2),
                "lower": round(mean_sales * 0.85, 2),
                "upper": round(mean_sales * 1.15, 2),
            })
        return {"actual": actual_list, "predicted": predicted_list, "store_id": store_id}
    
    X = np.arange(len(daily)).reshape(-1, 1)
    y = daily.values
    model = LinearRegression().fit(X, y)
    pred_trend = model.predict(X)
    residual_std = np.std(y - pred_trend) if len(y) > 2 else (np.std(y) if len(y) > 1 else 0)
    if np.isnan(residual_std) or residual_std <= 0:
        residual_std = np.mean(y) * 0.1
    
    # 향후 30일 예측
    last_date = daily.index.max()
    predicted_list = []
    for i in range(1, forecast_days + 1):
        x_future = np.array([[len(daily) + i - 1]])
        val = float(model.predict(x_future)[0])
        val = max(0, val)
        # 신뢰 구간: ±1.96*residual_std (대략 95%)
        margin = 1.96 * residual_std
        lower = max(0, val - margin)
        upper = val + margin
        d = last_date + pd.Timedelta(days=i)
        predicted_list.append({
            "date": d.strftime("%Y-%m-%d"),
            "value": round(val, 2),
            "lower": round(lower, 2),
            "upper": round(upper, 2),
        })
    
    return {"actual": actual_list, "predicted": predicted_list, "store_id": store_id}


def get_sales_forecast_chart_data(store_id: str, forecast_days: int = 30) -> Dict[str, Any]:
    """
    매출 예측 시계열 차트용 데이터.
    - actual: 실측 (검은색 실선)
    - predicted: 예측 (파란색 점선) + lower/upper 신뢰 구간 (흐린 파란색 영역)
    """
    return predict_sales(store_id, forecast_days=forecast_days)


def get_store_recommendations(store_id: str) -> Dict[str, Any]:
    """
    특정 store_id에 대한 4가지 추천 모델 결과 반환.
    
    반환:
    {
        "store_id": str,
        "store_summary": {
            "total_sales": float,
            "product_count": int,
            "store_name": str
        },
        "association": [...],  # 연관 분석 결과
        "similar_store": [...],  # 유사 상점 결과
        "latent_demand": [...],  # 잠재 수요 결과
        "trend": [...]  # 트렌드 분석 결과
    }
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {
            "store_id": store_id,
            "store_summary": {"total_sales": 0, "product_count": 0, "store_name": ""},
            "association": [],
            "similar_store": [],
            "latent_demand": [],
            "trend": []
        }
    
    store_df, _ = _get_store_data(df, store_id)

    # 상점 요약 정보 (해당 store_id에 데이터 없어도 안전하게 반환)
    store_summary = {
        "total_sales": float(store_df["total_sales"].sum()) if not store_df.empty and "total_sales" in store_df.columns else 0.0,
        "product_count": int(store_df["Product_Name"].nunique()) if not store_df.empty and "Product_Name" in store_df.columns else 0,
        "store_name": str(store_df["Store_Name"].iloc[0]) if not store_df.empty and "Store_Name" in store_df.columns else str(store_id),
    }
    
    # 추천 결과 없음 시 폴백: 전체 매출 기준 상위 5개 품목
    top5_names = _get_top5_product_names(df)

    def _fallback_association() -> List[Dict[str, Any]]:
        return [
            {
                "product_name": name,
                "lift": 0.0,
                "confidence": 0.0,
                "support": 0.0,
                "reason": "추천 결과 없음 → 전체 인기 상위 5개 품목",
                "is_fallback": True,
            }
            for name in top5_names
        ]

    def _fallback_similar_store() -> List[Dict[str, Any]]:
        return [
            {
                "product_name": name,
                "similarity_score": 0.0,
                "sales_in_similar_store": 0,
                "reason": "추천 결과 없음 → 전체 인기 상위 5개 품목",
                "is_fallback": True,
            }
            for name in top5_names
        ]

    def _fallback_latent_demand() -> List[Dict[str, Any]]:
        return [
            {"product_name": name, "predicted_sales": 0.0, "is_fallback": True}
            for name in top5_names
        ]

    def _fallback_trend() -> List[Dict[str, Any]]:
        return [
            {
                "product_name": name,
                "growth_rate": 0.0,
                "recent_sales": 0,
                "reason": "추천 결과 없음 → 전체 인기 상위 5개 품목",
                "is_fallback": True,
            }
            for name in top5_names
        ]

    # 4가지 추천 모델 실행
    try:
        assoc_df = association_recommendations(df, store_id, top_n=10)
        similar_df = similar_store_recommendations(df, store_id, top_n=10)
        latent_df = latent_demand_recommendations(df, store_id, top_n=10)
        trend_df = trend_recommendations(df, store_id, top_n=10)

        association_list = assoc_df.to_dict("records") if not assoc_df.empty else _fallback_association()
        similar_list = similar_df.to_dict("records") if not similar_df.empty else _fallback_similar_store()
        latent_list = latent_df.to_dict("records") if not latent_df.empty else _fallback_latent_demand()
        trend_list = trend_df.to_dict("records") if not trend_df.empty else _fallback_trend()

        # 기존 결과에 is_fallback=False 명시 (프론트 구분용)
        for item in association_list:
            item.setdefault("is_fallback", False)
        for item in similar_list:
            item.setdefault("is_fallback", False)
        for item in latent_list:
            item.setdefault("is_fallback", False)
        for item in trend_list:
            item.setdefault("is_fallback", False)

        return {
            "store_id": store_id,
            "store_summary": store_summary,
            "association": association_list,
            "similar_store": similar_list,
            "latent_demand": latent_list,
            "trend": trend_list,
        }
    except Exception as e:
        print(f"[추천 시스템] store_id={store_id} 오류: {e}")
        return {
            "store_id": store_id,
            "store_summary": store_summary,
            "association": _fallback_association(),
            "similar_store": _fallback_similar_store(),
            "latent_demand": _fallback_latent_demand(),
            "trend": _fallback_trend(),
        }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "store":
        # store_id 기반 추천 테스트
        store_id = sys.argv[2] if len(sys.argv) > 2 else "ST-01"
        print(f"\n=== 상점 {store_id} 추천 결과 ===\n")
        result = get_store_recommendations(store_id)
        print(f"상점 요약: {result['store_summary']}\n")
        print(f"1. 연관 분석: {len(result['association'])}개")
        print(f"2. 유사 상점: {len(result['similar_store'])}개")
        print(f"3. 잠재 수요: {len(result['latent_demand'])}개")
        print(f"4. 트렌드: {len(result['trend'])}개")
    else:
        # 기본 Top 상품/카테고리
        summary = get_recommendation_summary()
        print("--- 추천 상품 (매출 Top 15) ---")
        for p in summary["top_products"]:
            print(f"  {p['rank']}. {p['product']}: {p['sales']:,}")
        print("\n--- 추천 카테고리 (매출 Top 10) ---")
        for c in summary["top_categories"]:
            print(f"  {c['rank']}. {c['category']}: {c['sales']:,}")
