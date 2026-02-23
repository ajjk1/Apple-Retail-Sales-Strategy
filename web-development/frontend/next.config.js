/** @type {import('next').NextConfig} */
// /api/:path* → 백엔드(HF Space)로 전달. Vercel 빌드 시 env 미주입/ localhost 주입이어도 destination 이 절대 localhost 가 되지 않도록 상수 사용.
const PRODUCTION_BACKEND_URL = 'https://apple-retail-study-apple-retail-sales-strategy.hf.space';

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

const nextConfig = {
  async rewrites() {
    let raw = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
    // Vercel/프로덕션에서는 localhost·빈값·비공개 주소 무시 후 HF Space 상수 사용 (DNS_HOSTNAME_RESOLVED_PRIVATE 방지)
    if (isUnsafeBackendUrl(raw) && isProductionLike()) {
      raw = PRODUCTION_BACKEND_URL;
    } else if (isUnsafeBackendUrl(raw)) {
      raw = 'http://127.0.0.1:8000';
    }
    const backendUrl = String(raw).replace(/\/$/, '');
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/docs',
        destination: `${backendUrl}/docs`,
      },
      {
        source: '/docs/:path*',
        destination: `${backendUrl}/docs/:path*`,
      },
      {
        source: '/openapi.json',
        destination: `${backendUrl}/openapi.json`,
      },
    ];
  },
};

module.exports = nextConfig;
