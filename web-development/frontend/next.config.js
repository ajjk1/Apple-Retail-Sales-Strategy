/** @type {import('next').NextConfig} */
const nextConfig = {
  // Vercel: Settings → Environment Variables 에 BACKEND_URL, NEXT_PUBLIC_API_URL 설정 시 빌드/런타임에 자동 주입. 별도 env 선언 불필요.
  async rewrites() {
    const raw =
      process.env.BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://127.0.0.1:8000';
    const backendUrl = typeof raw === 'string' ? raw.replace(/\/$/, '') : raw;
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
