'use client';

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Application error:', error);
  }, [error]);

  return (
    <main className="min-h-screen bg-[#f5f5f7] text-[#1d1d1f] flex flex-col items-center justify-center p-8">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-bold text-red-500 mb-4">오류가 발생했습니다</h1>
        <p className="text-[#6e6e73] text-sm mb-6">
          {error.message || '알 수 없는 오류가 발생했습니다.'}
        </p>
        <button
          onClick={reset}
          className="px-6 py-3 rounded-xl bg-white border border-gray-200 hover:bg-gray-50 text-[#1d1d1f] font-medium transition-colors shadow-sm"
        >
          다시 시도
        </button>
      </div>
    </main>
  );
}
