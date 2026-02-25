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

[모듈화] 본 파일은 load_sales_data.py 의 load_sales_dataframe() 만 참조하여 데이터를 읽습니다.
- 상점 목록·추천·매출·피봇·상관관계 등 모두 동일 SQL 기반. Import 실패 시 폴백 함수 (독립된 if문).
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

# [4.1.1] 유저(상점) 맞춤형 추천: inventory_health는 main.py에서 Inventory Optimization 결과를 넘겨받음

# 모델 서버 루트 (load_sales_data.py 위치)
_MODEL_SERVER = Path(__file__).resolve().parent.parent
if str(_MODEL_SERVER) not in sys.path:
    sys.path.insert(0, str(_MODEL_SERVER))
# load_sales_data 참조 (실패 시 폴백 함수, 독립된 if문)
load_sales_dataframe = None
try:
    from load_sales_data import load_sales_dataframe as _rt_loader
except ImportError:
    _rt_loader = None
if _rt_loader is not None:
    load_sales_dataframe = _rt_loader
if load_sales_dataframe is None:
    def load_sales_dataframe():
        """Import 실패 시 폴백: 항상 None 반환."""
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
    반환: {"stores": [{"store_id": str, "store_name": str, "country": str}, ...]} (store_id 기준 정렬)
    - country는 매장에 해당하는 Country 컬럼(있을 경우)의 대표값.
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
    country_col = "Country" if "Country" in df.columns else ("country" if "country" in df.columns else None)
    stores = df[store_id_col].astype(str).str.strip().unique().tolist()
    store_names: Dict[str, str] = {}
    store_countries: Dict[str, str] = {}
    for sid in stores:
        sub = df[df[store_id_col].astype(str).str.strip() == sid]
        # 상점 이름
        if name_col and not sub.empty:
            val = sub[name_col].iloc[0]
            store_names[sid] = str(val).strip() if pd.notna(val) else sid
        else:
            store_names[sid] = sid
        # 국가 (있을 경우 첫번째 유효 값 사용)
        country_val = ""
        if country_col and not sub.empty and country_col in sub.columns:
            non_null = sub[country_col].dropna()
            if not non_null.empty:
                country_val = str(non_null.iloc[0]).strip()
        store_countries[sid] = country_val
    sorted_stores = sorted(stores, key=lambda x: (x.upper(), x))
    result = {
        "stores": [
            {
                "store_id": s,
                "store_name": store_names.get(s, s),
                "country": store_countries.get(s, ""),
            }
            for s in sorted_stores
        ]
    }
    n = len(result["stores"])
    print(
        f"[Real-time] get_store_list: 반환 상점 {n}건 (store_id 컬럼={store_id_col}, store_name 컬럼={name_col}, country 컬럼={country_col})"
    )
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
    - 결측치 제거 후 IQR 기준 이상치 제거하여 실측/예측에 반영.
    - 반환: actual (실측), predicted (예측), lower/upper (신뢰 구간).
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        return {"actual": [], "predicted": [], "store_id": store_id}
    
    daily = _get_daily_sales_for_store(df, store_id)
    if daily.empty or len(daily) < 2:
        return {"actual": [], "predicted": [], "store_id": store_id}
    
    # 결측치 제거
    daily = daily.dropna()
    if len(daily) < 2:
        return {"actual": [], "predicted": [], "store_id": store_id}
    
    # IQR 기준 이상치 제거 (Q1 - 1.5*IQR ~ Q3 + 1.5*IQR)
    q1, q3 = daily.quantile(0.25), daily.quantile(0.75)
    iqr = q3 - q1
    if iqr > 0:
        lb, ub = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        daily = daily[(daily >= lb) & (daily <= ub)]
    if daily.empty or len(daily) < 2:
        return {"actual": [], "predicted": [], "store_id": store_id}
    
    # 실측: 날짜와 매출 리스트 (정렬 유지)
    daily = daily.sort_index()
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


# ============================================================================
# 상점별 성장 전략 엔진 — "실수하지 않으면서도 돈을 버는 로직"
# CTO 원칙: if 문 하나하나가 비즈니스 리스크를 막는 방패. 정교한 구현 필수.
# 데이터 연동: model-server/02.Database for dashboard/dashboard_sales_data.sql (sales_data)
# ============================================================================

REQUIRED_PRODUCT_KEYS = ("price", "margin", "stock_age", "compatibility_tags")
STORE_TYPES = ("PREMIUM", "OUTLET", "STANDARD")

# ---------- 상점별 맞춤형 모드 (Dynamic Weighting): 매장 위치·성격에 따라 엔진의 '성격' 변경 ----------
# 상점 타입 -> (엔진의 상태 Internal State, (CEO, INV, OPS) 가중치)
DYNAMIC_WEIGHTING: Dict[str, tuple] = {
    "PREMIUM": ("브랜드 이미지가 최우선이야", (0.6, 0.2, 0.2)),
    "OUTLET": ("무조건 재고를 비워야 해", (0.1, 0.7, 0.2)),
    "STANDARD": ("골고루 잘 팔아보자", (0.3, 0.4, 0.3)),
}

# [방패] 브랜드 리스크: 고가 기기에 극저가 추천 시 브랜드 격 하락 → CEO 감점
CEO_PREMIUM_DEVICE_THRESHOLD = 1000.0
CEO_LOW_ITEM_PRICE_THRESHOLD = 10.0
CEO_PENALTY_RATIO = 0.2

# [방패] 자산 리스크: 재고 장기 체류 시 자금 유동성 저하 → 재고 회전 유도 가산
INVESTOR_AGED_STOCK_DAYS = 90
INVESTOR_AGED_BOOST = 1.5
INVESTOR_AGED_CAP = 1.5

# [방패] 운영 리스크: 호환 불일치 추천 시 반품·클레임 → COO 1순위 제외
COO_REJECT_MESSAGE = "이건 끼워 팔면 반품이야. 리스트에서 당장 빼!"

# [방패] 수치 안정성: 스코어 계산 시 0 나눗셈·비정상값 방지
CEO_PRICE_NORM_DIVISOR = 1500.0
OPERATION_AGE_NORM_DAYS = 180.0
SCORE_MIN, SCORE_MAX = 0.0, 1.0
MARGIN_MIN, MARGIN_MAX = 0.0, 1.0

# [방패] 실패 시 손실 최소화: Fallback으로 항상 유효 응답 보장
GROWTH_STRATEGY_FALLBACK_ITEMS = [
    {"product_id": "FB-1", "product_name": "AppleCare+", "reason": "Fallback: 기본 추천 1", "score": 0.9},
    {"product_id": "FB-2", "product_name": "USB-C 어댑터", "reason": "Fallback: 기본 추천 2", "score": 0.85},
    {"product_id": "FB-3", "product_name": "MagSafe 충전기", "reason": "Fallback: 기본 추천 3", "score": 0.8},
]


class StoreGrowthStrategyEngine:
    """
    이익·브랜드·운영 황금비율 계산기.
    각 if는 비즈니스 리스크 방패: 잘못된 추천(재고 없음/호환 불일치/브랜드 훼손)을 막고,
    돈을 버는 방향(재고 회전·마진·브랜드 일관성)만 스코어에 반영.
    """

    def __init__(self, store_id: str, store_type: str = "STANDARD"):
        self.store_id = str(store_id).strip() if store_id else ""
        # [방패] 잘못된 store_type 전달 시 기본값으로 수렴 → 예기치 않은 가중치 방지
        if store_type not in STORE_TYPES:
            self.store_type = "STANDARD"
        else:
            self.store_type = store_type

    # ---------- Data Schema: [방패] 잘못된 데이터가 스코어링/필터에 들어가는 것 방지 ----------
    def _validate_schema(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        리스크: 스키마 불일치 데이터가 들어가면 점수 왜곡·런타임 오류.
        방패: 필수 키 존재·타입 검사 후, 복사본만 반환(원본 불변).
        """
        if not isinstance(products, (list, tuple)):
            return []
        valid: List[Dict[str, Any]] = []
        for p in products:
            # [방패] dict가 아니면 스코어링 시 KeyError/AttributeError 방지
            if not isinstance(p, dict):
                continue
            # [방패] price 없음/None → 가격 기반 로직(CEO) 오동작 방지
            if "price" not in p or p.get("price") is None:
                continue
            # [방패] margin 없음/None → 이익(Investor) 점수 산출 불가 방지
            if "margin" not in p or p.get("margin") is None:
                continue
            # [방패] stock_age 없음/None → 재고 회전(Operation) 로직 오동작 방지
            if "stock_age" not in p or p.get("stock_age") is None:
                continue
            tags = p.get("compatibility_tags")
            # [방패] compatibility_tags가 list/tuple이 아니면 호환성 필터 오류 방지
            if not isinstance(tags, (list, tuple)):
                p = {**p, "compatibility_tags": []}
            else:
                p = {**p}
            valid.append(p)
        return valid

    # ---------- 1. Filter Layer: [방패] "팔 수 없는 것" 추천 → 고객 불만·신뢰 하락 ----------
    def _filter_cannot_sell(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        리스크: 재고 0이고 입고 예정도 없는 상품을 추천하면 이행 불가·불만·이미지 훼손.
        방패: 재고 > 0 이거나 expected_eta 가 있으면 통과; 그 외는 무조건 제외.
        """
        if not products:
            return []
        out: List[Dict[str, Any]] = []
        for p in products:
            stock = p.get("stock")
            # [방패] 재고가 있으면 즉시 통과(숫자 변환 실패 시 아래 ETA로만 판단)
            if stock is not None:
                try:
                    s_val = int(stock)
                    if s_val > 0:
                        out.append(p)
                        continue
                except (TypeError, ValueError):
                    pass
            # [방패] 재고 0이어도 입고 예정이 있으면 추천 가능(이행 가능성)
            eta = p.get("expected_eta")
            if eta is not None and str(eta).strip():
                out.append(p)
            # else: 재고 0이고 입고 예정 없음 → 추천 시 실수(이행 불가) → 제외
        return out

    def _charger_type_from_product(self, product: Dict[str, Any]) -> Optional[str]:
        """
        리스크: 충전/연결 타입 불일치 추천 시 반품·클레임.
        방패: product_name·compatibility_tags에서 magsafe/usb-c/lightning 일관 추출.
        """
        tags = product.get("compatibility_tags")
        if not isinstance(tags, (list, tuple)):
            tags = []
        name = (product.get("product_name") or product.get("product_id") or "").lower()
        for t in tags:
            t = str(t).lower()
            if "magsafe" in t or "mag safe" in t:
                return "magsafe"
            if "usb-c" in t or "usbc" in t or "usb_c" in t:
                return "usb-c"
            if "lightning" in t:
                return "lightning"
        if "magsafe" in name or "mag safe" in name:
            return "magsafe"
        if "usb-c" in name or "usbc" in name or "usb c" in name:
            return "usb-c"
        if "lightning" in name:
            return "lightning"
        return None

    # ---------- 1. Filter Layer: [방패] "팔면 안 되는 것" 추천 → 반품·클레임·브랜드 리스크 ----------
    def _filter_should_not_sell(
        self, products: List[Dict[str, Any]], target_compatibility_tags: List[str], target_charger_type: Optional[str] = None
    ) -> tuple:
        """
        리스크: 호환 불일치·충전기 타입 불일치 추천 시 끼워 팔면 반품 확률 극대화.
        방패: target과 1건이라도 겹치지 않으면 제외; 충전 타입이 명시된 경우 반드시 일치해야 통과.
        """
        out: List[Dict[str, Any]] = []
        rejected_log: List[Dict[str, Any]] = []
        target_set = {str(t).strip().lower() for t in (target_compatibility_tags or []) if t is not None and str(t).strip()}
        # [방패] target_charger_type 정규화(대소문자·공백)
        norm_charger = str(target_charger_type).strip().lower() if target_charger_type else None
        if norm_charger and norm_charger not in ("magsafe", "usb-c", "lightning"):
            norm_charger = None

        for p in products:
            pt = p.get("compatibility_tags") or []
            pt_set = {str(t).strip().lower() for t in pt if t is not None and str(t).strip()}
            # [방패] 호환 태그가 하나도 겹치지 않으면 추천 시 반품/불만 리스크 → 제외
            if target_set and not (pt_set & target_set):
                rejected_log.append({"product": p.get("product_name") or p.get("product_id"), "reason": COO_REJECT_MESSAGE})
                continue
            # [방패] 메인 기기 충전 타입이 정해졌을 때, 후보 충전 타입이 다르면 반품 유발 → 제외
            if norm_charger:
                prod_charger = self._charger_type_from_product(p)
                if prod_charger is not None and prod_charger != norm_charger:
                    rejected_log.append({"product": p.get("product_name") or p.get("product_id"), "reason": COO_REJECT_MESSAGE})
                    continue
            out.append(p)
        return out, rejected_log

    # ---------- 2. Scoring Layer: [방패] 비정상 수치로 점수 왜곡·NaN/Inf 방지 ----------
    def _safe_float(self, value: Any, default: float = 0.0, low: Optional[float] = None, high: Optional[float] = None) -> float:
        """리스크: str/None/NaN이 점수 계산에 들어가면 예외·Inf. 방패: float 변환 후 clamp."""
        try:
            if value is None:
                return default
            v = float(value)
            if pd.isna(v) if hasattr(pd, "isna") else (v != v):
                return default
            if low is not None and v < low:
                v = low
            if high is not None and v > high:
                v = high
            return v
        except (TypeError, ValueError):
            return default

    def _score_ceo_raw(self, product: Dict[str, Any]) -> float:
        """
        CEO(브랜드) 원점수 0~1.
        리스크: 음수/과대 가격·마진으로 점수 폭주. 방패: clamp 후 정규화.
        """
        price = self._safe_float(product.get("price"), 0.0, 0.0, None)
        margin = self._safe_float(product.get("margin"), 0.0, MARGIN_MIN, MARGIN_MAX)
        if CEO_PRICE_NORM_DIVISOR <= 0:
            price_score = 0.5
        else:
            price_score = min(SCORE_MAX, price / CEO_PRICE_NORM_DIVISOR) if price else 0.5
        raw = 0.5 * price_score + 0.5 * margin
        return round(max(SCORE_MIN, min(SCORE_MAX, raw)), 4)

    def _score_investor_raw(self, product: Dict[str, Any]) -> float:
        """
        Investor(이익) 원점수 0~1.
        리스크: 마진 > 1 또는 음수로 가산 로직 오류. 방패: 0~1 clamp.
        """
        margin = self._safe_float(product.get("margin"), 0.0, MARGIN_MIN, MARGIN_MAX)
        return round(margin, 4)

    def _score_operation_raw(self, product: Dict[str, Any]) -> float:
        """
        Operation(재고 회전) 원점수 0~1.
        리스크: 음수 재고령·0 나눗셈. 방패: age>=0, divisor>0 보장.
        """
        age = int(self._safe_float(product.get("stock_age"), 0.0, 0.0, None))
        if OPERATION_AGE_NORM_DAYS <= 0:
            return 0.0
        norm = min(SCORE_MAX, age / OPERATION_AGE_NORM_DAYS)
        return round(max(SCORE_MIN, norm), 4)

    def _get_weights(self) -> tuple:
        """
        상점별 맞춤형 모드(Dynamic Weighting): CTO 명세 고정 가중치.
        PREMIUM=브랜드 최우선(CEO 0.6), OUTLET=재고 비우기(INV 0.7), STANDARD=골고루(0.3/0.4/0.3).
        리스크: 합이 1이 아니면 점수 스케일 붕괴. 방패: 명세값 사용, 미정의 시 STANDARD.
        """
        entry = DYNAMIC_WEIGHTING.get(self.store_type, DYNAMIC_WEIGHTING["STANDARD"])
        _, (w_ceo, w_inv, w_op) = entry
        s = w_ceo + w_inv + w_op
        if s <= 0:
            w_ceo, w_inv, w_op = 0.3, 0.4, 0.3
        else:
            w_ceo, w_inv, w_op = w_ceo / s, w_inv / s, w_op / s
        return (round(w_ceo, 4), round(w_inv, 4), round(w_op, 4))

    def _get_internal_state(self) -> str:
        """엔진의 상태(Internal State): 매장 성격에 따른 엔진 성격 문구."""
        entry = DYNAMIC_WEIGHTING.get(self.store_type, DYNAMIC_WEIGHTING["STANDARD"])
        return entry[0]

    def _get_weights_dict(self) -> Dict[str, float]:
        """if 가중치 설정(Weights) 보고용: CEO, INV, OPS."""
        w_ceo, w_inv, w_op = self._get_weights()
        return {"CEO": w_ceo, "INV": w_inv, "OPS": w_op}

    def _apply_technical_logic(
        self,
        product: Dict[str, Any],
        ceo_raw: float,
        inv_raw: float,
        op_raw: float,
        main_device_price: Optional[float],
    ) -> tuple:
        """
        기술 로직: 각 if = 리스크 방패.
        - Investor: 재고령>90일 → 자금 묶임 리스크 → 1.5배 가산으로 회전 유도(상한 1.5).
        - CEO: 1000$ 기기+10$ 추천 → 브랜드 격 하락 리스크 → 80% 감점.
        """
        inv = max(SCORE_MIN, min(SCORE_MAX, inv_raw))
        stock_age = int(self._safe_float(product.get("stock_age"), 0.0, 0.0, None))
        # [방패] 재고 장기 체류 = 자금 유동성 리스크 → 점수 가산으로 우선 추천 유도
        if stock_age > INVESTOR_AGED_STOCK_DAYS:
            inv = min(INVESTOR_AGED_CAP, inv * INVESTOR_AGED_BOOST)

        ceo = max(SCORE_MIN, min(SCORE_MAX, ceo_raw))
        # [방패] 프리미엄 기기에 극저가 추천 = 브랜드 격 하락 리스크 → 감점
        if main_device_price is not None and main_device_price >= CEO_PREMIUM_DEVICE_THRESHOLD:
            cand_price = self._safe_float(product.get("price"), 0.0, 0.0, None)
            if cand_price <= CEO_LOW_ITEM_PRICE_THRESHOLD:
                ceo = ceo * CEO_PENALTY_RATIO

        return (round(max(SCORE_MIN, min(SCORE_MAX, ceo)), 4), round(max(SCORE_MIN, min(INVESTOR_AGED_CAP, inv)), 4), op_raw)

    # ---------- 3. Output Layer: [방패] 빈 문자열·None으로 대본/로그 오류 방지 ----------
    def _build_reasoning_log(
        self,
        product: Dict[str, Any],
        ceo: float,
        inv: float,
        op: float,
        total: float,
        path_steps: List[str],
    ) -> Dict[str, Any]:
        """보고용 JSON. 리스크: None/빈 값으로 프론트 오류. 방패: str()·기본문자열."""
        reason_text = path_steps[0] if path_steps else "균형 점수에 의해 선정됨"
        return {
            "product_id": str(product.get("product_id") or product.get("product_name") or ""),
            "product_name": str(product.get("product_name") or product.get("product_id") or ""),
            "reason": f"이 아이템은 {reason_text}",
            "if_then_path": list(path_steps) if path_steps else [],
            "scores": {"ceo": ceo, "investor": inv, "operation": op, "total": total},
            "store_type": self.store_type,
        }

    def _build_seller_script(self, product: Dict[str, Any], reason_text: str) -> str:
        """판매자 대화 대본. 리스크: 상품명 없을 때 빈 문장. 방패: 기본 '이 제품'."""
        name = product.get("product_name") or product.get("product_id") or "이 제품"
        return f"'{name}'은(는) {reason_text}로 인해 현재 가장 적합한 추천입니다. 고객님께 이렇게 말씀해 보세요."

    def run(
        self,
        products: List[Dict[str, Any]],
        target_compatibility_tags: Optional[List[str]] = None,
        target_charger_type: Optional[str] = None,
        main_device_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        3단계 Pipeline. 순서 엄수: 스키마 검증 → 팔 수 없음 제거 → 팔면 안 됨 제거 → 스코어링 → 출력.
        리스크: 필터 전에 스코어링하면 "팔면 안 되는" 상품이 추천될 수 있음. 방패: 반드시 Filter 후 Scoring.
        """
        target_tags = target_compatibility_tags if target_compatibility_tags is not None else []
        try:
            # [방패] 입력이 리스트가 아니면 조기 반환으로 하위 로직 오류 방지
            if not isinstance(products, (list, tuple)):
                return self._fallback_response("invalid_input: products must be a list")

            valid = self._validate_schema(products)
            if not valid:
                return self._fallback_response("schema_invalid: 필수 필드(price,margin,stock_age,compatibility_tags) 누락")

            # 1. Filter Layer — 순서 변경 금지: "팔 수 없는 것" 먼저, 그다음 "팔면 안 되는 것"
            can_sell = self._filter_cannot_sell(valid)
            filtered, rejected_log = self._filter_should_not_sell(can_sell, target_tags, target_charger_type)
            if not filtered:
                return self._fallback_response(
                    "constraint_excluded_all: 팔 수 없거나 팔면 안 되는 항목만 있음(호환/충전기 타입 불일치 또는 재고·입고예정 없음)",
                    rejected_log=rejected_log,
                )

            # 2. Scoring Layer — 필터 통과한 항목만 점수 산출(방패: 잘못된 항목 점수화 방지)
            w_ceo, w_inv, w_op = self._get_weights()
            scored: List[Dict[str, Any]] = []
            for p in filtered:
                ceo_r = self._score_ceo_raw(p)
                inv_r = self._score_investor_raw(p)
                op_r = self._score_operation_raw(p)
                ceo, inv, op = self._apply_technical_logic(p, ceo_r, inv_r, op_r, main_device_price)
                total = w_ceo * ceo + w_inv * inv + w_op * op
                total = round(max(SCORE_MIN, min(SCORE_MAX * 2, total)), 4)  # [방패] 합이 1 초과할 수 있으므로 상한 여유

                path_steps: List[str] = []
                main_ok = main_device_price is not None and main_device_price >= CEO_PREMIUM_DEVICE_THRESHOLD
                cand_price = self._safe_float(p.get("price"), 0.0, 0.0, None)
                if main_ok and cand_price <= CEO_LOW_ITEM_PRICE_THRESHOLD:
                    path_steps.append("브랜드 격이 떨어져. 점수를 80% 깎아. (1000$ 기기+10$ 추천)")
                if int(self._safe_float(p.get("stock_age"), 0.0, 0.0, None)) > INVESTOR_AGED_STOCK_DAYS:
                    path_steps.append("돈이 묶여있어! 점수를 1.5배 높여서 빨리 팔게 유도해. (재고령>90일)")
                if self.store_type == "PREMIUM" and w_ceo >= 0.5:
                    path_steps.append("브랜드 이미지 최우선(CEO 가중)에 의해 선정됨")
                elif self.store_type == "OUTLET" and w_inv >= 0.5:
                    path_steps.append("재고 비우기(INV 가중)에 의해 선정됨")
                if not path_steps:
                    path_steps.append("균형 점수에 의해 선정됨")

                log_entry = self._build_reasoning_log(p, ceo, inv, op, total, path_steps)
                script = self._build_seller_script(p, path_steps[0] if path_steps else "균형 점수")
                scored.append({
                    "product_id": p.get("product_id") or p.get("product_name"),
                    "product_name": p.get("product_name") or p.get("product_id"),
                    "score": total,
                    "ceo_score": ceo,
                    "investor_score": inv,
                    "operation_score": op,
                    "reasoning": log_entry,
                    "seller_script": script,
                })
            scored.sort(key=lambda x: (-(x["score"] or 0), str(x.get("product_name") or "")))

            # 3. Output Layer — 상점별 맞춤형 모드: 엔진 상태·가중치 노출
            reasoning_log = [x["reasoning"] for x in scored]
            return {
                "store_id": self.store_id,
                "store_type": self.store_type,
                "internal_state": self._get_internal_state(),
                "weights": self._get_weights_dict(),
                "recommendations": [
                    {
                        "product_id": x["product_id"],
                        "product_name": x["product_name"],
                        "score": x["score"],
                        "reason": x["reasoning"]["reason"],
                        "seller_script": x["seller_script"],
                    }
                    for x in scored
                ],
                "reasoning_log": reasoning_log,
                "seller_scripts": [x["seller_script"] for x in scored],
                "filter_rejected_log": rejected_log,
                "fallback_used": False,
                "fallback_reason": None,
            }
        except Exception as e:
            return self._fallback_response(f"error: {type(e).__name__}: {e}")

    def _fallback_response(
        self, fallback_reason: str, rejected_log: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        리스크: 예외/0건 시 빈 응답이면 대시보드·연동 오류.
        방패: 항상 동일 구조의 Fallback 반환으로 실수해도 손실 최소화.
        """
        return {
            "store_id": self.store_id,
            "store_type": self.store_type,
            "internal_state": self._get_internal_state(),
            "weights": self._get_weights_dict(),
            "recommendations": list(GROWTH_STRATEGY_FALLBACK_ITEMS),
            "reasoning_log": [
                {"product_id": item["product_id"], "product_name": item["product_name"], "reason": item["reason"], "if_then_path": [fallback_reason], "fallback": True}
                for item in GROWTH_STRATEGY_FALLBACK_ITEMS
            ],
            "seller_scripts": [],
            "filter_rejected_log": rejected_log if rejected_log is not None else [],
            "fallback_used": True,
            "fallback_reason": fallback_reason,
        }


def get_store_growth_strategy_recommendations(
    store_id: str,
    store_type: str = "STANDARD",
    products: Optional[List[Dict[str, Any]]] = None,
    target_compatibility_tags: Optional[List[str]] = None,
    target_charger_type: Optional[str] = None,
    main_device_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    상점별 성장 전략 엔진 진입점.
    - main_device_price: 1000$ 이상이면 10$ 이하 추천에 CEO 80% 감점.
    - target_charger_type: 메인 기기 충전 타입(magsafe, usb-c, lightning). 다르면 COO로 제외.
    """
    engine = StoreGrowthStrategyEngine(store_id=store_id, store_type=store_type)
    return engine.run(
        products=products or [],
        target_compatibility_tags=target_compatibility_tags or [],
        target_charger_type=target_charger_type,
        main_device_price=main_device_price,
    )


# dashboard_sales_data.sql 의 sales_data 테이블 컬럼명 (연동 확인용)
SALES_DATA_COLUMNS = (
    "sale_id", "sale_date", "store_id", "product_id", "quantity", "product_name",
    "category_id", "launch_date", "price", "category_name", "store_name", "city", "country",
    "total_sales", "store_stock_quantity", "inventory", "frozen_money", "safety_stock", "status",
)


def _infer_compatibility_tags(product_name: str, category_name: str) -> List[str]:
    """product_name, category_name에서 compatibility_tags 추론 (충전/연결 타입 등)."""
    tags = []
    name = (product_name or "").lower()
    cat = (category_name or "").lower()
    if "magsafe" in name or "mag safe" in name:
        tags.append("magsafe")
    if "usb-c" in name or "usbc" in name or "usb c" in name:
        tags.append("usb-c")
    if "lightning" in name:
        tags.append("lightning")
    if cat:
        tags.append(cat.replace(" ", "_"))
    if not tags:
        tags.append("general")
    return list(dict.fromkeys(tags))


def build_products_from_dashboard_sales_data(
    df: pd.DataFrame, store_id: Optional[str] = None, top_n_per_product: int = 1
) -> List[Dict[str, Any]]:
    """
    dashboard_sales_data.sql 의 sales_data 테이블과 연동.
    테이블 스키마: sale_id, sale_date, store_id, product_id, quantity, product_name,
    category_id, launch_date, price, category_name, store_name, city, country,
    total_sales, store_stock_quantity, inventory, frozen_money, safety_stock, status.
    컬럼명이 Product_Name, product_name 등으로 되어 있어도 매핑하여 사용.
    반환: 엔진 입력용 리스트 (price, margin, stock_age, compatibility_tags 필수 포함).
    """
    if df is None or df.empty:
        return []
    product_col = "product_name" if "product_name" in df.columns else ("Product_Name" if "Product_Name" in df.columns else None)
    pid_col = "product_id" if "product_id" in df.columns else None
    price_col = "price" if "price" in df.columns else None
    cat_col = "category_name" if "category_name" in df.columns else None
    launch_col = "launch_date" if "launch_date" in df.columns else None
    inv_col = "inventory" if "inventory" in df.columns else None
    if not product_col or not price_col:
        return []
    sub = df
    if store_id and "store_id" in df.columns:
        sub = df[df["store_id"].astype(str).str.strip() == str(store_id).strip()]
    if sub.empty:
        sub = df
    agg = sub.groupby(product_col, as_index=False).agg({
        price_col: "first",
        **({cat_col: "first"} if cat_col else {}),
        **({launch_col: "min"} if launch_col and launch_col in sub.columns else {}),
        **({inv_col: "sum"} if inv_col and inv_col in sub.columns else {}),
    })
    out = []
    today = pd.Timestamp.now().normalize()
    for _, row in agg.iterrows():
        name = str(row[product_col]).strip() if pd.notna(row[product_col]) else ""
        if not name:
            continue
        price = float(row[price_col]) if pd.notna(row[price_col]) else 299.0
        cat = str(row[cat_col]).strip() if cat_col and pd.notna(row.get(cat_col)) else ""
        launch = row.get(launch_col)
        if pd.notna(launch) and launch:
            try:
                launch_ts = pd.Timestamp(launch).normalize()
                stock_age = (today - launch_ts).days
            except Exception:
                stock_age = 0
        else:
            stock_age = 0
        inv = int(row[inv_col]) if inv_col and pd.notna(row.get(inv_col)) else 1
        tags = _infer_compatibility_tags(name, cat)
        out.append({
            "product_id": pid_col and pd.notna(row.get(pid_col)) and str(row[pid_col]).strip() or name,
            "product_name": name,
            "price": price,
            "margin": 0.35,
            "stock_age": max(0, stock_age),
            "compatibility_tags": tags,
            "stock": max(0, inv),
            "expected_eta": None,
        })
    return out


def _build_growth_strategy_products_from_df(
    df: pd.DataFrame, store_id: str, product_names: List[str]
) -> List[Dict[str, Any]]:
    """
    기존 추천 결과(상품명 목록) + df에서 price, margin, stock_age, compatibility_tags 수집.
    df는 dashboard_sales_data.sales_data 와 동일/호환 스키마일 때 정확도 높음.
    없으면 기본값으로 채워 스키마 만족시키고 엔진 입력용 리스트 반환.
    """
    if df is None or df.empty or not product_names:
        return []
    product_col = "Product_Name" if "Product_Name" in df.columns else "product_name"
    price_col = "price" if "price" in df.columns else None
    cat_col = "category_name" if "category_name" in df.columns else None
    launch_col = "launch_date" if "launch_date" in df.columns else None
    inv_col = "inventory" if "inventory" in df.columns else None
    today = pd.Timestamp.now().normalize()
    out = []
    for name in product_names[:30]:
        name = str(name).strip()
        if not name:
            continue
        rows = df[df[product_col].astype(str).str.strip() == name]
        row = rows.iloc[0] if not rows.empty else None
        price = float(row[price_col]) if price_col and row is not None and price_col in df.columns and pd.notna(row.get(price_col)) else 299.0
        margin = 0.35
        stock_age = 0
        if launch_col and row is not None and launch_col in df.columns and pd.notna(row.get(launch_col)):
            try:
                launch_ts = pd.Timestamp(row[launch_col]).normalize()
                stock_age = (today - launch_ts).days
            except Exception:
                pass
        inv = int(row[inv_col]) if inv_col and row is not None and inv_col in df.columns and pd.notna(row.get(inv_col)) else 1
        tags = _infer_compatibility_tags(name, str(row[cat_col]).strip() if cat_col and row is not None and cat_col in df.columns and pd.notna(row.get(cat_col)) else "")
        out.append({
            "product_id": name,
            "product_name": name,
            "price": price,
            "margin": margin,
            "stock_age": max(0, stock_age),
            "compatibility_tags": tags,
            "stock": max(0, inv),
            "expected_eta": None,
        })
    return out


def get_store_recommendations(store_id: str, store_type: str = "STANDARD") -> Dict[str, Any]:
    """
    특정 store_id에 대한 4가지 추천 모델 결과 + 상점별 성장 전략 엔진 결과 반환.
    
    반환:
    {
        "store_id": str,
        "store_summary": {...},
        "association": [...],
        "similar_store": [...],
        "latent_demand": [...],
        "trend": [...],
        "growth_strategy": { "recommendations", "reasoning_log", "fallback_used", ... }  # 투자자 보고용
    }
    """
    df = load_sales_dataframe()
    if df is None or df.empty:
        growth_fallback = get_store_growth_strategy_recommendations(store_id, store_type, [], [])
        return {
            "store_id": store_id,
            "store_summary": {"total_sales": 0, "product_count": 0, "store_name": ""},
            "association": [],
            "similar_store": [],
            "latent_demand": [],
            "trend": [],
            "growth_strategy": growth_fallback,
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

        # 상점별 성장 전략 엔진: 4가지 추천 결과에서 상품명 수집 → 엔진 입력 생성 → 실행 (dashboard_sales_data 호환)
        all_product_names = []
        for item in association_list + similar_list + latent_list + trend_list:
            pn = (item.get("product_name") or "").strip()
            if pn and pn not in all_product_names:
                all_product_names.append(pn)
        target_tags = []
        main_device_price = None
        target_charger_type = None
        if store_df is not None and not store_df.empty:
            cat_col = "category_name" if "category_name" in store_df.columns else None
            price_col = "price" if "price" in store_df.columns else None
            product_col = "Product_Name" if "Product_Name" in store_df.columns else "product_name"
            if cat_col:
                target_tags = store_df[cat_col].dropna().astype(str).str.strip().unique().tolist()
                target_tags = [t for t in target_tags if t and t != "nan"]
            if price_col and price_col in store_df.columns:
                store_df_num = store_df.copy()
                store_df_num["_price_num"] = pd.to_numeric(store_df_num[price_col], errors="coerce")
                idx = store_df_num["_price_num"].idxmax()
                if pd.notna(idx):
                    main_device_price = float(store_df_num.loc[idx, "_price_num"])
                    if product_col in store_df_num.columns and cat_col:
                        top_name = str(store_df_num.loc[idx, product_col] or "")
                        top_cat = str(store_df_num.loc[idx, cat_col] or "") if pd.notna(store_df_num.loc[idx, cat_col]) else ""
                        target_charger_type = next((t for t in _infer_compatibility_tags(top_name, top_cat) if t in ("magsafe", "usb-c", "lightning")), None)
        if not target_tags:
            target_tags = ["general"]
        growth_products = _build_growth_strategy_products_from_df(df, store_id, all_product_names)
        if not growth_products and "product_name" in df.columns:
            growth_products = build_products_from_dashboard_sales_data(df, store_id=store_id)
        growth_strategy = get_store_growth_strategy_recommendations(
            store_id, store_type, growth_products, target_tags, target_charger_type, main_device_price
        )

        return {
            "store_id": store_id,
            "store_summary": store_summary,
            "association": association_list,
            "similar_store": similar_list,
            "latent_demand": latent_list,
            "trend": trend_list,
            "growth_strategy": growth_strategy,
        }
    except Exception as e:
        print(f"[추천 시스템] store_id={store_id} 오류: {e}")
        growth_fallback = get_store_growth_strategy_recommendations(store_id, store_type, [], [])
        return {
            "store_id": store_id,
            "store_summary": store_summary,
            "association": _fallback_association(),
            "similar_store": _fallback_similar_store(),
            "latent_demand": _fallback_latent_demand(),
            "trend": _fallback_trend(),
            "growth_strategy": growth_fallback,
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
