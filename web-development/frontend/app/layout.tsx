import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Apple 리테일 대시보드',
  description: 'Apple 리테일 재고 전략 현황',
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
