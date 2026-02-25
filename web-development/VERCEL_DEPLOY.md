# Vercel 웹 배포 가이드

Next.js 프론트엔드를 Vercel에 배포하는 방법입니다. **백엔드(FastAPI)**는 Vercel에서 실행되지 않으므로 별도 서비스에 배포한 뒤 API URL만 연결합니다.

---

## 1. 사전 준비

- GitHub 저장소: **https://github.com/ajjk1/web-development**
- Vercel 계정: https://vercel.com (GitHub 로그인 권장)
- 백엔드 배포 URL (선택): Railway, Render, Fly.io 등에 FastAPI 배포 후 URL 확보

---

## 2. Vercel에 프로젝트 연결

1. **https://vercel.com** 접속 → 로그인
2. **Add New...** → **Project**
3. **Import Git Repository**에서 `ajjk1/web-development` 또는 **ajjk1** (전체 저장소) 선택
4. **Configure Project** 화면에서:

   | 설정 | 값 | 비고 |
   |------|-----|------|
   | **Framework Preset** | Next.js | 자동 감지됨 |
   | **Root Directory** | **반드시 설정** (아래 표 참고) | ⚠️ 비워 두면 빌드 실패. 저장소 루트에 Next 앱이 없음 |
   | **Build Command** | `npm run build` | 기본값 유지 |
   | **Output Directory** | (비움) | Next.js 기본값 |
   | **Install Command** | `npm install` | 기본값 유지 |

   **Root Directory 값 (저장소에 따라):**
   - 연결한 저장소가 **ajjk1 전체** (model-server, web-development 포함) → **`web-development/frontend`**
   - 연결한 저장소가 **web-development만** → **`frontend`**

   GitHub-Vercel 연동 오류 시 상세 안내: 저장소 루트의 **`VERCEL_GITHUB_SETUP.md`** 참고.

5. **Environment Variables** (아래 3번 참고) 입력 후 **Deploy** 클릭

---

## 3. 환경 변수 설정

Vercel 프로젝트 → **Settings** → **Environment Variables**에서 추가:

| 이름 | 값 | 용도 |
|------|-----|------|
| `BACKEND_URL` | `https://apple-retail-study-apple-retail-sales-strategy.hf.space` | Next.js rewrites가 API 요청을 전달할 백엔드(HF Space) 주소 |
| `NEXT_PUBLIC_API_URL` | `https://apple-retail-study-apple-retail-sales-strategy.hf.space` | 브라우저에서 API 직접 호출 시 사용. 위와 동일하게 설정 |

**이 프로젝트 기준 (데이터 연동)**

- **대시보드**: [https://apple-retail-sales-strategy-k1kp94g4f-ajjk1.vercel.app](https://apple-retail-sales-strategy-k1kp94g4f-ajjk1.vercel.app)
- **백엔드 API**: [https://apple-retail-study-apple-retail-sales-strategy.hf.space](https://apple-retail-study-apple-retail-sales-strategy.hf.space)
- 위 두 환경 변수를 HF Space URL로 설정한 뒤 **재배포**하면, Vercel 대시보드에서 HF Space 데이터(모델 상태·예측·매출 등)가 표시됩니다.

**다른 백엔드를 쓰는 경우**

- Railway/Render 등 본인 백엔드 URL로 `BACKEND_URL`, `NEXT_PUBLIC_API_URL`를 넣고 재배포하면 됩니다.

---

## 4. Root Directory 확인

저장소 구조에 따라 **Root Directory**만 맞추면 됩니다.

- 저장소가 **ajjk1 전체** (model-server, web-development 포함):
  - Root Directory: **`web-development/frontend`**
- 저장소가 **web-development만** (backend, frontend, start.ps1 등만 있음):
  - Root Directory: **`frontend`**
- 저장소가 **frontend만** 있음:
  - Root Directory: **(비움)**

---

## 5. 배포 후 확인

- 배포가 끝나면 **Visit** 또는 ***.vercel.app** URL로 접속
- API가 연결된 백엔드 URL을 넣었다면 대시보드·매출·안전재고 등이 동작
- API 없이 배포했다면 화면만 보이고 데이터는 “불러올 수 없습니다” 등으로 나올 수 있음 → 백엔드 배포 후 환경 변수 수정·재배포

---

## 6. 백엔드 배포 (선택)

FastAPI 백엔드는 Vercel이 아닌 다른 서비스에 두는 것을 권장합니다.

| 서비스 | 설명 |
|--------|------|
| **Railway** | https://railway.app — GitHub 연결 후 backend 폴더 또는 Docker로 배포 |
| **Render** | https://render.com — Web Service로 Python/FastAPI 선택 후 배포 |
| **Fly.io** | https://fly.io — Docker 또는 Dockerfile로 배포 |

백엔드 배포 후 받은 URL(예: `https://xxx.railway.app`)을 Vercel 환경 변수 `BACKEND_URL`, `NEXT_PUBLIC_API_URL`에 넣고 재배포하면 됩니다.

---

## 7. 요약

1. Vercel에서 **ajjk1/web-development** 저장소 Import
2. **Root Directory**를 `web-development/frontend` 또는 `frontend`로 설정
3. **Environment Variables**에 `BACKEND_URL`, `NEXT_PUBLIC_API_URL` 설정 (백엔드 URL 있으면)
4. **Deploy** 후 *.vercel.app URL로 접속해 확인

이 문서는 프로젝트 루트 또는 `web-development/` 에 두고 참고하면 됩니다.
