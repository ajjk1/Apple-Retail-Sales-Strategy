import { NextRequest, NextResponse } from 'next/server';

/** 백엔드 URL 후보 (서버사이드: BACKEND_URL 우선. 끝 슬래시 제거하여 이중 슬래시 방지) */
function getBackendUrls(): string[] {
  const primary =
    process.env.BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://127.0.0.1:8000';
  const normalized = typeof primary === 'string' ? primary.replace(/\/$/, '') : primary;
  const urls = [
    normalized,
    'http://localhost:8000',
    'http://localhost:8001',
    'http://127.0.0.1:8000',
    'http://127.0.0.1:8001',
  ];
  return Array.from(new Set(urls.filter(Boolean)));
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const storeName = searchParams.get('store_name') || '';
  const country = searchParams.get('country') || '';
  if (!storeName.trim()) {
    return NextResponse.json({ quarterly: [] });
  }
  const params = new URLSearchParams({ store_name: storeName.trim() });
  if (country.trim()) params.set('country', country.trim());
  const query = params.toString();
  for (const base of getBackendUrls()) {
    try {
      const res = await fetch(`${base}/api/sales-by-store-quarterly?${query}`, {
        cache: 'no-store',
        headers: { Accept: 'application/json' },
        signal: AbortSignal.timeout(8000),
      });
      if (res.ok) {
        const json = await res.json();
        return NextResponse.json(json);
      }
    } catch {
      continue;
    }
  }
  return NextResponse.json({ quarterly: [] });
}
