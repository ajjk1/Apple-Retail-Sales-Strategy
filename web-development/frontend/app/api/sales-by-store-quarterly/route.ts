import { NextRequest, NextResponse } from 'next/server';

/** 서버 전용: BACKEND_URL 또는 NEXT_PUBLIC_API_URL. 미설정 시 프로덕션에서는 HF Space 상수 사용. */
const PRODUCTION_BACKEND_URL = 'https://apple-retail-study-apple-retail-sales-strategy.hf.space';

function getBackendUrls(): string[] {
  let primary = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!primary || typeof primary !== 'string') {
    if (process.env.NODE_ENV === 'production') primary = PRODUCTION_BACKEND_URL;
    else primary = '';
  }
  if (!primary) return [];
  const normalized = primary.replace(/\/$/, '');
  return [normalized];
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
