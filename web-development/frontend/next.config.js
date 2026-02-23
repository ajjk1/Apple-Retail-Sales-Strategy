/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // .env.local의 BACKEND_URL 사용 권장 (예: http://127.0.0.1:8000). 미설정 시 localhost:8000
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
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
