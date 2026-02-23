/** @type {import('next').NextConfig} */
// /api/:path* 요청이 백엔드( HF Space )로 정확히 전달되도록 rewrites 목적지를 환경 변수 또는 프로덕션 상수로 설정.
const PRODUCTION_BACKEND_URL = 'https://apple-retail-study-apple-retail-sales-strategy.hf.space';

const nextConfig = {
  async rewrites() {
    let raw = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
    if (!raw || typeof raw !== 'string') {
      if (process.env.NODE_ENV === 'production') {
        raw = PRODUCTION_BACKEND_URL;
      } else {
        raw = 'http://127.0.0.1:8000';
      }
    }
    const backendUrl = raw.replace(/\/$/, '');
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
