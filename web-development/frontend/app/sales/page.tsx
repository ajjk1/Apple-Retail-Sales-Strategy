'use client';

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import Link from 'next/link';
import { ComposedChart, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend, Area, Line, Scatter } from 'recharts';
import { apiGet } from '../../lib/api';
import { formatCityDisplay, formatCountryDisplay, formatStoreDisplay, getContinentForCountry, resolveCountryToEn, stripApplePrefix } from '../../lib/country';

// 카테고리 9개+ 지원 (바/파이 동일 색상 매핑용)
const BAR_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1', '#14b8a6', '#a855f7'];

export default function SalesPage() {
  const [loading, setLoading] = useState(true);
  const [selectedContinentTab, setSelectedContinentTab] = useState<string | null>(null);
  const [selectedCountryForStores, setSelectedCountryForStores] = useState<string | null>(null);
  const [selectedCountryForCategory, setSelectedCountryForCategory] = useState<string | null>(null);
  const [selectedCountryForStoreSales, setSelectedCountryForStoreSales] = useState<string | null>(null);
  const [countryCategoryData, setCountryCategoryData] = useState<{ category: string; total_sales: number }[]>([]);
  const [countryCategoryLoading, setCountryCategoryLoading] = useState(false);
  const [countryStoreData, setCountryStoreData] = useState<{ sales_by_store: { store_name: string; total_sales: number }[]; sales_by_store_by_year: { store_name: string; year: number; total_sales: number }[] } | null>(null);
  const [countryStoreLoading, setCountryStoreLoading] = useState(false);
  const [selectedStoreForQuarterly, setSelectedStoreForQuarterly] = useState<{ store_name: string; display_label: string } | null>(null);
  const [quarterlyData, setQuarterlyData] = useState<{ period: string; year: number; quarter: number; total_sales: number }[]>([]);
  const [quarterlyCategoryData, setQuarterlyCategoryData] = useState<{ period: string; year: number; quarter: number; category: string; total_sales: number }[]>([]);
  const [quarterlyLoading, setQuarterlyLoading] = useState(false);
  const [selectedCategoryForBarChart, setSelectedCategoryForBarChart] = useState<string | null>(null);
  const [storePerformanceGrade, setStorePerformanceGrade] = useState<{
    store_performance: { country: string; store_name: string; total_sales: number; target_annual: number; achievement_rate: number; grade: string }[];
    grade_distribution: { grade: string; count: number; pct: number }[];
    annual_forecast_revenue: number;
  } | null>(null);
  const [data, setData] = useState<{
    total_sum: number;
    store_count: number;
    sales_by_year: { year: number; total_sales: number; is_forecast?: boolean }[];
    predicted_sales_2025?: number;
    forecast_method?: string;
    top_stores: { store_id: string; city: string; country: string; total_sales: number }[];
    stores?: { store_id: string; city: string; country: string; total_sales: number }[];
    sales_by_country?: { country: string; total_sales: number }[];
    sales_by_city?: { city: string; country: string; total_sales: number }[];
    sales_by_store?: { store_name: string; total_sales: number }[];
    sales_by_store_by_year?: { store_name: string; year: number; total_sales: number }[];
  } | null>(null);

  const fetchSalesData = useCallback(() => {
    setLoading(true);
    apiGet<{ total_sum?: number; store_count?: number; sales_by_year?: unknown[]; predicted_sales_2025?: number; forecast_method?: string; top_stores?: unknown[]; stores?: unknown[]; sales_by_country?: { country: string; total_sales: number }[]; sales_by_city?: { city: string; country: string; total_sales: number }[]; sales_by_store?: { store_name: string; total_sales: number }[]; sales_by_store_by_year?: { store_name: string; year: number; total_sales: number }[] }>('/api/sales-summary')
      .then((json) => {
        if (json) {
          setData({
            total_sum: json.total_sum ?? 0,
            store_count: json.store_count ?? 0,
            sales_by_year: (json.sales_by_year ?? []) as { year: number; total_sales: number; is_forecast?: boolean }[],
            predicted_sales_2025: json.predicted_sales_2025 ?? 0,
            forecast_method: json.forecast_method ?? 'linear_trend',
            top_stores: (json.top_stores ?? []) as { store_id: string; city: string; country: string; total_sales: number }[],
            stores: (json.stores ?? json.top_stores ?? []) as { store_id: string; city: string; country: string; total_sales: number }[],
            sales_by_country: (json.sales_by_country ?? []) as { country: string; total_sales: number }[],
            sales_by_city: (json.sales_by_city ?? []) as { city: string; country: string; total_sales: number }[],
            sales_by_store: (json.sales_by_store ?? []) as { store_name: string; total_sales: number }[],
            sales_by_store_by_year: (json.sales_by_store_by_year ?? []) as { store_name: string; year: number; total_sales: number }[],
          });
        } else setData(null);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchSalesData();
  }, [fetchSalesData]);

  useEffect(() => {
    apiGet<{ store_performance?: unknown[]; grade_distribution?: { grade: string; count: number; pct: number }[]; annual_forecast_revenue?: number }>('/api/store-performance-grade')
      .then((json) => {
        if (json && Array.isArray(json.store_performance)) {
          setStorePerformanceGrade({
            store_performance: json.store_performance as { country: string; store_name: string; total_sales: number; target_annual: number; achievement_rate: number; grade: string }[],
            grade_distribution: (json.grade_distribution ?? []) as { grade: string; count: number; pct: number }[],
            annual_forecast_revenue: json.annual_forecast_revenue ?? 0,
          });
        } else setStorePerformanceGrade(null);
      })
      .catch(() => setStorePerformanceGrade(null));
  }, []);

  // 로딩이 15초 이상 지속되면 강제 해제 → 에러/재시도 화면 표시 (백엔드 미응답 시 멈춤 방지)
  useEffect(() => {
    if (!loading) return;
    const t = setTimeout(() => {
      setLoading(false);
      setData(null);
    }, 15000);
    return () => clearTimeout(t);
  }, [loading]);

  useEffect(() => {
    if (!selectedCountryForCategory?.trim()) {
      setCountryCategoryData([]);
      setCountryCategoryLoading(false);
      return;
    }
    setCountryCategoryLoading(true);
    const countryEn = resolveCountryToEn(selectedCountryForCategory);
    apiGet<{ categories?: { category: string; total_sales: number }[] }>(
      `/api/sales-by-country-category?country=${encodeURIComponent(countryEn)}`
    )
      .then((json) => setCountryCategoryData((json?.categories ?? []) as { category: string; total_sales: number }[]))
      .catch(() => setCountryCategoryData([]))
      .finally(() => setCountryCategoryLoading(false));
  }, [selectedCountryForCategory]);

  useEffect(() => {
    if (!selectedCountryForStoreSales?.trim()) {
      setCountryStoreData(null);
      setCountryStoreLoading(false);
      return;
    }
    setCountryStoreLoading(true);
    const countryEn = resolveCountryToEn(selectedCountryForStoreSales);
    apiGet<{ sales_by_store?: { store_name: string; total_sales: number }[]; sales_by_store_by_year?: { store_name: string; year: number; total_sales: number }[] }>(
      `/api/sales-by-store?country=${encodeURIComponent(countryEn)}`
    )
      .then((json) => setCountryStoreData({ sales_by_store: json?.sales_by_store ?? [], sales_by_store_by_year: json?.sales_by_store_by_year ?? [] }))
      .catch(() => setCountryStoreData(null))
      .finally(() => setCountryStoreLoading(false));
  }, [selectedCountryForStoreSales]);

  useEffect(() => {
    if (!selectedStoreForQuarterly?.store_name?.trim()) {
      setQuarterlyData([]);
      setQuarterlyCategoryData([]);
      setQuarterlyLoading(false);
      setSelectedCategoryForBarChart(null);
      return;
    }
    setQuarterlyLoading(true);
    setSelectedCategoryForBarChart(null);
    const params = new URLSearchParams({ store_name: selectedStoreForQuarterly.store_name });
    if (selectedCountryForStoreSales?.trim()) {
      params.set('country', resolveCountryToEn(selectedCountryForStoreSales));
    }
    const base = `/api/sales-by-store-quarterly?${params.toString()}`;
    const baseCat = `/api/sales-by-store-quarterly-by-category?${params.toString()}`;
    Promise.all([
      apiGet<{ quarterly?: { period: string; year: number; quarter: number; total_sales: number }[] }>(base),
      apiGet<{ quarterly_by_category?: { period: string; year: number; quarter: number; category: string; total_sales: number }[] }>(baseCat),
    ])
      .then(([json, jsonCat]) => {
        setQuarterlyData((json?.quarterly ?? []) as { period: string; year: number; quarter: number; total_sales: number }[]);
        setQuarterlyCategoryData((jsonCat?.quarterly_by_category ?? []) as { period: string; year: number; quarter: number; category: string; total_sales: number }[]);
      })
      .catch(() => {
        setQuarterlyData([]);
        setQuarterlyCategoryData([]);
      })
      .finally(() => setQuarterlyLoading(false));
  }, [selectedStoreForQuarterly, selectedCountryForStoreSales]);

  // sales_by_country 우선 (전체 국가), 없으면 top_stores에서 국가별 집계
  const countrySalesData = useMemo(() => {
    const raw = data?.sales_by_country?.length
      ? data.sales_by_country
      : (data?.top_stores ?? []).reduce<{ country: string; total_sales: number }[]>((acc, s) => {
          const cur = acc.find((x) => x.country === s.country);
          if (cur) cur.total_sales += s.total_sales;
          else acc.push({ country: s.country, total_sales: s.total_sales });
          return acc;
        }, []);
    if (!raw.length) return [];
    return raw
      .map(({ country, total_sales }) => ({
        country,
        countryLabel: formatCountryDisplay(country),
        continent: getContinentForCountry(country),
        sales: total_sales,
        name: formatCountryDisplay(country),
      }))
      .sort((a, b) => b.sales - a.sales);
  }, [data]);

  // 대륙별 매출 집계 (국가 포함)
  const continentSalesData = useMemo(() => {
    if (!countrySalesData.length) return [];
    const byContinent = new Map<string, { sales: number; countries: { country: string; countryLabel: string; sales: number }[] }>();
    countrySalesData.forEach((d) => {
      const cur = byContinent.get(d.continent) ?? { sales: 0, countries: [] };
      cur.sales += d.sales;
      cur.countries.push({ country: d.country, countryLabel: d.countryLabel, sales: d.sales });
      byContinent.set(d.continent, cur);
    });
    return Array.from(byContinent.entries())
      .map(([continent, v]) => ({
        continent,
        continentLabel: `${continent}`,
        sales: v.sales,
        countries: v.countries.sort((a, b) => b.sales - a.sales),
      }))
      .sort((a, b) => b.sales - a.sales);
  }, [countrySalesData]);

  // 탭 선택 시: 전체=대륙별, 특정 대륙=해당 대륙 국가별 (country: 클릭 시 스토어 필터용)
  // 총매출 100% 기준 비율(%)로 변환
  const continentChartData = useMemo(() => {
    if (!countrySalesData.length) return [];
    if (selectedContinentTab) {
      const cont = continentSalesData.find((c) => c.continent === selectedContinentTab);
      if (!cont?.countries?.length) return [];
      const total = cont.countries.reduce((a, c) => a + c.sales, 0) || 1;
      return cont.countries.map((c) => ({
        label: c.countryLabel,
        country: c.country,
        sales: c.sales,
        pct: Math.round((c.sales / total) * 1000) / 10,
        name: c.countryLabel,
      }));
    }
    // 전체: 대륙별 표시 (%)
    const total = continentSalesData.reduce((a, d) => a + d.sales, 0) || 1;
    return continentSalesData.map((c) => ({
      label: c.continent,
      country: '', // 대륙 선택 시 국가 클릭 불가
      sales: c.sales,
      pct: Math.round((c.sales / total) * 1000) / 10,
      name: c.continent,
    }));
  }, [countrySalesData, continentSalesData, selectedContinentTab]);

  // Store_Name별 연간 매출 (매장별 바차트용) — 국가 클릭 시 해당 국가 스토어만, 아니면 전체
  const storeSalesData = useMemo(() => {
    if (selectedCountryForStoreSales) {
      // 국가 선택 시: 로딩 중이면 [], 완료되면 countryStoreData만 사용 (전역 데이터로 폴백 금지)
      if (countryStoreLoading) return [];
      return (countryStoreData?.sales_by_store ?? []);
    }
    const byStore = data?.sales_by_store ?? [];
    if (byStore.length > 0) return byStore;
    const stores = data?.top_stores ?? data?.stores ?? [];
    return stores.map((s) => ({
      store_name: s.city ? `${s.store_id} (${formatCityDisplay(s.city)})` : (s.store_id || ''),
      total_sales: s.total_sales ?? 0,
    })).sort((a, b) => b.total_sales - a.total_sales).slice(0, 50);
  }, [data?.sales_by_store, data?.top_stores, data?.stores, selectedCountryForStoreSales, countryStoreLoading, countryStoreData?.sales_by_store]);

  // 국가별 카테고리별 차트 데이터 (총매출 100% 기준)
  const countryCategoryChartData = useMemo(() => {
    if (!countryCategoryData.length) return [];
    const total = countryCategoryData.reduce((a, d) => a + d.total_sales, 0) || 1;
    return countryCategoryData
      .map((d) => ({
        label: d.category,
        category: d.category,
        sales: d.total_sales,
        pct: Math.round((d.total_sales / total) * 1000) / 10,
      }))
      .sort((a, b) => b.sales - a.sales);
  }, [countryCategoryData]);

  // 매장 선택 시 카테고리별 3개월 단위 매출 차트용 (period별로 category 키로 펼침)
  const quarterlyCategoryChartData = useMemo(() => {
    if (!quarterlyCategoryData.length) return [];
    const periods = Array.from(new Set(quarterlyCategoryData.map((d) => d.period))).sort();
    const categories = Array.from(new Set(quarterlyCategoryData.map((d) => d.category))).sort();
    const byPeriod = new Map<string, Record<string, number>>();
    quarterlyCategoryData.forEach((d) => {
      if (!byPeriod.has(d.period)) byPeriod.set(d.period, {});
      byPeriod.get(d.period)![d.category] = d.total_sales;
    });
    return periods.map((period) => {
      const row: Record<string, string | number> = { period };
      categories.forEach((cat) => {
        row[cat] = byPeriod.get(period)?.[cat] ?? 0;
      });
      return row;
    });
  }, [quarterlyCategoryData]);

  // 선택 매장의 카테고리별 총 매출 (파이 차트용: 전체 기간 합계)
  const quarterlyCategoryPieData = useMemo(() => {
    if (!quarterlyCategoryData.length) return [];
    const byCategory = new Map<string, number>();
    quarterlyCategoryData.forEach((d) => {
      byCategory.set(d.category, (byCategory.get(d.category) ?? 0) + d.total_sales);
    });
    const total = Array.from(byCategory.values()).reduce((a, b) => a + b, 0) || 1;
    return Array.from(byCategory.entries())
      .map(([name, value]) => ({ name, value, pct: Math.round((value / total) * 1000) / 10 }))
      .sort((a, b) => b.value - a.value);
  }, [quarterlyCategoryData]);

  // 분기 데이터는 있으나 카테고리 API가 빈 경우: 분기 합계를 "(전체)"로 바/파이 표시
  const quarterlyCategoryChartDataFallback = useMemo(() => {
    if (quarterlyData.length === 0 || quarterlyCategoryChartData.length > 0) return [];
    return quarterlyData.map((d) => ({ period: d.period, '(전체)': d.total_sales }));
  }, [quarterlyData, quarterlyCategoryChartData.length]);
  const quarterlyCategoryPieDataFallback = useMemo(() => {
    if (quarterlyData.length === 0 || quarterlyCategoryPieData.length > 0) return [];
    const total = quarterlyData.reduce((a, d) => a + d.total_sales, 0) || 1;
    return [{ name: '(전체)', value: total, pct: 100 }];
  }, [quarterlyData, quarterlyCategoryPieData.length]);

  // 선택한 국가의 스토어별 매출 (stores 우선, 없으면 top_stores에서 해당 국가만)
  const storesBySelectedCountry = useMemo(() => {
    if (!selectedCountryForStores || !data) return [];
    const list = (data.stores ?? data.top_stores ?? []).filter(
      (s) => String(s.country || '').trim() === String(selectedCountryForStores || '').trim()
    );
    return [...list].sort((a, b) => b.total_sales - a.total_sales);
  }, [selectedCountryForStores, data]);

  return (
    <main className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f]">
      <header className="bg-white border-b border-gray-200">
        <div className="w-full max-w-[1920px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="p-2 rounded-lg hover:bg-gray-100 text-[#6e6e73] hover:text-[#1d1d1f] transition-colors"
              aria-label="메인으로"
            >
              ←
            </Link>
            <div>
              <h1 className="text-xl font-bold text-[#1d1d1f]">매출 대시보드</h1>
              <p className="text-xs text-[#86868b] mt-0.5">데이터: Sales analysis.py (모델 서버 연동)</p>
            </div>
          </div>
        </div>
      </header>

      <div className="w-full max-w-[1920px] mx-auto px-6 py-8">
        {loading ? (
          <div className="text-center py-12">
            <p className="text-[#6e6e73]">로딩 중...</p>
            <p className="text-xs text-[#86868b] mt-2">백엔드(포트 8000)에서 매출 데이터를 불러오는 중입니다. 30초 이상 걸리면 재시도할 수 있습니다.</p>
          </div>
        ) : data ? (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {data.sales_by_year?.length ? (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <h3 className="text-sm font-medium text-[#6e6e73] mb-1 px-6 pt-6">연도별 매출 & 추이</h3>
                <p className="text-xs text-amber-600 px-6 mb-2">* 막대: 매출, 선: 추이 / 2025년: ARIMA·선형추세 예상 포함</p>
                <div className="px-6 pb-6 h-[min(300px,45vh)]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={data.sales_by_year} margin={{ top: 28, right: 30, left: 0, bottom: 5 }}>
                      <defs>
                        <linearGradient id="salesGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                      <XAxis dataKey="year" tick={{ fontSize: 11 }} stroke="#6e6e73" tickFormatter={(v) => `${v}년${v === 2025 ? '(예상)' : ''}`} />
                      <YAxis tick={{ fontSize: 11 }} stroke="#6e6e73" tickFormatter={(v) => `$${Number(v).toLocaleString()}`} />
                      <Tooltip
                        content={({ active, payload, label }) => {
                          if (!active || !payload?.length || label == null) return null;
                          const val = payload.find((p) => p.dataKey === 'total_sales')?.value;
                          const num = Number(val);
                          const text = Number.isFinite(num) ? `$${num.toLocaleString()}` : '—';
                          const yearLabel = `${label}년${label === 2025 ? ' (예상)' : ''}`;
                          return (
                            <div className="bg-white border border-[#10b981]/30 rounded-lg shadow-lg px-3 py-2 text-sm">
                              <p className="font-normal text-[#1d1d1f]">{yearLabel}</p>
                              <p className="font-semibold text-[#10b981]">매출 : {text}</p>
                            </div>
                          );
                        }}
                        contentStyle={{ backgroundColor: 'white', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 8 }}
                      />
                      <Area type="monotone" dataKey="total_sales" fill="url(#salesGradient)" stroke="none" />
                      <Line type="monotone" dataKey="total_sales" stroke="#10b981" strokeWidth={2} dot={{ r: 4 }} activeDot={{ r: 6 }} name="매출 추이" />
                      <Bar
                        dataKey="total_sales"
                        radius={[4, 4, 0, 0]}
                        name="매출"
                        label={{ position: 'top', formatter: (v: unknown) => `$${Number(v).toLocaleString()}`, fontSize: 10, fill: '#6e6e73' }}
                      >
                        {(data.sales_by_year ?? []).map((item, i) => (
                          <Cell key={i} fill={item.is_forecast ? '#f59e0b' : BAR_COLORS[i % BAR_COLORS.length]} fillOpacity={0.85} stroke={item.is_forecast ? '#d97706' : undefined} strokeDasharray={item.is_forecast ? '4 2' : undefined} strokeWidth={item.is_forecast ? 1.5 : 0} />
                        ))}
                      </Bar>
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}
            {continentSalesData.length > 0 ? (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <h3 className="text-sm font-medium text-[#6e6e73] mb-2 px-6 pt-6">대륙별 매출 (총매출 100% 기준)</h3>
                <p className="text-xs text-[#86868b] px-6 mb-1">* 전체: 대륙별 비중(파이) — 파이 클릭 시 해당 대륙 국가별 바차트로 전환 / 대륙 선택: 국가별 비중(바차트) · 국가 막대 클릭 시 카테고리별 매출 표시</p>
                <div className="flex flex-wrap gap-1 px-6 pb-2">
                  <button
                    type="button"
                    onClick={() => setSelectedContinentTab(null)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${selectedContinentTab === null ? 'bg-[#0071e3] text-white' : 'bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e8e8ed]'}`}
                  >
                    전체
                  </button>
                  {continentSalesData.map((c) => (
                    <button
                      key={c.continent}
                      type="button"
                      onClick={() => setSelectedContinentTab(c.continent)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${selectedContinentTab === c.continent ? 'bg-[#0071e3] text-white' : 'bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e8e8ed]'}`}
                    >
                      {c.continent}
                    </button>
                  ))}
                </div>
                <div className="pl-6 pr-6 pb-6 min-h-[400px] flex items-center">
                  {selectedContinentTab === null ? (
                    <ResponsiveContainer width="100%" height={Math.min(450, Math.max(300, continentChartData.length * 24))}>
                      <PieChart>
                        <Pie
                          data={continentChartData}
                          dataKey="pct"
                          nameKey="label"
                          cx="50%"
                          cy="50%"
                          innerRadius="35%"
                          outerRadius="80%"
                          paddingAngle={2}
                          label={(props) => `${props.name ?? ''} ${(props as { payload?: { pct?: number } }).payload?.pct ?? 0}%`}
                          onClick={(data: { name?: string }) => {
                            const continent = data?.name;
                            if (continent) setSelectedContinentTab(continent);
                          }}
                          cursor="pointer"
                        >
                          {continentChartData.map((_, i) => (
                            <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip
                          content={({ active, payload }) => {
                            if (!active || !payload?.[0]?.payload) return null;
                            const p = payload[0].payload as { label: string; sales?: number; pct?: number };
                            return (
                              <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm">
                                <p className="font-medium text-[#1d1d1f]">{p.label} · {p.pct ?? 0}%</p>
                                {p.sales != null && <p className="text-xs text-[#6e6e73]">${p.sales.toLocaleString()}</p>}
                              </div>
                            );
                          }}
                        />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                      </PieChart>
                    </ResponsiveContainer>
                  ) : (
                    <ResponsiveContainer width="100%" height={Math.max(400, Math.min(1200, continentChartData.length * 40))}>
                      <BarChart layout="vertical" data={continentChartData} margin={{ top: 5, right: 90, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                        <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#6e6e73" tickFormatter={(v) => `${v}%`} />
                        <YAxis type="category" dataKey="label" width={160} tick={{ fontSize: 11 }} stroke="#6e6e73" />
                        <Tooltip
                          formatter={(v: unknown, _n: unknown, props: { payload?: { sales?: number } }) => {
                            const pct = Number(v);
                            const sales = props?.payload?.sales;
                            const text = sales != null ? `${pct}% ($${sales.toLocaleString()})` : `${pct}%`;
                            return [text, '비중'];
                          }}
                          contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e5e7', borderRadius: 8 }}
                          labelFormatter={(l) => l}
                        />
                        <Bar
                          dataKey="pct"
                          radius={[0, 4, 4, 0]}
                          name="비중"
                          cursor="pointer"
                          onClick={(evt: unknown, index: number) => {
                            const payload = (evt as { payload?: { country?: string } })?.payload;
                            const entry = continentChartData[Number(index)];
                            const country = payload?.country ?? entry?.country;
                            if (country) {
                              setSelectedCountryForCategory((prev) => (prev === country ? null : country));
                              setSelectedCountryForStoreSales((prev) => (prev === country ? null : country));
                            }
                          }}
                          label={{ position: 'right', formatter: (v: unknown) => `${Number(v)}%`, fontSize: 10, fill: '#6e6e73' }}
                        >
                          {continentChartData.map((entry, i) => (
                            <Cell
                              key={i}
                              fill={BAR_COLORS[i % BAR_COLORS.length]}
                              opacity={selectedCountryForCategory && entry.country === selectedCountryForCategory ? 1 : 0.85}
                              stroke={selectedCountryForCategory && entry.country === selectedCountryForCategory ? '#0071e3' : 'none'}
                              strokeWidth={2}
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>
            ) : null}
            {(storeSalesData.length > 0 || selectedCountryForStoreSales) ? (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="flex items-center justify-between px-6 pt-6 mb-2">
                  <h3 className="text-sm font-medium text-[#6e6e73]">
                    {selectedCountryForStoreSales ? `${formatCountryDisplay(selectedCountryForStoreSales)} 상점별 연간 매출` : '상점별 연간 매출'}
                  </h3>
                  {selectedCountryForStoreSales && (
                    <button
                      type="button"
                      onClick={() => { setSelectedCountryForStoreSales(null); setSelectedCountryForCategory(null); }}
                      className="text-xs text-[#6e6e73] hover:text-[#0071e3] px-2 py-1 rounded hover:bg-gray-100"
                    >
                      전체 보기
                    </button>
                  )}
                </div>
                <p className="text-xs text-[#86868b] px-6 mb-2">
                  * {selectedCountryForStoreSales ? '해당 국가 상점별' : '상점별'} 연간 매출 (2020~2024)
                </p>
                <div className="px-6 pb-6 min-w-0 overflow-visible" style={{ minHeight: 300, height: countryStoreLoading || storeSalesData.length === 0 ? 300 : Math.min(800, Math.max(300, storeSalesData.length * 50)) }}>
                  {countryStoreLoading ? (
                    <p className="text-sm text-[#6e6e73] text-center py-12">상점 데이터 로딩 중...</p>
                  ) : storeSalesData.length === 0 ? (
                    <p className="text-sm text-[#6e6e73] text-center py-12">해당 국가에 스토어 데이터가 없습니다.</p>
                  ) : (
                  <ResponsiveContainer width="100%" height={Math.max(280, Math.min(800, storeSalesData.length * 50))} minHeight={280}>
                    <BarChart
                      layout="vertical"
                      data={storeSalesData.map((s) => ({
                        label: formatStoreDisplay(stripApplePrefix(s.store_name)),
                        sales: s.total_sales,
                        store_name: s.store_name,
                      }))}
                      margin={{ top: 8, right: 100, left: 8, bottom: 8 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                      <XAxis type="number" tick={{ fontSize: 11 }} stroke="#6e6e73" tickFormatter={(v) => `$${Number(v).toLocaleString()}`} />
                      <YAxis
                        type="category"
                        dataKey="label"
                        width={300}
                        tick={{ fontSize: storeSalesData.length > 25 ? 9 : 10 }}
                        stroke="#6e6e73"
                        interval={0}
                        tickMargin={6}
                        angle={0}
                      />
                      <Tooltip
                        formatter={(v: unknown) => [`$${Number(v).toLocaleString()}`, '매출']}
                        contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e5e7', borderRadius: 8 }}
                        labelFormatter={(l) => l}
                      />
                      <Bar
                        dataKey="sales"
                        radius={[0, 4, 4, 0]}
                        name="매출"
                        fill="#0071e3"
                        fillOpacity={0.9}
                        label={{ position: 'right', formatter: (v: unknown) => `$${Number(v).toLocaleString()}`, fontSize: 10, fill: '#6e6e73' }}
                        cursor="pointer"
                        onClick={(evt: unknown, index: number) => {
                          const payload = (evt as { payload?: { store_name?: string; label?: string } })?.payload;
                          const entry = storeSalesData[Number(index)];
                          const sn = payload?.store_name ?? entry?.store_name;
                          const dl = payload?.label ?? (entry ? formatStoreDisplay(stripApplePrefix(entry.store_name)) : '');
                          if (sn) setSelectedStoreForQuarterly((prev) => (prev?.store_name === sn ? null : { store_name: sn, display_label: dl || sn }));
                        }}
                      >
                        {storeSalesData.map((_, i) => (
                          <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  )}
                </div>
                {selectedStoreForQuarterly && (
                  <div className="border-t border-gray-200 px-6 py-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-medium text-[#6e6e73]">
                        {selectedStoreForQuarterly.display_label} · 3개월 단위 매출 추이
                      </h4>
                      <button
                        type="button"
                        onClick={() => setSelectedStoreForQuarterly(null)}
                        className="text-xs text-[#6e6e73] hover:text-[#0071e3] px-2 py-1 rounded hover:bg-gray-100"
                      >
                        닫기
                      </button>
                    </div>
                    <p className="text-xs text-[#86868b] mb-3">* 3개월(분기) 단위 매출 추이</p>
                    {quarterlyLoading ? (
                      <p className="text-sm text-[#6e6e73] text-center py-12">로딩 중...</p>
                    ) : quarterlyData.length > 0 ? (
                      <div style={{ height: 280 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <ComposedChart data={quarterlyData} margin={{ top: 8, right: 20, left: 0, bottom: 8 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                            <XAxis dataKey="period" tick={{ fontSize: 10 }} stroke="#6e6e73" />
                            <YAxis tick={{ fontSize: 10 }} stroke="#6e6e73" tickFormatter={(v) => `$${(Number(v) / 1_000_000).toFixed(1)}M`} />
                            <Tooltip
                              content={({ active, payload, label }) => {
                                if (!active || !payload?.length || !label) return null;
                                const val = payload.find((p) => p.dataKey === 'total_sales')?.value;
                                const num = Number(val);
                                const text = Number.isFinite(num) ? `$${num.toLocaleString()}` : '—';
                                return (
                                  <div className="bg-white border border-[#0071e3]/30 rounded-lg shadow-lg px-3 py-2 text-sm">
                                    <p className="font-normal text-[#1d1d1f]">{label}</p>
                                    <p className="font-semibold text-[#0071e3]">매출 : {text}</p>
                                  </div>
                                );
                              }}
                              contentStyle={{ backgroundColor: 'white', border: '1px solid rgba(0,113,227,0.3)', borderRadius: 8 }}
                            />
                            <Line type="monotone" dataKey="total_sales" name="매출" stroke="#0071e3" strokeWidth={2} dot={false} />
                            <Scatter dataKey="total_sales" fill="#0071e3" shape="circle" r={4} />
                          </ComposedChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <p className="text-sm text-[#6e6e73] text-center py-8">해당 매장의 분기별 데이터가 없습니다</p>
                    )}
                    <>
                      <h4 className="text-sm font-medium text-[#6e6e73] mt-6 mb-2">카테고리별 3개월 단위 매출 추이</h4>
                        <p className="text-xs text-[#86868b] mb-3">* 분기별 카테고리(제품군) 매출 추이 · 좌측 파이: 전체 기간 카테고리별 비중</p>
                        {quarterlyLoading ? (
                          <p className="text-sm text-[#6e6e73] text-center py-8">로딩 중...</p>
                        ) : (() => {
                          const barData = quarterlyCategoryChartData.length > 0 ? quarterlyCategoryChartData : quarterlyCategoryChartDataFallback;
                          const pieData = quarterlyCategoryPieData.length > 0 ? quarterlyCategoryPieData : quarterlyCategoryPieDataFallback;
                          const hasCharts = barData.length > 0 && pieData.length > 0;
                          if (!hasCharts) {
                            return <p className="text-sm text-[#6e6e73] text-center py-8">해당 매장의 카테고리별 분기 데이터가 없습니다</p>;
                          }
                          const categoryKeys = barData[0] ? Object.keys(barData[0]).filter((k) => k !== 'period') : [];
                          return (
                            <div className="grid grid-cols-1 md:grid-cols-[320px_minmax(0,1fr)] gap-6 items-start overflow-visible">
                              <div className="bg-[#fafafa] rounded-lg border border-gray-200 p-4 min-w-0 overflow-visible" style={{ minHeight: 280 }}>
                                <div className="mb-1 text-center min-w-0 overflow-visible">
                                  <p className="text-xs font-medium text-[#6e6e73] break-words whitespace-normal">전체 100% 기준 · 카테고리별 매출 비중(%)</p>
                                </div>
                                <div className="mb-2 text-center min-w-0 overflow-visible">
                                  <p className="text-[10px] text-[#86868b] break-words whitespace-normal">각 카테고리가 전체 매출에서 차지하는 비율 · 클릭 시 우측 바차트에 해당 카테고리만 표시</p>
                                </div>
                                <div style={{ width: '100%', height: 240, overflow: 'visible' }}>
                                  <ResponsiveContainer width="100%" height={240}>
                                    <PieChart margin={{ top: 24, right: 24, bottom: 56, left: 24 }}>
                                      <Pie
                                        data={pieData}
                                        dataKey="value"
                                        nameKey="name"
                                        cx="50%"
                                        cy="45%"
                                        innerRadius="38%"
                                        outerRadius="72%"
                                        paddingAngle={2}
                                        label={({ percent }: { percent?: number }) => {
                                          const p = percent != null ? percent : 0;
                                          if (p < 0.05) return ''; // 5% 미만은 라벨 숨김 → 겹침 방지
                                          const pct = Math.round(p * 1000) / 10;
                                          return `${pct}%`;
                                        }}
                                        labelLine={false}
                                        onClick={(entry: { name?: string }) => {
                                          const name = entry?.name;
                                          if (name) setSelectedCategoryForBarChart((prev) => (prev === name ? null : name));
                                        }}
                                        cursor="pointer"
                                      >
                                        {pieData.map((entry, i) => {
                                          const colorIdx = categoryKeys.indexOf(entry.name);
                                          const isSelected = selectedCategoryForBarChart === entry.name;
                                          return (
                                            <Cell
                                              key={entry.name}
                                              fill={BAR_COLORS[colorIdx >= 0 ? colorIdx % BAR_COLORS.length : i % BAR_COLORS.length]}
                                              stroke={isSelected ? '#0071e3' : undefined}
                                              strokeWidth={isSelected ? 2 : 0}
                                            />
                                          );
                                        })}
                                      </Pie>
                                      <Tooltip
                                        content={({ active, payload }) => {
                                          if (!active || !payload?.[0]?.payload) return null;
                                          const p = payload[0].payload as { name: string; value: number; pct?: number };
                                          const pct = p.pct != null ? p.pct : (payload[0].payload as { percent?: number }).percent != null ? Math.round((payload[0].payload as { percent: number }).percent * 1000) / 10 : 0;
                                          return (
                                            <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-sm overflow-visible" style={{ minWidth: 'max-content', maxWidth: 320 }}>
                                              <p className="font-medium text-[#1d1d1f] break-words whitespace-normal">{p.name}</p>
                                              <p className="text-[#0071e3] font-semibold whitespace-nowrap">비중: {pct}% (전체 100% 중)</p>
                                              <p className="text-xs text-[#6e6e73]">매출: ${p.value.toLocaleString()}</p>
                                            </div>
                                          );
                                        }}
                                      />
                                      <Legend layout="horizontal" align="center" verticalAlign="bottom" wrapperStyle={{ fontSize: 10, flexWrap: 'wrap', justifyContent: 'center' }} iconSize={10} iconType="square" />
                                    </PieChart>
                                  </ResponsiveContainer>
                                </div>
                              </div>
                              <div className="min-w-0 overflow-visible" style={{ width: '100%', minHeight: 280, height: 280 }}>
                                {selectedCategoryForBarChart && (
                                  <div className="flex items-center justify-between mb-1">
                                    <p className="text-xs font-medium text-[#6e6e73]">
                                      {selectedCategoryForBarChart} · 3개월 단위 매출
                                    </p>
                                    <button
                                      type="button"
                                      onClick={() => setSelectedCategoryForBarChart(null)}
                                      className="text-xs text-[#0071e3] hover:underline px-2 py-0.5"
                                    >
                                      전체 보기
                                    </button>
                                  </div>
                                )}
                                <ResponsiveContainer width="100%" height={selectedCategoryForBarChart ? 260 : 280}>
                                  {selectedCategoryForBarChart && categoryKeys.includes(selectedCategoryForBarChart) ? (
                                    <BarChart
                                      data={barData.map((row) => ({
                                        period: row.period,
                                        sales: Number((row as Record<string, unknown>)[selectedCategoryForBarChart]) || 0,
                                      }))}
                                      margin={{ top: 8, right: 20, left: 0, bottom: 8 }}
                                      barCategoryGap="12%"
                                    >
                                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                                      <XAxis dataKey="period" tick={{ fontSize: 10 }} stroke="#6e6e73" />
                                      <YAxis tick={{ fontSize: 10 }} stroke="#6e6e73" tickFormatter={(v) => `$${(Number(v) / 1_000_000).toFixed(1)}M`} />
                                      <Tooltip
                                        content={({ active, payload, label }) => {
                                          if (!active || !payload?.length || !label) return null;
                                          const val = payload.find((p) => p.dataKey === 'sales')?.value;
                                          const num = Number(val);
                                          return (
                                            <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm">
                                              <p className="font-normal text-[#1d1d1f] mb-1">{label}</p>
                                              <p className="font-medium text-[#0071e3]">{selectedCategoryForBarChart} : ${Number.isFinite(num) ? num.toLocaleString() : '—'}</p>
                                            </div>
                                          );
                                        }}
                                        contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e5e7', borderRadius: 8 }}
                                      />
                                      <Bar dataKey="sales" name={selectedCategoryForBarChart} fill={BAR_COLORS[categoryKeys.indexOf(selectedCategoryForBarChart) % BAR_COLORS.length]} radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                  ) : (
                                    <BarChart data={barData} margin={{ top: 8, right: 72, left: 0, bottom: 8 }} barCategoryGap="12%">
                                      <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                                      <XAxis dataKey="period" tick={{ fontSize: 10 }} stroke="#6e6e73" />
                                      <YAxis tick={{ fontSize: 10 }} stroke="#6e6e73" tickFormatter={(v) => `$${(Number(v) / 1_000_000).toFixed(1)}M`} />
                                      <Tooltip
                                        content={({ active, payload, label }) => {
                                          if (!active || !payload?.length || !label) return null;
                                          const seen = new Set<string>();
                                          const items = payload
                                            .filter((p) => p.dataKey && p.dataKey !== 'period' && !seen.has(String(p.dataKey)) && (seen.add(String(p.dataKey)), true))
                                            .filter((p) => Number.isFinite(Number(p.value)))
                                            .map((p) => ({ name: String(p.dataKey), value: Number(p.value) }));
                                          return (
                                            <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm">
                                              <p className="font-normal text-[#1d1d1f] mb-1">{label}</p>
                                              {items.map((it) => {
                                                const colorIdx = categoryKeys.indexOf(it.name);
                                                const color = colorIdx >= 0 ? BAR_COLORS[colorIdx % BAR_COLORS.length] : '#6e6e73';
                                                return (
                                                  <p key={it.name} className="font-medium" style={{ color }}>{it.name} : ${it.value.toLocaleString()}</p>
                                                );
                                              })}
                                            </div>
                                          );
                                        }}
                                        contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e5e7', borderRadius: 8 }}
                                      />
                                      <Legend
                                        layout="vertical"
                                        align="right"
                                        verticalAlign="middle"
                                        wrapperStyle={{ paddingLeft: 12 }}
                                        iconSize={10}
                                        iconType="square"
                                      />
                                      {categoryKeys.map((cat, i) => (
                                        <Bar key={cat} dataKey={cat} name={cat} fill={BAR_COLORS[i % BAR_COLORS.length]} stackId="q" radius={[0, 0, 0, 0]} />
                                      ))}
                                    </BarChart>
                                  )}
                                </ResponsiveContainer>
                              </div>
                            </div>
                          );
                        })()}
                    </>
                  </div>
                )}
              </div>
            ) : null}
            {countrySalesData.length > 0 ? (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <h3 className="text-sm font-medium text-[#6e6e73] mb-2 px-6 pt-6">국가별 카테고리별 매출 (총매출 100% 기준)</h3>
                <p className="text-xs text-[#86868b] px-6 mb-1">* 국가를 선택하면 해당 국가의 카테고리별 매출 비중을 볼 수 있습니다</p>
                <div className="flex flex-wrap gap-1 px-6 pb-2">
                  <button
                    type="button"
                    onClick={() => setSelectedCountryForCategory(null)}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${selectedCountryForCategory === null ? 'bg-[#0071e3] text-white' : 'bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e8e8ed]'}`}
                  >
                    국가 선택
                  </button>
                  {countrySalesData.map((c) => (
                    <button
                      key={c.country}
                      type="button"
                      onClick={() => setSelectedCountryForCategory(c.country)}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${selectedCountryForCategory === c.country ? 'bg-[#0071e3] text-white' : 'bg-[#f5f5f7] text-[#6e6e73] hover:bg-[#e8e8ed]'}`}
                    >
                      {c.countryLabel}
                    </button>
                  ))}
                </div>
                <div className="pl-6 pr-6 pb-6 min-h-[400px] flex items-center">
                  {selectedCountryForCategory && countryCategoryChartData.length > 0 ? (
                    <ResponsiveContainer width="100%" height={Math.max(400, Math.min(1200, countryCategoryChartData.length * 40))}>
                      <BarChart layout="vertical" data={countryCategoryChartData} margin={{ top: 5, right: 90, left: 0, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                        <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} stroke="#6e6e73" tickFormatter={(v) => `${v}%`} />
                        <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 10 }} stroke="#6e6e73" />
                        <Tooltip
                          formatter={(v: unknown, _n: unknown, props: { payload?: { sales?: number } }) => {
                            const pct = Number(v);
                            const sales = props?.payload?.sales;
                            const text = sales != null ? `${pct}% ($${sales.toLocaleString()})` : `${pct}%`;
                            return [text, '비중'];
                          }}
                          contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e5e7', borderRadius: 8 }}
                          labelFormatter={(l) => l}
                        />
                        <Bar dataKey="pct" radius={[0, 4, 4, 0]} name="비중" label={{ position: 'right', formatter: (v: unknown) => `${Number(v)}%`, fontSize: 10, fill: '#6e6e73' }}>
                          {countryCategoryChartData.map((_, i) => (
                            <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : selectedCountryForCategory && countryCategoryLoading ? (
                    <p className="text-sm text-[#6e6e73] w-full text-center py-12">카테고리 데이터를 불러오는 중...</p>
                  ) : selectedCountryForCategory ? (
                    <p className="text-sm text-[#6e6e73] w-full text-center py-12">해당 국가에 카테고리 데이터가 없습니다</p>
                  ) : (
                    <p className="text-sm text-[#6e6e73] w-full text-center py-12">위에서 국가를 선택하세요</p>
                  )}
                </div>
              </div>
            ) : null}

            {/* [3.4.1] 매장 등급 및 달성률 분석 */}
            {storePerformanceGrade && (storePerformanceGrade.store_performance?.length > 0 || storePerformanceGrade.grade_distribution?.length > 0) && (
              <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden mb-8">
                <h3 className="text-sm font-medium text-[#6e6e73] mb-1 px-6 pt-6">[3.4.1] 매장 등급 및 달성률 분석</h3>
                <p className="text-xs text-[#86868b] px-6 mb-4">연간 예측(2025) 대비 매장당 목표 달성률 · S(≥100%) / A(80~100%) / C(기본)</p>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 px-6 pb-6">
                  <div>
                    <p className="text-xs font-medium text-[#6e6e73] mb-2">매장 성과 등급 분포 (파이 차트)</p>
                    {storePerformanceGrade.grade_distribution && storePerformanceGrade.grade_distribution.length > 0 ? (
                      <ResponsiveContainer width="100%" height={220}>
                        <PieChart>
                          <Pie
                            data={storePerformanceGrade.grade_distribution}
                            dataKey="pct"
                            nameKey="grade"
                            cx="50%"
                            cy="50%"
                            innerRadius={50}
                            outerRadius={80}
                            label={(props) => {
                              const p = (props as { payload?: { grade?: string; pct?: number } }).payload;
                              return p ? `등급 ${p.grade ?? ''}: ${p.pct ?? 0}%` : '';
                            }}
                          >
                            {storePerformanceGrade.grade_distribution.map((entry, i) => (
                              <Cell
                                key={entry.grade}
                                fill={entry.grade === 'S' ? '#eab308' : entry.grade === 'A' ? '#3b82f6' : '#94a3b8'}
                              />
                            ))}
                          </Pie>
                          <Tooltip formatter={(v: unknown) => [`${Number(v)}%`, '비중']} />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <p className="text-sm text-[#6e6e73] py-8 text-center">등급 분포 데이터 없음</p>
                    )}
                  </div>
                  <div className="min-w-0 overflow-x-auto">
                    <p className="text-xs font-medium text-[#6e6e73] mb-2">매장별 달성률 (상위 20개) · 연간 목표: ₩{Number(storePerformanceGrade.annual_forecast_revenue || 0).toLocaleString()}</p>
                    {storePerformanceGrade.store_performance && storePerformanceGrade.store_performance.length > 0 ? (
                      <div className="max-h-64 overflow-y-auto border border-gray-200 rounded-lg">
                        <table className="w-full text-sm">
                          <thead className="bg-[#f5f5f7] sticky top-0">
                            <tr className="text-left text-[#6e6e73]">
                              <th className="px-3 py-2">매장</th>
                              <th className="px-3 py-2 text-right">매출</th>
                              <th className="px-3 py-2 text-right">달성률</th>
                              <th className="px-3 py-2">등급</th>
                            </tr>
                          </thead>
                          <tbody>
                            {storePerformanceGrade.store_performance
                              .sort((a, b) => b.achievement_rate - a.achievement_rate)
                              .slice(0, 20)
                              .map((row, i) => (
                                <tr key={i} className="border-t border-gray-100">
                                  <td className="px-3 py-1.5 text-[#1d1d1f] truncate max-w-[140px]" title={row.store_name}>{row.store_name || '-'}</td>
                                  <td className="px-3 py-1.5 text-right text-[#1d1d1f]">₩{Number(row.total_sales).toLocaleString()}</td>
                                  <td className="px-3 py-1.5 text-right font-medium">{row.achievement_rate.toFixed(1)}%</td>
                                  <td className="px-3 py-1.5">
                                    <span
                                      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
                                        row.grade === 'S' ? 'bg-amber-100 text-amber-800' : row.grade === 'A' ? 'bg-blue-100 text-blue-800' : 'bg-slate-100 text-slate-600'
                                      }`}
                                    >
                                      {row.grade}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-sm text-[#6e6e73] py-8 text-center">매장별 성과 데이터 없음</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {selectedCountryForStores ? (
              <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
                <div className="flex items-center justify-between px-6 pt-6 pb-3">
                  <h3 className="text-sm font-medium text-[#6e6e73]">
                    {formatCountryDisplay(selectedCountryForStores)} - 스토어별 매출
                    {storesBySelectedCountry.length > 0 ? ` (${storesBySelectedCountry.length}개)` : ''}
                  </h3>
                  <button
                    type="button"
                    onClick={() => setSelectedCountryForStores(null)}
                    className="text-xs text-[#6e6e73] hover:text-[#0071e3] px-2 py-1 rounded hover:bg-gray-100"
                  >
                    닫기
                  </button>
                </div>
                {storesBySelectedCountry.length > 0 ? (
                  <div className="px-6 pb-6" style={{ minHeight: 200, height: Math.min(500, Math.max(240, storesBySelectedCountry.length * 36)) }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        layout="vertical"
                        data={storesBySelectedCountry.map((s) => ({ label: `${s.store_id} (${s.city})`, store_id: s.store_id, city: s.city, sales: s.total_sales }))}
                        margin={{ top: 8, right: 100, left: 8, bottom: 8 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                        <XAxis type="number" tick={{ fontSize: 11 }} stroke="#6e6e73" tickFormatter={(v) => `$${Number(v).toLocaleString()}`} />
                        <YAxis type="category" dataKey="label" width={180} tick={{ fontSize: 11 }} stroke="#6e6e73" />
                        <Tooltip
                          formatter={(v: unknown) => [`$${Number(v).toLocaleString()}`, '매출']}
                          contentStyle={{ backgroundColor: 'white', border: '1px solid #e5e5e7', borderRadius: 8 }}
                          labelFormatter={(l) => l}
                        />
                        <Bar dataKey="sales" radius={[0, 4, 4, 0]} name="매출" fill="#0071e3" fillOpacity={0.9} label={{ position: 'right', formatter: (v: unknown) => `$${Number(v).toLocaleString()}`, fontSize: 10, fill: '#6e6e73' }}>
                          {storesBySelectedCountry.map((_, i) => (
                            <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="px-6 pb-6 text-sm text-[#6e6e73]">
                    {formatCountryDisplay(selectedCountryForStores)}에 해당하는 스토어 데이터가 없습니다.
                  </div>
                )}
              </div>
            ) : null}
            </div>
          </>
        ) : (
          <div className="text-center py-12">
            <p className="text-[#86868b] mb-4">매출 데이터를 불러올 수 없습니다.</p>
            <p className="text-xs text-[#86868b] mb-4">백엔드(포트 8000) 실행 여부와 .env.local의 NEXT_PUBLIC_API_URL 확인 후 재시도하세요.</p>
            <button
              type="button"
              onClick={() => fetchSalesData()}
              className="px-4 py-2 rounded-lg bg-[#0071e3] text-white text-sm font-medium hover:bg-[#0077ed] transition-colors"
            >
              다시 시도
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
