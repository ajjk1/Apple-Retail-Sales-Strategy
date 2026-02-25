'use client';

import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';
import { apiGet } from '../../lib/api';
import { stripApplePrefix, formatStoreDisplay } from '../../lib/country';

interface Store {
  store_id: string;
  store_name: string;
  country?: string;
}

interface RecItem {
  product_id?: string;
  product_name?: string;
  score?: number;
  reason?: string;
  seller_script?: string;
}

interface GrowthStrategy {
  store_id?: string;
  store_type?: string;
  recommendations?: RecItem[];
  reasoning_log?: unknown[];
  fallback_used?: boolean;
}

interface AssociationItem {
  product_name?: string;
  reason?: string;
}

interface StoreRecommendationsResponse {
  store_id: string;
  store_summary?: { total_sales?: number; product_count?: number; store_name?: string };
  growth_strategy?: GrowthStrategy;
  association?: AssociationItem[];
}

interface InventoryItem {
  Store_Name?: string;
  Product_Name?: string;
  Inventory?: number;
  Safety_Stock?: number;
  Status?: string;
}

interface InventoryFrozenResponse {
  items: InventoryItem[];
}

export default function SellerQuickDashboardPage() {
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedStoreId, setSelectedStoreId] = useState<string>('');
  const [rec, setRec] = useState<StoreRecommendationsResponse | null>(null);
  const [inventory, setInventory] = useState<InventoryFrozenResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [recIndex, setRecIndex] = useState(0);
  const [soldCount, setSoldCount] = useState(0);

  const list = useMemo(() => rec?.growth_strategy?.recommendations ?? [], [rec]);
  const current = list[recIndex] ?? null;
  const storeName = rec?.store_summary?.store_name ?? selectedStoreId;

  useEffect(() => {
    apiGet<{ stores?: Store[] }>('/api/store-list')
      .then((res) => {
        if (res?.stores?.length) {
          setStores(res.stores);
          if (!selectedStoreId) setSelectedStoreId(res.stores[0].store_id);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedStoreId) return;
    setLoading(true);
    Promise.all([
      apiGet<StoreRecommendationsResponse>(`/api/store-recommendations/${selectedStoreId}?store_type=STANDARD`),
      apiGet<InventoryFrozenResponse>('/api/inventory-frozen-money'),
    ])
      .then(([r, inv]) => {
        setRec(r ?? null);
        setInventory(inv ?? null);
        setRecIndex(0);
      })
      .catch(() => setRec(null))
      .finally(() => setLoading(false));
  }, [selectedStoreId]);

  const signal = useMemo(() => {
    if (!current?.product_name || !inventory?.items?.length) return null;
    const productMatch = (row: InventoryItem) =>
      row.Product_Name === current.product_name || (row.Product_Name ?? '').includes(current.product_name ?? '') || (current.product_name ?? '').includes(row.Product_Name ?? '');
    const storeMatch = (row: InventoryItem) => !row.Store_Name || !storeName || row.Store_Name === storeName || (storeName && row.Store_Name.includes(storeName));
    const inv = inventory.items.find((row) => productMatch(row) && storeMatch(row))
      ?? inventory.items.find((row) => productMatch(row));
    if (!inv) return null;
    const invVal = Number(inv.Inventory) ?? 0;
    const safeVal = Number(inv.Safety_Stock) ?? 0;
    if (safeVal <= 0) return 'green';
    return invVal < safeVal ? 'red' : 'green';
  }, [current?.product_name, inventory, storeName]);

  const totalSales = rec?.store_summary?.total_sales ?? 0;
  const contributionBase = current?.score != null ? Math.round(current.score * 100) : (list.length - recIndex) * 25;
  const expectedScore = contributionBase + soldCount * 10;
  const contributionPct = totalSales > 0 && current?.score != null ? Math.min(100, Math.round((current.score / 1) * 15)) : null;

  // 오늘의 추천 멘트: 재고 < 안전재고 → 품절 임박, association 있음 → 함께 사는 아이템, 아니면 오늘의 추천. 초간단 태그만 사용.
  const { mentText, mentTag, copyText } = useMemo(() => {
    const hasAssociation = (rec?.association?.length ?? 0) > 0;
    const isLowStock = current != null && signal === 'red';
    let text: string;
    let tag: string;
    if (isLowStock) {
      text = '품절 임박';
      tag = '마감 임박';
    } else if (hasAssociation) {
      text = '함께 사는 아이템';
      tag = '가성비 추천';
    } else {
      text = '오늘의 추천';
      tag = '신뢰 강조';
    }
    return { mentText: text, mentTag: tag, copyText: `${text} [${tag}]` };
  }, [rec?.association?.length, current, signal]);

  const handleCopyMent = () => {
    navigator.clipboard.writeText(copyText).catch(() => {});
  };

  if (loading && !rec) {
    return (
      <main className="min-h-screen bg-[#f5f5f7] flex items-center justify-center">
        <p className="text-[#6e6e73]">판매자 퀵 대시보드 로딩 중...</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f]">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-2xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="p-2 rounded-lg hover:bg-gray-100 text-[#6e6e73]" aria-label="메인으로">
            ←
          </Link>
          <h1 className="text-xl font-bold text-[#1d1d1f]">🛒 판매자 퀵 대시보드</h1>
          <div className="w-10" />
        </div>
      </header>

      <div className="max-w-2xl mx-auto px-6 py-8">
        {stores.length > 0 && (
          <div className="mb-6">
            <label className="block text-sm font-medium text-[#1d1d1f] mb-2">매장 선택</label>
            <select
              value={selectedStoreId}
              onChange={(e) => setSelectedStoreId(e.target.value)}
              className="w-full border border-gray-200 rounded-xl px-4 py-3 bg-white text-[#1d1d1f] focus:ring-2 focus:ring-[#0071e3]"
            >
              {stores.map((s) => (
                <option key={s.store_id} value={s.store_id}>
                  {formatStoreDisplay(stripApplePrefix(s.store_name ?? s.store_id))}
                </option>
              ))}
            </select>
          </div>
        )}

        {current ? (
          <>
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mb-6">
              <h2 className="text-sm font-medium text-[#86868b] mb-3">지금 추천 (한 줄 요약)</h2>
              <p className="text-2xl font-bold text-[#1d1d1f] mb-2">
                {current.product_name ?? current.product_id ?? '—'}
              </p>
              <p className="text-base text-[#6e6e73]">
                {current.reason ?? '추천 이유 없음'}
              </p>
            </section>

            <section className="mb-6 flex items-center gap-4">
              <span className="text-sm font-medium text-[#1d1d1f]">재고 상태</span>
              {signal === 'red' && (
                <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-100 border border-red-300">
                  <span className="w-4 h-4 rounded-full bg-red-500" aria-hidden />
                  <span className="font-semibold text-red-800">품절주의</span>
                  <span className="text-red-700 text-sm">(재고 &lt; 안전재고)</span>
                </div>
              )}
              {signal === 'green' && (
                <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-green-100 border border-green-300">
                  <span className="w-4 h-4 rounded-full bg-green-500" aria-hidden />
                  <span className="font-semibold text-green-800">적극판매</span>
                  <span className="text-green-700 text-sm">(재고 충분)</span>
                </div>
              )}
              {signal === null && (
                <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gray-100 border border-gray-200">
                  <span className="text-[#6e6e73] text-sm">재고 데이터 없음</span>
                </div>
              )}
            </section>

            <section className="mb-8">
              <button
                type="button"
                onClick={() => setRecIndex((i) => (i + 1 >= list.length ? 0 : i + 1))}
                className="w-full py-4 rounded-xl bg-[#0071e3] text-white font-semibold text-lg hover:opacity-90 transition-opacity"
              >
                고객 거절 시 대안 보기
              </button>
              <p className="text-xs text-[#86868b] mt-2 text-center">
                누르면 Real-time execution 엔진의 다음 순위 상품이 표시됩니다. ({recIndex + 1}/{list.length})
              </p>
            </section>

            <section className="bg-white rounded-2xl border border-amber-200 shadow-sm p-6 bg-gradient-to-br from-amber-50/50 to-white">
              <h2 className="text-sm font-medium text-[#86868b] mb-2">인센티브 · total_sales 기여도</h2>
              <p className="text-3xl font-bold text-[#1d1d1f] mb-1">
                예상 기여 점수: <span className="text-[#0071e3]">{expectedScore}</span>
              </p>
              {contributionPct != null && (
                <p className="text-sm text-[#6e6e73] mb-4">
                  이 상품 기여도(가중): 약 {contributionPct}% (상점 총 매출 대비)
                </p>
              )}
              <p className="text-sm text-[#6e6e73] mb-4">
                상점 총 매출: ₩{(totalSales ?? 0).toLocaleString()} · 판매 시 점수 반영
              </p>
              <button
                type="button"
                onClick={() => setSoldCount((c) => c + 1)}
                className="px-6 py-3 rounded-xl bg-amber-500 text-white font-semibold hover:bg-amber-600 transition-colors"
              >
                판매 완료 (+10점)
              </button>
              <p className="text-xs text-amber-800 mt-2">
                이 상품을 팔 때마다 예상 기여 점수가 올라갑니다.
              </p>
            </section>

            {/* 오늘의 추천 멘트: association → 함께 사는 아이템, 재고 < 안전재고 → 품절 임박, 문구 복사 버튼 */}
            <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mt-6">
              <h2 className="text-sm font-medium text-[#86868b] mb-3">오늘의 추천 멘트</h2>
              <p className="text-lg font-semibold text-[#1d1d1f] mb-2">{mentText}</p>
              <p className="text-sm text-[#6e6e73] mb-4">
                <span className="inline-block px-2 py-1 rounded-md bg-[#f5f5f7] text-[#1d1d1f] font-medium">[{mentTag}]</span>
              </p>
              <button
                type="button"
                onClick={handleCopyMent}
                className="w-full py-3 rounded-xl bg-[#0071e3] text-white font-semibold hover:opacity-90 transition-opacity"
              >
                문구 복사하기
              </button>
              <p className="text-xs text-[#86868b] mt-2 text-center">복사한 문구를 메시지로 손님에게 보내보세요.</p>
            </section>
          </>
        ) : (
          <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
            <p className="text-[#6e6e73]">추천 데이터가 없습니다. 매장을 선택했는지, 백엔드(port 8000)가 켜져 있는지 확인해 주세요.</p>
            <Link href="/recommendation" className="mt-4 inline-block text-[#0071e3] font-medium">
              추천 대시보드로 이동 →
            </Link>
          </div>
        )}

        {/* 추천 데이터 있을 때 하단에도 오늘의 추천 멘트 노출 (현재 상품 없어도 association/재고 기반 문구 표시) */}
        {rec && !current && (rec?.association?.length ?? 0) > 0 && (
          <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 mt-6">
            <h2 className="text-sm font-medium text-[#86868b] mb-3">오늘의 추천 멘트</h2>
            <p className="text-lg font-semibold text-[#1d1d1f] mb-2">함께 사는 아이템</p>
            <p className="text-sm text-[#6e6e73] mb-4">
              <span className="inline-block px-2 py-1 rounded-md bg-[#f5f5f7] text-[#1d1d1f] font-medium">[가성비 추천]</span>
            </p>
            <button
              type="button"
              onClick={() => navigator.clipboard.writeText('함께 사는 아이템 [가성비 추천]').catch(() => {})}
              className="w-full py-3 rounded-xl bg-[#0071e3] text-white font-semibold hover:opacity-90 transition-opacity"
            >
              문구 복사하기
            </button>
          </section>
        )}
      </div>
    </main>
  );
}
