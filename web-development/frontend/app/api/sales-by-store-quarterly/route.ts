import { NextRequest, NextResponse } from 'next/server';

/** 서버 전용: BACKEND_URL 또는 NEXT_PUBLIC_API_URL. Vercel/프로덕션에서는 localhost 미사용, HF Space 상수 사용. */
const PRODUCTION_BACKEND_URL = process.env.NEXT_PUBLIC_FALLBACK_BACKEND_URL || 'https://apple-retail-study-apple-retail-sales-strategy.hf.space';

function isProductionLike(): boolean {
  return process.env.VERCEL === '1' || process.env.NODE_ENV === 'production';
}

function isUnsafeBackendUrl(url: string | undefined): boolean {
  if (url == null || typeof url !== 'string') return true;
  const u = url.trim().toLowerCase();
  if (!u.startsWith('http')) return true;
  if (u.startsWith('http://localhost') || u.startsWith('https://localhost')) return true;
  if (u.startsWith('http://127.0.0.1') || u.startsWith('http://[::1]')) return true;
  return false;
}

function getBackendUrls(): string[] {
  if (process.env.VERCEL === '1') {
    return [PRODUCTION_BACKEND_URL.replace(/\/$/, '')];
  }
  const primary = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
  let base = primary;
  if (isUnsafeBackendUrl(base) && isProductionLike()) base = PRODUCTION_BACKEND_URL;
  else if (isUnsafeBackendUrl(base)) base = '';
  if (!base) return [];
  return [base.replace(/\/$/, '')];
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
