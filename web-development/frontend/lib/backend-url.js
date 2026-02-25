/**
 * 프로덕션 백엔드 URL 단일 소스.
 * next.config.js, API route, lib/api.ts 등에서 이 값을 사용함.
 * HF Space URL 변경 시: (1) 이 파일 수정 (2) vercel.json 의 rewrites destination 수동 동기화.
 */
module.exports = {
  PRODUCTION_BACKEND_URL: 'https://apple-retail-study-apple-retail-sales-strategy.hf.space',
};
