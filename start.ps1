# ============================================================================
# Apple Retail Dashboard - start.ps1
# ============================================================================
# 실행 순서: 0) 포트 8000/8001 정리 → 1) 백엔드(8000) 기동 → 2) Health 체크 → 3) 프론트엔드 기동
# 다음 작업 시: 이 스크립트 실행 후 대시보드(3000)·API(8000/docs) 사용. 상세는 web-development/README.md 참고.
# ============================================================================

# -----------------------------------------------------------------------------
# [지금까지 작업 순서] - 다음에도 순차적으로 참고용
# -----------------------------------------------------------------------------
# 1. 마커 라벨 한글(영문) 표기
#    - GlobeMap: getLabelText, continent_ko(continent), country ko(en), city
#    - lib/country.ts: CITY_LABELS, formatCityDisplay, getCityKo
#    - page.tsx: globeMarkersData에 city_ko 추가
#
# 2. 대시보드 한글 인식
#    - lib/country.ts: resolveCountryToEn, resolveContinentToEn, resolveCityToEn
#    - page.tsx, sales/page.tsx: API 호출 전 resolveCountryToEn 적용
#    - backend/main.py: _COUNTRY_KO_TO_EN, _resolve_country_to_en 등
#
# 3. 지도 마커/글자 색상 흰색
#    - GlobeMap: labelColor → #ffffff
#
# 4. 도시 마커 한글(영문) 표기
#    - GlobeMap: formatCityDisplay 사용, lib/country CASE_INSENSITIVE 매칭
#
# 5. 한글 ??? 표시 수정 (HTML 요소로 라벨 렌더링)
#    - GlobeMap: labelsData=[] , htmlElementsData 사용 (3D 텍스트 → HTML)
#    - createLabelElement로 CSS2DRenderer 기반 한글 지원
#
# 6. 모델 서버 연동 카드 추가
#    - page.tsx: 새 카드로 load_sales_data, prediction model 등 연동 상태 표시
#
# 7. 모델 서버 연동 카드 → 모델 상태 카드 우측 이동
#    - grid lg:grid-cols-2, 모델 상태 | 모델 서버 연동 나란히
#
# 8. 지도 줌 / 글자 줌 분리
#    - GlobeMap: 지도 줌(cameraAltitude), 마커/글자 줌(markerLabelScale)
#
# 9. 지도 줌=지도만, 마커/글자 줌=마커+글자
#    - pointRadius, createLabelElement: markerLabelScaleValue 사용 (altitude 제외)
#
# 10. 마커 우측에 한글(영문) 표기
#     - createLabelElement: transform:translateX(12px)
#
# 11. sales/page.tsx PieChart label 타입 에러 수정
#     - label prop: payload?.pct 사용
#
# 12. 대시보드 새로고침 버튼
#     - page.tsx 헤더: 새로고침 버튼 (window.location.reload)
#
# 13. import 경로 수정 (@/lib/country → ../lib/country, ../../lib/country)
#     - GlobeMap: ../../lib/country
#     - page.tsx: ../lib/country
#
# 14. 수요 대시보드 로직 → prediction model.py
#     - get_demand_dashboard_data(continent, country, store_id, city, year)
#     - GET /api/demand-dashboard → 프론트엔드 수요 박스·오버레이 연동
#     - 로직 수정: model-server/03.prediction model/prediction model.py
#
# 15. [2025-02-17] Store_Name 한글(영문) 형식 표시
#     - lib/country.ts: STORE_LABELS, formatStoreDisplay()
#     - sales/page.tsx: 매장 바차트 라벨 formatStoreDisplay(stripApplePrefix(...))
#
# 16. [2025-02-17] 매장별 연도별 매출(Top 15) 탭 제거
#     - sales/page.tsx: storeSalesByYearChartData 차트 섹션 삭제
#
# 17. [2025-02-17] 지역(도시)별 매출 섹션 제거
#     - sales/page.tsx: citySalesData 차트 섹션 및 useMemo 삭제
#
# 18. [2025-02-17] Store_Name 바차트 Y축 라벨 겹침 방지
#     - sales/page.tsx: YAxis width 260, interval=0, tickMargin=4, bar 높이 44px
#
# 19. [2025-02-17] 매장 클릭 시 3개월 단위 매출 스캐터·라인 차트
#     - Sales analysis.py: get_sales_by_store_quarterly(store_name, country)
#     - main.py: GET /api/sales-by-store-quarterly
#     - sales/page.tsx: Bar onClick → selectedStoreForQuarterly, ComposedChart(Line+Scatter)
#     - app/api/sales-by-store-quarterly/route.ts: Next.js 프록시 (8000→8001 폴백)
#     - 포트 8000 다중 프로세스 시 8001 사용 권장
#
# 20. [2025-02-17] 스토어명 매칭 강화 (소호(SoHo) 등)
#     - Sales analysis.py: _extract_store_name_for_match(), 괄호 내 영문 추출
#
# 21. [안전재고 대시보드] 카테고리/연도/대륙·국가·상점 필터, 상점별 3개월·상품별 판매 차트
#     - Inventory Optimization.py, main.py (safety-stock API), page.tsx 오버레이
# 22. [안전재고] 수요 예측: ARIMA(arima_model.joblib)만 사용, Prophet 제거. 2020년부터 분기별 차트
#     - get_demand_forecast_chart_data() 분기 집계, _fallback_safety_stock_forecast_chart 분기별
# 23. [정리] 상수·타입 정리, WORK_CONTEXT.md 및 .cursor/rules/project-context.mdc 추가
#
# 24. [추천 대시보드] 상점별 맞춤형 성장 전략 (recommendation/page.tsx)
#     - store-list, store-recommendations, store-sales-forecast API
#     - 4대 추천: 유사 상점, 연관 분석(Basket), 잠재 수요(SVD), 지역 트렌드
#     - 안전재고·매출·수요 대시보드 연동 분석(과잉 재고, 매출 요약, 수요 2025)
# 25. [추천 폴백] 추천 결과 없을 때 전체 매출 기준 상위 5개 품목 표시
#     - Real-time execution and performance dashboard.py: _get_top5_product_names, get_store_recommendations 폴백
#     - 프론트: is_fallback 시 "추천 결과 없음 → 전체 인기 상위 5개 품목" 문구
# 26. [안정화] recommendation page store_summary/배열 optional chaining·null 병합
#
# 27. [매출 대시보드 로드 안정화] API 호출 상대경로 우선
#     - frontend/lib/api.ts: apiGet/apiPost 시 항상 ''(프록시) 먼저 시도 후 NEXT_PUBLIC_API_URL, localhost:8000
#     - sales/page.tsx: 로딩 15초 초과 시 강제 해제 → "다시 시도" 표시
#
# 28. [3개월 단위 매출 추이 그래프 수정] 매장명 매칭 강화 (Sales analysis.py)
#     - _strip_apple_store_prefix() 추가 (Apple Store / Apple 접두사 제거)
#     - _extract_store_name_for_match() 후보에 "Apple SoHo", "Store SoHo" 추가
#     - get_sales_by_store_quarterly, get_sales_by_store_quarterly_by_category: 대소문자 무시·정규화 매칭
#     - "소호(SoHo)" 등 매장 클릭 시 분기별·카테고리별 차트 정상 표시
#
# 29. [전체 안정화·정리] README.md 섹션 9 안정화 및 최근 작업 정리, 매출 대시보드 워킹 노트 추가
#     - 데이터·역할 분리 원칙, 매출/추천 안정화 요약, start.ps1 작업 순서 갱신
# -----------------------------------------------------------------------------

$ErrorActionPreference = "SilentlyContinue"
$hostIp = "192.168.0.43"
$backendPath = Join-Path $PSScriptRoot "backend"
$frontendPath = Join-Path $PSScriptRoot "frontend"

Write-Host ""
Write-Host "=== Apple Retail Dashboard ===" -ForegroundColor Cyan
Write-Host "  순서: 포트 정리 -> Backend($hostIp:8000) -> Health 체크 -> Frontend(3000)" -ForegroundColor Gray
Write-Host ""

# Step 0: 포트 8000/8001 정리 (기존 프로세스로 인한 404 방지)
Write-Host "[0/4] Port 8000 cleanup..." -ForegroundColor Yellow
$pids = @()
try {
    $conn8000 = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    $conn8001 = Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue
    if ($conn8000) { $pids += $conn8000.OwningProcess | Select-Object -Unique }
    if ($conn8001) { $pids += $conn8001.OwningProcess | Select-Object -Unique }
    foreach ($p in ($pids | Sort-Object -Unique)) {
        if ($p -gt 0) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Write-Host "  Stopped PID $p" -ForegroundColor Gray
        }
    }
    if ($pids.Count -gt 0) { Start-Sleep -Seconds 2 }
} catch { }
Write-Host ""

# Step 1: Backend (호스트 $hostIp 에서 리스닝)
Write-Host "[1/4] Backend starting ($hostIp`:8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendPath'; Write-Host '=== FastAPI Backend ($hostIp`:8000) ===' -ForegroundColor Green; uvicorn main:app --reload --host $hostIp --port 8000"
Start-Sleep -Seconds 10

# Step 2: Wait for backend health ($hostIp:8000)
Write-Host "[2/4] Waiting for backend..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$ready = $false
$healthUri = "http://${hostIp}:8000/api/health"
while ($attempt -lt $maxAttempts) {
    try {
        $null = Invoke-WebRequest -Uri $healthUri -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
        $ready = $true
        Write-Host "  Backend ready!" -ForegroundColor Green
        break
    } catch {
        $attempt++
        Start-Sleep -Seconds 1
        Write-Host "  waiting... ($attempt/$maxAttempts)" -ForegroundColor Gray
    }
}
if (-not $ready) {
    Write-Host "  Backend timeout. Check the backend window." -ForegroundColor Red
}
Start-Sleep -Seconds 2

# Step 3: Frontend
Write-Host "[3/4] Frontend starting..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontendPath'; Write-Host '=== Next.js Frontend ===' -ForegroundColor Green; npm run dev"
Start-Sleep -Seconds 8

Write-Host ""
Write-Host "[4/4] Done!" -ForegroundColor Green
Write-Host ""
Write-Host "  --- 호스트 주소 ($hostIp) ---" -ForegroundColor Yellow
Write-Host "  대시보드 (프론트)  http://${hostIp}:3000" -ForegroundColor Cyan
Write-Host "  API 문서          http://${hostIp}:8000/docs" -ForegroundColor Cyan
Write-Host "  API 상태          http://${hostIp}:8000/api/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "  (API 404 시: 포트 8000 정리 후 start.ps1 재실행 · 상세: README.md)" -ForegroundColor Gray
Write-Host ""
Start-Process "http://${hostIp}:3000"
