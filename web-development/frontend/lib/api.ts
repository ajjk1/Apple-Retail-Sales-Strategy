/**
 * 클라이언트에서 사용할 백엔드 베이스 URL.
 * Next.js는 NEXT_PUBLIC_ 접두사가 있는 변수만 브라우저에 노출하므로, 클라이언트 fetch 시 반드시 NEXT_PUBLIC_API_URL 사용.
 * 끝 슬래시 제거하여 이중 슬래시 방지.
 */
function getApiBase(): string {
  if (typeof window === 'undefined') return '';
  const env = process.env.NEXT_PUBLIC_API_URL;
  if (env && typeof env === 'string') return env.replace(/\/$/, '');
  return '';
}

const API_TIMEOUT_MS = 25000;

/** API 호출: 상대경로(같은 오리진 → rewrites) 우선으로 CORS 없이 요청, 실패 시 localhost·NEXT_PUBLIC_API_URL 순 폴백. */
export async function apiGet<T = unknown>(path: string): Promise<T | null> {
  const fixed = getApiBase();
  const bases: string[] =
    fixed && fixed !== ''
      ? ['', 'http://localhost:8000', 'http://127.0.0.1:8000', fixed]
      : ['', 'http://localhost:8000', 'http://127.0.0.1:8000'];
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

/** POST 요청 (피드백 등). 상대경로 우선 → localhost 폴백. */
export async function apiPost<T = unknown>(path: string, body: object): Promise<T | null> {
  const fixed = getApiBase();
  const bases: string[] =
    fixed && fixed !== ''
      ? ['', 'http://localhost:8000', 'http://127.0.0.1:8000', fixed]
      : ['', 'http://localhost:8000', 'http://127.0.0.1:8000'];
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
