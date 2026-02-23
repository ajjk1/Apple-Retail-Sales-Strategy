/** @type {import('next').NextConfig} */
// /api/* 요청은 rewrites로 백엔드로 전달. Vercel 배포 시 환경 변수와 무관하게 항상 HF Space URL만 사용 (Target: localhost 방지).
const PRODUCTION_BACKEND_URL = 'https://apple-retail-study-apple-retail-sales-strategy.hf.space';

// Vercel 빌드 시 NEXT_PUBLIC_API_URL 미정의/ localhost 시 경고 및 fallback 안내
if (process.env.VERCEL === '1') {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL || '';
  const isUnsetOrLocalhost =
    !apiUrl ||
    typeof apiUrl !== 'string' ||
    apiUrl.trim() === '' ||
    /localhost|127\.0\.0\.1|\[::1\]/i.test(apiUrl);
  if (isUnsetOrLocalhost) {
    console.warn(
      '[Vercel build] NEXT_PUBLIC_API_URL (or BACKEND_URL) is not set or points to localhost. Rewrites will use fallback:',
      PRODUCTION_BACKEND_URL
    );
  }
}

function isProductionLike() {
  return process.env.VERCEL === '1' || process.env.NODE_ENV === 'production';
}

function isUnsafeBackendUrl(url) {
  if (!url || typeof url !== 'string') return true;
  const u = url.trim().toLowerCase();
  if (!u.startsWith('http')) return true;
  if (u.startsWith('http://localhost') || u.startsWith('https://localhost')) return true;
  if (u.startsWith('http://127.0.0.1') || u.startsWith('http://[::1]')) return true;
  return false;
}

function getRewrites(backendUrl) {
  const base = String(backendUrl).replace(/\/$/, '');
  return [
    { source: '/api/:path*', destination: `${base}/api/:path*` },
    { source: '/docs', destination: `${base}/docs` },
    { source: '/docs/:path*', destination: `${base}/docs/:path*` },
    { source: '/openapi.json', destination: `${base}/openapi.json` },
  ];
}

const nextConfig = {
  async rewrites() {
    // Vercel 환경: 환경 변수와 무관하게 항상 HF Space를 destination으로 사용 (DNS_HOSTNAME_RESOLVED_PRIVATE 방지)
    if (process.env.VERCEL === '1') {
      return getRewrites(PRODUCTION_BACKEND_URL);
    }
    // 그 외 프로덕션: env가 유효한 공개 URL일 때만 사용, 아니면 HF Space fallback
    if (isProductionLike()) {
      const raw = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
      const url = !isUnsafeBackendUrl(raw) ? raw : PRODUCTION_BACKEND_URL;
      return getRewrites(url);
    }
    // 로컬 개발: env 우선, 없거나 localhost면 개발용 fallback (환경 변수로 변경 가능)
    const devRaw = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
    const devUrl = !isUnsafeBackendUrl(devRaw) ? devRaw : process.env.DEV_BACKEND_URL || 'http://127.0.0.1:8000';
    return getRewrites(devUrl);
  },
};

module.exports = nextConfig;
