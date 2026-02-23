/** @type {import('next').NextConfig} */
// /api/* 요청은 rewrites로 백엔드로 전달. Vercel/프로덕션에서는 destination을 리터럴 HF URL로만 고정 (Target: localhost 방지).
const PRODUCTION_BACKEND_URL = 'https://apple-retail-study-apple-retail-sales-strategy.hf.space';

// 프로덕션 rewrites: 하드코딩된 HF URL만 사용 (환경 변수 미참조로 빌드/런타임에서 localhost로 바뀔 가능성 제거)
const PRODUCTION_REWRITES = [
  { source: '/api/:path*', destination: `${PRODUCTION_BACKEND_URL}/api/:path*` },
  { source: '/docs', destination: `${PRODUCTION_BACKEND_URL}/docs` },
  { source: '/docs/:path*', destination: `${PRODUCTION_BACKEND_URL}/docs/:path*` },
  { source: '/openapi.json', destination: `${PRODUCTION_BACKEND_URL}/openapi.json` },
];

// Vercel 빌드 시 API URL 유효성 체크 및 명확한 콘솔 메시지
function assertProductionRewriteDestination() {
  if (process.env.VERCEL !== '1') return;
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || process.env.BACKEND_URL || '';
  const isUnsetOrLocalhost =
    !apiUrl ||
    typeof apiUrl !== 'string' ||
    apiUrl.trim() === '' ||
    /localhost|127\.0\.0\.1|\[::1\]/i.test(apiUrl);
  if (isUnsetOrLocalhost) {
    console.warn(
      '[Vercel build] NEXT_PUBLIC_API_URL (or BACKEND_URL) is not set or points to localhost. Rewrites use fixed destination:',
      PRODUCTION_BACKEND_URL
    );
  }
  // destination이 절대 localhost가 아님을 검증
  const hasInvalidDestination = PRODUCTION_REWRITES.some(
    (r) =>
      typeof r.destination === 'string' &&
      /localhost|127\.0\.0\.1|\[::1\]/i.test(r.destination)
  );
  if (hasInvalidDestination) {
    console.error('[Vercel build] FATAL: Rewrite destination must not be localhost. Check next.config.js.');
    throw new Error('Invalid rewrite destination: localhost is not allowed in production.');
  }
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
    // Vercel 또는 NODE_ENV=production: 리터럴 PRODUCTION_REWRITES만 사용 (process.env 미사용)
    if (process.env.VERCEL === '1' || process.env.NODE_ENV === 'production') {
      assertProductionRewriteDestination();
      return PRODUCTION_REWRITES;
    }
    // 로컬 개발: env 우선, 없거나 localhost면 개발용 fallback
    const devRaw = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
    const devUrl = !isUnsafeBackendUrl(devRaw) ? devRaw : process.env.DEV_BACKEND_URL || 'http://127.0.0.1:8000';
    return getRewrites(devUrl);
  },
};

// 빌드 시점( config 로드 시) Vercel 환경에서 destination 유효성 검사
if (process.env.VERCEL === '1') {
  try {
    assertProductionRewriteDestination();
  } catch (e) {
    console.error('[next.config.js]', e.message);
    throw e;
  }
}

module.exports = nextConfig;
