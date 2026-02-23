'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { apiGet, apiPost } from '../../lib/api';
import {
  ComposedChart,
  Area,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  ScatterChart,
  Scatter,
} from 'recharts';

interface StoreRecommendation {
  product_name: string;
  lift?: number;
  confidence?: number;
  support?: number;
  similarity_score?: number;
  sales_in_similar_store?: number;
  predicted_sales?: number;
  growth_rate?: number;
  recent_sales?: number;
  reason?: string;
  is_fallback?: boolean;
}

interface StoreRecommendationsData {
  store_id: string;
  store_summary: {
    total_sales: number;
    product_count: number;
    store_name: string;
  };
  association: StoreRecommendation[];
  similar_store: StoreRecommendation[];
  latent_demand: StoreRecommendation[];
  trend: StoreRecommendation[];
}

interface Store {
  store_id: string;
  store_name: string;
}

interface SalesForecastData {
  actual: { date: string; value: number }[];
  predicted: { date: string; value: number; lower: number; upper: number }[];
  store_id: string;
}

/** 안전재고 대시보드: 과잉 재고 (매장별, Inventory Action Center 연동) */
interface OverstockItem {
  Store_Name?: string;
  Product_Name: string;
  Inventory: number;
  Safety_Stock: number;
  Status: string;
  Frozen_Money: number;
  price?: number;
}

/** 매출 대시보드 요약 (Sales summary 연동) */
interface SalesSummaryData {
  total_sum?: number;
  store_count?: number;
  sales_by_year?: { year: number; total_sales?: number }[];
  predicted_sales_2025?: number;
  top_stores?: { store_name?: string; total_sales?: number }[];
}

/** 수요 대시보드 (demand-dashboard API 연동) */
interface DemandDashboardData {
  total_demand?: number;
  category_demand?: { category: string; quantity: number }[];
  category_demand_2025?: { category: string; predicted_quantity?: number; quantity_2024?: number }[];
  product_demand_2025?: { product_id?: string; product_name?: string; predicted_quantity?: number; quantity_2024?: number; category?: string }[];
  yearly_quantity?: { year: number; quantity?: number }[];
}

/** [3.4.2] 지역별 카테고리 매출 피봇 (region-category-pivot API) */
interface RegionCategoryPivotData {
  countries: string[];
  categories: string[];
  pivot_rows: { country: string; total_sales: number; by_category: Record<string, number> }[];
  category_share?: { category: string; pct: number; total_sales: number }[];
}

/** [3.4.3] 가격-수요 상관관계 (price-demand-correlation API) */
interface PriceDemandCorrelationData {
  product_name: string;
  correlation: number | null;
  insight: string;
  scatter_data: { price: number; quantity: number }[];
  available_products: string[];
}

/** [3.4.4] 실시간 재고·예측 신뢰도 경고 (inventory-critical-alerts API) */
interface InventoryCriticalAlertsData {
  critical_count: number;
  critical_items: { Store_Name?: string; Product_Name: string; Health_Index: number; Inventory: number; Safety_Stock: number }[];
}

/** [4.1.1] 유저(상점) 맞춤형 추천 (user-personalized-recommendations API) */
interface UserPersonalizedRecommendationData {
  user_id?: number;
  user_identifier?: string;
  recommendations?: { rank: number; product_id: string; reason: string }[];
  top_3?: { product_name: string; score: number }[];
  user_history_categories?: string[];
  /** [4.3] 성과 지표 시뮬레이션: 추천 도입 후 재고 소진 속도 */
  performance_simulation?: {
    lift_rate: number;
    expected_sales_increase_pct: number;
    insight: string;
    projected_scores: number[];
    data_source?: string;
    data_source_description?: string;
  };
}

/** [4.1.1] 유저(상점) 기반 협업 필터링 및 재고 가중치 결합 (collab-filter-recommendations API) */
interface CollabFilterRecommendationData {
  target_store: string;
  top_recommendations: { product_name: string; base_score: number; boost: number; final_score: number }[];
}

/** [4.4.1] 고객 여정 단계별 수치 분석 (customer-journey-funnel API) */
interface CustomerJourneyFunnelData {
  stages: { stage: string; user_count: number; conversion_rate: number }[];
  overall_cvr: number;
  drop_off: { stage: string; conversion_rate: number }[];
  data_source?: string;
  data_source_description?: string;
}

/** [4.4.2] 퍼널 위치에 따른 가중치 동적 할당 (funnel-stage-weight API) */
interface FunnelStageWeightData {
  stages?: { stage: string; recommendation_weight: number; strategy: string }[];
  current_stage?: string;
  recommendation_weight?: number;
  strategy?: string;
  data_source?: string;
  data_source_description?: string;
}

export default function RecommendationPage() {
  const [loading, setLoading] = useState(true);
  const [storeLoading, setStoreLoading] = useState(false);
  const [selectedStoreId, setSelectedStoreId] = useState<string>('');
  const [stores, setStores] = useState<Store[]>([]);
  const [recommendations, setRecommendations] = useState<StoreRecommendationsData | null>(null);
  const [salesForecast, setSalesForecast] = useState<SalesForecastData | null>(null);
  const [overstockList, setOverstockList] = useState<OverstockItem[]>([]);
  const [salesSummary, setSalesSummary] = useState<SalesSummaryData | null>(null);
  const [demandDashboard, setDemandDashboard] = useState<DemandDashboardData | null>(null);
  const [summaryData, setSummaryData] = useState<{
    top_products: { product: string; sales: number; rank: number }[];
    top_categories: { category: string; sales: number; rank: number }[];
  } | null>(null);
  const [regionCategoryPivot, setRegionCategoryPivot] = useState<RegionCategoryPivotData | null>(null);
  const [pivotSelectedCountry, setPivotSelectedCountry] = useState<string>('');
  const [priceDemandCorrelation, setPriceDemandCorrelation] = useState<PriceDemandCorrelationData | null>(null);
  const [correlationProduct, setCorrelationProduct] = useState<string>('');
  const [criticalAlerts, setCriticalAlerts] = useState<InventoryCriticalAlertsData | null>(null);
  const [storeListLoaded, setStoreListLoaded] = useState(false);
  const [storeListRetry, setStoreListRetry] = useState(0);
  const [storeListError, setStoreListError] = useState<string | null>(null);
  const [userPersonalizedRec, setUserPersonalizedRec] = useState<UserPersonalizedRecommendationData | null>(null);
  const [collabFilterRec, setCollabFilterRec] = useState<CollabFilterRecommendationData | null>(null);
  const [feedbackClicks, setFeedbackClicks] = useState<Record<string, 0 | 1>>({});
  const [feedbackResult, setFeedbackResult] = useState<{ clicked_items: string[]; message: string; log_path: string } | null>(null);
  const [customerJourneyFunnel, setCustomerJourneyFunnel] = useState<CustomerJourneyFunnelData | null>(null);
  const [funnelStageWeights, setFunnelStageWeights] = useState<FunnelStageWeightData | null>(null);
  const [selectedFunnelStage, setSelectedFunnelStage] = useState<string>('Add_to_Cart');

  // [4.3.2] 추천 상품 목록: userPersonalizedRec.top_3 또는 collabFilterRec.top_recommendations
  const feedbackProductList = useMemo(() => {
    const fromTop3 = userPersonalizedRec?.top_3?.map((r) => r.product_name) ?? [];
    const fromCollab = collabFilterRec?.top_recommendations?.map((r) => r.product_name) ?? [];
    const names = fromTop3.length ? fromTop3 : fromCollab;
    return names.filter(Boolean);
  }, [userPersonalizedRec?.top_3, collabFilterRec?.top_recommendations]);

  useEffect(() => {
    if (feedbackProductList.length) {
      setFeedbackClicks((prev) => {
        const next = { ...prev };
        feedbackProductList.forEach((name) => {
          if (next[name] === undefined) next[name] = 0;
        });
        return next;
      });
    } else {
      setFeedbackClicks({});
    }
    setFeedbackResult(null);
  }, [feedbackProductList.join(',')]);

  const handleFeedbackSubmit = async () => {
    setFeedbackResult(null);
    const res = await apiPost<{ clicked_items: string[]; message: string; log_path: string }>('/api/recommendation-feedback', {
      store_id: selectedStoreId || undefined,
      user_id: userPersonalizedRec?.user_id,
      feedback: feedbackProductList.length ? feedbackClicks : {},
    });
    if (res) setFeedbackResult(res);
  };

  // Store 목록 로드 (타임아웃 12초로 조기 종료 → 로딩 상태 해제 보장)
  useEffect(() => {
    setStoreListLoaded(false);
    setStoreListError(null);
    const STORE_LIST_TIMEOUT_MS = 12000;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), STORE_LIST_TIMEOUT_MS);
    const url = '/api/store-list';
    fetch(url, { signal: controller.signal, cache: 'no-store' })
      .then((res) => (res?.ok ? res.json() : null))
      .then((json: { stores?: Store[] } | null) => {
        clearTimeout(timeoutId);
        if (json?.stores && json.stores.length > 0) {
          setStores(json.stores);
          setSelectedStoreId(json.stores[0].store_id);
          setStoreListError(null);
        } else {
          setStores([]);
          setStoreListError(json ? '상점 데이터가 비어 있습니다.' : '응답 형식 오류');
        }
      })
      .catch((err) => {
        clearTimeout(timeoutId);
        console.error('[Recommendation] Failed to load store-list:', err);
        setStores([]);
        setStoreListError(err?.name === 'AbortError' ? '연결 시간이 초과되었습니다. 백엔드(port 8000) 실행 후 다시 시도해 주세요.' : '상점 목록을 불러오지 못했습니다.');
      })
      .finally(() => setStoreListLoaded(true));
    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  }, [storeListRetry]);

  // 기본 요약 + 안전재고 과잉 품목 + 매출 대시보드 요약
  useEffect(() => {
    Promise.all([
      apiGet<{ top_products?: unknown[]; top_categories?: unknown[] }>('/api/recommendation-summary'),
      apiGet<OverstockItem[]>('/api/safety-stock-inventory-list?status_filter=Overstock'),
      apiGet<SalesSummaryData>('/api/sales-summary'),
    ])
      .then(([recSummary, overstock, sales]) => {
        if (recSummary) {
          setSummaryData({
            top_products: (recSummary.top_products ?? []) as { product: string; sales: number; rank: number }[],
            top_categories: (recSummary.top_categories ?? []) as { category: string; sales: number; rank: number }[],
          });
        }
        setOverstockList(Array.isArray(overstock) ? overstock : []);
        if (sales && typeof sales === 'object') setSalesSummary(sales);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // [3.4.2] 지역별 카테고리 매출 피봇 로드
  useEffect(() => {
    apiGet<RegionCategoryPivotData>('/api/region-category-pivot')
      .then((data) => {
        if (data && (data.pivot_rows?.length > 0 || data.countries?.length > 0)) {
          setRegionCategoryPivot(data);
          setPivotSelectedCountry((prev) => {
            if (prev && data.countries?.includes(prev)) return prev;
            const preferred = data.countries?.find((c) => c === 'South Korea') ?? data.countries?.[0];
            return preferred ?? '';
          });
        }
      })
      .catch(() => {});
  }, []);

  // [3.4.3] 가격-수요 상관관계 로드 (제품 변경 시 재요청)
  useEffect(() => {
    const product = correlationProduct || undefined;
    apiGet<PriceDemandCorrelationData>(`/api/price-demand-correlation${product ? `?product_name=${encodeURIComponent(product)}` : ''}`)
      .then((data) => {
        if (data) {
          setPriceDemandCorrelation(data);
          if (!correlationProduct && data.available_products?.length > 0) {
            const preferred = data.available_products.find((p) => p.includes('iPhone 15 Pro')) ?? data.available_products[0];
            setCorrelationProduct(preferred ?? '');
          }
        }
      })
      .catch(() => setPriceDemandCorrelation(null));
  }, [correlationProduct]);

  // [3.4.4] 실시간 재고·예측 신뢰도 경고 (품절 위기 항목)
  useEffect(() => {
    apiGet<InventoryCriticalAlertsData>('/api/inventory-critical-alerts?limit=50')
      .then((data) => data && (data.critical_count >= 0 || data.critical_items) && setCriticalAlerts(data))
      .catch(() => setCriticalAlerts(null));
  }, []);

  // [4.4.1] 고객 여정 퍼널 분석
  useEffect(() => {
    apiGet<CustomerJourneyFunnelData>('/api/customer-journey-funnel')
      .then((data) => data && setCustomerJourneyFunnel(data))
      .catch(() => setCustomerJourneyFunnel(null));
  }, []);

  // [4.4.2] 퍼널 단계별 가중치 (전체 목록)
  useEffect(() => {
    apiGet<FunnelStageWeightData>('/api/funnel-stage-weight')
      .then((data) => data && setFunnelStageWeights(data))
      .catch(() => setFunnelStageWeights(null));
  }, []);

  // 선택된 퍼널 단계에 따른 가중치·전략 (선택 변경 시 재조회)
  const funnelStageDetail = useMemo(() => {
    if (!funnelStageWeights?.stages?.length) return null;
    return funnelStageWeights.stages.find((s) => s.stage === selectedFunnelStage) ?? funnelStageWeights.stages[0];
  }, [funnelStageWeights, selectedFunnelStage]);

  // 선택된 store_id의 추천 데이터 + 매출 예측 + 수요 대시보드 로드
  useEffect(() => {
    if (!selectedStoreId) return;
    setStoreLoading(true);
    const params = new URLSearchParams({ store_id: selectedStoreId, year: '2024' });
    Promise.all([
      apiGet<StoreRecommendationsData>(`/api/store-recommendations/${selectedStoreId}`),
      apiGet<SalesForecastData>(`/api/store-sales-forecast/${selectedStoreId}`),
      apiGet<DemandDashboardData>(`/api/demand-dashboard?${params.toString()}`),
      apiGet<UserPersonalizedRecommendationData>(`/api/user-personalized-recommendations?store_id=${encodeURIComponent(selectedStoreId)}`),
      apiGet<CollabFilterRecommendationData>(`/api/collab-filter-recommendations?store_id=${encodeURIComponent(selectedStoreId)}`),
    ])
      .then(([rec, forecast, demand, userRec, collabRec]) => {
        if (rec && (rec.store_summary?.total_sales > 0 || rec.association?.length > 0 || rec.similar_store?.length > 0 || rec.latent_demand?.length > 0 || rec.trend?.length > 0)) {
          setRecommendations(rec);
        } else {
          console.warn('[Recommendation] store-recommendations returned empty data:', rec);
          setRecommendations(null);
        }
        setSalesForecast(forecast && (forecast.actual?.length > 0 || forecast.predicted?.length > 0) ? forecast : null);
        setDemandDashboard(demand && typeof demand === 'object' ? demand : null);
        setUserPersonalizedRec(userRec ?? null);
        setCollabFilterRec(collabRec ?? null);
      })
      .catch((err) => {
        console.error('[Recommendation] Failed to load recommendations:', err);
        setRecommendations(null);
        setSalesForecast(null);
        setDemandDashboard(null);
        setUserPersonalizedRec(null);
        setCollabFilterRec(null);
      })
      .finally(() => setStoreLoading(false));
  }, [selectedStoreId]);

  // 매출 시계열 차트용 통합 데이터 (실측 + 예측, 신뢰구간)
  const salesChartData = useMemo(() => {
    if (!salesForecast) return [];
    const map = new Map<string, { date: string; actual?: number; predicted?: number; lower?: number; upper?: number }>();
    salesForecast.actual.forEach((a) => map.set(a.date, { ...map.get(a.date), date: a.date, actual: a.value }));
    salesForecast.predicted.forEach((p) =>
      map.set(p.date, {
        ...map.get(p.date),
        date: p.date,
        predicted: p.value,
        lower: p.lower,
        upper: p.upper,
      })
    );
    return Array.from(map.entries())
      .map(([, v]) => v)
      .sort((a, b) => (a.date < b.date ? -1 : 1));
  }, [salesForecast]);

  // [3.4.2] 선택 국가 카테고리 점유율 (파이 차트용)
  const pivotCountryPieData = useMemo(() => {
    if (!regionCategoryPivot?.pivot_rows?.length || !pivotSelectedCountry) return [];
    const row = regionCategoryPivot.pivot_rows.find((r) => r.country === pivotSelectedCountry);
    if (!row || row.total_sales <= 0) return [];
    return Object.entries(row.by_category)
      .filter(([, v]) => Number(v) > 0)
      .map(([category, sales]) => ({
        name: category,
        value: Math.round((Number(sales) / row.total_sales) * 1000) / 10,
        total_sales: Number(sales),
      }))
      .sort((a, b) => b.value - a.value);
  }, [regionCategoryPivot, pivotSelectedCountry]);

  const PIE_COLORS = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

  return (
    <main className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f]">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="p-2 rounded-lg hover:bg-gray-100 text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
              aria-label="메인으로"
            >
              ←
            </Link>
            <div>
              <h1 className="text-xl font-bold text-[#1d1d1f]">🏪 상점별 맞춤형 성장 전략 대시보드</h1>
              <p className="text-xs text-[#86868b] mt-0.5">상점별 지능형 추천 · 매출 예측 · 4대 추천 전략</p>
              <p className="text-xs text-[#6e6e73] mt-2 px-2 py-1 rounded bg-[#f5f5f7] border border-gray-200">
                <strong>데이터:</strong> SQL(01.data/*.sql) · <strong>예측 모델:</strong> arima_model.joblib · 샘플/시뮬레이션 구간은 <span className="text-amber-700 font-medium">강조 표시</span>
              </p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* 매출 예측 시계열 차트 (최상단) */}
        {salesForecast && salesChartData.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
            <h2 className="text-base font-semibold text-[#1d1d1f] mb-2">📈 향후 30일 매출 예측</h2>
            <p className="text-xs text-[#86868b] mb-4">
              과거 매출(검은색 실선) · 예측 매출(파란색 점선) · 신뢰 구간(흐린 파란색)
            </p>
            <div className="h-[320px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={salesChartData} margin={{ top: 8, right: 12, left: 8, bottom: 24 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    stroke="#6e6e73"
                    tickFormatter={(v) => (v && String(v).slice(0, 7)) || v}
                  />
                  <YAxis tick={{ fontSize: 10 }} stroke="#6e6e73" tickFormatter={(v) => (Number(v) / 1000).toFixed(0) + 'k'} />
                  <Tooltip
                    formatter={(value: number) => [value != null ? value.toLocaleString() : '', '']}
                    labelFormatter={(label) => label}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {/* 신뢰 구간: 흐린 파란색 영역 */}
                  <Area
                    type="monotone"
                    dataKey="upper"
                    fill="#3b82f6"
                    fillOpacity={0.2}
                    stroke="none"
                    legendType="none"
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="lower"
                    fill="#fff"
                    fillOpacity={1}
                    stroke="none"
                    legendType="none"
                    isAnimationActive={false}
                  />
                  {/* 실측: 검은색 실선 */}
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="#1d1d1f"
                    strokeWidth={2}
                    dot={{ r: 2 }}
                    connectNulls
                    name="실측 매출 (Actual Sales)"
                    isAnimationActive={false}
                  />
                  {/* 예측: 파란색 점선 */}
                  <Line
                    type="monotone"
                    dataKey="predicted"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    strokeDasharray="6 4"
                    dot={{ r: 2 }}
                    connectNulls
                    name="예측 매출 (Predicted Sales)"
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* 사이드바 역할: 분석할 상점 선택 */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6 flex flex-wrap items-center gap-4">
          <div className="flex-1 min-w-0">
            <label className="block text-sm font-medium text-[#1d1d1f] mb-2">분석할 상점을 선택하세요</label>
            <select
              value={selectedStoreId}
              onChange={(e) => setSelectedStoreId(e.target.value)}
              className="w-full max-w-md text-sm border border-gray-200 rounded-lg px-4 py-2 bg-white text-[#1d1d1f] focus:outline-none focus:ring-2 focus:ring-[#0071e3]"
              disabled={stores.length === 0}
            >
              {stores.length === 0 ? (
                <option value="">상점 목록 로딩 중...</option>
              ) : (
                stores.map((s) => (
                  <option key={s.store_id} value={s.store_id}>
                    {s.store_name || s.store_id} ({s.store_id})
                  </option>
                ))
              )}
            </select>
          </div>
          {recommendations && (
            <p className="text-sm text-[#6e6e73] bg-[#f5f5f7] px-4 py-2 rounded-lg">
              현재 선택된 상점: <strong className="text-[#1d1d1f]">{recommendations.store_summary?.store_name ?? selectedStoreId}</strong> ({selectedStoreId})
            </p>
          )}
        </div>

        {/* [4.1.1] 유저(상점) 맞춤형 추천 결과 — user_id, recommendations(rank, product_id, reason) */}
        {selectedStoreId && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
            <h2 className="text-base font-semibold text-[#1d1d1f] mb-2">[4.1.1] 유저(상점) 맞춤형 추천 결과</h2>
            <p className="text-sm text-[#6e6e73] mb-4">
              재고 건전성(Health_Index) + 해당 상점 판매 이력(카테고리) 반영 · 상위 3개 추천 (rank, product_id, reason)
            </p>
            {storeLoading ? (
              <p className="text-sm text-[#6e6e73] py-4">추천 계산 중...</p>
            ) : userPersonalizedRec ? (
              <div className="space-y-4">
                {userPersonalizedRec.user_id != null && (
                  <p className="text-sm text-[#6e6e73]">
                    User ID: <span className="text-[#1d1d1f] font-medium">{userPersonalizedRec.user_id}</span>
                    {userPersonalizedRec.user_identifier && (
                      <span className="ml-2 text-[#86868b]">(상점: {userPersonalizedRec.user_identifier})</span>
                    )}
                  </p>
                )}
                {userPersonalizedRec.user_history_categories?.length ? (
                  <p className="text-sm text-[#6e6e73]">
                    이 상점 판매 이력 카테고리: <span className="text-[#1d1d1f] font-medium">{userPersonalizedRec.user_history_categories.join(', ')}</span>
                  </p>
                ) : null}
                {userPersonalizedRec.recommendations?.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left border-b border-gray-200 text-[#6e6e73]">
                          <th className="py-2 pr-4">순위</th>
                          <th className="py-2 pr-4">product_id</th>
                          <th className="py-2">reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userPersonalizedRec.recommendations.map((row, i) => (
                          <tr key={i} className="border-b border-gray-100">
                            <td className="py-2 text-[#1d1d1f]">{row.rank}</td>
                            <td className="py-2 text-[#1d1d1f] font-mono">{row.product_id}</td>
                            <td className="py-2 text-[#1d1d1f]">{row.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : userPersonalizedRec.top_3?.length ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left border-b border-gray-200 text-[#6e6e73]">
                          <th className="py-2 pr-4">순위</th>
                          <th className="py-2 pr-4">제품명</th>
                          <th className="py-2 text-right">추천 점수</th>
                        </tr>
                      </thead>
                      <tbody>
                        {userPersonalizedRec.top_3.map((row, i) => (
                          <tr key={i} className="border-b border-gray-100">
                            <td className="py-2 text-[#1d1d1f]">{i + 1}</td>
                            <td className="py-2 text-[#1d1d1f]">{row.product_name}</td>
                            <td className="py-2 text-right font-medium text-[#1d1d1f]">{row.score}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-[#86868b] py-2">추천 결과가 없습니다. (재고·판매 이력 데이터 확인)</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-[#86868b] py-2">상점 선택 후 추천 데이터를 불러옵니다.</p>
            )}
          </div>
        )}

        {/* [4.3] 성과 지표 시뮬레이션: 추천 도입 후 재고 소진 속도 — 인사이트 대시보드 (시뮬레이션 강조) */}
        {selectedStoreId && userPersonalizedRec?.performance_simulation && (
          <div className="bg-white rounded-xl border-2 border-amber-400 shadow-sm p-6 mb-6 relative">
            <span className="absolute top-3 right-3 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">시뮬레이션 데이터</span>
            <h2 className="text-base font-semibold text-[#1d1d1f] mb-2">[4.3] 추천 엔진 기대 성과</h2>
            <p className="text-sm text-[#6e6e73] mb-4">
              성과 지표 시뮬레이션: 추천 도입 후 재고 소진 속도 · 기존 판매량 대비 Lift 가정
            </p>
            {userPersonalizedRec.performance_simulation.data_source_description && (
              <p className="text-xs text-amber-700 mb-3 px-3 py-1.5 rounded bg-amber-50 border border-amber-200">{userPersonalizedRec.performance_simulation.data_source_description}</p>
            )}
            <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 space-y-3">
              <p className="text-sm font-medium text-emerald-900">
                {userPersonalizedRec.performance_simulation.insight}
              </p>
              <div className="flex flex-wrap gap-4 text-sm">
                <span className="text-[#6e6e73]">
                  Lift rate: <strong className="text-[#1d1d1f]">{userPersonalizedRec.performance_simulation.lift_rate}</strong>
                  <span className="text-[#86868b] ml-1">(기존 대비 15% 상승 가정)</span>
                </span>
                <span className="text-[#6e6e73]">
                  예상 매출 증대: <strong className="text-emerald-700">{userPersonalizedRec.performance_simulation.expected_sales_increase_pct}%</strong>
                </span>
              </div>
              {userPersonalizedRec.performance_simulation.projected_scores?.length > 0 && (
                <p className="text-xs text-emerald-800">
                  추천 상위 제품 예상 점수(Score × Lift): {userPersonalizedRec.performance_simulation.projected_scores.map((s, i) => `#${i + 1} ${s}`).join(' · ')}
                </p>
              )}
            </div>
          </div>
        )}

        {/* [4.1.1] 유저(상점) 기반 협업 필터링 및 재고 가중치 결합 */}
        {selectedStoreId && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
            <h2 className="text-base font-semibold text-[#1d1d1f] mb-2">[4.1.1] 유저 기반 협업 필터링 및 재고 가중치 결합</h2>
            <p className="text-sm text-[#6e6e73] mb-4">
              유사 상점(코사인 유사도 상위 5곳) 구매 패턴 평균(base_score) × 재고 가산(Health_Index≥120 과잉 재고 품목 20% 가산) → 최종 추천 상위 3선
            </p>
            {storeLoading ? (
              <p className="text-sm text-[#6e6e73] py-4">추천 계산 중...</p>
            ) : collabFilterRec?.top_recommendations?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left border-b border-gray-200 text-[#6e6e73]">
                      <th className="py-2 pr-4">순위</th>
                      <th className="py-2 pr-4">제품명</th>
                      <th className="py-2 text-right">base_score</th>
                      <th className="py-2 text-right">boost</th>
                      <th className="py-2 text-right">final_score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {collabFilterRec.top_recommendations.map((row, i) => (
                      <tr key={i} className="border-b border-gray-100">
                        <td className="py-2 text-[#1d1d1f]">{i + 1}</td>
                        <td className="py-2 text-[#1d1d1f]">{row.product_name}</td>
                        <td className="py-2 text-right font-mono text-[#1d1d1f]">{row.base_score}</td>
                        <td className="py-2 text-right font-mono text-[#1d1d1f]">{row.boost}</td>
                        <td className="py-2 text-right font-medium text-[#1d1d1f]">{row.final_score}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {collabFilterRec.target_store && (
                  <p className="text-xs text-[#86868b] mt-2">대상 상점: {collabFilterRec.target_store}</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-[#86868b] py-2">추천 결과가 없습니다. (유사 상점·재고 데이터 확인)</p>
            )}
          </div>
        )}

        {/* [4.3.2] 추천 시스템 피드백 루프 시뮬레이션 */}
        {selectedStoreId && feedbackProductList.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
            <h2 className="text-base font-semibold text-[#1d1d1f] mb-2">[4.3.2] 추천 시스템 피드백 루프 시뮬레이션</h2>
            <p className="text-sm text-[#6e6e73] mb-4">
              실제 클릭 데이터 수집 가정 (1: 클릭, 0: 무시). 클릭된 제품은 다음 학습 시 가중치 강화 대상으로 저장됩니다.
            </p>
            <div className="space-y-3">
              {feedbackProductList.map((productName) => (
                <div key={productName} className="flex items-center gap-4 py-2 border-b border-gray-100 last:border-0">
                  <span className="text-sm text-[#1d1d1f] flex-1 truncate">{productName}</span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setFeedbackClicks((prev) => ({ ...prev, [productName]: 1 }))}
                      className={`px-3 py-1.5 rounded-lg text-sm ${feedbackClicks[productName] === 1 ? 'bg-[#0071e3] text-white' : 'bg-gray-100 text-[#6e6e73]'}`}
                    >
                      클릭(1)
                    </button>
                    <button
                      type="button"
                      onClick={() => setFeedbackClicks((prev) => ({ ...prev, [productName]: 0 }))}
                      className={`px-3 py-1.5 rounded-lg text-sm ${feedbackClicks[productName] !== 1 ? 'bg-gray-400 text-white' : 'bg-gray-100 text-[#6e6e73]'}`}
                    >
                      무시(0)
                    </button>
                  </div>
                </div>
              ))}
              <div className="pt-2 flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleFeedbackSubmit}
                  className="px-4 py-2 rounded-lg bg-[#0071e3] text-white text-sm font-medium hover:opacity-90"
                >
                  피드백 제출
                </button>
              </div>
              {feedbackResult && (
                <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4 mt-4 space-y-2 text-sm">
                  <p className="font-medium text-blue-900">--- [4.3.2 피드백 수집 완료] ---</p>
                  <p className="text-[#1d1d1f]">다음 학습 시 가중치 강화 대상: {feedbackResult.clicked_items?.length ? feedbackResult.clicked_items.join(', ') : '(없음)'}</p>
                  <p className="text-[#6e6e73]">산출물: {feedbackResult.log_path || '/logs/feedback_YYYYMMDD.json'} 저장 완료</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* [4.4.1] 고객 여정 단계별 수치 분석 (샘플 퍼널 강조) */}
        {customerJourneyFunnel && (
          <div className={`bg-white rounded-xl shadow-sm p-6 mb-6 relative ${customerJourneyFunnel.data_source === 'sample' ? 'border-2 border-amber-400' : 'border border-gray-200'}`}>
            {customerJourneyFunnel.data_source === 'sample' && (
              <span className="absolute top-3 right-3 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">샘플 데이터</span>
            )}
            <h2 className="text-base font-semibold text-[#1d1d1f] mb-2">[4.4.1] 고객 여정 단계별 수치 분석</h2>
            <p className="text-sm text-[#6e6e73] mb-4">
              퍼널 단계별 유저 수·전환율(이전 단계 대비). 전환율 40% 미만 구간은 집중 개선 필요(병목)로 표시됩니다.
            </p>
            {customerJourneyFunnel.data_source_description && (
              <p className="text-xs text-amber-700 mb-3 px-3 py-1.5 rounded bg-amber-50 border border-amber-200">{customerJourneyFunnel.data_source_description}</p>
            )}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={customerJourneyFunnel.stages} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                    <XAxis dataKey="stage" tick={{ fontSize: 11 }} tickFormatter={(v) => v.replace(/_/g, ' ')} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(val: number) => [val.toLocaleString(), 'User Count']} labelFormatter={(l) => String(l).replace(/_/g, ' ')} />
                    <Bar dataKey="user_count" fill="#0071e3" name="User Count" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-4">
                <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-4">
                  <p className="text-sm font-medium text-violet-900">--- [4.4.1 고객 여정 퍼널 분석 결과] ---</p>
                  <p className="text-[#1d1d1f] mt-2">전체 구매 전환율(Overall CVR): <strong className="text-violet-700">{customerJourneyFunnel.overall_cvr}%</strong></p>
                </div>
                {customerJourneyFunnel.drop_off?.length > 0 ? (
                  <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4">
                    <p className="text-sm font-medium text-amber-900">집중 개선 필요 구간 (전환율 &lt; 40%)</p>
                    <table className="w-full mt-2 text-sm">
                      <thead>
                        <tr className="text-left text-amber-800 border-b border-amber-200">
                          <th className="py-1.5 pr-2">Stage</th>
                          <th className="py-1.5 text-right">Conversion_Rate</th>
                        </tr>
                      </thead>
                      <tbody>
                        {customerJourneyFunnel.drop_off.map((row, i) => (
                          <tr key={i} className="border-b border-amber-100">
                            <td className="py-1.5 text-[#1d1d1f]">{row.stage.replace(/_/g, ' ')}</td>
                            <td className="py-1.5 text-right font-mono">{row.conversion_rate}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-[#6e6e73]">전환율 40% 미만 구간 없음 (병목 없음)</p>
                )}
              </div>
            </div>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left border-b border-gray-200 text-[#6e6e73]">
                    <th className="py-2 pr-4">Stage</th>
                    <th className="py-2 text-right">User_Count</th>
                    <th className="py-2 text-right">Conversion_Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {customerJourneyFunnel.stages.map((row, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-2 text-[#1d1d1f]">{row.stage.replace(/_/g, ' ')}</td>
                      <td className="py-2 text-right font-mono">{row.user_count.toLocaleString()}</td>
                      <td className="py-2 text-right font-mono">{row.conversion_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* [4.4.2] 퍼널 위치에 따른 가중치 동적 할당 (예시 가중치 강조) */}
        {funnelStageWeights && (funnelStageWeights.stages?.length ?? 0) > 0 && (
          <div className={`bg-white rounded-xl shadow-sm p-6 mb-6 relative ${funnelStageWeights.data_source === 'sample' ? 'border-2 border-amber-400' : 'border border-gray-200'}`}>
            {funnelStageWeights.data_source === 'sample' && (
              <span className="absolute top-3 right-3 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">샘플 데이터</span>
            )}
            <h2 className="text-base font-semibold text-[#1d1d1f] mb-2">[4.4.2] 퍼널 위치에 따른 가중치 동적 할당</h2>
            <p className="text-sm text-[#6e6e73] mb-4">
              현재 유저 단계에 따라 추천 가중치(recommendation_weight)와 전략을 동적으로 적용합니다.
            </p>
            {funnelStageWeights.data_source_description && (
              <p className="text-xs text-amber-700 mb-3 px-3 py-1.5 rounded bg-amber-50 border border-amber-200">{funnelStageWeights.data_source_description}</p>
            )}
            <div className="flex flex-wrap items-center gap-4 mb-4">
              <label className="text-sm font-medium text-[#1d1d1f]">현재 유저 단계:</label>
              <select
                value={selectedFunnelStage}
                onChange={(e) => setSelectedFunnelStage(e.target.value)}
                className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-[#1d1d1f] focus:outline-none focus:ring-2 focus:ring-[#0071e3]"
              >
                {funnelStageWeights.stages.map((s) => (
                  <option key={s.stage} value={s.stage}>{s.stage.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>
            {funnelStageDetail && (
              <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-4 space-y-2">
                <p className="text-sm font-medium text-indigo-900">선택 단계: {funnelStageDetail.stage.replace(/_/g, ' ')}</p>
                <p className="text-[#1d1d1f]">추천 가중치: <strong className="text-indigo-700">{funnelStageDetail.recommendation_weight}</strong></p>
                <p className="text-[#1d1d1f]">전략: {funnelStageDetail.strategy}</p>
              </div>
            )}
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left border-b border-gray-200 text-[#6e6e73]">
                    <th className="py-2 pr-4">Stage</th>
                    <th className="py-2 text-right">recommendation_weight</th>
                    <th className="py-2">strategy</th>
                  </tr>
                </thead>
                <tbody>
                  {funnelStageWeights.stages.map((row, i) => (
                    <tr key={i} className={`border-b border-gray-100 ${row.stage === selectedFunnelStage ? 'bg-indigo-50/50' : ''}`}>
                      <td className="py-2 text-[#1d1d1f]">{row.stage.replace(/_/g, ' ')}</td>
                      <td className="py-2 text-right font-mono">{row.recommendation_weight}</td>
                      <td className="py-2 text-[#1d1d1f]">{row.strategy}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {!storeListLoaded ? (
          <div className="text-center py-12">
            <p className="text-[#6e6e73]">상점 목록 로딩 중...</p>
            <p className="text-sm text-[#86868b] mt-2">최대 12초 대기. 백엔드(port 8000)가 실행 중인지 확인해 주세요.</p>
          </div>
        ) : stores.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-[#86868b]">
              {storeListError || '상점 목록을 불러올 수 없습니다.'}
            </p>
            <p className="text-sm text-[#86868b] mt-2">web-development 폴더에서 start.ps1 실행 후 새로고침하거나 아래 버튼으로 다시 시도해 주세요.</p>
            <button
              type="button"
              onClick={() => setStoreListRetry((c) => c + 1)}
              className="mt-4 px-4 py-2 rounded-lg bg-[#0071e3] text-white text-sm font-medium hover:opacity-90"
            >
              다시 불러오기
            </button>
          </div>
        ) : !selectedStoreId ? (
          <p className="text-[#86868b] text-center py-12">
            분석할 상점을 선택해주세요.
          </p>
        ) : storeLoading ? (
          <p className="text-[#6e6e73] text-center py-12">추천 데이터 로딩 중...</p>
        ) : recommendations ? (
          <>
            {/* 안전재고 · 매출 · 수요 대시보드 연동 분석 */}
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
              <h2 className="text-base font-semibold text-[#1d1d1f] mb-4">📊 안전재고 · 매출 · 수요 대시보드 연동 분석</h2>
              <p className="text-sm text-[#6e6e73] mb-4">
                과잉 재고(안전재고), 전체 매출(매출 대시보드), 수요 예측(수요 대시보드)을 반영한 상점별 성장 전략 참고용입니다.
              </p>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* 과잉 재고 물품 (프로모션 추천) */}
                <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4">
                  <h3 className="text-sm font-semibold text-amber-900 mb-1">🟡 과잉 재고 품목 (프로모션 추천)</h3>
                  <p className="text-xs text-amber-800 mb-3">안전재고 대시보드 Overstock 품목 · 잠긴 돈 순</p>
                  {overstockList.length > 0 ? (
                    <div className="overflow-x-auto max-h-48">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-amber-800 text-left border-b border-amber-200">
                            <th className="py-1.5 pr-2">제품명</th>
                            <th className="py-1.5 text-right">잠긴 돈</th>
                            <th className="py-1.5 text-right">재고</th>
                          </tr>
                        </thead>
                        <tbody>
                          {overstockList.slice(0, 8).map((row, i) => (
                            <tr key={i} className="border-b border-amber-100/50">
                              <td className="py-1.5 text-[#1d1d1f] truncate max-w-[180px]">{(row.Store_Name ?? row.Product_Name) || '—'}</td>
                              <td className="py-1.5 text-right text-[#1d1d1f]">₩{Number(row.Frozen_Money).toLocaleString()}</td>
                              <td className="py-1.5 text-right text-[#1d1d1f]">{Number(row.Inventory).toLocaleString()}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {overstockList.length > 8 && (
                        <p className="text-xs text-amber-700 mt-1">외 {overstockList.length - 8}건 · 전체는 안전재고 대시보드에서 확인</p>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-amber-700 py-2">과잉 재고 데이터 없음 (안전재고 대시보드 연동 확인)</p>
                  )}
                  <p className="text-xs text-amber-800 mt-2">→ 프로모션·번들 전략으로 재고 회전율을 높이세요.</p>
                </div>
                {/* 매출 대시보드 요약 */}
                <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4">
                  <h3 className="text-sm font-semibold text-blue-900 mb-1">💰 매출 대시보드 요약</h3>
                  <p className="text-xs text-blue-800 mb-3">전체 매출 · 스토어 수 · 2025 예상</p>
                  {salesSummary ? (
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-[#6e6e73]">전체 매출 합계</span>
                        <span className="font-medium text-[#1d1d1f]">₩{Number(salesSummary.total_sum ?? 0).toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-[#6e6e73]">스토어 수</span>
                        <span className="font-medium text-[#1d1d1f]">{salesSummary.store_count ?? 0}개</span>
                      </div>
                      {(salesSummary.predicted_sales_2025 ?? 0) > 0 && (
                        <div className="flex justify-between">
                          <span className="text-[#6e6e73]">2025 예상 매출</span>
                          <span className="font-medium text-[#1d1d1f]">₩{Number(salesSummary.predicted_sales_2025).toLocaleString()}</span>
                        </div>
                      )}
                      {(recommendations.store_summary?.total_sales ?? 0) > 0 && salesSummary?.total_sum && salesSummary.total_sum > 0 && (
                        <div className="flex justify-between pt-1 border-t border-blue-200">
                          <span className="text-[#6e6e73]">이 상점 매출 비중</span>
                          <span className="font-medium text-[#1d1d1f]">
                            {(((recommendations.store_summary?.total_sales ?? 0) / salesSummary.total_sum) * 100).toFixed(1)}%
                          </span>
                        </div>
                      )}
                  </div>
                  ) : (
                    <p className="text-xs text-blue-700 py-2">매출 요약 데이터 없음 (매출 대시보드 연동 확인)</p>
                  )}
                  <p className="text-xs text-blue-800 mt-2">→ 매출 대시보드와 연계해 상점별 성장 전략을 수립하세요.</p>
                </div>
                {/* 수요 대시보드 (선택 상점 기준) */}
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4">
                  <h3 className="text-sm font-semibold text-emerald-900 mb-1">📈 수요 대시보드</h3>
                  <p className="text-xs text-emerald-800 mb-3">선택 상점·지역 기준 2025 수요 예측 (prediction model 연동)</p>
                  {demandDashboard && (demandDashboard.total_demand != null || (demandDashboard.category_demand_2025?.length ?? 0) > 0 || (demandDashboard.product_demand_2025?.length ?? 0) > 0) ? (
                    <div className="space-y-2 text-sm">
                      {demandDashboard.total_demand != null && demandDashboard.total_demand > 0 && (
                        <div className="flex justify-between">
                          <span className="text-[#6e6e73]">총 수요(선택 기준)</span>
                          <span className="font-medium text-[#1d1d1f]">{Number(demandDashboard.total_demand).toLocaleString()}대</span>
                        </div>
                      )}
                      {(demandDashboard.category_demand_2025?.length ?? 0) > 0 && (
                        <div className="pt-1 border-t border-emerald-200">
                          <p className="text-xs text-emerald-800 mb-1">카테고리별 2025 예측 (상위 5)</p>
                          <ul className="space-y-0.5 text-xs">
                            {demandDashboard.category_demand_2025!.slice(0, 5).map((c, i) => (
                              <li key={i} className="flex justify-between">
                                <span className="text-[#1d1d1f] truncate max-w-[100px]">{c.category || '-'}</span>
                                <span className="font-medium text-[#1d1d1f]">{Number(c.predicted_quantity ?? 0).toLocaleString()}대</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {(demandDashboard.product_demand_2025?.length ?? 0) > 0 && (
                        <div className="pt-1 border-t border-emerald-200">
                          <p className="text-xs text-emerald-800 mb-1">제품별 2025 예측 (상위 5)</p>
                          <ul className="space-y-0.5 text-xs">
                            {demandDashboard.product_demand_2025!.slice(0, 5).map((p, i) => (
                              <li key={i} className="flex justify-between gap-2">
                                <span className="text-[#1d1d1f] truncate">{p.product_name || p.product_id || '-'}</span>
                                <span className="font-medium text-[#1d1d1f] shrink-0">{Number(p.predicted_quantity ?? 0).toLocaleString()}대</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                  </div>
                  ) : (
                    <p className="text-xs text-emerald-700 py-2">수요 데이터 없음 (수요 대시보드·store_id 연동 확인)</p>
                  )}
                  <p className="text-xs text-emerald-800 mt-2">→ 수요 예측을 반영해 발주·재고 계획을 세우세요.</p>
                </div>
              </div>
            </div>

            {/* [3.4.2] 지역별 카테고리 매출 피봇 분석 */}
            <div className="rounded-xl border border-violet-200 bg-violet-50/50 p-4 mb-6">
              <h3 className="text-sm font-semibold text-violet-900 mb-1">🌍 [3.4.2] 지역별 카테고리 매출 피봇</h3>
              <p className="text-xs text-violet-800 mb-3">국가별 × 제품군 매출 · 선택 국가 카테고리 비중(파이)</p>
              {regionCategoryPivot && regionCategoryPivot.pivot_rows.length > 0 ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs text-violet-700">국가:</span>
                    <select
                      className="text-sm border border-violet-300 rounded-lg px-3 py-1.5 bg-white text-[#1d1d1f]"
                      value={pivotSelectedCountry}
                      onChange={(e) => setPivotSelectedCountry(e.target.value)}
                    >
                      {(regionCategoryPivot.countries ?? []).map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <p className="text-xs font-medium text-violet-800 mb-2">{pivotSelectedCountry} 시장 카테고리 비중</p>
                      {pivotCountryPieData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={220}>
                          <PieChart>
                            <Pie
                              data={pivotCountryPieData}
                              dataKey="value"
                              nameKey="name"
                              cx="50%"
                              cy="50%"
                              outerRadius={80}
                              label={({ name, value }) => `${name} ${value}%`}
                            >
                              {pivotCountryPieData.map((_, i) => (
                                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip formatter={(value: number) => `${value}%`} />
                          </PieChart>
                        </ResponsiveContainer>
                      ) : (
                        <p className="text-xs text-violet-600 py-4">해당 국가 매출 데이터 없음</p>
                      )}
                    </div>
                    <div className="overflow-x-auto">
                      <p className="text-xs font-medium text-violet-800 mb-2">국가별 매출 요약 (피봇)</p>
                      <table className="w-full text-xs border border-violet-200 rounded-lg overflow-hidden bg-white">
                        <thead>
                          <tr className="bg-violet-100 text-violet-900 text-left">
                            <th className="py-2 px-2 border-b border-violet-200">국가</th>
                            <th className="py-2 px-2 border-b border-violet-200 text-right">총 매출</th>
                            {(regionCategoryPivot.categories ?? []).slice(0, 5).map((cat) => (
                              <th key={cat} className="py-2 px-2 border-b border-violet-200 text-right truncate max-w-[80px]" title={cat}>{cat}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {(regionCategoryPivot.pivot_rows ?? []).slice(0, 10).map((row, i) => (
                            <tr key={i} className={row.country === pivotSelectedCountry ? 'bg-violet-50' : ''}>
                              <td className="py-1.5 px-2 border-b border-violet-100 font-medium">{row.country}</td>
                              <td className="py-1.5 px-2 border-b border-violet-100 text-right">₩{Number(row.total_sales).toLocaleString()}</td>
                              {(regionCategoryPivot.categories ?? []).slice(0, 5).map((cat) => (
                                <td key={cat} className="py-1.5 px-2 border-b border-violet-100 text-right">{Number(row.by_category?.[cat] ?? 0).toLocaleString()}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {(regionCategoryPivot.pivot_rows?.length ?? 0) > 10 && (
                        <p className="text-xs text-violet-600 mt-1">상위 10개 국가만 표시</p>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-xs text-violet-600 py-2">지역별 카테고리 피봇 데이터 없음 (API 연동 확인)</p>
              )}
            </div>

            {/* [3.4.3] 가격-수요 상관관계 및 인사이트 */}
            <div className="rounded-xl border border-sky-200 bg-sky-50/50 p-4 mb-6">
              <h3 className="text-sm font-semibold text-sky-900 mb-1">📊 [3.4.3] 가격-수요 상관관계 및 인사이트</h3>
              <p className="text-xs text-sky-800 mb-3">제품별 가격 vs 수량 상관계수 · 스캐터 라인 전략 인사이트</p>
              {priceDemandCorrelation ? (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs text-sky-700">제품:</span>
                    <select
                      className="text-sm border border-sky-300 rounded-lg px-3 py-1.5 bg-white text-[#1d1d1f]"
                      value={correlationProduct || priceDemandCorrelation.product_name}
                      onChange={(e) => setCorrelationProduct(e.target.value)}
                    >
                      {(priceDemandCorrelation.available_products ?? []).map((p) => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex flex-wrap gap-4 items-center text-sm">
                    <div className="flex items-baseline gap-2">
                      <span className="text-sky-700">상관계수:</span>
                      <span className="font-semibold text-[#1d1d1f]">
                        {priceDemandCorrelation.correlation != null ? priceDemandCorrelation.correlation.toFixed(2) : '-'}
                      </span>
                    </div>
                    <div className="flex-1 min-w-[200px] rounded-lg bg-white/80 border border-sky-200 px-3 py-2">
                      <span className="text-xs text-sky-700">전략 인사이트</span>
                      <p className="font-medium text-[#1d1d1f] text-sm mt-0.5">{priceDemandCorrelation.insight}</p>
                    </div>
                  </div>
                  {priceDemandCorrelation.scatter_data?.length > 0 ? (
                    <div className="bg-white rounded-lg border border-sky-200 p-3">
                      <p className="text-xs text-sky-800 mb-2">가격 × 수량 스캐터 (선택 제품)</p>
                      <ResponsiveContainer width="100%" height={260}>
                        <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: 8 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                          <XAxis type="number" dataKey="price" name="가격" unit="" tick={{ fontSize: 11 }} />
                          <YAxis type="number" dataKey="quantity" name="수량" tick={{ fontSize: 11 }} />
                          <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(val: number) => [val, '']} />
                          <Scatter name="가격-수량" data={priceDemandCorrelation.scatter_data} fill="#0ea5e9" fillOpacity={0.7} />
                        </ScatterChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="text-xs text-sky-600 py-2">스캐터 데이터 없음 (해당 제품 가격·수량 데이터 필요)</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-sky-600 py-2">가격-수요 상관 데이터 없음 (API 연동 확인)</p>
              )}
            </div>

            {/* [3.4.4] 실시간 재고 및 예측 신뢰도 경고 */}
            <div className="rounded-xl border border-rose-200 bg-rose-50/50 p-4 mb-6">
              <h3 className="text-sm font-semibold text-rose-900 mb-1">⚠️ [3.4.4] 실시간 재고·예측 신뢰도 경고</h3>
              <p className="text-xs text-rose-800 mb-3">안전 재고 대비 현재 재고 비율(Health_Index) 70% 미만 시 Critical 등급</p>
              {criticalAlerts ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-rose-800">품절 위기 항목:</span>
                    <span className="font-bold text-rose-900">{criticalAlerts.critical_count}건 발견</span>
                  </div>
                  {criticalAlerts.critical_items?.length > 0 ? (
                    <div className="overflow-x-auto max-h-64">
                      <table className="w-full text-sm border border-rose-200 rounded-lg overflow-hidden bg-white">
                        <thead>
                          <tr className="bg-rose-100 text-rose-900 text-left">
                            {criticalAlerts.critical_items[0]?.Store_Name !== undefined && (
                              <th className="py-2 px-2 border-b border-rose-200">매장명</th>
                            )}
                            <th className="py-2 px-2 border-b border-rose-200">제품명</th>
                            <th className="py-2 px-2 border-b border-rose-200 text-right">Health_Index(%)</th>
                            <th className="py-2 px-2 border-b border-rose-200 text-right">현재재고</th>
                            <th className="py-2 px-2 border-b border-rose-200 text-right">안전재고</th>
                          </tr>
                        </thead>
                        <tbody>
                          {criticalAlerts.critical_items.slice(0, 20).map((row, i) => (
                            <tr key={i} className="border-b border-rose-100">
                              {row.Store_Name !== undefined && (
                                <td className="py-1.5 px-2 text-[#1d1d1f] truncate max-w-[120px]">{row.Store_Name || '-'}</td>
                              )}
                              <td className="py-1.5 px-2 font-medium text-[#1d1d1f] truncate max-w-[180px]">{(row.Store_Name ?? row.Product_Name) || '—'}</td>
                              <td className="py-1.5 px-2 text-right text-rose-700 font-medium">{row.Health_Index}%</td>
                              <td className="py-1.5 px-2 text-right text-[#1d1d1f]">{Number(row.Inventory).toLocaleString()}</td>
                              <td className="py-1.5 px-2 text-right text-[#1d1d1f]">{Number(row.Safety_Stock).toLocaleString()}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {criticalAlerts.critical_items.length > 20 && (
                        <p className="text-xs text-rose-600 mt-1">상위 20건만 표시 (전체 {criticalAlerts.critical_count}건)</p>
                      )}
                    </div>
                  ) : (
                    <p className="text-xs text-rose-600 py-2">현재 Critical 항목 없음</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-rose-600 py-2">경고 데이터 없음 (API 연동 확인)</p>
              )}
            </div>

            {/* 상점 요약 정보 */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
                <p className="text-xs text-[#86868b] mb-1">상점명</p>
                <p className="text-lg font-semibold text-[#1d1d1f]">{recommendations.store_summary?.store_name ?? selectedStoreId}</p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
                <p className="text-xs text-[#86868b] mb-1">총 매출</p>
                <p className="text-lg font-semibold text-[#1d1d1f]">₩{(recommendations.store_summary?.total_sales ?? 0).toLocaleString()}</p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
                <p className="text-xs text-[#86868b] mb-1">취급 품목 수</p>
                <p className="text-lg font-semibold text-[#1d1d1f]">{recommendations.store_summary?.product_count ?? 0}개</p>
              </div>
            </div>

            {/* 4대 추천 전략 (2x2 그리드) */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* 1. 유사 상점 추천 (CF) */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="px-6 py-4 bg-green-50 border-b border-gray-200">
                  <h3 className="text-sm font-semibold text-[#1d1d1f]">🤝 유사 상점 추천</h3>
                  <p className="text-xs text-[#86868b] mt-1">우리 매장과 비슷한 규모의 다른 매장 효자 상품</p>
                </div>
                <div className="overflow-x-auto max-h-96">
                  {(recommendations.similar_store ?? []).length > 0 ? (
                    <>
                      {(recommendations.similar_store ?? [])[0]?.is_fallback && (
                        <p className="px-4 py-2 text-xs text-amber-700 bg-amber-50 border-b border-amber-100">추천 결과 없음 → 전체 인기 상위 5개 품목</p>
                      )}
                    <table className="w-full text-sm">
                      <thead className="bg-[#f5f5f7] sticky top-0">
                        <tr className="text-[#6e6e73] text-left">
                          <th className="px-4 py-2">제품명</th>
                          <th className="px-4 py-2 text-right">유사도</th>
                          <th className="px-4 py-2 text-right">판매량</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(recommendations.similar_store ?? []).map((item, i) => (
                          <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                            <td className="px-4 py-2 text-[#1d1d1f]">{item.product_name}</td>
                            <td className="px-4 py-2 text-right text-[#1d1d1f]">{item.similarity_score?.toFixed(3)}</td>
                            <td className="px-4 py-2 text-right text-[#1d1d1f]">{item.sales_in_similar_store?.toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </>
                  ) : (
                    <p className="px-6 py-8 text-xs text-[#86868b] text-center">추천 결과 없음</p>
                  )}
                </div>
              </div>

              {/* 2. 연관 분석 (Basket) */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="px-6 py-4 bg-blue-50 border-b border-gray-200">
                  <h3 className="text-sm font-semibold text-[#1d1d1f]">🔗 연관 분석 (Basket)</h3>
                  <p className="text-xs text-[#86868b] mt-1">이 제품을 구매한 고객은 이 제품도 함께 샀어요</p>
                </div>
                <div className="overflow-x-auto max-h-96">
                  {(recommendations.association ?? []).length > 0 ? (
                    <>
                      {(recommendations.association ?? [])[0]?.is_fallback && (
                        <p className="px-4 py-2 text-xs text-amber-700 bg-amber-50 border-b border-amber-100">추천 결과 없음 → 전체 인기 상위 5개 품목</p>
                      )}
                    <table className="w-full text-sm">
                      <thead className="bg-[#f5f5f7] sticky top-0">
                        <tr className="text-[#6e6e73] text-left">
                          <th className="px-4 py-2">제품명</th>
                          <th className="px-4 py-2 text-right">Lift</th>
                          <th className="px-4 py-2 text-right">신뢰도</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(recommendations.association ?? []).map((item, i) => (
                          <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                            <td className="px-4 py-2 text-[#1d1d1f]">{item.product_name}</td>
                            <td className="px-4 py-2 text-right text-[#1d1d1f]">{item.lift?.toFixed(2)}</td>
                            <td className="px-4 py-2 text-right text-[#1d1d1f]">{(item.confidence! * 100).toFixed(1)}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </>
                  ) : (
                    <p className="px-6 py-8 text-xs text-[#86868b] text-center">인기 품목 연관 추천 (Lift 기반)</p>
                  )}
                </div>
              </div>

              {/* 3. 잠재 수요 분석 (SVD) */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="px-6 py-4 bg-purple-50 border-b border-gray-200">
                  <h3 className="text-sm font-semibold text-[#1d1d1f]">💎 잠재 수요 분석 (SVD)</h3>
                  <p className="text-xs text-[#86868b] mt-1">아직 판매량은 적지만 우리 매장 성향에 딱 맞는 제품</p>
                </div>
                <div className="overflow-x-auto max-h-96">
                  {(recommendations.latent_demand ?? []).length > 0 ? (
                    <>
                      {(recommendations.latent_demand ?? [])[0]?.is_fallback && (
                        <p className="px-4 py-2 text-xs text-amber-700 bg-amber-50 border-b border-amber-100">추천 결과 없음 → 전체 인기 상위 5개 품목</p>
                      )}
                    <table className="w-full text-sm">
                      <thead className="bg-[#f5f5f7] sticky top-0">
                        <tr className="text-[#6e6e73] text-left">
                          <th className="px-4 py-2">제품명</th>
                          <th className="px-4 py-2 text-right">예상 판매량</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(recommendations.latent_demand ?? []).map((item, i) => (
                          <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                            <td className="px-4 py-2 text-[#1d1d1f]">{item.product_name}</td>
                            <td className="px-4 py-2 text-right text-[#1d1d1f] font-medium">{item.predicted_sales?.toFixed(1)}대</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </>
                  ) : (
                    <p className="px-6 py-8 text-xs text-[#86868b] text-center">추천 결과 없음</p>
                  )}
                </div>
              </div>

              {/* 4. 지역 트렌드 */}
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="px-6 py-4 bg-amber-50 border-b border-gray-200">
                  <h3 className="text-sm font-semibold text-[#1d1d1f]">🔥 지역 트렌드</h3>
                  <p className="text-xs text-[#86868b] mt-1">요즘 이 지역에서 급상승 중인 신제품</p>
                </div>
                <div className="overflow-x-auto max-h-96">
                  {(recommendations.trend ?? []).length > 0 ? (
                    <>
                      {(recommendations.trend ?? [])[0]?.is_fallback && (
                        <p className="px-4 py-2 text-xs text-amber-700 bg-amber-50 border-b border-amber-100">추천 결과 없음 → 전체 인기 상위 5개 품목</p>
                      )}
                    <table className="w-full text-sm">
                      <thead className="bg-[#f5f5f7] sticky top-0">
                        <tr className="text-[#6e6e73] text-left">
                          <th className="px-4 py-2">제품명</th>
                          <th className="px-4 py-2 text-right">증가율</th>
                          <th className="px-4 py-2 text-right">최근 판매</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(recommendations.trend ?? []).map((item, i) => (
                          <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                            <td className="px-4 py-2 text-[#1d1d1f]">{item.product_name}</td>
                            <td className="px-4 py-2 text-right text-[#1d1d1f] font-medium">
                              {item.growth_rate && item.growth_rate > 100 ? '신규' : `${item.growth_rate?.toFixed(1)}%`}
                            </td>
                            <td className="px-4 py-2 text-right text-[#1d1d1f]">{item.recent_sales?.toLocaleString()}대</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    </>
                  ) : (
                    <p className="px-6 py-8 text-xs text-[#86868b] text-center">추천 결과 없음</p>
                  )}
                </div>
              </div>
            </div>

            {/* 하단 가이드 */}
            <div className="mt-8 p-4 rounded-xl bg-[#f0f9ff] border border-[#bae6fd] text-sm text-[#0c4a6e]">
              <p className="font-medium mb-1">💡 팁</p>
              <p>
                유사 상점 추천 리스트의 제품을 다음 발주 시 고려해 보세요. 예측 매출 상승기에 맞춰 재고를 확보하는 것이 좋습니다.
              </p>
            </div>
          </>
        ) : (
          <p className="text-[#86868b] text-center py-12">추천 데이터를 불러올 수 없습니다. (Real-time execution and performance dashboard 연동 확인)</p>
        )}
      </div>
    </main>
  );
}
