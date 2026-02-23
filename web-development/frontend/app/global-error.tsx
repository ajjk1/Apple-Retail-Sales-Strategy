'use client';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="ko">
      <body style={{ margin: 0, padding: 0, background: '#f5f5f7', color: '#1d1d1f', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', maxWidth: 400, padding: 24 }}>
          <h1 style={{ color: '#ef4444', fontSize: 20, marginBottom: 16 }}>오류가 발생했습니다</h1>
          <p style={{ color: '#6e6e73', fontSize: 14, marginBottom: 24 }}>{error.message || '알 수 없는 오류'}</p>
          <button
            onClick={reset}
            style={{ padding: '12px 24px', borderRadius: 12, background: '#fff', color: '#1d1d1f', border: '1px solid #e5e5e7', cursor: 'pointer', fontSize: 14 }}
          >
            다시 시도
          </button>
        </div>
      </body>
    </html>
  );
}
