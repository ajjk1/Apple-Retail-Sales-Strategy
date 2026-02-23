import { NextRequest, NextResponse } from 'next/server';

/** 서버 전용: BACKEND_URL 또는 NEXT_PUBLIC_API_URL 만 사용. localhost 폴백 없음 (Vercel 배포 시 env 필수). */
function getBackendUrls(): string[] {
  const primary = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  if (!primary || typeof primary !== 'string') return [];
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
