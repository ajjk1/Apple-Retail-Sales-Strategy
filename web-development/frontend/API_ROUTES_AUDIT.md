# API 경로 대조 (백엔드 main.py ↔ 프론트엔드 fetch/apiGet)

백엔드(FastAPI) 라우트와 프론트엔드 호출 경로가 철자까지 일치하는지 정리합니다.

## rewrites (next.config.js)

- `source: '/api/:path*'` → `destination: \`${backendUrl}/api/:path*\``
- backendUrl: `BACKEND_URL` 또는 `NEXT_PUBLIC_API_URL` 또는 프로덕션 시 `https://apple-retail-study-apple-retail-sales-strategy.hf.space`

## 백엔드 라우트 ↔ 프론트 호출

| 백엔드 (main.py) | 프론트 호출 | 비고 |
|------------------|-------------|------|
| GET /api/health | /api/health | page.tsx 헬스체크 |
| GET /api/apple-data | /api/apple-data | page.tsx fetchData |
| GET /api/city-category-pie | /api/city-category-pie | page.tsx |
| GET /api/store-markers | /api/store-markers | page.tsx |
| GET /api/continent-category-pie | /api/continent-category-pie | page.tsx |
| GET /api/store-category-pie | /api/store-category-pie?store_id= | page.tsx |
| GET /api/country-category-pie | /api/country-category-pie?country= | page.tsx |
| GET /api/safety-stock | /api/safety-stock | page.tsx |
| GET /api/safety-stock-forecast-chart | /api/safety-stock-forecast-chart, ?product_name= | page.tsx |
| GET /api/safety-stock-kpi | /api/safety-stock-kpi | page.tsx |
| GET /api/inventory-comments | /api/inventory-comments | page.tsx (GET/fetch) |
| POST /api/inventory-comments | POST /api/inventory-comments | page.tsx |
| GET /api/safety-stock-inventory-list | /api/safety-stock-inventory-list?status_filter= 등 | page.tsx |
| GET /api/safety-stock-sales-by-store-period | /api/safety-stock-sales-by-store-period? | page.tsx |
| GET /api/safety-stock-sales-by-product | /api/safety-stock-sales-by-product? | page.tsx |
| GET /api/sales-quantity-forecast | /api/sales-quantity-forecast | page.tsx |
| GET /api/sales-box | /api/sales-box | page.tsx |
| GET /api/demand-dashboard | /api/demand-dashboard? | page.tsx, recommendation |
| GET /api/data-source | /api/data-source | page.tsx |
| GET /api/quick-status | /api/quick-status | page.tsx |
| GET /api/integration-status | /api/integration-status | page.tsx |
| GET /api/last-updated | /api/last-updated | page.tsx |
| GET /api/sales-summary | /api/sales-summary | sales/page, recommendation |
| GET /api/store-performance-grade | /api/store-performance-grade | sales/page |
| GET /api/sales-by-country-category | /api/sales-by-country-category?country= | sales/page |
| GET /api/sales-by-store | /api/sales-by-store?country= | sales/page |
| GET /api/sales-by-store-quarterly | /api/sales-by-store-quarterly? (route.ts 프록시) | sales/page |
| GET /api/sales-by-store-quarterly-by-category | /api/sales-by-store-quarterly-by-category? | sales/page |
| GET /api/recommendation-summary | /api/recommendation-summary | recommendation |
| GET /api/store-list | /api/store-list | recommendation (fetch) |
| GET /api/store-recommendations/{store_id} | /api/store-recommendations/${id} | recommendation |
| GET /api/store-sales-forecast/{store_id} | /api/store-sales-forecast/${id} | recommendation |
| GET /api/user-personalized-recommendations | /api/user-personalized-recommendations?store_id= | recommendation |
| GET /api/collab-filter-recommendations | /api/collab-filter-recommendations?store_id= | recommendation |
| POST /api/recommendation-feedback | /api/recommendation-feedback | recommendation apiPost |
| GET /api/region-category-pivot | /api/region-category-pivot | recommendation |
| GET /api/price-demand-correlation | /api/price-demand-correlation?product_name= | recommendation |
| GET /api/inventory-critical-alerts | /api/inventory-critical-alerts?limit=50 | recommendation |
| GET /api/customer-journey-funnel | /api/customer-journey-funnel | recommendation |
| GET /api/funnel-stage-weight | /api/funnel-stage-weight | recommendation |
| GET /api/predicted-demand-by-product | /api/predicted-demand-by-product | page.tsx |

## 백엔드만 존재 (프론트 미호출)

- GET /api/sale-id-pie
- GET /api/country-stores-pie
- GET /api/continent-countries-pie
- GET /api/store-product-quantity-barchart

위 경로는 프론트에서 호출하지 않음. 신규 화면 연동 시 이 문서와 경로를 맞출 것.
