# Apple 리테일 대시보드 (Vue.js)

Vue 3 + Vite + TypeScript + Vue Router + Tailwind CSS 기반 프론트엔드입니다.  
기존 Next.js 프론트엔드와 **동일한 백엔드 API**를 사용합니다.

## 기술 스택

- **Vue 3** (Composition API, `<script setup>`)
- **Vite** (빌드 도구)
- **Vue Router** (라우팅)
- **TypeScript**
- **Tailwind CSS**

## 실행 방법

백엔드가 먼저 실행 중이어야 합니다 (포트 8000).

```bash
cd web-development/frontend-vue
npm install
npm run dev
```

- **Vue 대시보드**: http://localhost:3001  
- 개발 서버는 `/api/*` 요청을 http://localhost:8000 으로 프록시합니다.

## 빌드

```bash
npm run build
npm run preview   # 빌드 결과 미리보기
```

## 프로젝트 구조

```
frontend-vue/
├── src/
│   ├── main.ts       # 엔트리, Vue Router 등록
│   ├── App.vue       # 루트 컴포넌트
│   ├── style.css     # Tailwind
│   └── views/
│       └── Dashboard.vue   # 대시보드 페이지
├── index.html
├── vite.config.ts    # 프록시: /api → 백엔드
└── package.json
```

## Next.js 프론트엔드와 비교

| 항목     | Next.js (frontend) | Vue.js (frontend-vue) |
|----------|--------------------|------------------------|
| 포트     | 3000               | 3001                   |
| 프레임워크 | React + Next.js   | Vue 3 + Vite          |
| 백엔드 API | 동일 (localhost:8000) | 동일 (프록시)        |
