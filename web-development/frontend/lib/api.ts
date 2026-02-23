/** 백엔드 API 베이스 URL (NEXT_PUBLIC_API_URL 우선, 없으면 상대경로·직접 URL 시도) */
function getApiBase(): string {
  if (typeof window === 'undefined') return '';
  const env = process.env.NEXT_PUBLIC_API_URL;
  if (env && typeof env === 'string') return env.replace(/\/$/, '');
  return '';
}

const API_TIMEOUT_MS = 25000;

/** API 호출: 타임아웃·재시도. 상대경로 우선(Next.js rewrites → 백엔드 8000)으로 CORS 회피. */
export async function apiGet<T = unknown>(path: string): Promise<T | null> {
  const fixed = getApiBase();
  // 항상 상대경로('') 먼저 시도 → 같은 오리진(3000) 요청이 Next rewrites로 8000 프록시. 매출/추천 대시보드 안정 로드.
  const bases: string[] = [''];
  if (fixed && fixed !== '') bases.push(fixed);
  bases.push('http://localhost:8000', 'http://127.0.0.1:8000');
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

/** POST 요청 (피드백 등). */
export async function apiPost<T = unknown>(path: string, body: object): Promise<T | null> {
  const fixed = getApiBase();
  const bases: string[] = [''];
  if (fixed && fixed !== '') bases.push(fixed);
  bases.push('http://localhost:8000', 'http://127.0.0.1:8000');
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
