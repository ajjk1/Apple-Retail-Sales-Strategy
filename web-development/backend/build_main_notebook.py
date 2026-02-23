# -*- coding: utf-8 -*-
"""main.py를 ipynb로 변환하고 각 섹션을 상세히 셀 단위로 구분하는 스크립트."""
import json

# 섹션 순서: 01.Database for dashboard → 02.prediction model → 03.Sales analysis → 04.Inventory Optimization → 05.Inventory Optimization (실시간·대시보드)
SECTION_ORDER = [
    "01.Database for dashboard",
    "02.prediction model",
    "03.Sales analysis",
    "04.Inventory Optimization",
    "05.Inventory Optimization",
]

def main():
    with open("main.py", "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines()

    # (시작 0-based, 끝 exclusive, 제목, 설명, 섹션)
    blocks = [
        (0, 22, "모듈 docstring", "Apple Retail API 개요·모듈화·CORS·HF Spaces 실행 안내.", "01.Database for dashboard"),
        (22, 45, "라이브러리 import 및 FastAPI 앱 생성", "FastAPI, pandas, pathlib, typing 등 import 후 app = FastAPI(title=...) 생성.", "01.Database for dashboard"),
        (45, 81, "경로·한글 매핑 상수", "_PROJECT_ROOT, _MODEL_SERVER, _COUNTRY_KO_TO_EN, _CONTINENT_KO_TO_EN 정의.", "01.Database for dashboard"),
        (80, 110, "국가/대륙 영문 변환 및 모델 경로 헬퍼", "_resolve_country_to_en, _resolve_continent_to_en, _model_path 함수.", "01.Database for dashboard"),
        (109, 139, "load_sales_data.py 동적 로드", "importlib로 model-server/load_sales_data.py 로드, load_sales_dataframe·get_data_source_info 바인딩.", "01.Database for dashboard"),
        (138, 152, "내장 로더 전역 변수", "_LS_DATA_DIR, _LS_SQL_FILES, _ls_cache_df 등 캐시·경로 변수.", "01.Database for dashboard"),
        (151, 178, "문자열 정규화 유틸", "_ls_strip_wrapping_quotes, _ls_normalize_text_columns (SQL/CSV 따옴표 정리).", "01.Database for dashboard"),
        (176, 212, "데이터 디렉터리·SQL/CSV 경로 목록", "_ls_get_data_dir, _ls_get_sql_files, _ls_get_csv_candidates.", "01.Database for dashboard"),
        (211, 266, "SQL VALUES 파싱·소스 mtime", "_ls_parse_insert_values, _ls_source_mtime.", "01.Database for dashboard"),
        (265, 358, "내장 SQL/CSV 로더 본문", "_ls_load_sales_dataframe (in-memory sqlite → CSV 폴백).", "01.Database for dashboard"),
        (356, 382, "데이터 소스 정보·load_sales_data 심 등록", "_ls_get_data_source_info, load_sales_dataframe None 시 전역 할당 및 sys.modules 주입.", "01.Database for dashboard"),
        (829, 884, "prediction model.py 동적 로드", "get_city_category_pie_response, get_store_markers, get_sales_quantity_forecast 등 바인딩.", "02.prediction model"),
        (1458, 1474, "도시/카테고리 파이·sale-id 파이", "get_city_category_pie, get_sale_id_pie.", "02.prediction model"),
        (1473, 1516, "store-markers·store/country 파이", "api_store_markers, api_store_category_pie, api_country_category_pie, api_country_stores_pie.", "02.prediction model"),
        (1514, 1560, "대륙 파이·매출 요약·매장 등급", "api_continent_category_pie, api_continent_countries_pie, api_sales_summary, api_store_performance_grade.", "02.prediction model"),
        (2115, 2186, "고객 여정·퍼널 가중치·수요 예측·상품별 수요", "api_customer_journey_funnel, api_funnel_stage_weight, api_sales_quantity_forecast, api_predicted_demand_by_product.", "02.prediction model"),
        (2184, 2283, "product 카테고리 매핑·demand-dashboard", "_get_product_category_map, _norm_category, _enrich_product_demand_with_category, api_demand_dashboard.", "02.prediction model"),
        (2281, 2347, "스토어/상품 바차트·apple-data 폴백", "api_store_product_quantity_barchart, _apple_data_fallback.", "02.prediction model"),
        (883, 907, "Sales analysis.py 동적 로드", "get_store_sales_summary, get_sales_by_store_quarterly 등.", "03.Sales analysis"),
        (1557, 1621, "지역 피봇·가격수요 상관·매출 박스", "api_region_category_pivot, api_price_demand_correlation, api_sales_box.", "03.Sales analysis"),
        (1619, 1691, "국가/스토어별 매출·data-source", "api_sales_by_country_category ~ api_data_source.", "03.Sales analysis"),
        (381, 421, "Inventory 상수·ARIMA 로드", "_INV_DEFAULT_PRODUCT, _ARIMA_MODEL_PATH, _inv_load_arima_model (전체).", "04.Inventory Optimization"),
        (421, 463, "안전재고 파이프라인", "_inv_run_inventory_pipeline (Safety_Stock·Inventory·Status·Frozen_Money 산출).", "04.Inventory Optimization"),
        (461, 477, "재고 상태별 건수 API용", "get_safety_stock_summary.", "04.Inventory Optimization"),
        (475, 525, "안전재고 KPI (동결자금·Danger/Overstock·예상매출)", "get_kpi_summary.", "04.Inventory Optimization"),
        (523, 626, "안전재고 상세 리스트 (매장별)", "get_inventory_list, _get_inventory_list_impl (status_filter·한글·0.1~3.5배 시뮬레이션).", "04.Inventory Optimization"),
        (551, 591, "재고 경고 (Health_Index < 70)", "get_inventory_critical_alerts.", "04.Inventory Optimization"),
        (589, 611, "추천용 재고 건전성·분기 라벨·ARIMA 차트 헬퍼", "get_inventory_health_for_recommendation, _inv_quarter_label, _inv_get_forecast_chart_with_arima.", "04.Inventory Optimization"),
        (608, 696, "수요 예측 차트 데이터", "get_demand_forecast_chart_data (ARIMA·캐시).", "04.Inventory Optimization"),
        (694, 760, "카테고리별 상점·분기 판매", "get_sales_by_store_six_month.", "04.Inventory Optimization"),
        (758, 831, "카테고리/필터별 상품별 판매", "get_sales_by_product.", "04.Inventory Optimization"),
        (1021, 1162, "안전재고 차트 폴백·CORS·GZip", "SAFETY_STOCK_DEFAULT_PRODUCT, _fallback_safety_stock_forecast_chart, CORSMiddleware, GZipMiddleware.", "04.Inventory Optimization"),
        (1689, 1712, "안전재고 상태·차트 진입점", "api_safety_stock, api_safety_stock_forecast_chart 시작.", "04.Inventory Optimization"),
        (1710, 1786, "안전재고 차트 (2025 수요 대시보드 반영)", "api_safety_stock_forecast_chart 나머지·quarters_2025 교체.", "04.Inventory Optimization"),
        (1783, 1844, "안전재고 상점/상품·KPI·리스트·경고", "api_safety_stock_sales_by_store_period ~ api_inventory_critical_alerts.", "04.Inventory Optimization"),
        (1842, 1891, "인벤토리 코멘트 (경로·읽기/쓰기·GET/POST)", "_INVENTORY_COMMENTS_PATH, _read_inventory_comments, _append_inventory_comment, api_inventory_comments.", "04.Inventory Optimization"),
        (906, 930, "Real-time dashboard.py 동적 로드", "get_recommendation_summary, get_store_list 등 + load_sales_dataframe 주입.", "05.Inventory Optimization"),
        (928, 1022, "연동 진단·startup 이벤트", "_run_integration_report, @app.on_event('startup').", "05.Inventory Optimization"),
        (1160, 1186, "캐시·KST 날짜·last_updated 계산", "_cached_last_updated, _today_kst, _compute_last_updated.", "05.Inventory Optimization"),
        (1185, 1359, "리테일 데이터 요약 로드", "load_retail_data (모델 서버 우선·CSV 폴백).", "05.Inventory Optimization"),
        (1356, 1393, "대시보드 URL·루트", "_DASHBOARD_VERCEL_URL, root.", "05.Inventory Optimization"),
        (1392, 1460, "health·dashboard HTML", "health_check, api_health_check, api_health_page, dashboard_html.", "05.Inventory Optimization"),
        (1889, 1972, "quick-status·integration-status·추천 요약·스토어 예측/추천", "api_quick_status, api_integration_status, api_recommendation_summary, api_store_sales_forecast, api_store_recommendations.", "05.Inventory Optimization"),
        (1970, 2080, "store-list 이전 구간", "api_recommendation_summary 등 ~ store-sales-forecast 데코레이터 직전.", "05.Inventory Optimization"),
        (2080, 2095, "store-sales-forecast", "api_store_sales_forecast (매출 예측 시계열, docstring 포함 전체).", "05.Inventory Optimization"),
        (2095, 2121, "store-recommendations", "api_store_recommendations (4가지 추천 모델, docstring 포함 전체).", "05.Inventory Optimization"),
        (2122, 2180, "store-list (realtime 우선·폴백)", "api_store_list.", "05.Inventory Optimization"),
        (2179, 2260, "맞춤 추천·협업 필터·피드백 루프", "api_user_personalized_recommendations, api_collab_filter_recommendations, api_recommendation_feedback.", "05.Inventory Optimization"),
        (2343, 2484, "last-updated·apple-data·__main__", "api_last_updated, get_apple_data, --integration-check 진입.", "05.Inventory Optimization"),
    ]

    # 섹션 순서로 정렬 (동일 섹션 내에서는 main.py 등장 순서 유지)
    order_map = {s: i for i, s in enumerate(SECTION_ORDER)}
    blocks_sorted = sorted(blocks, key=lambda b: (order_map.get(b[4], 99), b[0]))

    cells = []
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# Apple Retail API — main.py 노트북 버전\n\n",
            "구조: **Chapter** → **Step** → **Section** → **Phase** 순으로 구분했습니다.\n\n",
            "- **Chapter**: 01.Database / 02.prediction model / 03.Sales analysis / 04.Inventory Optimization / 05.Inventory Optimization\n",
            "- **Step**: 챕터 내 단계 번호 (Step 1.1, 1.2, …)\n",
            "- **Section**: 블록 제목 (예: 모듈 docstring, 라이브러리 import)\n",
            "- **Phase**: 실행 단계 (해당 코드 셀)\n\n",
            "- **실행**: 실제 API는 `uvicorn main:app`으로 실행합니다."
        ]
    })

    prev_section = None
    step_per_chapter = {}  # chapter_num -> step index (1-based)
    for start, end, title, desc, section in blocks_sorted:
        chapter_num = order_map.get(section, 0) + 1  # 1..5
        if section != prev_section:
            step_per_chapter[chapter_num] = 0
            cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": [f"---\n\n# Chapter {chapter_num}: {section}\n"]
            })
            prev_section = section
        step_per_chapter[chapter_num] = step_per_chapter.get(chapter_num, 0) + 1
        step_label = f"Step {chapter_num}.{step_per_chapter[chapter_num]}"

        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [f"## {step_label}\n\n", f"### Section: {title}\n\n", desc, "\n\n#### Phase\n"]
        })
        code_lines = lines[start:end]
        code = "\n".join(code_lines)
        if code.strip():
            code = f"# [{title}] main.py 라인 {start+1}~{end}\n\n" + code
        code_source = [line + "\n" for line in code.split("\n")]
        if code_source and not code_source[-1].endswith("\n") and code_source[-1].rstrip():
            code_source[-1] = code_source[-1].rstrip() + "\n"
        cells.append({
            "cell_type": "code",
            "metadata": {},
            "source": code_source,
            "outputs": [],
            "execution_count": None
        })

    nb = {
        "nbformat": 4,
        "nbformat_minor": 4,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.0"}
        },
        "cells": cells
    }
    with open("main.ipynb", "w", encoding="utf-8") as out:
        json.dump(nb, out, ensure_ascii=False, indent=1)
    print(f"Created main.ipynb with {len(cells)} cells (sections: 01→02→03→04→05)")

if __name__ == "__main__":
    main()
