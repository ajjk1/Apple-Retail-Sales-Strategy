'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

/** 추천 대시보드 공통 레이아웃: 순서대로 추천 | 투자자 대시보드 | 판매자 퀵 대시보드 탭 */
export default function RecommendationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname() ?? '';

  const tabs = [
    { href: '/recommendation', label: '추천' },
    { href: '/recommendation/investor', label: '투자자 대시보드' },
    { href: '/recommendation/seller', label: '판매자 퀵 대시보드' },
  ];

  return (
    <div className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f]">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-3">
          <div className="flex items-center justify-between gap-4">
            <Link
              href="/"
              className="p-2 rounded-lg hover:bg-gray-100 text-[#6e6e73] hover:text-[#1d1d1f] transition-colors shrink-0"
              aria-label="메인으로"
            >
              ←
            </Link>
            <nav className="flex items-center gap-1 flex-wrap" aria-label="추천 대시보드 메뉴">
              {tabs.map((tab) => {
                const isActive = pathname === tab.href || (tab.href !== '/recommendation' && pathname.startsWith(tab.href));
                return (
                  <Link
                    key={tab.href}
                    href={tab.href}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-[#0071e3] text-white'
                        : 'text-[#6e6e73] hover:bg-gray-100 hover:text-[#1d1d1f]'
                    }`}
                  >
                    {tab.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        </div>
      </header>
      {children}
    </div>
  );
}
