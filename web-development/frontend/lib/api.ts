/**
 * 클라이언트 전용: 백엔드 베이스 URL.
 * API 경로는 반드시 '/api/...' 상대 경로로 호출하면 next.config.js rewrites 규칙(source: /api/:path*)과 일치합니다.
 * NEXT_PUBLIC_API_URL 미설정/ localhost 시 vercel.app에서는 fallback 사용.
 */
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

const API_TIMEOUT_MS = 25000;

/** API 호출: NEXT_PUBLIC_API_URL 우선. 설정 시 해당 URL만 사용, 미설정 시 상대경로(rewrites)만 시도. localhost 미사용. */
export async function apiGet<T = unknown>(path: string): Promise<T | null> {
  const fixed = getApiBase();
  const bases: string[] = fixed ? [fixed] : [''];
  for (const base of bases) {
    try {
      const url = base ? `${base}${path}` : path;
      const ac = new AbortController();
      const t = setTimeout(() => ac.abort(), API_TIMEOUT_MS);
      const res = await fetch(url, { signal: ac.signal, cache: 'no-store' });
      clearTimeout(t);
      if (res?.ok) return (await res.json()) as T;
    } catch {
      continue;
    }
  }
  return null;
}

/** POST 요청: NEXT_PUBLIC_API_URL 사용. 미설정 시 상대경로만. localhost 미사용. */
export async function apiPost<T = unknown>(path: string, body: object): Promise<T | null> {
  const fixed = getApiBase();
  const bases: string[] = fixed ? [fixed] : [''];
  for (const base of bases) {
    try {
      const url = base ? `${base}${path}` : path;
      const ac = new AbortController();
      const t = setTimeout(() => ac.abort(), API_TIMEOUT_MS);
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: ac.signal,
        cache: 'no-store',
      });
      clearTimeout(t);
      if (res?.ok) return (await res.json()) as T;
    } catch {
      continue;
    }
  }
  return null;
}
