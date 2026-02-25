'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { apiGet } from '../../../lib/api';
import {
  BarChart,
  Bar,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

/** KPI: 총 동결 자금 등 (safety-stock-kpi) */
interface SafetyStockKpi {
  total_frozen_money?: number;
  danger_count?: number;
  overstock_count?: number;
  predicted_demand?: number;
  expected_revenue?: number;
}

/** 재고 목록 항목 (inventory-frozen-money) */
interface InventoryItem {
  Store_Name?: string;
  Product_Name?: string;
  Inventory?: number;
  Safety_Stock?: number;
  Status?: string;
  Frozen_Money?: number;
  price?: number;
  investor_alert?: boolean;
}

interface InventoryFrozenMoneyResponse {
  items: InventoryItem[];
  investor_value_message?: string;
}

/** 성과 시뮬레이터 (performance-simulator) */
interface PerformanceSimulator {
  scenario?: {
    chart_data?: { period: string; sales_before: number; sales_after: number }[];
    before?: { periods?: string[]; sales?: number[] };
    after?: { periods?: string[]; sales?: number[] };
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
  performance_lift?: {
    chart_data?: { period: string; 기존_곡선: number; 성장_곡선_15: number }[];
    lift_rate?: number;
    investor_message?: string;
  };
  summary?: {
    total_sales_lift_pct?: number;
    return_rate_reduction_pct?: number;
    inventory_turnover_acceleration_pct?: number;
  };
  investor_message?: string;
}

export default function InvestorDashboardPage() {
  const [kpi, setKpi] = useState<SafetyStockKpi | null>(null);
  const [inventoryFrozen, setInventoryFrozen] = useState<InventoryFrozenMoneyResponse | null>(null);
  const [simulator, setSimulator] = useState<PerformanceSimulator | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiGet<SafetyStockKpi>('/api/safety-stock-kpi'),
      apiGet<InventoryFrozenMoneyResponse>('/api/inventory-frozen-money'),
      apiGet<PerformanceSimulator>('/api/performance-simulator'),
    ])
      .then(([k, inv, sim]) => {
        if (k) setKpi(k);
        if (inv) setInventoryFrozen(inv);
        if (sim) setSimulator(sim);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const frozenMoneyBarData = useMemo(() => {
    const items = inventoryFrozen?.items ?? [];
    if (items.length === 0) return [];
    const withRatio = items.map((row) => {
      const inv = Number(row.Inventory) || 0;
      const fm = Number(row.Frozen_Money) || 0;
      const ratio = inv > 0 ? Math.round((fm / inv) * 100) / 100 : 0;
      const label = row.Store_Name
        ? `${row.Store_Name} · ${(row.Product_Name ?? '').slice(0, 20)}`
        : (row.Product_Name ?? '').slice(0, 24);
      return {
        name: label || '-',
        frozen_money: fm,
        inventory: inv,
        ratio_pct: inv > 0 ? Math.round((fm / inv) * 100) : 0,
        fullName: row.Product_Name ?? row.Store_Name ?? '-',
      };
    });
    return withRatio
      .sort((a, b) => b.frozen_money - a.frozen_money)
      .slice(0, 20);
  }, [inventoryFrozen]);

  const engineCurveData = useMemo(() => {
    const chart = simulator?.scenario?.chart_data ?? simulator?.performance_lift?.chart_data;
    if (!chart?.length) return [];
    if ('sales_before' in chart[0]) {
      return (chart as { period: string; sales_before: number; sales_after: number }[]).map((d) => ({
        period: d.period,
        적용전: d.sales_before,
        적용후: d.sales_after,
      }));
    }
    return (chart as { period: string; 기존_곡선: number; 성장_곡선_15: number }[]).map((d) => ({
      period: d.period,
      적용전: d.기존_곡선,
      적용후: d.성장_곡선_15,
    }));
  }, [simulator]);

  const statusAlertItems = useMemo(() => {
    const items = inventoryFrozen?.items ?? [];
    return items.filter((row) => {
      const st = String(row.Status ?? '').trim();
      const isNormal = st === 'Normal' || st === '정상';
      const inv = Number(row.Inventory) ?? 0;
      const ss = Number(row.Safety_Stock) ?? 0;
      return isNormal && inv < ss && ss > 0;
    });
  }, [inventoryFrozen]);

  const totalFrozen = kpi?.total_frozen_money ?? 0;
  const expectedProfit = simulator?.roi?.opportunity_cost_saved_annual ?? 0;

  if (loading) {
    return (
      <main className="flex items-center justify-center py-24">
        <p className="text-[#6e6e73]">투자자 대시보드 로딩 중...</p>
      </main>
    );
  }

  return (
    <main className="max-w-6xl mx-auto px-6 py-8">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <p className="text-sm text-[#86868b] mb-1">총 동결 자금 합계</p>
          <p className="text-3xl font-bold text-[#1d1d1f]">
            ${(totalFrozen / 1000).toFixed(1)}K
          </p>
          <p className="text-xs text-[#6e6e73] mt-1">frozen_money 집계 (재고·가격 기반)</p>
        </div>
        <div className="bg-white rounded-xl border border-emerald-200 shadow-sm p-6 bg-gradient-to-br from-emerald-50/50 to-white">
          <p className="text-sm text-[#86868b] mb-1">엔진 도입 시 예상 추가 이익</p>
          <p className="text-3xl font-bold text-emerald-700">
            ${(expectedProfit / 1000).toFixed(1)}K
          </p>
          <p className="text-xs text-[#6e6e73] mt-1">연간 기회비용 절감 (main.py · Real-time 시뮬레이션)</p>
        </div>
      </div>

      <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-8">
        <h2 className="text-lg font-bold text-[#1d1d1f] mb-2">📦 재고 가치 시각화</h2>
        <p className="text-sm text-[#6e6e73] mb-4">frozen_money 막대 그래프 · inventory 대비 비중(%) 표시</p>
        {frozenMoneyBarData.length > 0 ? (
          <div className="h-[400px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={frozenMoneyBarData}
                layout="vertical"
                margin={{ top: 8, right: 24, left: 120, bottom: 24 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                <XAxis type="number" tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={115} />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length || !label) return null;
                    const row = frozenMoneyBarData.find((r) => r.name === label);
                    return (
                      <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm">
                        <p className="font-medium text-[#1d1d1f] mb-1">{row?.fullName ?? label}</p>
                        <p>Frozen Money: ${payload.find((p) => p.dataKey === 'frozen_money')?.value?.toLocaleString() ?? 0}</p>
                        <p>Inventory: {payload.find((p) => p.dataKey === 'inventory')?.value?.toLocaleString() ?? 0}</p>
                        <p className="text-[#6e6e73]">inventory 대비 비중: <strong>{row?.ratio_pct ?? 0}%</strong></p>
                      </div>
                    );
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="frozen_money" name="Frozen Money ($)" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                <Bar dataKey="inventory" name="Inventory (개)" fill="#94a3b8" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-sm text-[#86868b] py-8">재고·동결 자금 데이터가 없습니다.</p>
        )}
        {frozenMoneyBarData.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[#6e6e73] border-b border-gray-200">
                  <th className="py-2 pr-3">항목</th>
                  <th className="py-2 text-right">Frozen Money</th>
                  <th className="py-2 text-right">Inventory</th>
                  <th className="py-2 text-right">비중 (FM/Inv %)</th>
                </tr>
              </thead>
              <tbody>
                {frozenMoneyBarData.slice(0, 10).map((row, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-1.5 text-[#1d1d1f] truncate max-w-[200px]" title={row.fullName}>{row.name}</td>
                    <td className="py-1.5 text-right font-medium">${row.frozen_money.toLocaleString()}</td>
                    <td className="py-1.5 text-right">{row.inventory.toLocaleString()}</td>
                    <td className="py-1.5 text-right text-[#6e6e73]">{row.ratio_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-8">
        <h2 className="text-lg font-bold text-[#1d1d1f] mb-2">📈 추천 성과 대조</h2>
        <p className="text-sm text-[#6e6e73] mb-4">main.py · Real-time execution 시뮬레이션 결과 — 엔진 적용 전/후 예상 매출 곡선</p>
        {engineCurveData.length > 0 ? (
          <div className="h-[320px]">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={engineCurveData} margin={{ top: 8, right: 8, left: 8, bottom: 24 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e7" />
                <XAxis dataKey="period" tick={{ fontSize: 11 }} stroke="#6e6e73" />
                <YAxis tick={{ fontSize: 11 }} stroke="#6e6e73" tickFormatter={(v) => (Number(v) / 1000).toFixed(0) + 'k'} />
                <Tooltip formatter={(value: number) => [value?.toLocaleString(), '']} labelFormatter={(l) => `기간: ${l}`} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line type="monotone" dataKey="적용전" name="엔진 적용 전" stroke="#64748b" strokeWidth={2} dot={{ r: 4 }} />
                <Line type="monotone" dataKey="적용후" name="엔진 적용 후" stroke="#059669" strokeWidth={2} strokeDasharray="4 4" dot={{ r: 4 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <p className="text-sm text-[#86868b] py-8">시뮬레이션 곡선 데이터가 없습니다. (performance-simulator API 확인)</p>
        )}
      </section>

      <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-8">
        <h2 className="text-lg font-bold text-[#1d1d1f] mb-2">⚠️ 상태 알림</h2>
        <p className="text-sm text-[#6e6e73] mb-4">Status가 Normal(정상)인데 재고(inventory)가 안전재고(safety_stock)보다 적은 상품 — 즉시 보충 권장</p>
        {statusAlertItems.length > 0 ? (
          <div className="space-y-3">
            {statusAlertItems.slice(0, 30).map((row, i) => (
              <div
                key={i}
                className="flex items-center gap-4 p-4 rounded-xl bg-red-50 border border-red-200 border-l-4 border-l-red-500"
              >
                <span className="flex-shrink-0 w-10 h-10 rounded-full bg-red-500 flex items-center justify-center" aria-hidden>
                  <span className="text-white text-lg">!</span>
                </span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-[#1d1d1f]">
                    {row.Store_Name ?? ''} · {row.Product_Name ?? '-'}
                  </p>
                  <p className="text-sm text-[#6e6e73]">
                    재고 <strong className="text-red-700">{Number(row.Inventory).toLocaleString()}</strong>
                    {' < '} 안전재고 <strong className="text-red-700">{Number(row.Safety_Stock).toLocaleString()}</strong>
                    {' · '}Status: {row.Status}
                  </p>
                </div>
                <span className="flex-shrink-0 px-3 py-1 rounded-full text-xs font-semibold bg-red-200 text-red-900">
                  보충 필요
                </span>
              </div>
            ))}
            {statusAlertItems.length > 30 && (
              <p className="text-xs text-[#86868b]">외 {statusAlertItems.length - 30}건 (상위 30건만 표시)</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-emerald-700 py-6 rounded-xl bg-emerald-50 border border-emerald-200">
            해당 조건의 경고 항목이 없습니다. (Normal이면서 inventory &lt; safety_stock 인 건 없음)
          </p>
        )}
      </section>
    </main>
  );
}
