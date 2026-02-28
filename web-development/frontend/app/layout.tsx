import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Apple 리테일 대시보드',
  description: 'AI 활용한 수요 매층 재고 추천 시스템',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" style={{ height: '100%' }}>
      <body className="min-h-screen min-h-[100vh] bg-[#f5f5f7] text-[#1d1d1f] antialiased" style={{ minHeight: '100vh' }}>
        {children}
      </body>
    </html>
  );
}
