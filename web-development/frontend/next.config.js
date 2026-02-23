/** @type {import('next').NextConfig} */
// /api/:path* → 백엔드(HF Space)로 전달. Vercel 빌드 시 env 미주입이어도 destination 이 절대 localhost 가 되지 않도록 상수 사용.
const PRODUCTION_BACKEND_URL = 'https://apple-retail-study-apple-retail-sales-strategy.hf.space';

const nextConfig = {
  async rewrites() {
    let raw = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
    // Vercel 배포(VERCEL=1) 또는 프로덕션에서 env 없으면 무조건 HF Space URL 사용. 빈 문자열이면 localhost 로 해석되어 404 발생.
    if (!raw || typeof raw !== 'string' || !raw.startsWith('http')) {
      if (process.env.VERCEL === '1' || process.env.NODE_ENV === 'production') {
        raw = PRODUCTION_BACKEND_URL;
      } else {
        raw = 'http://127.0.0.1:8000';
      }
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
