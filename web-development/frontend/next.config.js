/** @type {import('next').NextConfig} */
const nextConfig = {
  // rewrites: 환경 변수만 사용. localhost 하드코딩 없음 (Vercel 404/DNS 에러 방지).
  // 프로덕션: BACKEND_URL 또는 NEXT_PUBLIC_API_URL 필수. 개발: 미설정 시에만 127.0.0.1:8000 사용.
  async rewrites() {
    let raw = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL;
    if (!raw && process.env.NODE_ENV === 'development') {
      raw = 'http://127.0.0.1:8000';
    }
    const backendUrl = typeof raw === 'string' ? raw.replace(/\/$/, '') : '';
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
