'use client';

// 클라이언트 컴포넌트: API 베이스는 process.env.NEXT_PUBLIC_API_URL 만 사용. BACKEND_URL 은 서버(rewrites/API route) 전용.
// WebGPU 미지원 환경에서 Three.js/글로브 오류 방지 (Cannot read properties of undefined reading 'VERTEX')
if (typeof window !== 'undefined') {
  const w = window as unknown as { GPUShaderStage?: { VERTEX: number; FRAGMENT: number; COMPUTE: number }; GPUBufferUsage?: Record<string, number> };
  if (!w.GPUShaderStage) w.GPUShaderStage = { VERTEX: 1, FRAGMENT: 2, COMPUTE: 4 };
  if (!w.GPUBufferUsage) w.GPUBufferUsage = { MAP_READ: 0x0001, MAP_WRITE: 0x0002, COPY_SRC: 0x0004, COPY_DST: 0x0008, INDEX: 0x0010, VERTEX: 0x0020, UNIFORM: 0x0040, STORAGE: 0x0080, QUERY_RESOLVE: 0x0100 };
}

import { useCallback, useEffect, useRef, useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip, ComposedChart, BarChart, Bar, Area, Line, Scatter, XAxis, YAxis, CartesianGrid, LabelList } from 'recharts';
import { getContinentInfo, resolveCountryToEn, stripApplePrefix } from '../lib/country';

const GlobeMap = dynamic(() => import('./components/GlobeMap'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full flex items-center justify-center bg-gray-100 rounded-xl text-gray-500">
      지도 로딩 중...
    </div>
  ),
});

interface RetailData {
  title: string;
  status: string;
  last_updated: string;
  summary: {
    total_sales?: number;
    total_transactions?: number;
    avg_order_value?: number;
  };
  sales_by_category: { category: string; sales: number }[];
  sales_by_country: { country: string; sales: number }[];
  top_products: { product: string; sales: number }[];
  inventory_status: { status: string; count: number }[];
}

interface PieDataItem {
  city: string;
  year: number;
  category: string;
  quantity: number;
}

interface StoreMarker {
  store_id: string;
  store_name?: string;
  store_name_ko?: string;
  city: string;
  country: string;
  lon: number;
  lat: number;
}

interface StoreCategoryPieItem {
  category: string;
  quantity: number;
}

interface ContinentPieItem {
  continent: string;
  continent_ko: string;
  lon: number;
  lat: number;
  data?: { category: string; quantity: number }[];
  data_by_year?: Record<number, { category: string; quantity: number }[]>;
}

/** 연도별 파이 데이터 (스토어/국가 API 응답) */
interface PieDataByYear {
  data_by_year: Record<number, { category: string; quantity: number }[]>;
}

/** product_id별 2020~2024 실적 + 2025 예측 수요 */
interface ProductDemandItem {
  product_id: string;
  product_name: string;
  category?: string;
  launch_year?: number;  // Launch_Date 기준 출시 연도 (그래프 X축 시작점)
  quantity_2020?: number;
  quantity_2021?: number;
  quantity_2022?: number;
  quantity_2023?: number;
  quantity_2024?: number;
  predicted_quantity: number;
}

/** category별 2020~2024 실적 + 2025 예측 수요 */
interface CategoryDemandItem {
  category_id?: string;
  category: string;
  quantity_2020?: number;
  quantity_2021?: number;
  quantity_2022?: number;
  quantity_2023?: number;
  quantity_2024?: number;
  predicted_quantity: number;
}

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316'];
const PIE_YEARS = [2020, 2021, 2022, 2023, 2024] as const;

/** 수량 단위 (가격탄력성 등 데이터 준비용) */
const QUANTITY_UNIT = '대';
const QUANTITY_LABEL = `수량(단위: ${QUANTITY_UNIT})`;

/** 클라이언트 전용: NEXT_PUBLIC_API_URL 사용. 미설정/ localhost 시 vercel.app이면 NEXT_PUBLIC_FALLBACK_BACKEND_URL 또는 HF Space 상수 사용. */
const API_BASE_FALLBACK =
  (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_FALLBACK_BACKEND_URL) ||
  'https://apple-retail-study-apple-retail-sales-strategy.hf.space';

function isUnsafeApiBase(url: string | undefined): boolean {
  if (url == null || typeof url !== 'string') return true;
  const u = url.trim().toLowerCase();
  if (!u.startsWith('http')) return true;
  if (u.includes('localhost') || u.startsWith('http://127.0.0.1') || u.startsWith('http://[::1]')) return true;
  return false;
}

function getApiBase(): string {
  if (typeof window === 'undefined') return '';
  const env = process.env.NEXT_PUBLIC_API_URL;
  const isVercel = typeof window !== 'undefined' && window.location?.hostname?.includes('vercel.app');
  if (env != null && typeof env === 'string' && env.trim() !== '' && !isUnsafeApiBase(env)) return env.trim().replace(/\/$/, '');
  if (isVercel) return API_BASE_FALLBACK;
  return '';
}

const API_TIMEOUT_MS = 20000;

/** API 호출: NEXT_PUBLIC_API_URL 사용. 미설정 시 상대경로만. localhost 미사용. */
async function apiGet<T = unknown>(path: string): Promise<T | null> {
  const fixed = getApiBase();
  const bases = fixed ? [fixed] : [''];
  for (const base of bases) {
    try {
      const url = base ? `${base}${path}` : path;
      const ac = new AbortController();
      const t = setTimeout(() => ac.abort(), API_TIMEOUT_MS);
      const res = await fetch(url, { signal: ac.signal });
      clearTimeout(t);
      if (res?.ok) return (await res.json()) as T;
    } catch {
      continue;
    }
  }
  return null;
}

/** 분기별 수량 차트용 Tooltip - Line+Scatter 중복 방지, 1개만 표시 */
function QuarterlyChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { payload?: { quantity?: number; isPredicted?: boolean } }[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0 || !label) return null;
  const first = payload[0]?.payload;
  const qty = first?.quantity;
  const isPred = first?.isPredicted ?? false;
  const val = typeof qty === 'number' && !Number.isNaN(qty) ? qty : 0;
  return (
    <div
      className="rounded-lg p-2 px-3 shadow-lg border border-gray-200"
      style={{ backgroundColor: 'rgba(255,255,255,0.98)' }}
    >
      <div className="text-sm font-medium text-[#1d1d1f] mb-1">{label}</div>
      <div className="flex justify-between gap-4 text-sm">
        <span className="text-gray-600">{isPred ? '2025년(예측)' : '실적'}</span>
        <span className="text-[#1d1d1f] font-medium">{val.toLocaleString()}{QUANTITY_UNIT}</span>
      </div>
    </div>
  );
}

/** 연도별 수량을 3개월(분기) 단위 데이터로 변환 (연간 수량을 4등분) */
function yearlyToQuarterly(yearly: { year: number; quantity: number; isPredicted: boolean }[]) {
  const out: { period: string; label: string; quantity: number; isPredicted: boolean }[] = [];
  for (const row of yearly) {
    const q = row.quantity / 4;
    for (let qtr = 1; qtr <= 4; qtr++) {
      out.push({
        period: `${row.year}-Q${qtr}`,
        label: `${row.year} Q${qtr}`,
        quantity: Math.round(q),
        isPredicted: row.isPredicted,
      });
    }
  }
  return out;
}

/** 수량 배열을 전체 100% 기준 카테고리별 % 배열로 변환 (범례/툴팁 수량 표시 시에는 사용하지 않음) */
function toPercentData(items: { name: string; value: number }[]): { name: string; value: number }[] {
  const total = items.reduce((a, d) => a + (d.value || 0), 0) || 1;
  return items.map((d) => ({ name: d.name, value: Math.round((d.value / total) * 1000) / 10 }));
}

/** 파이차트 수량 표시용 Tooltip (value = 수량) */
function PieTooltipContentQuantity({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      className="rounded-lg p-2 px-3 shadow-lg border border-gray-200"
      style={{ backgroundColor: 'rgba(255,255,255,0.98)' }}
    >
      {payload.map((entry, i) => (
        <div key={i} className="flex justify-between gap-4 text-sm">
          <span className="text-gray-600">{entry.name}</span>
          <span className="text-[#1d1d1f] font-medium">{(entry.value ?? 0).toLocaleString()}{QUANTITY_UNIT}</span>
        </div>
      ))}
    </div>
  );
}

/** 연도 필터 적용: 전체 = 20~24년 합산 1개 파이차트, 특정 연도 = 해당 연도 1개 파이차트 (수량 표시) */
function PieChartsByYearFilter({
  dataByYear,
  selectedYear,
  mode = 'quantity',
}: {
  dataByYear: Record<number, { category: string; quantity: number }[]>;
  selectedYear: number | null;
  mode?: 'quantity' | 'percent';
}) {
  const getChartData = (items: { category: string; quantity: number }[]) => {
    const map = new Map<string, number>();
    items.forEach((d) => map.set(d.category, (map.get(d.category) ?? 0) + (d.quantity ?? 0)));
    return Array.from(map.entries())
      .map(([name, value]) => ({ name, value }))
      .filter((d) => d.value > 0);
  };

  const toModeData = (raw: { name: string; value: number }[]) => (mode === 'percent' ? toPercentData(raw) : raw);
  const tooltipNode = mode === 'percent' ? <PieTooltipContent /> : <PieTooltipContentQuantity />;
  const legendFormatter =
    mode === 'percent'
      ? (_: unknown, entry: { payload?: { name?: string; value?: number } }) => (
          <span style={{ fontSize: 9, lineHeight: '12px' }}>
            {entry.payload?.name ?? ''} {((entry.payload?.value ?? 0) as number).toFixed(1)}%
          </span>
        )
      : (_: unknown, entry: { payload?: { name?: string; value?: number } }) => (
          <span style={{ fontSize: 9, lineHeight: '12px' }}>
            {entry.payload?.name ?? ''} {(entry.payload?.value ?? 0).toLocaleString()}{QUANTITY_UNIT}
          </span>
        );

  if (selectedYear !== null) {
    const rawQty = getChartData(dataByYear[selectedYear] ?? []);
    if (rawQty.length === 0) {
      return (
        <p className="text-[#6e6e73] text-sm p-4 text-center">{selectedYear}년 데이터 없음</p>
      );
    }
    const raw = toModeData(rawQty);
    return (
      <div className="h-full min-h-[200px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={raw}
              cx="50%"
              cy="50%"
              innerRadius="40%"
              outerRadius="82%"
              paddingAngle={1}
              dataKey="value"
              label={false}
            >
              {raw.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={tooltipNode} contentStyle={{ backgroundColor: 'transparent', border: 'none' }} />
            <Legend
              height={56}
              iconSize={6}
              wrapperStyle={{ overflowY: 'auto', fontSize: 9, lineHeight: '12px' }}
              formatter={legendFormatter}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // 전체 = 20~24년 합산 파이차트 (수량 기준)
  const rawAggQty = getChartData(
    PIE_YEARS.flatMap((y) => dataByYear[y] ?? [])
  );
  if (rawAggQty.length === 0) {
    return <p className="text-[#6e6e73] text-sm p-4 text-center">데이터가 없습니다</p>;
  }
  const rawAgg = toModeData(rawAggQty);
  return (
    <div className="h-full min-h-[200px] flex flex-col">
      <p className="text-xs font-medium text-white mb-1 text-center shrink-0 px-2 py-1 rounded bg-transparent">(20~24년 합산)</p>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rawAgg}
              cx="50%"
              cy="50%"
              innerRadius="40%"
              outerRadius="82%"
              paddingAngle={1}
              dataKey="value"
              label={false}
            >
              {rawAgg.map((_, i) => (
                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
              ))}
            </Pie>
            <Tooltip content={tooltipNode} contentStyle={{ backgroundColor: 'transparent', border: 'none' }} />
            <Legend
              height={56}
              iconSize={6}
              wrapperStyle={{ overflowY: 'auto', fontSize: 9, lineHeight: '12px' }}
              formatter={legendFormatter}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** 파이차트 % 표시용 Tooltip (예: 2025 예상 비율 등에서 필요 시 사용) */
function PieTooltipContent({ active, payload }: { active?: boolean; payload?: { name: string; value: number }[] }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div
      className="rounded-lg p-2 px-3 shadow-lg border border-gray-200"
      style={{ backgroundColor: 'rgba(255,255,255,0.98)' }}
    >
      {payload.map((entry, i) => (
        <div key={i} className="flex justify-between gap-4 text-sm">
          <span className="text-gray-600">{entry.name}</span>
          <span className="text-[#1d1d1f] font-medium">{(entry.value ?? 0).toFixed(1)}%</span>
        </div>
      ))}
    </div>
  );
}

export default function Home() {
  const [data, setData] = useState<RetailData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pieData, setPieData] = useState<PieDataItem[]>([]);
  const [selectedCity, setSelectedCity] = useState<string>('');
  const [selectedYear, setSelectedYear] = useState<number>(2023);
  const [showPieChart, setShowPieChart] = useState(false);
  /** 파이차트 패널 연도 필터: null = 전체(5개), 숫자 = 해당 연도만 */
  const [selectedPieYear, setSelectedPieYear] = useState<number | null>(null);
  const [storeMarkers, setStoreMarkers] = useState<StoreMarker[]>([]);
  const [selectedStoreId, setSelectedStoreId] = useState<string>('');
  const [storeCategoryPieData, setStoreCategoryPieData] = useState<PieDataByYear | null>(null);
  const [selectedCountry, setSelectedCountry] = useState<string>('');
  const [countryCategoryPieData, setCountryCategoryPieData] = useState<PieDataByYear | null>(null);
  const [continentPieData, setContinentPieData] = useState<ContinentPieItem[]>([]);
  const [selectedContinent, setSelectedContinent] = useState<string>('');
  const globeContainerRef = useRef<HTMLDivElement>(null);
  const fetchCleanupRef = useRef<(() => void) | null>(null);
  const [globeSize, setGlobeSize] = useState({ width: 800, height: 400 });
  const [salesBoxValue, setSalesBoxValue] = useState<number | null>(null);
  const [salesBoxLoading, setSalesBoxLoading] = useState(false);
  const [showSafetyStockDashboard, setShowSafetyStockDashboard] = useState(false);
  const [safetyStockData, setSafetyStockData] = useState<{
    statuses: { status: string; count: number }[];
    total_count: number;
  } | null>(null);
  const [safetyStockForecastChartData, setSafetyStockForecastChartData] = useState<{
    product_name: string;
    chart_data: Array<{
      month: string;
      yhat: number;
      yhat_lower: number;
      yhat_upper: number;
      store_stock_quantity?: number;
      insight: { sales_label: string; stock_label: string; message: string };
    }>;
  } | null>(null);
  const [safetyStockLoading, setSafetyStockLoading] = useState(false);
  /** 안전재고 대시보드 내 카테고리별 판매대수 카드 연도 필터 */
  const [safetyStockCategoryYear, setSafetyStockCategoryYear] = useState<number>(2023);
  /** 파이차트 클릭 시 선택된 카테고리 → 재고 상태 카드에 상점별 6개월 판매 그래프 표시 */
  const [safetyStockSelectedCategory, setSafetyStockSelectedCategory] = useState<string | null>(null);
  const [safetyStockStorePeriodData, setSafetyStockStorePeriodData] = useState<{
    category: string;
    periods: string[];
    data: Record<string, unknown>[];
    store_names: string[];
    store_continents?: Record<string, string>;
    store_countries?: Record<string, string>;
    filter_options?: { continents: string[]; countries: string[]; stores: string[] };
  } | null>(null);
  const [safetyStockStorePeriodLoading, setSafetyStockStorePeriodLoading] = useState(false);
  const [safetyStockProductData, setSafetyStockProductData] = useState<{ category: string; period?: string | null; products: { product_id: string; product_name: string; quantity: number }[] } | null>(null);
  const [safetyStockProductLoading, setSafetyStockProductLoading] = useState(false);
  /** 상점별 3개월 차트에서 막대 클릭 시 선택된 분기(상품별 차트에 반영) */
  const [safetyStockSelectedPeriod, setSafetyStockSelectedPeriod] = useState<string | null>(null);
  /** 상품별 판매 수량 차트에서 막대 클릭 시 선택된 상품 → 아래 수요 예측 & 적정 재고 그래프에 표시 */
  const [safetyStockSelectedProduct, setSafetyStockSelectedProduct] = useState<{ product_id: string; product_name: string } | null>(null);
  const [safetyStockForecastChartDataForProduct, setSafetyStockForecastChartDataForProduct] = useState<{ product_name: string; chart_data: Array<{ month: string; yhat: number; yhat_lower: number; yhat_upper: number; store_stock_quantity?: number; insight: { sales_label: string; stock_label: string; message: string } }> } | null>(null);
  const [safetyStockForecastForProductLoading, setSafetyStockForecastForProductLoading] = useState(false);
  const [safetyStockFilterContinent, setSafetyStockFilterContinent] = useState<string>('');
  const [safetyStockFilterCountry, setSafetyStockFilterCountry] = useState<string>('');
  const [safetyStockFilterStore, setSafetyStockFilterStore] = useState<string>('');
  /** Inventory Action Center: Risk KPIs */
  const [safetyStockKpiData, setSafetyStockKpiData] = useState<{
    total_frozen_money?: number;
    danger_count?: number;
    overstock_count?: number;
    predicted_demand?: number;
    expected_revenue?: number;
  } | null>(null);
  /** Inventory Action Center: 재고 목록 (매장별). Store_Name, Inventory, Safety_Stock, Status(위험/과잉/정상), Frozen_Money */
  const [safetyStockInventoryList, setSafetyStockInventoryList] = useState<
    { Store_Name: string; Inventory: number; Safety_Stock: number; Status: string; Frozen_Money: number }[]
  >([]);
  const [safetyStockInventoryListLoading, setSafetyStockInventoryListLoading] = useState(false);
  /** 상태 필터: '' | '위험' | '과잉' (한글) */
  const [inventoryStatusFilter, setInventoryStatusFilter] = useState<string>('');
  /** 관리자 코멘트: 선택된 매장명 */
  const [selectedStoreForNote, setSelectedStoreForNote] = useState<string | null>(null);
  const [managerNoteInput, setManagerNoteInput] = useState('');
  const [inventoryComments, setInventoryComments] = useState<{ store_name: string; product_name?: string; comment: string; author: string; created_at: string }[]>([]);
  const [inventoryCommentsLoading, setInventoryCommentsLoading] = useState(false);
  const [saveCommentLoading, setSaveCommentLoading] = useState(false);
  const [showDemandDashboard, setShowDemandDashboard] = useState(false);
  const [forecastData, setForecastData] = useState<{
    yearly_quantity: { year: number; quantity: number }[];
    total_quantity_2020_2024: number;
    predicted_quantity_2025: number;
    predicted_2025_by_category?: { category: string; quantity: number }[];
    method?: string;
  } | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [productDemandList, setProductDemandList] = useState<ProductDemandItem[] | null>(null);
  const [productDemandLoading, setProductDemandLoading] = useState(false);
  /** 상품명 클릭 시 연도별 판매수량 스캐터 라인 그래프용 선택 상품 */
  const [selectedProductForChart, setSelectedProductForChart] = useState<ProductDemandItem | null>(null);
  /** 카테고리명 클릭 시 연도별 판매수량 스캐터 라인 그래프용 선택 카테고리 */
  const [selectedCategoryForChart, setSelectedCategoryForChart] = useState<CategoryDemandItem | null>(null);
  /** 카테고리 클릭 시 상품별 수량 필터 (해당 카테고리만 표시) */
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string | null>(null);
  /** 수요 대시보드: prediction model.py get_demand_dashboard_data 연동 */
  const [demandDashboardData, setDemandDashboardData] = useState<{
    total_demand: number;
    category_demand: { category: string; quantity: number }[];
    category_demand_2025: CategoryDemandItem[];
    product_demand_2025: ProductDemandItem[];
    yearly_quantity: { year: number; quantity: number }[];
    overall_quantity_by_year: number | null;
  } | null>(null);
  const [dataSourceInfo, setDataSourceInfo] = useState<{ data_dir: string; source: string; sql_file_count: number; csv_path: string | null } | null>(null);
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  const [healthCheckTrigger, setHealthCheckTrigger] = useState(0);
  const [integrationStatus, setIntegrationStatus] = useState<{
    modules_loaded?: { load_sales_data?: boolean; prediction_model?: boolean; sales_analysis?: boolean; inventory_optimization?: boolean; realtime_dashboard?: boolean };
    data_source?: { source?: string; sql_file_count?: number };
  } | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');

  // 파이차트 패널 열릴 때 수요 박스와 같은 연도로 맞춤
  useEffect(() => {
    if (showPieChart && selectedPieYear === null) setSelectedPieYear(selectedYear);
  }, [showPieChart]);

  // 안전재고 대시보드 열릴 때 카테고리 연도 필터를 현재 선택 연도와 맞춤
  useEffect(() => {
    if (showSafetyStockDashboard) setSafetyStockCategoryYear(selectedYear);
  }, [showSafetyStockDashboard, selectedYear]);

  useEffect(() => {
    // NEXT_PUBLIC_API_URL 사용. 미설정 시 상대경로 /api/health 만 시도. localhost 미사용.
    const fixed = getApiBase();
    const bases = fixed ? [fixed] : [''];
    let cancelled = false;
    const timeoutMs = 20000; // HF cold start 등으로 여유 있게
    const tryOne = (base: string): Promise<void> => {
      const url = base ? `${base}/api/health` : '/api/health';
      const ac = new AbortController();
      const t = setTimeout(() => ac.abort(), timeoutMs);
      return fetch(url, { signal: ac.signal, cache: 'no-store' })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(r.statusText))))
        .then(() => { if (!cancelled) setBackendConnected(true); })
        .catch(() => Promise.reject())
        .finally(() => clearTimeout(t));
    };
    const run = (i: number): Promise<void> =>
      i < bases.length ? tryOne(bases[i]).catch(() => run(i + 1)) : Promise.reject();
    run(0).catch(() => { if (!cancelled) setBackendConnected(false); });
    return () => { cancelled = true; };
  }, [healthCheckTrigger]);

  useEffect(() => {
    const el = globeContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (el) {
        const w = el.clientWidth;
        const h = el.clientHeight;
        if (w > 0 && h > 0) setGlobeSize({ width: w, height: h });
      }
    });
    ro.observe(el);
    const w = el.clientWidth;
    const h = el.clientHeight;
    if (w > 0 && h > 0) setGlobeSize({ width: w, height: h });
    return () => ro.disconnect();
  }, []);

  const fetchData = () => {
    if (fetchCleanupRef.current) {
      fetchCleanupRef.current();
      fetchCleanupRef.current = null;
    }
    setLoading(true);
    setError(null);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000); // 데이터 로드 느릴 수 있음
    let cancelled = false;

    const setDataAndClearError = (json: unknown) => {
      if (!cancelled) {
        const r = json as RetailData;
        setData(r);
        if (r?.last_updated) setLastUpdated(r.last_updated);
        setError(null);
      }
    };

    const tryFetch = (url: string) =>
      fetch(url, { signal: controller.signal })
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then(setDataAndClearError);

    const base = getApiBase();
    // NEXT_PUBLIC_API_URL 사용. 설정 시 해당 URL만, 미설정 시 상대경로만. localhost 미사용.
    const url = base ? `${base}/api/apple-data` : '/api/apple-data';
    tryFetch(url)
      .catch((err: Error) => {
        if (!cancelled && err?.name !== 'AbortError') setError('백엔드 연결 실패');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
        clearTimeout(timeout);
      });

    const cleanup = () => {
      cancelled = true;
      clearTimeout(timeout);
      controller.abort();
    };
    fetchCleanupRef.current = cleanup;
    return cleanup;
  };

  useEffect(() => {
    fetchData();
    return () => {
      if (fetchCleanupRef.current) {
        fetchCleanupRef.current();
        fetchCleanupRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    apiGet<{ data?: PieDataItem[] }>('/api/city-category-pie').then((json) => {
      if (json?.data && json.data.length > 0) {
        setPieData(json.data);
        const cities = Array.from(new Set(json.data.map((d) => d.city))).sort();
        setSelectedCity((prev) => (prev === '' && cities.length > 0 ? cities[0] : prev));
      }
    });
  }, []);

  useEffect(() => {
    apiGet<{ data?: StoreMarker[] }>('/api/store-markers').then((json) => {
      if (json?.data && json.data.length > 0) setStoreMarkers(json.data);
    });
  }, []);

  useEffect(() => {
    apiGet<{ data?: ContinentPieItem[] }>('/api/continent-category-pie').then((json) => {
      if (json?.data && json.data.length > 0) setContinentPieData(json.data);
    });
  }, []);


  useEffect(() => {
    if (!selectedStoreId) {
      setStoreCategoryPieData(null);
      return;
    }
    const enc = encodeURIComponent(selectedStoreId);
    apiGet<{ data_by_year?: Record<number, { category: string; quantity: number }[]> }>(`/api/store-category-pie?store_id=${enc}`)
      .then((json) => setStoreCategoryPieData(json?.data_by_year ? { data_by_year: json.data_by_year } : null))
      .catch(() => setStoreCategoryPieData(null));
  }, [selectedStoreId]);

  useEffect(() => {
    if (!selectedCountry) {
      setCountryCategoryPieData(null);
      return;
    }
    const countryEn = resolveCountryToEn(selectedCountry);
    const enc = encodeURIComponent(countryEn);
    apiGet<{ data_by_year?: Record<number, { category: string; quantity: number }[]> }>(`/api/country-category-pie?country=${enc}`)
      .then((json) => setCountryCategoryPieData(json?.data_by_year ? { data_by_year: json.data_by_year } : null))
      .catch(() => setCountryCategoryPieData(null));
  }, [selectedCountry]);

  useEffect(() => {
    if (!showSafetyStockDashboard) return;
    setSafetyStockLoading(true);
    setSafetyStockInventoryListLoading(true);
    setInventoryCommentsLoading(true);
    Promise.all([
      apiGet<{ statuses?: { status: string; count: number }[]; total_count?: number }>('/api/safety-stock').then((json) => {
        if (json) setSafetyStockData({ statuses: json.statuses ?? [], total_count: json.total_count ?? 0 });
        else setSafetyStockData(null);
      }).catch(() => setSafetyStockData(null)),
      apiGet<{ product_name?: string; chart_data?: Array<{ month: string; yhat: number; yhat_lower: number; yhat_upper: number; store_stock_quantity?: number; insight: { sales_label: string; stock_label: string; message: string } }> }>('/api/safety-stock-forecast-chart').then((json) => {
        if (json && Array.isArray(json.chart_data)) setSafetyStockForecastChartData({ product_name: json.product_name ?? '', chart_data: json.chart_data });
        else setSafetyStockForecastChartData(null);
      }).catch(() => setSafetyStockForecastChartData(null)),
      apiGet<{ total_frozen_money?: number; danger_count?: number; overstock_count?: number }>('/api/safety-stock-kpi').then((json) => {
        if (json) setSafetyStockKpiData(json);
        else setSafetyStockKpiData(null);
      }).catch(() => setSafetyStockKpiData(null)),
      apiGet<{ comments?: { store_name?: string; product_name?: string; comment: string; author: string; created_at: string }[] }>('/api/inventory-comments').then((json) => {
        const raw = json && typeof json === 'object' && 'comments' in json ? (json as { comments?: unknown }).comments : null;
        const list = Array.isArray(raw) ? raw : [];
        setInventoryComments(list.map((c: { store_name?: string; product_name?: string; comment?: string; author?: string; created_at?: string }) => ({
          store_name: (c.store_name ?? c.product_name ?? '').trim(),
          product_name: (c.store_name ?? c.product_name ?? '').trim(),
          comment: (c.comment ?? '').trim(),
          author: (c.author ?? '').trim(),
          created_at: (c.created_at ?? '').trim(),
        })));
      }).catch(() => setInventoryComments([])),
    ]).finally(() => { setSafetyStockLoading(false); setInventoryCommentsLoading(false); });
    // 매장별 재고 목록 (한글 상태 필터: 위험, 과잉)
    const filterParam = inventoryStatusFilter ? `?status_filter=${encodeURIComponent(inventoryStatusFilter)}` : '';
    apiGet<unknown[]>(`/api/safety-stock-inventory-list${filterParam}`).then((json) => {
      if (Array.isArray(json)) setSafetyStockInventoryList(json as { Store_Name: string; Inventory: number; Safety_Stock: number; Status: string; Frozen_Money: number }[]);
      else setSafetyStockInventoryList([]);
    }).catch(() => setSafetyStockInventoryList([])).finally(() => setSafetyStockInventoryListLoading(false));
  }, [showSafetyStockDashboard, inventoryStatusFilter]);

  // 매장별 재고 목록/필터 변경 시, 선택 매장이 목록에 없으면 선택 해제 (동기화)
  useEffect(() => {
    if (!selectedStoreForNote) return;
    const names = new Set(safetyStockInventoryList.map((r) => (r.Store_Name ?? '').trim()).filter(Boolean));
    if (!names.has(selectedStoreForNote.trim())) setSelectedStoreForNote(null);
  }, [safetyStockInventoryList, selectedStoreForNote]);

  /** 상품별 차트에서 선택한 상품에 대한 수요 예측 & 적정 재고 차트 데이터 로드 */
  useEffect(() => {
    if (!showSafetyStockDashboard || !safetyStockSelectedProduct) {
      setSafetyStockForecastChartDataForProduct(null);
      return;
    }
    const name = safetyStockSelectedProduct.product_name;
    setSafetyStockForecastForProductLoading(true);
    apiGet<{ product_name?: string; chart_data?: Array<{ month: string; yhat: number; yhat_lower: number; yhat_upper: number; store_stock_quantity?: number; insight: { sales_label: string; stock_label: string; message: string } }> }>(
      `/api/safety-stock-forecast-chart?product_name=${encodeURIComponent(name)}`
    ).then((json) => {
      if (json && Array.isArray(json.chart_data))
        setSafetyStockForecastChartDataForProduct({ product_name: json.product_name ?? name, chart_data: json.chart_data });
      else setSafetyStockForecastChartDataForProduct(null);
    }).catch(() => setSafetyStockForecastChartDataForProduct(null)).finally(() => setSafetyStockForecastForProductLoading(false));
  }, [showSafetyStockDashboard, safetyStockSelectedProduct]);

  useEffect(() => {
    if (!safetyStockSelectedCategory || !showSafetyStockDashboard) {
      setSafetyStockStorePeriodData(null);
      setSafetyStockStorePeriodLoading(false);
      return;
    }
    setSafetyStockStorePeriodLoading(true);
    const enc = encodeURIComponent(safetyStockSelectedCategory);
    const params = new URLSearchParams();
    params.set('category', safetyStockSelectedCategory);
    if (safetyStockFilterContinent) params.set('continent', safetyStockFilterContinent);
    if (safetyStockFilterCountry) params.set('country', safetyStockFilterCountry);
    if (safetyStockFilterStore) params.set('store_name', safetyStockFilterStore);
    apiGet<{ category?: string; periods?: string[]; data?: Record<string, unknown>[]; store_names?: string[]; store_continents?: Record<string, string>; store_countries?: Record<string, string>; filter_options?: { continents: string[]; countries: string[]; stores: string[] } }>(
      `/api/safety-stock-sales-by-store-period?${params.toString()}`
    ).then((json) => {
      const opts = json?.filter_options ?? { continents: [], countries: [], stores: [] };
      const storeContinents = json?.store_continents ?? {};
      const storeCountries = json?.store_countries ?? {};
      if (json && Array.isArray(json.data))
        setSafetyStockStorePeriodData({
          category: json.category ?? safetyStockSelectedCategory,
          periods: json.periods ?? [],
          data: json.data,
          store_names: Array.isArray(json.store_names) ? json.store_names : (json.data[0] ? Object.keys(json.data[0]).filter((k) => k !== 'period') : []),
          store_continents: storeContinents,
          store_countries: storeCountries,
          filter_options: opts,
        });
      else setSafetyStockStorePeriodData((prev) => prev ? { ...prev, data: [], periods: [], store_names: [], store_continents: storeContinents, store_countries: storeCountries, filter_options: opts } : null);
    }).catch(() => setSafetyStockStorePeriodData(null)).finally(() => setSafetyStockStorePeriodLoading(false));

    setSafetyStockProductLoading(true);
    if (safetyStockSelectedPeriod) params.set('period', safetyStockSelectedPeriod);
    apiGet<{ category?: string; period?: string | null; products?: { product_id: string; product_name: string; quantity: number }[] }>(
      `/api/safety-stock-sales-by-product?${params.toString()}`
    ).then((json) => {
      if (json?.products && Array.isArray(json.products))
        setSafetyStockProductData({ category: json.category ?? safetyStockSelectedCategory, period: json.period ?? undefined, products: json.products });
      else setSafetyStockProductData(null);
    }).catch(() => setSafetyStockProductData(null)).finally(() => setSafetyStockProductLoading(false));
  }, [safetyStockSelectedCategory, showSafetyStockDashboard, safetyStockFilterContinent, safetyStockFilterCountry, safetyStockFilterStore, safetyStockSelectedPeriod]);

  useEffect(() => {
    if (safetyStockSelectedCategory) {
      setSafetyStockFilterContinent('');
      setSafetyStockFilterCountry('');
      setSafetyStockFilterStore('');
      setSafetyStockSelectedPeriod(null);
      setSafetyStockSelectedProduct(null);
      setSafetyStockForecastChartDataForProduct(null);
    } else {
      setSafetyStockProductData(null);
      setSafetyStockSelectedPeriod(null);
    }
  }, [safetyStockSelectedCategory]);

  /** 카테고리별 판매대수 연도와 연동: 상점별 3개월 차트는 선택한 연도 분기만 표시 */
  const safetyStockStorePeriodDataByYear = useMemo(() => {
    if (!safetyStockStorePeriodData?.data?.length) return [];
    const year = safetyStockCategoryYear;
    return safetyStockStorePeriodData.data.filter(
      (row) => String((row as { period?: string }).period ?? '').startsWith(`${year} `)
    );
  }, [safetyStockStorePeriodData?.data, safetyStockCategoryYear]);

  /** 분기별 합계(total) 포함 — 바 색상·라벨용 */
  const safetyStockStorePeriodChartData = useMemo(() => {
    if (!safetyStockStorePeriodDataByYear.length || !safetyStockStorePeriodData?.store_names?.length) return [];
    const storeNames = safetyStockStorePeriodData.store_names.slice(0, 12);
    return safetyStockStorePeriodDataByYear.map((row) => {
      const total = storeNames.reduce((sum, name) => sum + (Number((row as Record<string, unknown>)[name]) || 0), 0);
      return { ...row, total } as Record<string, unknown> & { period?: string; total: number };
    });
  }, [safetyStockStorePeriodDataByYear, safetyStockStorePeriodData?.store_names]);

  useEffect(() => {
    if (!showDemandDashboard) return;
    setForecastLoading(true);
    apiGet<{
      yearly_quantity?: { year: number; quantity: number }[];
      total_quantity_2020_2024?: number;
      predicted_quantity_2025?: number;
      predicted_2025_by_category?: { category: string; quantity: number }[];
      method?: string;
    }>('/api/sales-quantity-forecast')
      .then((json) => {
        if (json) {
          setForecastData({
            yearly_quantity: json.yearly_quantity ?? [],
            total_quantity_2020_2024: json.total_quantity_2020_2024 ?? 0,
            predicted_quantity_2025: json.predicted_quantity_2025 ?? 0,
            predicted_2025_by_category: json.predicted_2025_by_category ?? [],
            method: json.method ?? "linear_trend",
          });
        } else setForecastData(null);
      })
      .catch(() => setForecastData(null))
      .finally(() => setForecastLoading(false));

    setProductDemandLoading(true);
    apiGet<{ data?: ProductDemandItem[] }>('/api/predicted-demand-by-product')
      .then((json) => setProductDemandList(json?.data ?? null))
      .catch(() => setProductDemandList(null))
      .finally(() => setProductDemandLoading(false));
  }, [showDemandDashboard]);

  // 매출 박스: Sales analysis.py 연동 — 박스가 보일 때 /api/sales-box 호출
  useEffect(() => {
    if (!(selectedContinent || selectedCountry || selectedStoreId)) {
      setSalesBoxValue(null);
      return;
    }
    setSalesBoxLoading(true);
    apiGet<{ value?: number }>('/api/sales-box')
      .then((json) => setSalesBoxValue(typeof json?.value === 'number' ? json.value : null))
      .catch(() => setSalesBoxValue(null))
      .finally(() => setSalesBoxLoading(false));
  }, [selectedContinent, selectedCountry, selectedStoreId]);

  // 수요 대시보드: prediction model.py get_demand_dashboard_data 연동 (선택 지역·연도 변경 시)
  useEffect(() => {
    const params = new URLSearchParams();
    if (selectedContinent) params.set('continent', selectedContinent);
    if (selectedCountry) params.set('country', selectedCountry);
    if (selectedStoreId) params.set('store_id', selectedStoreId);
    if (selectedCity) params.set('city', selectedCity);
    params.set('year', String(selectedYear));
    apiGet<{
      total_demand: number;
      category_demand: { category: string; quantity: number }[];
      category_demand_2025: CategoryDemandItem[];
      product_demand_2025: ProductDemandItem[];
      yearly_quantity: { year: number; quantity: number }[];
      overall_quantity_by_year: number | null;
    }>(`/api/demand-dashboard?${params.toString()}`)
      .then((json) => setDemandDashboardData(json ?? null))
      .catch(() => setDemandDashboardData(null));
  }, [selectedContinent, selectedCountry, selectedStoreId, selectedCity, selectedYear]);

  // 모델 서버 데이터 소스 (SQL ↔ 대시보드 연동 표시)
  useEffect(() => {
    apiGet<{ data_dir: string; source: string; sql_file_count: number; csv_path: string | null }>('/api/data-source').then(setDataSourceInfo);
  }, []);

  // 모델 서버 연동 상태 (quick-status 우선·빠름, "다시 확인" 시 integration-status)
  const RETRY_DELAY_MS = 1500;
  const MAX_RETRIES = 1;
  const fetchIntegrationStatus = useCallback((retryCount = 0, useFullCheck = false) => {
    if (backendConnected !== true) return;
    const url = (retryCount > 0 || useFullCheck) ? '/api/integration-status' : '/api/quick-status';
    apiGet<{
      modules_loaded?: { load_sales_data?: boolean; prediction_model?: boolean; sales_analysis?: boolean; inventory_optimization?: boolean; realtime_dashboard?: boolean };
      data_source?: { source?: string; sql_file_count?: number };
    }>(url)
      .then((v) => {
        if (v) {
          setIntegrationStatus(v);
        } else if (retryCount < MAX_RETRIES) {
          console.warn('[IntegrationStatus] 응답 없음, 재시도 예정:', retryCount + 1);
          setTimeout(() => fetchIntegrationStatus(retryCount + 1), RETRY_DELAY_MS);
        } else {
          console.warn('[IntegrationStatus] 재시도 후에도 응답 없음');
        }
      })
      .catch((err) => {
        console.warn('[IntegrationStatus] 요청 실패:', err);
        if (retryCount < MAX_RETRIES) {
          setTimeout(() => fetchIntegrationStatus(retryCount + 1), RETRY_DELAY_MS);
        }
      });
  }, [backendConnected]);

  useEffect(() => {
    if (backendConnected !== true) {
      setIntegrationStatus(null);
      return;
    }
    fetchIntegrationStatus();
  }, [backendConnected, healthCheckTrigger, fetchIntegrationStatus]);

  // 마지막 업데이트 날짜: 마운트 시 즉시 조회 + 30초마다 폴링 (backendConnected 무관)
  useEffect(() => {
    const poll = () => {
      apiGet<{ last_updated?: string }>('/api/last-updated').then((json) => {
        if (json?.last_updated) setLastUpdated(json.last_updated);
      });
    };
    poll();
    const id = setInterval(poll, 30000);
    return () => clearInterval(id);
  }, []);

  // 파이차트 패널용 25년 예상 판매 수량 - 페이지 로드 시 1회 조회
  useEffect(() => {
    apiGet<{
      yearly_quantity?: { year: number; quantity: number }[];
      total_quantity_2020_2024?: number;
      predicted_quantity_2025?: number;
      predicted_2025_by_category?: { category: string; quantity: number }[];
      method?: string;
    }>('/api/sales-quantity-forecast').then((json) => {
      if (json) {
        setForecastData({
          yearly_quantity: json.yearly_quantity ?? [],
          total_quantity_2020_2024: json.total_quantity_2020_2024 ?? 0,
          predicted_quantity_2025: json.predicted_quantity_2025 ?? 0,
          predicted_2025_by_category: json.predicted_2025_by_category ?? [],
          method: json.method ?? 'linear_trend',
        });
      }
    });
  }, []);

  // 도시 좌표 (경도, 위도) - 하위 호환용 (storeMarkers 사용 시 대체됨)
  const cityMarkers: { city: string; country: string; lon: number; lat: number }[] = [
    { city: 'Paris', country: 'France', lon: 2.35, lat: 48.85 },
    { city: 'London', country: 'United Kingdom', lon: -0.13, lat: 51.51 },
    { city: 'Dubai', country: 'UAE', lon: 55.27, lat: 25.2 },
    { city: 'New York', country: 'United States', lon: -74.01, lat: 40.71 },
    { city: 'Melbourne', country: 'Australia', lon: 145.0, lat: -37.8 },
    { city: 'Tokyo', country: 'Japan', lon: 139.69, lat: 35.69 },
    { city: 'Mexico City', country: 'Mexico', lon: -99.13, lat: 19.43 },
    { city: 'Bangkok', country: 'Thailand', lon: 100.5, lat: 13.75 },
    { city: 'Singapore', country: 'Singapore', lon: 103.85, lat: 1.29 },
    { city: 'Seoul', country: 'South Korea', lon: 126.98, lat: 37.57 },
    { city: 'Beijing', country: 'China', lon: 116.41, lat: 39.9 },
    { city: 'Chicago', country: 'United States', lon: -87.63, lat: 41.88 },
    { city: 'Los Angeles', country: 'United States', lon: -118.24, lat: 34.05 },
    { city: 'Toronto', country: 'Canada', lon: -79.38, lat: 43.65 },
    { city: 'Shanghai', country: 'China', lon: 121.47, lat: 31.23 },
    { city: 'Bogota', country: 'Colombia', lon: -74.07, lat: 4.71 },
    { city: 'San Francisco', country: 'United States', lon: -122.42, lat: 37.77 },
    { city: 'Vienna', country: 'Austria', lon: 16.37, lat: 48.21 },
    { city: 'Amsterdam', country: 'Netherlands', lon: 4.9, lat: 52.37 },
    { city: 'Rome', country: 'Italy', lon: 12.5, lat: 41.9 },
    { city: 'Berlin', country: 'Germany', lon: 13.4, lat: 52.52 },
    { city: 'Taipei', country: 'Taiwan', lon: 121.57, lat: 25.04 },
    { city: 'Abu Dhabi', country: 'UAE', lon: 54.37, lat: 24.45 },
    { city: 'Munich', country: 'Germany', lon: 11.58, lat: 48.14 },
    { city: 'Kyoto', country: 'Japan', lon: 135.77, lat: 35.01 },
    { city: 'Honolulu', country: 'United States', lon: -157.86, lat: 21.31 },
    { city: 'Montreal', country: 'Canada', lon: -73.57, lat: 45.5 },
    { city: 'Macau', country: 'China', lon: 113.54, lat: 22.19 },
    { city: 'Cologne', country: 'Germany', lon: 6.95, lat: 50.94 },
  ];

  // 국가명 한글 매핑 + 수도 좌표(경도lon, 위도lat) + 국가 크기별 글자 비율
  const countryLabels: { en: string; ko: string; lon: number; lat: number; scale: number }[] = [
    { en: 'United States', ko: '미국', lon: -77.04, lat: 38.91, scale: 1 },      // Washington D.C.
    { en: 'Canada', ko: '캐나다', lon: -75.69, lat: 45.42, scale: 0.95 },       // Ottawa
    { en: 'Mexico', ko: '멕시코', lon: -99.13, lat: 19.43, scale: 0.9 },       // Mexico City
    { en: 'Colombia', ko: '콜롬비아', lon: -74.07, lat: 4.71, scale: 0.72 },   // Bogota
    { en: 'United Kingdom', ko: '영국', lon: -0.13, lat: 51.51, scale: 0.68 }, // London
    { en: 'France', ko: '프랑스', lon: 2.35, lat: 48.85, scale: 0.82 },        // Paris
    { en: 'Germany', ko: '독일', lon: 13.4, lat: 52.52, scale: 0.72 },          // Berlin
    { en: 'Austria', ko: '오스트리아', lon: 16.37, lat: 48.21, scale: 0.55 },  // Vienna
    { en: 'Spain', ko: '스페인', lon: -3.7, lat: 40.42, scale: 0.8 },           // Madrid
    { en: 'Italy', ko: '이탈리아', lon: 12.5, lat: 41.9, scale: 0.72 },         // Rome
    { en: 'Netherlands', ko: '네덜란드', lon: 4.9, lat: 52.37, scale: 0.48 },  // Amsterdam
    { en: 'China', ko: '중국', lon: 116.41, lat: 39.9, scale: 0.95 },          // Beijing
    { en: 'Japan', ko: '일본', lon: 139.69, lat: 35.69, scale: 0.78 },         // Tokyo
    { en: 'South Korea', ko: '한국', lon: 126.98, lat: 37.57, scale: 0.52 },   // Seoul
    { en: 'Taiwan', ko: '대만', lon: 121.57, lat: 25.04, scale: 0.5 },          // Taipei
    { en: 'Singapore', ko: '싱가포르', lon: 103.85, lat: 1.29, scale: 0.5 },   // Singapore
    { en: 'Thailand', ko: '태국', lon: 100.5, lat: 13.75, scale: 0.72 },       // Bangkok
    { en: 'UAE', ko: '아랍에미리트', lon: 54.37, lat: 24.45, scale: 0.5 },     // Abu Dhabi
    { en: 'Australia', ko: '호주', lon: 149.13, lat: -35.28, scale: 1 },       // Canberra
  ];
  /** 국가명 표시: 한글(영문) 형식 */
  const formatCountryDisplay = (enName: string) => {
    const c = countryLabels.find((x) => x.en === enName);
    return c ? `${c.ko}(${c.en})` : enName;
  };

  /** 스토어 표시: 한글(영문) 형식 */
  const formatStoreDisplay = (storeId: string) => {
    const m = storeMarkers.find((s) => (s.store_id || '').trim().toLowerCase() === (storeId || '').trim().toLowerCase());
    if (!m) return storeId;
    const en = m.store_name || storeId;
    const ko = m.store_name_ko?.trim();
    return ko ? `${ko}(${en})` : en;
  };

  const globeMarkersData = useMemo(() => {
    const markers: Array<{ type: 'country' | 'store' | 'continent'; lat: number; lng: number; [key: string]: unknown }> = [];
    countryLabels.forEach(({ ko, en, lon, lat }) => {
      markers.push({ type: 'country', lat, lng: lon, ko, en });
    });
    const stores = storeMarkers.length > 0
      ? storeMarkers
      : cityMarkers
          .filter((m) => !pieData.length || pieData.some((d) => d.city === m.city))
          .map((m) => ({ ...m, store_id: m.city } as StoreMarker));
    stores.forEach((m) => {
      markers.push({ type: 'store', lat: m.lat, lng: m.lon, store_id: m.store_id, city: m.city, country: m.country, isStore: storeMarkers.length > 0 });
    });
    continentPieData.filter((c) => (c.data?.length ?? 0) > 0 && c.data?.some((d) => (d.quantity ?? 0) > 0)).forEach(({ continent, continent_ko, lon, lat }) => {
      markers.push({ type: 'continent', lat, lng: lon, continent, continent_ko });
    });
    return markers;
  }, [countryLabels, storeMarkers, cityMarkers, pieData, continentPieData]);

  // 모델 상태: API 연결 성공 시 정상, 실패 시 대기 중
  const modelStatus = data ? '예측 모델 연결됨' : '예측 모델 연결 대기 중';
  const lastUpdatedDisplay = lastUpdated || data?.last_updated || '';

  // 수요: 선택된 지역의 "연도별" 총 수요 — prediction model.py get_demand_dashboard_data 우선, 없으면 기존 pie 데이터
  const overallQuantityByYear = useMemo(() => {
    const yq = demandDashboardData?.yearly_quantity ?? forecastData?.yearly_quantity ?? [];
    const row = yq.find((r) => r.year === selectedYear);
    return typeof row?.quantity === 'number' ? row.quantity : null;
  }, [demandDashboardData, forecastData, selectedYear]);

  const demandTotalByYear = useMemo(() => {
    if (demandDashboardData != null) return demandDashboardData.total_demand;
    const sum = (items?: Array<{ quantity: number }>) => (items ?? []).reduce((a, d) => a + (d.quantity || 0), 0);
    if (selectedContinent) {
      const cont = continentPieData.find((c) => c.continent === selectedContinent);
      const byYear = cont?.data_by_year?.[selectedYear] ?? null;
      if (byYear) return sum(byYear);
      return sum(cont?.data ?? []);
    }
    if (selectedCountry && countryCategoryPieData?.data_by_year) {
      return sum(countryCategoryPieData.data_by_year[selectedYear] ?? []);
    }
    if (selectedStoreId && storeCategoryPieData?.data_by_year) {
      return sum(storeCategoryPieData.data_by_year[selectedYear] ?? []);
    }
    if (selectedCity && pieData.length > 0) {
      return pieData
        .filter((d) => d.city === selectedCity && d.year === selectedYear)
        .reduce((a, d) => a + (d.quantity || 0), 0);
    }
    return null;
  }, [demandDashboardData, selectedContinent, continentPieData, selectedCountry, countryCategoryPieData, selectedStoreId, storeCategoryPieData, selectedCity, selectedYear, pieData]);

  // 카테고리별 수요(수량) — prediction model.py 우선
  const demandCategoryRows = useMemo(() => {
    if (demandDashboardData?.category_demand?.length) return demandDashboardData.category_demand;
    const flatToRows = (items: { category: string; quantity: number }[]) => {
      const map = new Map<string, number>();
      items
        .filter((d) => (d.quantity ?? 0) > 0)
        .forEach((d) => map.set(d.category, (map.get(d.category) ?? 0) + (d.quantity ?? 0)));
      return Array.from(map.entries()).map(([category, quantity]) => ({ category, quantity }));
    };
    const rows: { category: string; quantity: number }[] = selectedContinent
      ? (
          continentPieData.find((c) => c.continent === selectedContinent)?.data_by_year?.[selectedYear]
          ?? continentPieData.find((c) => c.continent === selectedContinent)?.data
          ?? []
        ).filter((d) => (d.quantity ?? 0) > 0)
      : selectedCountry && countryCategoryPieData?.data_by_year
        ? flatToRows(countryCategoryPieData.data_by_year[selectedYear] ?? [])
        : selectedStoreId && storeCategoryPieData?.data_by_year
          ? flatToRows(storeCategoryPieData.data_by_year[selectedYear] ?? [])
          : selectedCity && pieData.length > 0
            ? flatToRows(
                pieData
                  .filter((d) => d.city === selectedCity && d.year === selectedYear)
                  .map((d) => ({ category: d.category, quantity: d.quantity }))
              )
            : [];
    return rows;
  }, [
    demandDashboardData,
    selectedContinent,
    continentPieData,
    selectedCountry,
    countryCategoryPieData,
    selectedStoreId,
    storeCategoryPieData,
    selectedCity,
    selectedYear,
    pieData,
  ]);

  const demandCategoryPercentData = useMemo(() => {
    if (!demandCategoryRows || demandCategoryRows.length === 0) return [];
    return toPercentData(demandCategoryRows.map((r) => ({ name: r.category, value: r.quantity }))).sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  }, [demandCategoryRows]);

  // 안전재고 대시보드 카드용: 선택 연도별 카테고리 판매대수(비율)
  const safetyStockCategoryPercentData = useMemo(() => {
    const flatToRows = (items: { category: string; quantity: number }[]) => {
      const map = new Map<string, number>();
      items.filter((d) => (d.quantity ?? 0) > 0).forEach((d) => map.set(d.category, (map.get(d.category) ?? 0) + (d.quantity ?? 0)));
      return Array.from(map.entries()).map(([category, quantity]) => ({ category, quantity }));
    };
    const year = safetyStockCategoryYear;
    let rows: { category: string; quantity: number }[] = [];
    if (selectedContinent) {
      const cont = continentPieData.find((c) => c.continent === selectedContinent);
      const arr = cont?.data_by_year?.[year] ?? cont?.data ?? [];
      rows = arr.filter((d) => (d.quantity ?? 0) > 0);
    } else if (selectedCountry && countryCategoryPieData?.data_by_year) {
      rows = flatToRows(countryCategoryPieData.data_by_year[year] ?? []);
    } else if (selectedStoreId && storeCategoryPieData?.data_by_year) {
      rows = flatToRows(storeCategoryPieData.data_by_year[year] ?? []);
    } else if (selectedCity && pieData.length > 0) {
      rows = flatToRows(pieData.filter((d) => d.city === selectedCity && d.year === year).map((d) => ({ category: d.category, quantity: d.quantity })));
    }
    if (rows.length === 0) return [];
    return toPercentData(rows.map((r) => ({ name: r.category, value: r.quantity }))).sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  }, [safetyStockCategoryYear, selectedContinent, continentPieData, selectedCountry, countryCategoryPieData, selectedStoreId, storeCategoryPieData, selectedCity, pieData]);

  /** category별 2020~2025 수량 — prediction model.py get_demand_dashboard_data */
  const categoryDemandDisplay = demandDashboardData?.category_demand_2025 ?? [];

  /** product_id별 2025 예측 — prediction model.py get_demand_dashboard_data 우선, 선택 카테고리로 필터 */
  const productDemandDisplayRaw = demandDashboardData?.product_demand_2025?.length
    ? demandDashboardData.product_demand_2025
    : productDemandList;
  const productDemandDisplay = useMemo(() => {
    if (!productDemandDisplayRaw) return null;
    if (!selectedCategoryFilter) return productDemandDisplayRaw;
    const norm = (s: string) => (s ?? "").trim().toLowerCase();
    return productDemandDisplayRaw.filter(
      (p) => norm(p.category ?? "") === norm(selectedCategoryFilter)
    );
  }, [productDemandDisplayRaw, selectedCategoryFilter]);

  // 선택 지역 데이터가 없어 0이 나오면 → 전체(선택 연도) 수량으로 대체 (prediction model overall_quantity_by_year 우선)
  const demandTotalDisplay = useMemo(() => {
    if (demandTotalByYear == null) return null;
    if (demandTotalByYear > 0) return demandTotalByYear;
    const hasSelection = Boolean(selectedContinent || selectedCountry || selectedStoreId || selectedCity);
    const fallback = demandDashboardData?.overall_quantity_by_year ?? overallQuantityByYear;
    if (hasSelection && demandTotalByYear === 0 && fallback != null) return fallback;
    return demandTotalByYear;
  }, [demandTotalByYear, demandDashboardData?.overall_quantity_by_year, overallQuantityByYear, selectedContinent, selectedCountry, selectedStoreId, selectedCity]);

  return (
    <main className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f]">
      {/* 헤더 - Apple 스타일 */}
      <header className="pt-10 pb-8 text-center relative">
        <div className="flex items-center justify-center gap-3">
          <span className="text-4xl">🍎</span>
          <h1 className="text-3xl md:text-4xl font-bold text-[#1d1d1f] tracking-tight">Apple 리테일 전략</h1>
        </div>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="absolute top-10 right-6 md:right-12 px-3 py-1.5 text-sm rounded-lg bg-[#f5f5f7] hover:bg-[#e8e8ed] text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
        >
          새로고침
        </button>
      </header>

      <div className="w-full max-w-[1600px] mx-auto px-6 pb-16">
        {/* 메인 개요 + 모델 상태 - 가로 배치 (랜드스케이프) */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 lg:col-span-2">
            <h2 className="text-2xl font-bold text-[#1d1d1f] mb-2">
              Apple 리테일 재고 전략 현황
            </h2>
            <p className="text-[#6e6e73] text-base">
              예측 모델과 연동되어 제고 최적화 전략을 실시간으로 제공합니다.
            </p>
          </div>
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <h3 className="text-sm font-medium text-[#6e6e73] mb-4">마지막 업데이트</h3>
            <p className="text-2xl font-bold text-[#1d1d1f]">{lastUpdatedDisplay || '—'}</p>
          </div>
        </section>

        {/* 글로벌 리테일 네트워크 - 지도 */}
        <section className="bg-white rounded-2xl p-6 mb-8 overflow-hidden shadow-sm border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-semibold text-[#1d1d1f]">글로벌 리테일 네트워크</h3>
            <p className="text-[#6e6e73] text-xs">지역·스토어 클릭 시 카테고리별 판매 {QUANTITY_LABEL} 표시</p>
          </div>
          {/* 지도 컨테이너: 3D 글로브 + 오버레이 패널(맨 앞) */}
          <div
            ref={globeContainerRef}
            className="relative w-full bg-[#e8e8ed] rounded-xl overflow-hidden select-none isolate"
            style={{ aspectRatio: '2/1' }}
          >
            <div className="absolute inset-0 z-0">
            <GlobeMap
              width={Math.max(1, globeSize.width)}
              height={Math.max(1, globeSize.height)}
              htmlElementsData={globeMarkersData}
              onCountryClick={(en) => {
                if (selectedContinent) {
                  setShowPieChart(false);
                  setSelectedContinent('');
                  setSelectedCountry('');
                  setSelectedStoreId('');
                  setSelectedCity('');
                } else {
                  setSelectedContinent('');
                  setSelectedCountry(en);
                  setSelectedStoreId('');
                  setSelectedCity('');
                  setShowPieChart(true);
                }
              }}
              onStoreClick={(storeId, city, isStore) => {
                if (selectedContinent) {
                  setShowPieChart(false);
                  setSelectedContinent('');
                  setSelectedCountry('');
                  setSelectedStoreId('');
                  setSelectedCity('');
                } else {
                  setSelectedContinent('');
                  setSelectedCountry('');
                  if (isStore) {
                    setSelectedStoreId(storeId);
                    setSelectedCity('');
                  } else {
                    setSelectedCity(city);
                    setSelectedStoreId('');
                  }
                  setShowPieChart(true);
                }
              }}
              onContinentClick={(continent) => {
                setSelectedContinent(continent);
                setSelectedCountry('');
                setSelectedStoreId('');
                setSelectedCity('');
                setShowPieChart(true);
              }}
              onGlobeClick={() => {
                setShowPieChart(false);
                setSelectedContinent('');
                setSelectedCountry('');
                setSelectedStoreId('');
                setSelectedCity('');
              }}
              selectedCountry={selectedCountry}
              selectedStoreId={selectedStoreId}
              selectedCity={selectedCity}
              selectedContinent={selectedContinent}
            />
            </div>
            {/* 지도 위 파이차트 오버레이 - 맨 앞에 표시 */}
            {showPieChart && (selectedCountry || selectedStoreId || selectedCity || selectedContinent) ? (
              <div
                className="absolute top-3 right-3 bottom-3 w-[min(420px,55%)] min-h-[240px] z-[100] bg-white/98 backdrop-blur-sm rounded-xl border border-gray-200 shadow-2xl overflow-hidden flex flex-col"
                onMouseDown={(e) => e.stopPropagation()}
              >
                <div className="flex flex-col gap-2 px-3 py-2 border-b border-gray-200 shrink-0 bg-[#1d1d1f]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-white truncate min-w-0">
                      {selectedContinent
                        ? `${continentPieData.find((c) => c.continent === selectedContinent)?.continent_ko ?? selectedContinent} - 대륙 카테고리별 판매 ${QUANTITY_LABEL}`
                        : selectedCountry
                          ? `${formatCountryDisplay(selectedCountry)} - 국가 카테고리별 판매 ${QUANTITY_LABEL}`
                          : selectedStoreId
                            ? `${formatStoreDisplay(selectedStoreId)} - 카테고리별 판매 ${QUANTITY_LABEL}`
                            : selectedCity
                              ? `${selectedCity} - 도시 카테고리별 판매 ${QUANTITY_LABEL}`
                              : `카테고리별 판매 ${QUANTITY_LABEL}`}
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowPieChart(false)}
                      className="p-1 rounded hover:bg-white/20 text-white/80 hover:text-white transition-colors shrink-0"
                      aria-label="닫기"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="flex items-center justify-between gap-2 px-2 py-1.5 rounded bg-transparent border border-transparent">
                    <span className="text-sm font-medium text-white/80 shrink-0 text-right w-10">연도</span>
                    <div className="relative flex-1 min-w-0 max-w-[140px]">
                      <select
                        value={selectedPieYear === null ? '' : selectedPieYear}
                        onChange={(e) => {
                          const val = e.target.value;
                          const y = val === '' ? null : Number(val);
                          setSelectedPieYear(y);
                          if (y !== null) setSelectedYear(y);
                        }}
                        className="w-full appearance-none bg-white/95 border border-white/30 rounded pl-2 pr-7 py-1.5 text-xs text-[#1d1d1f] cursor-pointer focus:outline-none focus:ring-1 focus:ring-white/50 focus:border-white/50"
                      >
                        <option value="">전체 (20~24년 합산)</option>
                        {PIE_YEARS.map((y) => (
                          <option key={y} value={y}>{y}년</option>
                        ))}
                        <option value={2025}>2025년 (예상)</option>
                      </select>
                      <span className="pointer-events-none absolute right-1.5 top-1/2 -translate-y-1/2 text-[#374151] text-[10px]">▼</span>
                    </div>
                  </div>
                </div>
                <div className="flex-1 min-h-0 p-2 overflow-auto">
                  {selectedPieYear === 2025 ? (
                    forecastData?.predicted_2025_by_category && forecastData.predicted_2025_by_category.length > 0 ? (
                      <div className="h-full min-h-[200px] flex flex-col">
                        <p className="text-xs font-medium text-white mb-1 text-center shrink-0 px-2 py-1 rounded bg-transparent">
                          25년 예상 판매 {QUANTITY_LABEL} 비중(%) (카테고리별)
                          {forecastData.method ? (
                            <span className="ml-1 text-[10px] text-white">· {forecastData.method === 'arima' ? 'ARIMA' : '선형추세'}</span>
                          ) : null}
                        </p>
                        <div className="flex-1 min-h-0">
                          <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                              <Pie
                                data={toPercentData(forecastData.predicted_2025_by_category.map((d) => ({ name: d.category, value: d.quantity })))}
                                cx="50%"
                                cy="50%"
                                innerRadius="40%"
                                outerRadius="82%"
                                paddingAngle={1}
                                dataKey="value"
                                label={false}
                              >
                                {forecastData.predicted_2025_by_category.map((_, i) => (
                                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                                ))}
                              </Pie>
                              <Tooltip content={<PieTooltipContent />} contentStyle={{ backgroundColor: 'transparent', border: 'none' }} />
                              <Legend
                                height={56}
                                iconSize={6}
                                wrapperStyle={{ overflowY: 'auto', fontSize: 9, lineHeight: '12px' }}
                                formatter={(_, entry: { payload?: { name?: string; value?: number } }) => (
                                  <span style={{ fontSize: 9, lineHeight: '12px' }}>
                                    {entry.payload?.name ?? ''} {((entry.payload?.value ?? 0) as number).toFixed(1)}%
                                  </span>
                                )}
                              />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    ) : (
                      <p className="text-[#6e6e73] text-sm p-4 text-center">25년 예상 데이터를 불러오는 중...</p>
                    )
                  ) : selectedContinent ? (
                    (() => {
                      const contData = continentPieData.find((c) => c.continent === selectedContinent);
                      const byYear = contData?.data_by_year ?? {};
                      const hasAny = PIE_YEARS.some((y) => (byYear[y]?.length ?? 0) > 0);
                      if (!hasAny) return <p className="text-[#6e6e73] text-sm p-4 text-center">데이터가 없습니다</p>;
                      return <PieChartsByYearFilter dataByYear={byYear} selectedYear={selectedPieYear} mode="percent" />;
                    })()
                  ) : selectedCountry && !countryCategoryPieData ? (
                    <p className="text-[#6e6e73] text-sm p-4 text-center">데이터를 불러오는 중...</p>
                  ) : selectedCountry && countryCategoryPieData?.data_by_year ? (
                    <PieChartsByYearFilter dataByYear={countryCategoryPieData.data_by_year} selectedYear={selectedPieYear} mode="percent" />
                  ) : selectedStoreId && !storeCategoryPieData ? (
                    <p className="text-[#6e6e73] text-sm p-4 text-center">데이터를 불러오는 중...</p>
                  ) : selectedStoreId && storeCategoryPieData?.data_by_year ? (
                    <PieChartsByYearFilter dataByYear={storeCategoryPieData.data_by_year} selectedYear={selectedPieYear} mode="percent" />
                  ) : selectedCity && pieData.length > 0 ? (
                    (() => {
                      const byYear: Record<number, { category: string; quantity: number }[]> = { 2020: [], 2021: [], 2022: [], 2023: [], 2024: [] };
                      pieData
                        .filter((d) => d.city === selectedCity)
                        .forEach((d) => {
                          if (!byYear[d.year]) byYear[d.year] = [];
                          byYear[d.year].push({ category: d.category, quantity: d.quantity });
                        });
                      PIE_YEARS.forEach((y) => {
                        const map = new Map<string, number>();
                        (byYear[y] ?? []).forEach((d) => map.set(d.category, (map.get(d.category) ?? 0) + d.quantity));
                        byYear[y] = Array.from(map.entries()).map(([category, quantity]) => ({ category, quantity }));
                      });
                      return (
                        <>
                          <div className="flex gap-2 mb-2 shrink-0">
                            <select
                              value={selectedCity}
                              onChange={(e) => setSelectedCity(e.target.value)}
                              className="px-2 py-1 text-xs rounded bg-[#f5f5f7] text-[#1d1d1f] border border-gray-200"
                            >
                              {Array.from(new Set(pieData.map((d) => d.city))).sort().map((city) => (
                                <option key={city} value={city}>{city}</option>
                              ))}
                            </select>
                          </div>
                          <PieChartsByYearFilter dataByYear={byYear} selectedYear={selectedPieYear} mode="percent" />
                        </>
                      );
                    })()
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
        </section>

        {/* 4개 박스 - 대륙·국가·스토어 클릭 시 표시 (가로 1열) */}
        {selectedContinent || selectedCountry || selectedStoreId ? (
          <section className="grid grid-cols-4 gap-4 mb-6">
            <button
              type="button"
              onClick={() => setShowDemandDashboard(true)}
              className="bg-white rounded-2xl p-6 w-full text-left hover:bg-[#f5f5f7] transition-colors cursor-pointer border border-gray-100 shadow-sm hover:shadow"
            >
              <h3 className="text-sm font-medium text-[#6e6e73] mb-2">수요</h3>
              <div className="flex items-center justify-between gap-3">
                <p className="text-xl font-bold text-[#1d1d1f]">
                  {demandTotalDisplay != null ? `${demandTotalDisplay.toLocaleString()}${QUANTITY_UNIT}` : '—'}
                </p>
                {/* 패널 미니 파이차트 (카테고리 100% 기준) */}
                {demandCategoryPercentData.length > 0 ? (
                  <div className="w-20 h-20 shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={demandCategoryPercentData}
                          cx="50%"
                          cy="50%"
                          innerRadius="55%"
                          outerRadius="85%"
                          paddingAngle={1}
                          dataKey="value"
                          isAnimationActive={false}
                        >
                          {demandCategoryPercentData.map((_, i) => (
                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                ) : null}
              </div>
              <p className="text-xs text-[#86868b] mt-1">
                {selectedContinent
                  ? (continentPieData.find((c) => c.continent === selectedContinent)?.continent_ko ?? selectedContinent)
                  : selectedCountry
                    ? formatCountryDisplay(selectedCountry)
                    : selectedStoreId
                      ? formatStoreDisplay(selectedStoreId)
                      : '클릭 시 수요 대시보드'}
                {demandTotalDisplay != null ? ` · ${selectedYear}년` : ''}
              </p>
            </button>
            <Link
              href="/sales"
              className="bg-white rounded-2xl p-6 w-full text-left hover:bg-[#f5f5f7] transition-colors cursor-pointer border border-gray-100 shadow-sm hover:shadow block"
            >
              <h3 className="text-sm font-medium text-[#6e6e73] mb-2">매출</h3>
              <p className="text-xl font-bold text-[#1d1d1f]">
                {salesBoxLoading ? '…' : salesBoxValue != null ? salesBoxValue.toLocaleString() : '—'}
              </p>
              <p className="text-xs text-[#86868b] mt-1">
                {selectedContinent || selectedCountry || selectedStoreId
                  ? 'Sales analysis.py 연동 · 클릭 시 매출 대시보드'
                  : '클릭 시 매출 대시보드'}
              </p>
            </Link>
            <button
              type="button"
              onClick={() => setShowSafetyStockDashboard(true)}
              className="bg-white rounded-2xl p-6 w-full text-left hover:bg-[#f5f5f7] transition-colors cursor-pointer border border-gray-100 shadow-sm hover:shadow"
            >
              <h3 className="text-sm font-medium text-[#6e6e73] mb-2">안전재고</h3>
              <p className="text-xl font-bold text-[#1d1d1f]">—</p>
              <p className="text-xs text-[#86868b] mt-1">클릭 시 안전재고 대시보드</p>
            </button>
            <Link
              href="/recommendation"
              className="bg-white rounded-2xl p-6 w-full text-left hover:bg-[#f5f5f7] transition-colors cursor-pointer border border-gray-100 shadow-sm hover:shadow block"
            >
              <h3 className="text-sm font-medium text-[#6e6e73] mb-2">추천</h3>
              <p className="text-xl font-bold text-[#1d1d1f]">—</p>
              <p className="text-xs text-[#86868b] mt-1">
                {selectedContinent || selectedCountry || selectedStoreId
                  ? 'Real-time execution and performance dashboard 연동 · 클릭 시 추천 대시보드'
                  : '클릭 시 추천 대시보드'}
              </p>
            </Link>
          </section>
        ) : (
          <section className="bg-white rounded-2xl p-6 mb-6 shadow-sm border border-gray-100">
            <p className="text-[#6e6e73] text-center text-sm">
              지도에서 <strong className="text-[#1d1d1f]">대륙·국가·스토어</strong>를 클릭하면 수요·매출·안전재고·추천 박스를 볼 수 있습니다.
            </p>
          </section>
        )}

        {/* 모델 상태 + 모델 서버 연동 */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6 max-w-4xl">
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <h3 className="text-sm font-medium text-[#6e6e73] mb-4">모델 상태</h3>
            <div className="flex flex-col gap-2">
              <div className="inline-flex items-center gap-2 px-4 py-3 bg-[#f5f5f7] rounded-xl">
                <span className={`w-2.5 h-2.5 rounded-full ${backendConnected === true ? 'bg-[#34c759]' : backendConnected === false ? 'bg-[#ff3b30]' : 'bg-[#ff9f0a]'}`} />
                <span className="text-[#1d1d1f] font-medium">
                  {backendConnected === null ? '백엔드 확인 중...' : backendConnected ? '백엔드 API 연결됨' : '백엔드 연결 안됨'}
                </span>
              </div>
              {(backendConnected === false || backendConnected === null) && (
                <div className="flex flex-wrap items-center gap-2 px-1">
                  <button
                    type="button"
                    onClick={() => { setBackendConnected(null); setHealthCheckTrigger((n) => n + 1); }}
                    className="text-xs px-2 py-1.5 rounded bg-[#f5f5f7] hover:bg-gray-200 text-[#1d1d1f]"
                  >
                    다시 확인
                  </button>
                  {backendConnected === false && (
                    <p className="text-xs text-[#6e6e73]">
                      터미널에서 백엔드 실행: <code className="bg-gray-100 px-1 rounded">cd web-development/backend</code> 후 <code className="bg-gray-100 px-1 rounded">uvicorn main:app --reload --port 8000</code>
                    </p>
                  )}
                </div>
              )}
              <div className="inline-flex items-center gap-2 px-4 py-3 bg-[#f5f5f7] rounded-xl">
                <span className={`w-2.5 h-2.5 rounded-full ${data ? 'bg-[#34c759]' : 'bg-[#ff9f0a]'}`} />
                <span className="text-[#1d1d1f] font-medium">
                  {loading ? '연결 중...' : (data ? '예측 모델 연결됨' : modelStatus)}
                </span>
              </div>
              {error && (
                <div className="flex items-center gap-2">
                  <p className="text-amber-600 text-sm">{error}</p>
                  <button
                    onClick={fetchData}
                    className="px-2 py-1 text-xs rounded bg-[#f5f5f7] hover:bg-gray-200 text-[#1d1d1f]"
                  >
                    다시 시도
                  </button>
                </div>
              )}
            </div>
          </div>
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <h3 className="text-sm font-medium text-[#6e6e73] mb-4">모델 서버 연동</h3>
            {backendConnected !== true ? (
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${backendConnected === false ? 'bg-[#ff3b30]' : 'bg-[#ff9f0a]'}`} />
                <p className="text-sm text-[#6e6e73]">
                  {backendConnected === null ? '백엔드 확인 중...' : '백엔드 연결 후 표시'}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {[
                  { key: 'load_sales_data' as const, label: 'load_sales_data.py' },
                  { key: 'prediction_model' as const, label: 'prediction model' },
                  { key: 'sales_analysis' as const, label: 'Sales analysis' },
                  { key: 'inventory_optimization' as const, label: 'Inventory Optimization' },
                  { key: 'realtime_dashboard' as const, label: 'Real-time dashboard' },
                ].map(({ key, label }) => {
                  const ok = integrationStatus?.modules_loaded?.[key] ?? false;
                  return (
                    <div key={key} className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${ok ? 'bg-[#34c759]' : 'bg-[#ff3b30]'}`} />
                      <span className="text-sm text-[#1d1d1f] flex-1">{label}</span>
                      <span className="text-xs text-[#6e6e73]">{ok ? '연동됨' : '미연동'}</span>
                    </div>
                  );
                })}
                {(integrationStatus === null || (integrationStatus?.modules_loaded && Object.values(integrationStatus.modules_loaded).some((v) => v === false))) && (
                  <button
                    type="button"
                    onClick={() => fetchIntegrationStatus(0, true)}
                    className="text-xs px-2 py-1.5 mt-1 rounded bg-[#f5f5f7] hover:bg-gray-200 text-[#1d1d1f]"
                  >
                    다시 확인
                  </button>
                )}
                {integrationStatus?.data_source?.source && integrationStatus.data_source.source !== 'none' && (
                  <p className="text-xs text-[#6e6e73] pt-1 border-t border-gray-100">
                    데이터: {integrationStatus.data_source.source}
                    {integrationStatus.data_source.sql_file_count != null && integrationStatus.data_source.sql_file_count > 0
                      ? ` (SQL ${integrationStatus.data_source.sql_file_count}개)`
                      : ''}
                  </p>
                )}
                {/* Vercel 환경 변수 확인: NEXT_PUBLIC_API_URL 설정 시 표시 */}
                <p className="text-xs text-[#6e6e73] pt-1 border-t border-gray-100">
                  API 베이스:{' '}
                  {typeof window !== 'undefined' && process.env.NEXT_PUBLIC_API_URL
                    ? (() => {
                        try {
                          const h = new URL(process.env.NEXT_PUBLIC_API_URL).hostname;
                          return h ? ` 설정됨 (${h})` : ' 설정됨';
                        } catch {
                          return ' 설정됨';
                        }
                      })()
                    : ' 미설정 (로컬/상대경로)'}
                </p>
              </div>
            )}
          </div>
        </section>

        {/* 푸터 */}
        <p className="text-center text-[#86868b] text-sm">
          백엔드 API와 실시간 연동됨
        </p>
      </div>

      {/* Inventory Action Center 오버레이 */}
      {showSafetyStockDashboard ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          onClick={() => { setShowSafetyStockDashboard(false); setSafetyStockSelectedCategory(null); }}
        >
          <div
            className="bg-white rounded-2xl border border-gray-200 shadow-2xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 shrink-0">
              <div>
                <h2 className="text-xl font-bold text-[#1d1d1f]">Inventory Action Center</h2>
                <p className="text-xs text-[#86868b] mt-0.5">현황 파악(Monitoring) · 조치 기록(Action Logging)</p>
                <div className="mt-1.5 flex flex-wrap gap-2 text-[10px] text-[#86868b]">
                  <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">📊 데이터: SQL (01.data/*.sql)</span>
                  <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">🤖 예측: ARIMA 모델 (arima_model.joblib)</span>
                  <span className="px-2 py-0.5 rounded bg-green-50 text-green-700 border border-green-200">💰 예상 매출 = (ARIMA 예측 수량) × 단가</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => { setShowSafetyStockDashboard(false); setSafetyStockSelectedCategory(null); }}
                className="p-2 rounded-lg hover:bg-gray-100 text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
                aria-label="닫기"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-auto p-6">
              {safetyStockLoading ? (
                <p className="text-[#6e6e73] text-center py-12">로딩 중...</p>
              ) : (
                <>
                  {/* 구역 1. 상단: 재고 리스크 현황 (KPI 카드) - 한글 라벨 */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                    <div className="rounded-xl p-4 border-2 border-red-200 bg-red-50">
                      <p className="text-xs font-medium text-red-700 mb-1">💰 총 잠긴 돈 (Total Frozen Money)</p>
                      <p className="text-2xl font-bold text-red-800">
                        {safetyStockKpiData?.total_frozen_money != null
                          ? `₩${Number(safetyStockKpiData.total_frozen_money).toLocaleString()}`
                          : '—'}
                      </p>
                    </div>
                    <div className="rounded-xl p-4 border-2 border-red-200 bg-red-50">
                      <p className="text-xs font-medium text-red-700 mb-1">🚨 위험 품목 수</p>
                      <p className="text-2xl font-bold text-red-800">
                        {safetyStockKpiData?.danger_count != null ? safetyStockKpiData.danger_count.toLocaleString() : '—'}
                      </p>
                    </div>
                    <div className="rounded-xl p-4 border-2 border-amber-200 bg-amber-50">
                      <p className="text-xs font-medium text-amber-800 mb-1">🟡 과잉 품목 수</p>
                      <p className="text-2xl font-bold text-amber-900">
                        {safetyStockKpiData?.overstock_count != null ? safetyStockKpiData.overstock_count.toLocaleString() : '—'}
                      </p>
                    </div>
                    <div className="rounded-xl p-4 border-2 border-green-200 bg-green-50">
                      <p className="text-xs font-medium text-green-700 mb-1">💰 예상 매출 (Expected Revenue)</p>
                      <p className="text-2xl font-bold text-green-800">
                        {safetyStockKpiData?.expected_revenue != null && safetyStockKpiData.expected_revenue > 0
                          ? `₩${Number(safetyStockKpiData.expected_revenue).toLocaleString()}`
                          : '—'}
                      </p>
                      <div className="mt-1 space-y-0.5">
                        {safetyStockKpiData?.predicted_demand != null && safetyStockKpiData.predicted_demand > 0 ? (
                          <>
                            <p className="text-xs text-green-600">
                              예측 수요: <strong>{safetyStockKpiData.predicted_demand.toLocaleString()}대</strong> (ARIMA)
                            </p>
                            <p className="text-[10px] text-green-500 italic">
                              계산식: (ARIMA 예측 수량) × 제품 단가
                            </p>
                          </>
                        ) : (
                          <p className="text-xs text-green-600">(ARIMA 예측 필요)</p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* 구역 2 & 3: 좌측 매장별 재고 막대 그래프 · 우측 관리자 코멘트 */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* 좌측: 매장별 재고 현황 — 가로형 막대 그래프 (재고 상태별 색상) */}
                    <div className="lg:col-span-2 rounded-xl border border-gray-200 overflow-hidden bg-[#fafafa]">
                      <div className="px-4 py-3 border-b border-gray-200 bg-white flex flex-wrap items-center gap-3">
                        <div className="flex-1 min-w-0">
                          <h3 className="text-sm font-semibold text-[#1d1d1f]">매장별 재고 현황</h3>
                          <p className="text-xs text-[#86868b] mt-0.5">
                            매장명 · 잠긴 돈(₩) 기준 가로형 막대 | 재고 상태에 따라 색상: 위험(빨강) · 과잉(노랑/주황) · 정상(초록/파랑) |
                            <span className="ml-1 text-[10px]">데이터: SQL (Inventory Optimization 파이프라인) | 정렬: 잠긴 돈 내림차순</span>
                          </p>
                        </div>
                        <select
                          value={inventoryStatusFilter}
                          onChange={(e) => setInventoryStatusFilter(e.target.value)}
                          className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 bg-white text-[#1d1d1f] focus:outline-none focus:ring-1 focus:ring-[#0071e3] shrink-0"
                        >
                          <option value="">전체</option>
                          <option value="위험">위험만</option>
                          <option value="과잉">과잉만</option>
                        </select>
                      </div>
                      <div className="p-4 overflow-auto" style={{ maxHeight: '420px' }}>
                        {safetyStockInventoryListLoading ? (
                          <p className="text-xs text-[#86868b] py-8 text-center">재고 목록 불러오는 중…</p>
                        ) : safetyStockInventoryList.length === 0 ? (
                          <p className="text-xs text-[#86868b] py-8 text-center">데이터 없음</p>
                        ) : (
                          <div className="w-full" style={{ minHeight: '320px' }}>
                            <ResponsiveContainer width="100%" height={Math.max(320, Math.min(400, safetyStockInventoryList.length * 28))}>
                              <BarChart
                                layout="vertical"
                                data={safetyStockInventoryList.map((row) => ({
                                  name: (row.Store_Name ?? '').trim() || '—',
                                  잠긴돈: Number(row.Frozen_Money) || 0,
                                  상태: (row.Status ?? '').trim() || '정상',
                                }))}
                                margin={{ top: 8, right: 24, left: 8, bottom: 8 }}
                              >
                                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                                <XAxis type="number" tickFormatter={(v) => `₩${(Number(v) || 0).toLocaleString()}`} />
                                <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
                                <Tooltip formatter={(value: number) => [`₩${(Number(value) || 0).toLocaleString()}`, '잠긴 돈']} labelFormatter={(label) => `매장: ${label ?? '—'}`} />
                                <Bar dataKey="잠긴돈" radius={[0, 4, 4, 0]} isAnimationActive={true}>
                                  {safetyStockInventoryList.map((row, i) => {
                                    const status = (row.Status ?? '').trim();
                                    let fill = '#3b82f6';
                                    if (status === '위험') fill = '#dc2626';
                                    else if (status === '과잉') fill = '#f59e0b';
                                    else if (status === '정상') fill = '#22c55e';
                                    return <Cell key={`cell-${i}`} fill={fill} />;
                                  })}
                                </Bar>
                              </BarChart>
                            </ResponsiveContainer>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* 우측: 관리자 코멘트 (매장 선택 후 메모 저장) */}
                    <div className="rounded-xl border border-gray-200 overflow-hidden bg-white flex flex-col">
                      <div className="px-4 py-3 border-b border-gray-200 bg-[#f5f5f7]">
                        <h3 className="text-sm font-semibold text-[#1d1d1f]">관리자 코멘트</h3>
                        <p className="text-xs text-[#86868b] mt-0.5">
                          매장 선택 후 메모 저장 →
                          <span className="ml-1 text-[10px]">backend/data/inventory_comments.csv (재시작 후에도 유지)</span>
                        </p>
                      </div>
                      <div className="p-4 flex-1 flex flex-col gap-3 min-h-0">
                        <div>
                          <label className="block text-xs font-medium text-[#6e6e73] mb-1">매장 선택</label>
                          <select
                            value={selectedStoreForNote ?? ''}
                            onChange={(e) => { const v = e.target.value; setSelectedStoreForNote(v || null); }}
                            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-[#1d1d1f] focus:outline-none focus:ring-1 focus:ring-[#0071e3]"
                          >
                            <option value="">선택하세요</option>
                            {Array.from(new Set(safetyStockInventoryList.map((r) => r.Store_Name))).sort().map((name) => (
                              <option key={name} value={name}>{name}</option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-[#6e6e73] mb-1">메모 (조치 사항)</label>
                          <textarea
                            value={managerNoteInput}
                            onChange={(e) => setManagerNoteInput(e.target.value)}
                            placeholder="예: 15% 할인 행사 기획 중 (김팀장)"
                            rows={3}
                            className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-[#1d1d1f] focus:outline-none focus:ring-1 focus:ring-[#0071e3] resize-none"
                          />
                        </div>
                        <button
                          type="button"
                          disabled={!selectedStoreForNote?.trim() || !managerNoteInput.trim() || saveCommentLoading}
                          onClick={async () => {
                            if (!selectedStoreForNote?.trim() || !managerNoteInput.trim()) return;
                            setSaveCommentLoading(true);
                            try {
                              const res = await fetch('/api/inventory-comments', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ store_name: selectedStoreForNote, comment: managerNoteInput, author: '관리자' }),
                              });
                              const data = await res.json().catch(() => ({}));
                              if (res.ok && data?.comments) {
                                setInventoryComments(data.comments);
                                setManagerNoteInput('');
                              }
                            } finally {
                              setSaveCommentLoading(false);
                            }
                          }}
                          className="w-full py-2 rounded-lg bg-[#0071e3] text-white text-sm font-medium hover:bg-[#0077ed] disabled:opacity-50 disabled:pointer-events-none"
                        >
                          {saveCommentLoading ? '저장 중…' : '저장'}
                        </button>
                        <div className="flex-1 overflow-auto border-t border-gray-100 pt-3 mt-2">
                          <p className="text-xs font-medium text-[#6e6e73] mb-2">저장된 코멘트</p>
                          {inventoryCommentsLoading ? (
                            <p className="text-xs text-[#86868b]">불러오는 중…</p>
                          ) : inventoryComments.length === 0 ? (
                            <p className="text-xs text-[#86868b]">아직 없음</p>
                          ) : (
                            <ul className="space-y-2">
                              {inventoryComments.map((c, i) => (
                                <li key={i} className="text-xs p-2 rounded-lg bg-gray-50 border border-gray-100">
                                  <span className="font-medium text-[#1d1d1f]">{(c.store_name || c.product_name) || '—'}</span>
                                  <span className="text-[#86868b] ml-1">· {c.created_at} {c.author ? `(${c.author})` : ''}</span>
                                  <p className="mt-1 text-[#1d1d1f]">{c.comment}</p>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                </>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {/* 수요 대시보드 오버레이 */}
      {showDemandDashboard ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
          onClick={() => { setShowDemandDashboard(false); setSelectedProductForChart(null); setSelectedCategoryForChart(null); setSelectedCategoryFilter(null); }}
        >
          <div
            className="bg-white rounded-2xl border border-gray-200 shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 shrink-0">
              <div>
                <h2 className="text-xl font-bold text-[#1d1d1f]">수요 대시보드</h2>
                <p className="text-xs text-[#86868b] mt-0.5">데이터: prediction model.py (모델 서버 연동)</p>
              </div>
              <button
                type="button"
                onClick={() => setShowDemandDashboard(false)}
                className="p-2 rounded-lg hover:bg-gray-100 text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
                aria-label="닫기"
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-auto p-6">
              {/* 선택 지역 · 총 수요 (좌) | 카테고리별 수요 100% (우) */}
              {(selectedContinent || selectedCountry || selectedStoreId || selectedCity) && (
                <div className="flex flex-col md:flex-row gap-4 mb-6">
                  <div className="flex-shrink-0 md:w-[280px]">
                    <div className="mb-4">
                      <p className="text-sm text-[#6e6e73] mb-1">선택 지역</p>
                      <p className="text-lg font-semibold text-[#1d1d1f]">
                        {selectedContinent
                          ? (continentPieData.find((c) => c.continent === selectedContinent)?.continent_ko ?? selectedContinent)
                          : selectedCountry
                            ? formatCountryDisplay(selectedCountry)
                            : selectedStoreId
                              ? formatStoreDisplay(selectedStoreId)
                              : selectedCity}
                        {selectedContinent ? ' (대륙 전체)' : selectedCountry ? ' (국가 전체)' : selectedStoreId ? ' (스토어)' : ` (도시, ${selectedYear}년)`}
                      </p>
                    </div>
                    <div className="bg-[#f5f5f7] rounded-xl p-4">
                      <p className="text-sm text-[#6e6e73] mb-1">총 수요 (판매 {QUANTITY_LABEL}, {selectedYear}년)</p>
                      <p className="text-2xl font-bold text-[#1d1d1f]">
                        {demandTotalDisplay != null ? `${demandTotalDisplay.toLocaleString()}${QUANTITY_UNIT}` : '—'}
                      </p>
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium text-[#6e6e73] mb-3">카테고리별 수요 (전체 100% 기준)</h3>
                    {demandCategoryPercentData.length === 0 ? (
                      <p className="text-[#86868b] text-sm py-4">카테고리별 데이터가 없습니다.</p>
                    ) : (
                      <div className="h-[280px] w-full rounded-xl border border-gray-200 bg-white p-3">
                        <ResponsiveContainer width="100%" height="100%">
                          <PieChart>
                            <Pie
                              data={demandCategoryPercentData}
                              cx="50%"
                              cy="50%"
                              innerRadius="42%"
                              outerRadius="70%"
                              paddingAngle={2}
                              dataKey="value"
                              label={false}
                            >
                              {demandCategoryPercentData.map((_, i) => (
                                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip content={<PieTooltipContent />} contentStyle={{ backgroundColor: 'transparent', border: 'none' }} />
                            <Legend
                              wrapperStyle={{ overflow: 'hidden' }}
                              formatter={(_, entry: { payload?: { name?: string; value?: number } }) =>
                                `${entry.payload?.name ?? ''} ${(entry.payload?.value ?? 0).toFixed(1)}%`
                              }
                            />
                          </PieChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* 2020~2024 기준 2025년 예측 판매 수량 */}
              <div className="mb-6 pb-6 border-b border-gray-200">
                <h3 className="text-sm font-medium text-[#6e6e73] mb-2">2020~2024 데이터 기준 2025년 예측 판매 {QUANTITY_LABEL}</h3>
                {forecastLoading ? (
                  <p className="text-[#6e6e73] text-sm">예측 불러오는 중...</p>
                ) : forecastData ? (
                  <>
                    <div className="bg-[#f5f5f7] rounded-xl p-4 mb-3">
                      <p className="text-sm text-[#6e6e73] mb-1">2025년 예측 판매 {QUANTITY_LABEL} ({forecastData.method === 'arima' ? 'ARIMA' : '선형 추세'})</p>
                      <p className="text-2xl font-bold text-[#1d1d1f]">
                        {forecastData.predicted_quantity_2025.toLocaleString()}{QUANTITY_UNIT}
                      </p>
                    </div>
                    <p className="text-xs text-[#86868b] mb-2">2020~2024 연도별 실적</p>
                    {forecastData.yearly_quantity.length > 0 ? (
                      <div className="flex flex-col md:flex-row gap-4">
                        <div className="overflow-x-auto rounded-lg border border-gray-200 shrink-0">
                          <table className="w-full text-sm min-w-[140px]">
                            <thead>
                              <tr className="bg-[#f5f5f7] text-[#6e6e73] text-left">
                                <th className="px-3 py-2 rounded-tl-lg">연도</th>
                                <th className="px-3 py-2 text-right rounded-tr-lg">{QUANTITY_LABEL}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {forecastData.yearly_quantity.map((r) => (
                                <tr key={r.year} className="border-t border-gray-100">
                                  <td className="px-3 py-1.5 text-[#1d1d1f]">{r.year}년</td>
                                  <td className="px-3 py-1.5 text-[#1d1d1f] text-right font-medium">{r.quantity.toLocaleString()}{QUANTITY_UNIT}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <div className="flex-1 min-w-0 rounded-lg border border-gray-200 bg-white p-3" style={{ minHeight: 200 }}>
                          <p className="text-xs text-[#6e6e73] mb-2">연도별 판매 {QUANTITY_LABEL}</p>
                          <ResponsiveContainer width="100%" height={180}>
                            <ComposedChart
                              data={[
                                ...forecastData.yearly_quantity.map((r) => ({ year: r.year, quantity: r.quantity, isPredicted: false })),
                                { year: 2025, quantity: forecastData.predicted_quantity_2025, isPredicted: true },
                              ]}
                              margin={{ top: 8, right: 16, left: 8, bottom: 24 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                              <XAxis dataKey="year" tick={{ fontSize: 11 }} stroke="#6e6e73" />
                              <YAxis tick={{ fontSize: 11 }} stroke="#6e6e73" tickFormatter={(v) => v.toLocaleString()} />
                              <Tooltip
                                formatter={(value: number, _name: string, props: { payload?: { isPredicted?: boolean } }) => [
                                  `${Number(value).toLocaleString()}${QUANTITY_UNIT}`,
                                  props?.payload?.isPredicted ? '2025년(예측)' : '실적',
                                ]}
                                labelFormatter={(label) => `${label}년`}
                              />
                              <Bar dataKey="quantity" radius={[4, 4, 0, 0]} name={QUANTITY_LABEL}>
                                {[
                                  ...forecastData.yearly_quantity.map((r) => ({ year: r.year, quantity: r.quantity, isPredicted: false })),
                                  { year: 2025, quantity: forecastData.predicted_quantity_2025, isPredicted: true },
                                ].map((_, index) => (
                                  <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                                ))}
                              </Bar>
                              <Line
                                type="monotone"
                                dataKey="quantity"
                                stroke="#0f172a"
                                strokeWidth={2}
                                dot={{ r: 4, fill: '#0f172a' }}
                                activeDot={{ r: 6, fill: '#0f172a', stroke: '#fff', strokeWidth: 2 }}
                                connectNulls
                                name={QUANTITY_LABEL}
                              />
                            </ComposedChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    ) : null}
                    <p className="text-xs text-[#86868b] mt-2">2020~2024 합계: {forecastData.total_quantity_2020_2024.toLocaleString()}{QUANTITY_UNIT}</p>
                  </>
                ) : (
                  <p className="text-[#86868b] text-sm">예측 데이터를 불러올 수 없습니다. (prediction model.py 연동 확인)</p>
                )}
              </div>

              {/* 카테고리별 수량 · 상품별 수량 가로 배치 */}
              <div className="mb-6 flex flex-col md:flex-row gap-4">
                {/* 카테고리별 수량 (2020~2024 실적 + 2025 예측) */}
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-[#6e6e73] mb-3">카테고리별 {QUANTITY_LABEL} (2020~2025)</h3>
                  {categoryDemandDisplay.length > 0 ? (
                    <div className="overflow-x-auto rounded-xl border border-gray-200 max-h-[280px] overflow-y-auto">
                      <table className="w-full text-sm min-w-[320px]">
                        <thead className="sticky top-0 bg-[#f5f5f7]">
                          <tr className="text-[#6e6e73] text-left">
                            <th className="px-3 py-3 rounded-tl-xl">카테고리</th>
                            {[2020, 2021, 2022, 2023, 2024].map((y) => (
                              <th key={y} className="px-2 py-3 text-right">{y}년</th>
                            ))}
                            <th className="px-3 py-3 text-right rounded-tr-xl">2025년(예측)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {categoryDemandDisplay.map((c) => {
                            const isSelected = selectedCategoryFilter === c.category;
                            return (
                            <tr key={c.category} className={`border-t border-gray-100 hover:bg-gray-50 ${isSelected ? 'bg-[#e8f4fd]' : ''}`}>
                              <td
                                className="px-3 py-2 text-[#1d1d1f] font-medium cursor-pointer hover:text-[#0071e3] hover:underline"
                                onClick={() => {
                                  if (isSelected) {
                                    setSelectedCategoryForChart(null);
                                    setSelectedCategoryFilter(null);
                                  } else {
                                    setSelectedCategoryForChart(c);
                                    setSelectedCategoryFilter(c.category);
                                  }
                                }}
                                role="button"
                                tabIndex={0}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    if (isSelected) {
                                      setSelectedCategoryForChart(null);
                                      setSelectedCategoryFilter(null);
                                    } else {
                                      setSelectedCategoryForChart(c);
                                      setSelectedCategoryFilter(c.category);
                                    }
                                  }
                                }}
                              >
                                {c.category || ''}
                              </td>
                              {[2020, 2021, 2022, 2023, 2024].map((y) => {
                                const q = (c as unknown as Record<string, number | undefined>)[`quantity_${y}`];
                                const num = typeof q === 'number' ? q : (typeof q === 'string' ? parseInt(String(q), 10) : NaN);
                                const display = !Number.isNaN(num) ? `${num.toLocaleString()}${QUANTITY_UNIT}` : `0${QUANTITY_UNIT}`;
                                return (
                                  <td key={y} className="px-2 py-2 text-[#1d1d1f] text-right">{display}</td>
                                );
                              })}
                              <td className="px-3 py-2 text-[#1d1d1f] text-right font-medium">
                                {typeof c.predicted_quantity === 'number' ? `${c.predicted_quantity.toLocaleString()}${QUANTITY_UNIT}` : (c.predicted_quantity != null ? `${Number(c.predicted_quantity).toLocaleString()}${QUANTITY_UNIT}` : `0${QUANTITY_UNIT}`)}
                              </td>
                            </tr>
                          );})}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-[#86868b] text-sm py-4">카테고리별 수요 데이터가 없습니다.</p>
                  )}
                </div>

                {/* 상품별 수량 (2020~2024 실적 + 2025 예측) */}
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-[#6e6e73] mb-3">
                    상품별 {QUANTITY_LABEL} (2020~2025)
                    {selectedCategoryFilter && (
                      <span className="ml-2 text-[#0071e3]">
                        · {selectedCategoryFilter}
                        <button
                          type="button"
                          onClick={() => { setSelectedCategoryFilter(null); setSelectedCategoryForChart(null); }}
                          className="ml-1 text-xs underline hover:no-underline"
                        >
                          (전체 보기)
                        </button>
                      </span>
                    )}
                  </h3>
                  {!demandDashboardData && productDemandLoading ? (
                    <p className="text-[#6e6e73] text-sm">불러오는 중...</p>
                  ) : productDemandDisplay && productDemandDisplay.length > 0 ? (
                    <div className="overflow-x-auto rounded-xl border border-gray-200 max-h-[280px] overflow-y-auto">
                      <table className="w-full text-sm min-w-[320px]">
                        <thead className="sticky top-0 bg-[#f5f5f7]">
                          <tr className="text-[#6e6e73] text-left">
                            <th className="px-3 py-3 rounded-tl-xl">상품명</th>
                            {[2020, 2021, 2022, 2023, 2024].map((y) => (
                              <th key={y} className="px-2 py-3 text-right">{y}년</th>
                            ))}
                            <th className="px-3 py-3 text-right rounded-tr-xl">2025년(예측)</th>
                          </tr>
                        </thead>
                        <tbody>
                          {productDemandDisplay.map((p) => (
                            <tr key={p.product_id} className="border-t border-gray-100 hover:bg-gray-50">
                              <td
                                className="px-3 py-2 text-[#1d1d1f] font-medium cursor-pointer hover:text-[#0071e3] hover:underline"
                                onClick={() => setSelectedProductForChart(selectedProductForChart?.product_id === p.product_id ? null : p)}
                                role="button"
                                tabIndex={0}
                                onKeyDown={(e) => e.key === 'Enter' && setSelectedProductForChart(selectedProductForChart?.product_id === p.product_id ? null : p)}
                              >
                                {p.product_name || ''}
                              </td>
                              {[2020, 2021, 2022, 2023, 2024].map((y) => {
                                const q = (p as unknown as Record<string, number | undefined>)[`quantity_${y}`];
                                const num = typeof q === 'number' ? q : (typeof q === 'string' ? parseInt(String(q), 10) : NaN);
                                const display = !Number.isNaN(num) ? `${num.toLocaleString()}${QUANTITY_UNIT}` : `0${QUANTITY_UNIT}`;
                                return (
                                  <td key={y} className="px-2 py-2 text-[#1d1d1f] text-right">{display}</td>
                                );
                              })}
                              <td className="px-3 py-2 text-[#1d1d1f] text-right font-medium">
                                {typeof p.predicted_quantity === 'number' ? `${p.predicted_quantity.toLocaleString()}${QUANTITY_UNIT}` : (p.predicted_quantity != null ? `${Number(p.predicted_quantity).toLocaleString()}${QUANTITY_UNIT}` : `0${QUANTITY_UNIT}`)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : selectedCategoryFilter && productDemandDisplay && productDemandDisplay.length === 0 ? (
                    <p className="text-[#86868b] text-sm py-4">{selectedCategoryFilter} 카테고리에 해당하는 상품이 없습니다.</p>
                  ) : (
                    <p className="text-[#86868b] text-sm py-4">상품별 수요 데이터가 없습니다. (prediction model.py)</p>
                  )}
                </div>
              </div>

              {/* 연도별 판매수량 스캐터 라인 그래프 (카테고리명 클릭 시) */}
              {selectedCategoryForChart && (
                <div className="mb-6 p-4 rounded-xl border border-gray-200 bg-[#f5f5f7]/50">
                  <h3 className="text-sm font-medium text-[#6e6e73] mb-3">
                    {selectedCategoryForChart.category} 연도별 판매 {QUANTITY_LABEL}
                    <button
                      type="button"
                      onClick={() => setSelectedCategoryForChart(null)}
                      className="ml-2 text-xs text-[#86868b] hover:text-[#1d1d1f]"
                    >
                      (닫기)
                    </button>
                  </h3>
                  <div className="h-[240px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart
                        data={yearlyToQuarterly([
                          { year: 2020, quantity: (selectedCategoryForChart as unknown as Record<string, number>).quantity_2020 ?? 0, isPredicted: false },
                          { year: 2021, quantity: (selectedCategoryForChart as unknown as Record<string, number>).quantity_2021 ?? 0, isPredicted: false },
                          { year: 2022, quantity: (selectedCategoryForChart as unknown as Record<string, number>).quantity_2022 ?? 0, isPredicted: false },
                          { year: 2023, quantity: (selectedCategoryForChart as unknown as Record<string, number>).quantity_2023 ?? 0, isPredicted: false },
                          { year: 2024, quantity: (selectedCategoryForChart as unknown as Record<string, number>).quantity_2024 ?? 0, isPredicted: false },
                          { year: 2025, quantity: selectedCategoryForChart.predicted_quantity ?? 0, isPredicted: true },
                        ])}
                        margin={{ top: 8, right: 20, left: 8, bottom: -40 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                        <XAxis dataKey="label" tick={{ fontSize: 10, dy: 20 }} stroke="#6e6e73" interval={0} angle={-35} textAnchor="end" height={90} />
                        <YAxis tick={{ fontSize: 12 }} stroke="#6e6e73" tickFormatter={(v) => v.toLocaleString()} />
                        <Tooltip content={<QuarterlyChartTooltip />} />
                        <Line
                          type="monotone"
                          dataKey="quantity"
                          stroke="#10b981"
                          strokeWidth={2}
                          dot={false}
                          activeDot={false}
                          connectNulls
                          name={QUANTITY_LABEL}
                        />
                        <Scatter
                          dataKey="quantity"
                          fill="#10b981"
                          shape="circle"
                          r={6}
                          name={QUANTITY_LABEL}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* 연도별 판매수량 스캐터 라인 그래프 (상품명 클릭 시) */}
              {selectedProductForChart && (
                <div className="mb-6 p-4 rounded-xl border border-gray-200 bg-[#f5f5f7]/50">
                  <h3 className="text-sm font-medium text-[#6e6e73] mb-3">
                    {selectedProductForChart.product_name} 연도별 판매 {QUANTITY_LABEL}
                    <button
                      type="button"
                      onClick={() => setSelectedProductForChart(null)}
                      className="ml-2 text-xs text-[#86868b] hover:text-[#1d1d1f]"
                    >
                      (닫기)
                    </button>
                  </h3>
                  <div className="h-[240px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart
                        data={(() => {
                          const p = selectedProductForChart as unknown as Record<string, number | undefined>;
                          const actualStart = typeof p.launch_year === 'number' && p.launch_year >= 2020 && p.launch_year <= 2025
                            ? p.launch_year
                            : 2020;
                          const years: number[] = [];
                          for (let y = actualStart; y <= 2025; y++) years.push(y);
                          const yearly = years.map((year) => {
                            const isPredicted = year === 2025;
                            const qty = isPredicted
                              ? (p.predicted_quantity ?? 0)
                              : (p[`quantity_${year}` as keyof typeof p] as number | undefined) ?? 0;
                            return { year, quantity: qty, isPredicted };
                          });
                          return yearlyToQuarterly(yearly);
                        })()}
                        margin={{ top: 8, right: 20, left: 8, bottom: -40 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                        <XAxis dataKey="label" tick={{ fontSize: 10, dy: 20 }} stroke="#6e6e73" interval={0} angle={-35} textAnchor="end" height={90} />
                        <YAxis tick={{ fontSize: 12 }} stroke="#6e6e73" tickFormatter={(v) => v.toLocaleString()} />
                        <Tooltip content={<QuarterlyChartTooltip />} />
                        <Line
                          type="monotone"
                          dataKey="quantity"
                          stroke="#0071e3"
                          strokeWidth={2}
                          dot={false}
                          activeDot={false}
                          connectNulls
                          name={QUANTITY_LABEL}
                        />
                        <Scatter
                          dataKey="quantity"
                          fill="#0071e3"
                          shape="circle"
                          r={6}
                          name={QUANTITY_LABEL}
                        />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {!(selectedContinent || selectedCountry || selectedStoreId || selectedCity) && (
                <p className="text-[#6e6e73] text-center py-8">
                  지도에서 대륙·국가·스토어·도시를 선택하면 해당 지역의 수요(판매 수량) 데이터를 볼 수 있습니다.
                </p>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {/* 모델 서버 데이터 소스 (SQL ↔ 대시보드 연동) */}
      {dataSourceInfo && (dataSourceInfo.source === 'sql' || dataSourceInfo.source === 'csv') && (
        <p className="text-center text-xs text-[#86868b] py-4">
          데이터: {dataSourceInfo.source === 'sql'
            ? `SQL (${dataSourceInfo.sql_file_count}개 파일)`
            : 'CSV'}
        </p>
      )}
    </main>
  );
}
