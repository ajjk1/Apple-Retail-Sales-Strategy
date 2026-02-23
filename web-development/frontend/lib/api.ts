/**
 * 클라이언트 전용: 백엔드 베이스 URL. NEXT_PUBLIC_ 접두사만 브라우저에 노출되므로 반드시 NEXT_PUBLIC_API_URL 사용.
 * localhost 폴백 없음 — Vercel 배포 시 환경 변수에 설정된 URL만 사용 (404/DNS 에러 방지).
 */
function getApiBase(): string {
  if (typeof window === 'undefined') return '';
  const env = process.env.NEXT_PUBLIC_API_URL;
  if (env && typeof env === 'string') return env.replace(/\/$/, '');
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
