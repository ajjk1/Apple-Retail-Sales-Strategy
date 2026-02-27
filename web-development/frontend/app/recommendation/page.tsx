'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { apiGet, apiPost } from '../../lib/api';
import { getContinentForCountry, formatCountryDisplay, stripApplePrefix, formatStoreDisplay } from '../../lib/country';
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

/** 성과 시뮬레이터 (Performance Simulator) — 투자자용 실효성 증명 */
interface PerformanceSimulatorData {
  scenario?: {
    before?: { periods?: string[]; sales?: number[]; inventory_level?: number[] };
    after?: { periods?: string[]; sales?: number[]; inventory_level?: number[] };
    chart_data?: { period: string; sales_before: number; sales_after: number; inventory_before: number; inventory_after: number }[];
  };
  roi?: {
    opportunity_cost_saved_annual?: number;
    opportunity_cost_before?: number;
    opportunity_cost_after?: number;
    old_days?: number;
    new_days?: number;
    avg_inventory_value?: number;
    cost_of_capital_pct?: number;
  };
  summary?: {
    total_sales_lift_pct?: number;
    return_rate_reduction_pct?: number;
    inventory_turnover_acceleration?: number;
    inventory_turnover_acceleration_pct?: number;
  };
  /** 전략 실행 후 기대 수익 시뮬레이션 (1.15배 상승 곡선) */
  performance_lift?: {
    periods?: string[];
    baseline?: number[];
    growth_15pct?: number[];
    chart_data?: { period: string; 기존_곡선: number; 성장_곡선_15: number }[];
    lift_rate?: number;
    investor_message?: string;
  };
  investor_message?: string;
}

/** 재고 Status API값 → 한글(영문) 표시 (실시간 재고·자금 동결 테이블용) */
function inventoryStatusToDisplay(apiStatus: string): string {
  const s = (apiStatus ?? '').trim();
  if (s === 'Danger' || s === '위험') return '위험 품목 (Danger)';
  if (s === 'Overstock' || s === '과잉') return '과잉 재고 (Overstock)';
  if (s === 'Normal' || s === '정상') return '정상 재고 (Normal)';
  return s || '-';
}

/** 실시간 재고 및 자금 동결 현황 (투자자용) — Frozen Money + Status → investor_alert */
interface InventoryFrozenMoneyData {
  items: (OverstockItem & { investor_alert?: boolean })[];
  investor_value_message?: string;
}

/** 상점별 성장 전략 엔진 — Dynamic Weighting(상점별 맞춤형 모드) + 이익·브랜드·운영 */
interface GrowthStrategyData {
  store_id: string;
  store_type: string;
  /** 엔진의 상태 (Internal State): 매장 성격에 따른 엔진 성격 */
  internal_state?: string;
  /** if 가중치 설정 (Weights): CEO, INV, OPS */
  weights?: { CEO?: number; INV?: number; OPS?: number };
  recommendations: { product_id?: string; product_name?: string; score?: number; reason?: string; seller_script?: string }[];
  reasoning_log?: {
    product_id?: string;
    product_name?: string;
    reason?: string;
    if_then_path?: string[];
    scores?: { ceo?: number; investor?: number; operation?: number; total?: number };
    store_type?: string;
    fallback?: boolean;
  }[];
  seller_scripts?: string[];
  filter_rejected_log?: { product?: string; reason?: string }[];
  fallback_used?: boolean;
  fallback_reason?: string | null;
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
  growth_strategy?: GrowthStrategyData;
}

interface Store {
  store_id: string;
  store_name: string;
  country?: string;
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
  const [storeType, setStoreType] = useState<'STANDARD' | 'PREMIUM' | 'OUTLET'>('STANDARD');
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedContinent, setSelectedContinent] = useState<string>('');
  const [selectedCountry, setSelectedCountry] = useState<string>('');
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
  const [performanceSimulator, setPerformanceSimulator] = useState<PerformanceSimulatorData | null>(null);
  /** 실시간 재고·자금 동결: 안전재고 대시보드와 동일 데이터(safety-stock-inventory-list) */
  const [inventoryListAll, setInventoryListAll] = useState<OverstockItem[]>([]);
  const [selectedFunnelStage, setSelectedFunnelStage] = useState<string>('Add_to_Cart');
  /** 4대 엔진 중 클릭한 엔진 — 해당 엔진 추천 결과를 대시보드에 표시 */
  const [selectedEngineKey, setSelectedEngineKey] = useState<'association' | 'similar_store' | 'latent_demand' | 'trend' | null>(null);
  /** 추천 결과 테이블에서 선택한 제품명 — 주차별 매출·재고 수준·Performance Lift 차트와 연동 표시 */
  const [selectedRecommendationProduct, setSelectedRecommendationProduct] = useState<string | null>(null);
  /** 실시간 재고·자금 동결 테이블: 투자자 경고 필터 (전체 / 경고만 / 경고 제외) */
  const [investorWarningFilter, setInvestorWarningFilter] = useState<'all' | 'alert' | 'no_alert'>('all');

  // 추천 대시보드 → 투자자/판매자 대시보드 딥링크용 공통 쿼리 문자열 생성
  const buildDeepLinkQuery = (includeProduct: boolean) => {
    const params = new URLSearchParams();
    if (selectedStoreId) params.set('store_id', selectedStoreId);
    if (includeProduct && selectedRecommendationProduct) params.set('product', selectedRecommendationProduct);
    const qs = params.toString();
    return qs ? `?${qs}` : '';
  };

  // [4.3.2] 추천 상품 목록: userPersonalizedRec.top_3 또는 collabFilterRec.top_recommendations
  const feedbackProductList = useMemo(() => {
    const fromTop3 = userPersonalizedRec?.top_3?.map((r) => r.product_name) ?? [];
    const fromCollab = collabFilterRec?.top_recommendations?.map((r) => r.product_name) ?? [];
    const names = fromTop3.length ? fromTop3 : fromCollab;
    return names.filter(Boolean);
  }, [userPersonalizedRec?.top_3, collabFilterRec?.top_recommendations]);

  // 스토어 목록에 대륙·국가 정보 매핑
  const storesWithRegion = useMemo(
    () =>
      stores.map((s) => {
        const countryEn = s.country || '';
        const continentKo = countryEn ? getContinentForCountry(countryEn) : '기타';
        return { ...s, country: countryEn, continent: continentKo };
      }),
    [stores]
  );

  const continentOptions = useMemo(
    () =>
      Array.from(
        new Set(
          storesWithRegion
            .map((s) => s.continent as string | undefined)
            .filter((v): v is string => !!v && v !== '기타')
        )
      ),
    [storesWithRegion]
  );

  const countryOptions = useMemo(() => {
    let candidate = storesWithRegion;
    if (selectedContinent) {
      candidate = candidate.filter((s) => s.continent === selectedContinent);
    }
    return Array.from(
      new Set(
        candidate
          .map((s) => s.country as string | undefined)
          .filter((v): v is string => !!v)
      )
    );
  }, [storesWithRegion, selectedContinent]);

  const filteredStores = useMemo(() => {
    let list = storesWithRegion;
    if (selectedContinent) {
      list = list.filter((s) => s.continent === selectedContinent);
    }
    if (selectedCountry) {
      list = list.filter((s) => s.country === selectedCountry);
    }
    return list;
  }, [storesWithRegion, selectedContinent, selectedCountry]);

  // 필터 변경 시 현재 선택된 상점이 목록에 없으면 첫 상점으로 자동 보정
  useEffect(() => {
    if (!filteredStores.length) return;
    if (!filteredStores.find((s) => s.store_id === selectedStoreId)) {
      setSelectedStoreId(filteredStores[0].store_id);
    }
  }, [filteredStores, selectedStoreId]);

  /** 엔진 선택에 따른 성과 시뮬레이터 지표 (총 매출/반품/재고/ROI) */
  const enginePerformance = useMemo(() => {
    if (!performanceSimulator) {
      return {
        totalSalesLiftPct: 0,
        returnRateReductionPct: 0,
        inventoryTurnoverAccelPct: 0,
        opportunityCostSavedAnnual: 0,
      };
    }

    const baseTotal = performanceSimulator.summary?.total_sales_lift_pct ?? 0;
    const baseReturn = performanceSimulator.summary?.return_rate_reduction_pct ?? 0;
    const baseTurnover = performanceSimulator.summary?.inventory_turnover_acceleration_pct ?? 0;
    const baseRoi = performanceSimulator.roi?.opportunity_cost_saved_annual ?? 0;

    type EngineKey = 'association' | 'similar_store' | 'latent_demand' | 'trend';
    const key: EngineKey | 'baseline' = (selectedEngineKey as EngineKey | null) ?? 'baseline';

    const WEIGHTS: Record<'baseline' | EngineKey, { sales: number; returns: number; turnover: number; roi: number }> = {
      baseline: { sales: 1, returns: 1, turnover: 1, roi: 1 },
      association: { sales: 1.1, returns: 1.05, turnover: 1.1, roi: 1.0 },
      similar_store: { sales: 1.3, returns: 1.0, turnover: 1.1, roi: 1.2 },
      latent_demand: { sales: 1.8, returns: 1.2, turnover: 1.5, roi: 1.5 },
      trend: { sales: 1.5, returns: 1.0, turnover: 1.8, roi: 1.3 },
    };

    const w = WEIGHTS[key] ?? WEIGHTS.baseline;
    const totalSalesLiftPct = Math.round(baseTotal * w.sales);
    const returnRateReductionPct = Math.round(baseReturn * w.returns);
    const inventoryTurnoverAccelPct = Math.round(baseTurnover * w.turnover);
    const opportunityCostSavedAnnual = Math.round(baseRoi * w.roi);

    return {
      totalSalesLiftPct,
      returnRateReductionPct,
      inventoryTurnoverAccelPct,
      opportunityCostSavedAnnual,
    };
  }, [performanceSimulator, selectedEngineKey]);

  /** 엔진 선택에 따른 주차별 매출 (엔진 적용 전 vs 후) 시나리오 */
  const engineScenarioChartData = useMemo(() => {
    if (!performanceSimulator?.scenario?.chart_data || !performanceSimulator.scenario.chart_data.length) {
      return performanceSimulator?.scenario?.chart_data ?? [];
    }

    const baseData = performanceSimulator.scenario.chart_data;
    const baseLift = performanceSimulator.summary?.total_sales_lift_pct ?? 0;
    const targetLift = enginePerformance.totalSalesLiftPct;

    if (!baseLift || !targetLift || baseLift === targetLift) {
      return baseData;
    }

    const factor = (100 + targetLift) / (100 + baseLift);

    return baseData.map((row) => ({
      ...row,
      sales_after: Math.round(((row as { sales_after?: number }).sales_after ?? 0) * factor),
    }));
  }, [performanceSimulator, enginePerformance.totalSalesLiftPct]);

  /** 엔진 선택에 따른 Performance Lift 곡선 (기존 vs 성장) */
  const enginePerformanceLiftChartData = useMemo(() => {
    const base = performanceSimulator?.performance_lift;
    if (!base?.chart_data || !base.chart_data.length) return base?.chart_data ?? [];

    const baseLiftRate = base.lift_rate ?? 1.15;
    const targetLiftRate = 1 + (enginePerformance.totalSalesLiftPct || 0) / 100;
    if (!baseLiftRate || baseLiftRate === targetLiftRate) return base.chart_data;

    const factor = targetLiftRate / baseLiftRate;

    return base.chart_data.map((row) => ({
      ...row,
      성장_곡선_15: Math.round((row.성장_곡선_15 ?? 0) * factor),
    }));
  }, [performanceSimulator, enginePerformance.totalSalesLiftPct]);

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
          // 첫 상점을 기준으로 기본 대륙·국가 선택
          const first = json.stores[0];
          if (first?.country) {
            setSelectedCountry(first.country);
            setSelectedContinent(getContinentForCountry(first.country));
          } else {
            setSelectedCountry('');
            setSelectedContinent('');
          }
          setSelectedStoreId(first.store_id);
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

  // 실시간 재고 및 자금 동결 현황: 안전재고 대시보드와 동일 API(safety-stock-inventory-list) + 매출 대시보드(sales-summary) 데이터로 작성
  useEffect(() => {
    apiGet<OverstockItem[]>('/api/safety-stock-inventory-list')
      .then((data) => setInventoryListAll(Array.isArray(data) ? data : []))
      .catch(() => setInventoryListAll([]));
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

  // 성과 시뮬레이터 (투자자용 실효성 증명)
  useEffect(() => {
    apiGet<PerformanceSimulatorData>('/api/performance-simulator')
      .then((data) => data && setPerformanceSimulator(data))
      .catch(() => setPerformanceSimulator(null));
  }, []);

  // 선택된 퍼널 단계에 따른 가중치·전략 (선택 변경 시 재조회)
  const funnelStageDetail = useMemo(() => {
    if (!funnelStageWeights?.stages?.length) return null;
    return funnelStageWeights.stages.find((s) => s.stage === selectedFunnelStage) ?? funnelStageWeights.stages[0];
  }, [funnelStageWeights, selectedFunnelStage]);

  // 선택된 store_id의 추천 데이터 + 매출 예측 + 수요 대시보드 로드 (store_type: 성장 전략 엔진용)
  useEffect(() => {
    if (!selectedStoreId) return;
    setStoreLoading(true);
    const params = new URLSearchParams({ store_id: selectedStoreId, year: '2024' });
    const recUrl = `/api/store-recommendations/${selectedStoreId}?store_type=${encodeURIComponent(storeType)}`;
    Promise.all([
      apiGet<StoreRecommendationsData>(recUrl),
      apiGet<SalesForecastData>(`/api/store-sales-forecast/${selectedStoreId}`),
      apiGet<DemandDashboardData>(`/api/demand-dashboard?${params.toString()}`),
      apiGet<UserPersonalizedRecommendationData>(`/api/user-personalized-recommendations?store_id=${encodeURIComponent(selectedStoreId)}`),
      apiGet<CollabFilterRecommendationData>(`/api/collab-filter-recommendations?store_id=${encodeURIComponent(selectedStoreId)}`),
    ])
      .then(([rec, forecast, demand, userRec, collabRec]) => {
        const hasFour = rec && (rec.association?.length > 0 || rec.similar_store?.length > 0 || rec.latent_demand?.length > 0 || rec.trend?.length > 0);
        const hasGrowth = rec?.growth_strategy?.recommendations?.length;
        if (rec && (rec.store_summary?.total_sales > 0 || hasFour || hasGrowth)) {
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
  }, [selectedStoreId, storeType]);

  // 매출 시계열 차트용 통합 데이터 (실측 + 예측, 신뢰구간) — 결측치 제거 후 스캐터·라인용
  const salesChartData = useMemo(() => {
    if (!salesForecast) return [];
    const map = new Map<string, { date: string; actual?: number; predicted?: number; lower?: number; upper?: number }>();
    salesForecast.actual.forEach((a) => {
      const v = a?.value;
      if (v != null && !Number.isNaN(Number(v))) map.set(a.date, { ...map.get(a.date), date: a.date, actual: Number(v) });
    });
    salesForecast.predicted.forEach((p) => {
      const v = p?.value;
      if (v != null && !Number.isNaN(Number(v))) {
        map.set(p.date, {
          ...map.get(p.date),
          date: p.date,
          predicted: Number(v),
          lower: p.lower != null ? Number(p.lower) : undefined,
          upper: p.upper != null ? Number(p.upper) : undefined,
        });
      }
    });
    return Array.from(map.entries())
      .map(([, v]) => v)
      .filter((row) => row.actual != null || row.predicted != null)
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

  // 실시간 재고 카드: 매장명 → 국가 (한글(영문) 표시용)
  const storeNameToCountry = useMemo(() => {
    const m = new Map<string, string>();
    stores.forEach((s) => {
      const name = stripApplePrefix(s.store_name ?? s.store_id);
      if (name) m.set(name, s.country ?? '');
      if (s.store_name) m.set(s.store_name.trim(), s.country ?? '');
    });
    return m;
  }, [stores]);

  // 상점명 → store_id (실시간 재고 테이블에서 상점 클릭 시 4-Engine 연동용)
  const storeNameToStoreId = useMemo(() => {
    const m = new Map<string, string>();
    stores.forEach((s) => {
      const id = s.store_id ?? '';
      if (id && s.store_name) {
        m.set(s.store_name.trim(), id);
        const stripped = stripApplePrefix(s.store_name);
        if (stripped) m.set(stripped, id);
      }
    });
    return m;
  }, [stores]);

  // 실시간 재고·자금 동결 테이블: 투자자 경고 필터 적용 목록
  const inventoryFrozenTableItems = useMemo(() => {
    if (!inventoryListAll.length) return [];
    const frozenVals = inventoryListAll.map((r) => Number(r.Frozen_Money) || 0).filter((v) => v >= 0);
    const sorted = [...frozenVals].sort((a, b) => a - b);
    const threshold = sorted.length
      ? sorted[Math.min(Math.floor(sorted.length * 0.75), sorted.length - 1)] ?? 0
      : 0;
    return inventoryListAll.map((row) => {
      const fm = Number(row.Frozen_Money) || 0;
      const st = String(row.Status ?? '').trim();
      const investor_alert = fm >= threshold && (st === '정상' || st === 'Normal');
      return { ...row, investor_alert };
    });
  }, [inventoryListAll]);

  // 투자자 경고 필터 적용된 테이블 목록
  const filteredInventoryFrozenTableItems = useMemo(() => {
    if (investorWarningFilter === 'all') return inventoryFrozenTableItems;
    return inventoryFrozenTableItems.filter((row) => {
      const alert = (row as { investor_alert?: boolean }).investor_alert;
      return investorWarningFilter === 'alert' ? alert : !alert;
    });
  }, [inventoryFrozenTableItems, investorWarningFilter]);

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
        {/* 1. 실시간 재고 및 자금 동결 현황 — 매출 대시보드·안전재고 대시보드 데이터로 작성 */}
        {(inventoryFrozenTableItems.length > 0 || salesSummary) && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-8">
            <h2 className="text-lg font-bold text-[#1d1d1f] mb-2">💰 실시간 재고 및 자금 동결 현황 (Inventory vs Frozen Money)</h2>
            <p className="text-sm text-[#6e6e73] mb-2">
              어떤 제품에 얼마의 돈이 묶여 있는지 실시간으로 추적하여 즉시 현금화 전략을 짭니다.
            </p>
            {/* 매출 대시보드 요약 (sales-summary API) */}
            {salesSummary && (
              <div className="mb-4 p-3 rounded-lg bg-[#f5f5f7] border border-gray-200 text-sm text-[#1d1d1f]">
                <span className="font-semibold">매출 대시보드 요약:</span>{' '}
                총 매출 ₩{(Number(salesSummary.total_sum) || 0).toLocaleString()}
                {salesSummary.store_count != null && ` · 상점 수 ${salesSummary.store_count}개`}
                {salesSummary.predicted_sales_2025 != null && ` · 2025 예상 매출 ₩${Number(salesSummary.predicted_sales_2025).toLocaleString()}`}
              </div>
            )}
            {/* 안전재고 대시보드와 동일 데이터 (safety-stock-inventory-list API) */}
            {inventoryFrozenTableItems.length > 0 && (
              <div className="overflow-x-auto max-h-[320px] overflow-y-auto">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <p className="text-xs text-[#86868b]">
                    아래 표: 안전재고 대시보드(safety-stock-inventory-list) 동일 데이터 ·{' '}
                    <span className="text-[#0071e3]">
                      상점명을 클릭하면 해당 상점의 맞춤형 추천 엔진(4-Engine)으로 연동됩니다.
                    </span>
                  </p>
                </div>
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
                    <tr className="text-left text-[#6e6e73]">
                      <th className="py-2 pr-3">국가</th>
                      <th className="py-2 pr-3">상점 명</th>
                      <th className="py-2 pr-3">제품 명</th>
                      <th className="py-2 pr-3 text-right">재고</th>
                      <th className="py-2 pr-3 text-right">안전재고</th>
                      <th className="py-2 pr-3 text-right">자금동결 ($)</th>
                      <th className="py-2 pr-3">Status</th>
                      <th className="py-2 align-top">
                        <div className="flex items-center gap-2 justify-start text-xs text-[#6e6e73]">
                          <span>투자자 경고</span>
                          <select
                            value={investorWarningFilter}
                            onChange={(e) => setInvestorWarningFilter(e.target.value as 'all' | 'alert' | 'no_alert')}
                            className="border border-gray-200 rounded px-2 py-1 bg-white text-[#1d1d1f] focus:outline-none focus:ring-1 focus:ring-[#0071e3]"
                          >
                            <option value="all">전체</option>
                            <option value="alert">경고만</option>
                            <option value="no_alert">경고 제외</option>
                          </select>
                        </div>
                        <div className="mt-1 text-[11px] text-[#86868b]">
                          ({filteredInventoryFrozenTableItems.length}건)
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredInventoryFrozenTableItems.map((row, i) => {
                      const storeName = row.Store_Name ?? '';
                      const stripped = stripApplePrefix(storeName);
                      const countryEn = storeNameToCountry.get(stripped) ?? storeNameToCountry.get(storeName.trim()) ?? '';
                      const countryDisplay = countryEn ? formatCountryDisplay(countryEn) : '-';
                      const investor_alert = (row as { investor_alert?: boolean }).investor_alert;
                      return (
                        <tr
                          key={i}
                          className={`border-b border-gray-100 ${investor_alert ? 'bg-red-50 border-l-4 border-l-red-500' : ''}`}
                        >
                          <td className="py-2 text-[#1d1d1f]">{countryDisplay}</td>
                          <td className="py-2 text-[#1d1d1f]">
                            {storeName ? (
                              <button
                                type="button"
                                onClick={() => {
                                  const storeId = storeNameToStoreId.get(storeName.trim()) ?? storeNameToStoreId.get(stripped);
                                  if (storeId) {
                                    setSelectedStoreId(storeId);
                                    document.getElementById('recommendation-engine-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                  }
                                }}
                                className="text-left font-medium text-[#0071e3] hover:underline cursor-pointer"
                              >
                                {formatStoreDisplay(stripped)}
                              </button>
                            ) : (
                              '-'
                            )}
                          </td>
                          <td className="py-2 text-[#1d1d1f]">{row.Product_Name ?? '-'}</td>
                          <td className="py-2 text-right text-[#1d1d1f]">{Number(row.Inventory).toLocaleString()}</td>
                          <td className="py-2 text-right text-[#1d1d1f]">{Number(row.Safety_Stock).toLocaleString()}</td>
                          <td className="py-2 text-right font-medium text-[#1d1d1f]">${Number(row.Frozen_Money).toLocaleString('en-US')}</td>
                          <td className="py-2 text-[#1d1d1f]">{inventoryStatusToDisplay(row.Status ?? '')}</td>
                          <td className="py-2">
                            {investor_alert ? (
                              <span className="px-2 py-0.5 rounded text-xs font-semibold bg-red-200 text-red-900">투자자 모드 가동 필요</span>
                            ) : (
                              <span className="text-[#86868b]">-</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* 2. 상점별 맞춤형 추천 엔진 가동 현황 (4-Engine Strategy) — 클릭 시 해당 엔진 추천 결과 표시 (실시간 재고 테이블 상점명 클릭 시 연동) */}
        {recommendations && (recommendations.association?.length > 0 || recommendations.similar_store?.length > 0 || recommendations.latent_demand?.length > 0 || recommendations.trend?.length > 0) && (
          <div id="recommendation-engine-section" className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-8">
            <h2 className="text-lg font-bold text-[#1d1d1f] mb-2">⚙️ 상점별 맞춤형 추천 엔진 가동 현황 (4-Engine Strategy)</h2>
            <p className="text-sm text-[#6e6e73] mb-4">
              상점의 특성에 따라 가장 효율적인 무기를 골라 사용합니다. CTO 설계 4대 엔진이 이 상점에서 어떻게 작동하는지 확인하세요. <strong>엔진 카드를 클릭하면 해당 추천 결과가 아래에 표시되고, 📊 성과 시뮬레이터 카드로 자동 이동합니다.</strong>
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {(() => {
                const a = recommendations.association ?? [];
                const s = recommendations.similar_store ?? [];
                const l = recommendations.latent_demand ?? [];
                const t = recommendations.trend ?? [];
                const scoreA = a.length ? a.reduce((sum, r) => sum + (r.lift ?? 0), 0) / a.length : 0;
                const scoreS = s.length ? s.reduce((sum, r) => sum + (r.similarity_score ?? 0), 0) / s.length : 0;
                const scoreL = l.length ? l.reduce((sum, r) => sum + (r.predicted_sales ?? 0), 0) / l.length : 0;
                const scoreT = t.length ? t.reduce((sum, r) => sum + (r.growth_rate ?? 0), 0) / t.length : 0;
                const arr = [
                  { key: 'association' as const, label: 'Association Engine', score: scoreA, count: a.length, msg: 'A 상품을 산 고객은 B도 삽니다 (연관 판매 강조)' },
                  { key: 'similar_store' as const, label: 'Similar Store', score: scoreS, count: s.length, msg: '유사 매장에서 잘 팔리는 상품을 이 매장에도' },
                  { key: 'latent_demand' as const, label: 'Latent Demand', score: scoreL, count: l.length, msg: '아직 안 샀지만 곧 살 고객 타겟팅' },
                  { key: 'trend' as const, label: 'Trend', score: scoreT, count: t.length, msg: '성장률 기반 트렌드 반영' },
                ];
                const maxScore = Math.max(scoreA, scoreS, scoreL, scoreT);
                return arr.map((e) => {
                  const isSelected = selectedEngineKey === e.key;
                  const isLeading = maxScore > 0 && e.score === maxScore;
                  return (
                    <button
                      key={e.key}
                      type="button"
                      onClick={() => {
                        setSelectedEngineKey(e.key);
                        document.getElementById('performance-simulator-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                      }}
                      className={`rounded-xl border-2 p-4 text-left w-full cursor-pointer transition-colors hover:border-[#0071e3] hover:bg-blue-50/50 ${
                        isSelected ? 'border-[#0071e3] bg-blue-50 ring-2 ring-[#0071e3]/30' : isLeading ? 'border-[#0071e3] bg-blue-50' : 'border-gray-200 bg-gray-50'
                      }`}
                    >
                      <p className="text-xs font-semibold text-[#6e6e73] mb-1">{e.label}</p>
                      <p className="text-sm font-medium text-[#1d1d1f] mb-2">
                        점수 요약: {e.score.toFixed(2)} · 추천 {e.count}건
                      </p>
                      <p className="text-xs text-[#6e6e73]">{e.msg}</p>
                      {isLeading && (
                        <span className="mt-2 inline-block px-2 py-0.5 rounded text-xs font-semibold bg-[#0071e3] text-white">주도 엔진</span>
                      )}
                      {isSelected && (
                        <span className="mt-2 ml-1 inline-block px-2 py-0.5 rounded text-xs font-semibold bg-emerald-600 text-white">선택됨</span>
                      )}
                    </button>
                  );
                });
              })()}
            </div>
            {/* 선택한 엔진 추천 결과 표시 */}
            {(() => {
              const engineKey = selectedEngineKey ?? (() => {
                const a = recommendations.association ?? [];
                const s = recommendations.similar_store ?? [];
                const l = recommendations.latent_demand ?? [];
                const t = recommendations.trend ?? [];
                const scoreA = a.length ? a.reduce((sum, r) => sum + (r.lift ?? 0), 0) / a.length : 0;
                const scoreS = s.length ? s.reduce((sum, r) => sum + (r.similarity_score ?? 0), 0) / s.length : 0;
                const scoreL = l.length ? l.reduce((sum, r) => sum + (r.predicted_sales ?? 0), 0) / l.length : 0;
                const scoreT = t.length ? t.reduce((sum, r) => sum + (r.growth_rate ?? 0), 0) / t.length : 0;
                const max = Math.max(scoreA, scoreS, scoreL, scoreT);
                if (max === scoreT && t.length) return 'trend' as const;
                if (max === scoreL && l.length) return 'latent_demand' as const;
                if (max === scoreS && s.length) return 'similar_store' as const;
                if (max === scoreA && a.length) return 'association' as const;
                return null;
              })();
              const list = engineKey ? (recommendations[engineKey] ?? []) : [];
              const labels: Record<string, string> = {
                association: 'Association Engine',
                similar_store: 'Similar Store',
                latent_demand: 'Latent Demand',
                trend: 'Trend',
              };
              const scoreKeys: Record<string, keyof StoreRecommendation> = {
                association: 'lift',
                similar_store: 'similarity_score',
                latent_demand: 'predicted_sales',
                trend: 'growth_rate',
              };
              const scoreLabels: Record<string, string> = {
                association: 'Lift',
                similar_store: '유사도 점수',
                latent_demand: '예상 매출',
                trend: '성장률',
              };
              const sk = scoreKeys[engineKey] ?? 'lift';
              if (engineKey == null) return null;
              return (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h3 className="text-base font-semibold text-[#1d1d1f] mb-3">
                    📋 {labels[engineKey]} 추천 결과 {selectedEngineKey ? '' : '(주도 엔진)'}
                  </h3>
                  {list.length === 0 ? (
                    <p className="text-sm text-[#86868b] py-4">이 엔진에 대한 추천 결과가 없습니다.</p>
                  ) : (
                    <div className="overflow-x-auto max-h-[320px] overflow-y-auto">
                      <table className="w-full text-sm">
                        <thead className="sticky top-0 bg-gray-50 border-b border-gray-200">
                          <tr className="text-left text-[#6e6e73]">
                            <th className="py-2 pr-4">순위</th>
                            <th className="py-2 pr-4">제품명</th>
                            <th className="py-2 text-right">{scoreLabels[engineKey]}</th>
                            {(engineKey === 'similar_store' || engineKey === 'trend') && (
                              <th className="py-2 text-right text-[#6e6e73]">비고</th>
                            )}
                          </tr>
                        </thead>
                        <tbody>
                          {list.map((row, i) => (
                            <tr key={i} className="border-b border-gray-100">
                              <td className="py-2 text-[#1d1d1f]">{i + 1}</td>
                              <td className="py-2">
                                <button
                                  type="button"
                                  onClick={() => {
                                    const name = row.product_name ?? null;
                                    setSelectedRecommendationProduct(name);
                                    document.getElementById('performance-simulator-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                                  }}
                                  className="text-[#0071e3] hover:underline font-medium text-left"
                                >
                                  {row.product_name ?? '-'}
                                </button>
                              </td>
                              <td className="py-2 text-right font-medium text-[#1d1d1f]">
                                {sk === 'lift' && row.lift != null && row.lift.toFixed(2)}
                                {sk === 'similarity_score' && row.similarity_score != null && row.similarity_score.toFixed(2)}
                                {sk === 'predicted_sales' && row.predicted_sales != null && Number(row.predicted_sales).toLocaleString()}
                                {sk === 'growth_rate' && row.growth_rate != null && row.growth_rate.toFixed(2)}
                                {row[sk] == null && '-'}
                              </td>
                              {(engineKey === 'similar_store' || engineKey === 'trend') && (
                                <td className="py-2 text-right text-[#86868b] text-xs">
                                  {engineKey === 'similar_store' && row.sales_in_similar_store != null && `유사매장 매출 ${Number(row.sales_in_similar_store).toLocaleString()}`}
                                  {engineKey === 'trend' && row.recent_sales != null && `최근 매출 ${Number(row.recent_sales).toLocaleString()}`}
                                  {((engineKey === 'similar_store' && row.sales_in_similar_store == null) || (engineKey === 'trend' && row.recent_sales == null)) && '-'}
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        )}

        {/* 성과 시뮬레이터 — 투자자용 실효성 증명 (4-Engine 클릭 시 연동·시각화) */}
        {performanceSimulator && (
          <div id="performance-simulator-section" className="bg-gradient-to-br from-slate-50 to-blue-50 rounded-xl border border-slate-200 shadow-sm p-6 mb-8">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
              <div>
                <h2 className="text-lg font-bold text-[#1d1d1f]">📊 성과 시뮬레이터</h2>
                <p className="text-xs text-[#6e6e73] mt-1">엔진 적용 전·후 매출·재고 비교 · 기회비용 절감 · 실효성 지표</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/investor${buildDeepLinkQuery(true)}`}
                  className="inline-flex items-center px-3 py-1.5 rounded-full border border-emerald-300 bg-emerald-50 text-xs font-medium text-emerald-800 hover:bg-emerald-100 transition-colors"
                >
                  투자자 대시보드에서 자세히 보기 →
                </Link>
                <Link
                  href={`/seller${buildDeepLinkQuery(true)}`}
                  className="inline-flex items-center px-3 py-1.5 rounded-full border border-[#0071e3] bg-white text-xs font-medium text-[#0071e3] hover:bg-blue-50 transition-colors"
                >
                  판매자 퀵 대시보드에서 보기 →
                </Link>
              </div>
            </div>
            {selectedEngineKey && (
              <p className="text-sm text-[#0071e3] font-medium mb-4">
                연동된 엔진: {selectedEngineKey === 'association' && 'Association Engine'}
                {selectedEngineKey === 'similar_store' && 'Similar Store'}
                {selectedEngineKey === 'latent_demand' && 'Latent Demand'}
                {selectedEngineKey === 'trend' && 'Trend'}
              </p>
            )}

            {performanceSimulator.investor_message && (
              <div className="mb-6 p-4 rounded-xl bg-[#1d1d1f] text-white text-sm leading-relaxed border-l-4 border-[#0071e3]">
                &quot;{performanceSimulator.investor_message}&quot;
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
              <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <p className="text-xs text-[#86868b] mb-1">총 매출 상승률</p>
                <p className="text-2xl font-bold text-[#0071e3]">
                  +{enginePerformance.totalSalesLiftPct}%
                </p>
                <p className="text-xs text-[#6e6e73] mt-1">엔진 적용 후 시뮬레이션</p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <p className="text-xs text-[#86868b] mb-1">반품 감소율</p>
                <p className="text-2xl font-bold text-emerald-600">
                  {enginePerformance.returnRateReductionPct}%
                </p>
                <p className="text-xs text-[#6e6e73] mt-1">호환/COO 필터 효과</p>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <p className="text-xs text-[#86868b] mb-1">재고 회전 가속도</p>
                <p className="text-2xl font-bold text-amber-600">
                  +{enginePerformance.inventoryTurnoverAccelPct}%
                </p>
                <p className="text-xs text-[#6e6e73] mt-1">90일 → 30일 가정</p>
              </div>
            </div>

            {performanceSimulator.roi && performanceSimulator.roi.opportunity_cost_saved_annual != null && (
              <div className="mb-6 p-4 rounded-xl bg-emerald-50 border border-emerald-200">
                <p className="text-sm font-semibold text-emerald-800">💰 기회비용 절감 (ROI)</p>
                <p className="text-xl font-bold text-emerald-700 mt-1">
                  연간 ${(enginePerformance.opportunityCostSavedAnnual / 1000).toFixed(1)}K 절감
                </p>
                <p className="text-xs text-emerald-700 mt-1">
                  재고령 {performanceSimulator.roi.old_days}일 → {performanceSimulator.roi.new_days}일 가정 · 자본비용 {((performanceSimulator.roi.cost_of_capital_pct ?? 0) * 100).toFixed(0)}%
                </p>
              </div>
            )}

            {performanceSimulator.scenario?.chart_data && performanceSimulator.scenario.chart_data.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <p className="text-sm font-semibold text-[#1d1d1f] mb-3">📈 주차별 매출 (엔진 적용 전 vs 후){selectedRecommendationProduct ? <span className="ml-2 text-[#0071e3] font-normal">· 선택 제품: {selectedRecommendationProduct}</span> : null}</p>
                  <div className="h-[260px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={engineScenarioChartData.length ? engineScenarioChartData : performanceSimulator.scenario.chart_data} margin={{ top: 8, right: 8, left: 8, bottom: 24 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                        <XAxis dataKey="period" tick={{ fontSize: 10 }} stroke="#6e6e73" />
                        <YAxis tick={{ fontSize: 10 }} stroke="#6e6e73" />
                        <Tooltip
                          formatter={(value: number) => {
                            if (value == null || Number.isNaN(Number(value))) return ['', ''];
                            const rounded = Math.round(Number(value));
                            return [rounded.toLocaleString(), ''];
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Bar dataKey="sales_before" name="엔진 적용 전" fill="#94a3b8" radius={[2, 2, 0, 0]} />
                        <Bar dataKey="sales_after" name="엔진 적용 후" fill="#0071e3" radius={[2, 2, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <p className="text-sm font-semibold text-[#1d1d1f] mb-3">📉 재고 수준 (소진 속도 비교){selectedRecommendationProduct ? <span className="ml-2 text-[#0071e3] font-normal">· 선택 제품: {selectedRecommendationProduct}</span> : null}</p>
                  <div className="h-[260px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={engineScenarioChartData.length ? engineScenarioChartData : performanceSimulator.scenario.chart_data} margin={{ top: 8, right: 8, left: 8, bottom: 24 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                        <XAxis dataKey="period" tick={{ fontSize: 10 }} stroke="#6e6e73" />
                        <YAxis tick={{ fontSize: 10 }} stroke="#6e6e73" />
                        <Tooltip
                          formatter={(value: number) => {
                            if (value == null || Number.isNaN(Number(value))) return ['', ''];
                            const rounded = Math.round(Number(value));
                            return [rounded.toLocaleString(), ''];
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Line type="monotone" dataKey="inventory_before" name="엔진 적용 전" stroke="#94a3b8" strokeWidth={2} dot={{ r: 3 }} />
                        <Line type="monotone" dataKey="inventory_after" name="엔진 적용 후" stroke="#0ea5e9" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 3 }} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            )}

            {/* 3. 전략 실행 후 기대 수익 시뮬레이션 (Performance Lift) — 기존 곡선 vs 성장 곡선 (엔진별 상승률 반영) */}
            {performanceSimulator.performance_lift?.chart_data && performanceSimulator.performance_lift.chart_data.length > 0 && (
              <div className="mt-6 bg-white rounded-xl border-2 border-emerald-200 p-4">
                <p className="text-sm font-semibold text-[#1d1d1f] mb-2">📈 전략 실행 후 기대 수익 시뮬레이션 (Performance Lift){selectedRecommendationProduct ? <span className="ml-2 text-[#0071e3] font-normal">· 선택 제품: {selectedRecommendationProduct}</span> : null}</p>
                <p className="text-xs text-[#6e6e73] mb-3">
                  기존 곡선: 현재 데이터 기반 매출 추이 · 성장 곡선: 선택한 엔진 적용 시나리오(매출 {enginePerformance.totalSalesLiftPct}% 상승, 재고 회전 가속)
                </p>
                <div className="h-[260px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={enginePerformanceLiftChartData.length ? enginePerformanceLiftChartData : performanceSimulator.performance_lift.chart_data} margin={{ top: 8, right: 8, left: 8, bottom: 24 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                      <XAxis dataKey="period" tick={{ fontSize: 10 }} stroke="#6e6e73" />
                      <YAxis tick={{ fontSize: 10 }} stroke="#6e6e73" />
                      <Tooltip
                        formatter={(value: number) => {
                          if (value == null || Number.isNaN(Number(value))) return ['', ''];
                          const rounded = Math.round(Number(value));
                          return [rounded.toLocaleString(), ''];
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="기존_곡선" name="기존 곡선" stroke="#64748b" strokeWidth={2} dot={{ r: 3 }} />
                      <Line
                        type="monotone"
                        dataKey="성장_곡선_15"
                        name={`성장 곡선 (${enginePerformance.totalSalesLiftPct}% 상승)`}
                        stroke="#059669"
                        strokeWidth={2}
                        strokeDasharray="4 4"
                        dot={{ r: 3 }}
                      />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                {(() => {
                  // 선택된 제품명과 엔진별 상승률을 바탕으로 인사이트 문구 생성
                  const name = selectedRecommendationProduct;
                  const lift = enginePerformance.totalSalesLiftPct ?? 0;
                  if (!name) {
                    if (!performanceSimulator.performance_lift.investor_message) return null;
                    return (
                      <p className="mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-900 italic">
                        &quot;{performanceSimulator.performance_lift.investor_message}&quot;
                      </p>
                    );
                  }

                  let insight: string;
                  if (lift >= 30) {
                    insight = `${name}는 단순한 추측이 아닙니다. 이미 코드에 박혀 있는 ${lift}% 수준의 성장 곡선이 투자 관점에서 의미 있는 업사이드를 보여줍니다.`;
                  } else if (lift >= 15) {
                    insight = `${name}는 안정적인 성장 구간에 들어와 있습니다. 시뮬레이션 상 약 ${lift}% 매출 상승이 반복적으로 관측되며, 지금의 전략을 유지·강화할 근거가 됩니다.`;
                  } else if (lift > 0) {
                    insight = `${name}는 방어적인 포지션에 가깝지만, 약 ${lift}% 수준의 개선 여지가 있습니다. 재고와 가격 전략을 함께 조정하면 추가 업사이드가 기대됩니다.`;
                  } else {
                    insight = `${name}는 현재 전략 하에서는 뚜렷한 상승 신호가 약합니다. 재고 비중을 조정하거나 다른 핵심 상품과의 번들 전략을 검토할 시점입니다.`;
                  }

                  return (
                    <p className="mt-4 p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-sm text-emerald-900 italic">
                      &quot;{insight}&quot;
                    </p>
                  );
                })()}
              </div>
            )}

            <div className="mt-6">
              <p className="text-sm font-semibold text-[#1d1d1f] mb-3">📋 Visual Summary</p>
              <div className="overflow-x-auto">
                <div className="h-[200px] min-w-[320px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      layout="vertical"
                      data={[
                        { name: '총 매출 상승률', value: enginePerformance.totalSalesLiftPct, fill: '#0071e3' },
                        { name: '반품 감소율', value: enginePerformance.returnRateReductionPct, fill: '#10b981' },
                        { name: '재고 회전 가속도', value: enginePerformance.inventoryTurnoverAccelPct, fill: '#f59e0b' },
                      ]}
                      margin={{ top: 8, right: 24, left: 100, bottom: 8 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                      <XAxis type="number" unit="%" domain={[0, 'auto']} tick={{ fontSize: 10 }} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={90} />
                      <Tooltip formatter={(value: number) => [`${value}%`, '']} />
                      <Bar dataKey="value" name="%" radius={[0, 4, 4, 0]}>
                        {[0, 1, 2].map((i) => (
                          <Cell key={i} fill={['#0071e3', '#10b981', '#f59e0b'][i]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
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
          <></>
        ) : (
          <p className="text-[#86868b] text-center py-12">추천 데이터를 불러올 수 없습니다. (Real-time execution and performance dashboard 연동 확인)</p>
        )}
      </div>
    </main>
  );
}
