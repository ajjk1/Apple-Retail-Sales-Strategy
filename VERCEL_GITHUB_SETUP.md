# GitHub ↔ Vercel 연동 설정 (오류 해결)

이 저장소(ajjk1)는 **모노레포**입니다. Next.js 앱은 `web-development/frontend` 안에 있으므로, Vercel이 빌드할 때 **Root Directory**를 반드시 지정해야 합니다.  
(Vercel은 `vercel.json`으로 Root Directory를 지정할 수 없으며, **대시보드에서만** 설정 가능합니다.)

---

## ✅ 해결 방법 (필수)

1. **Vercel** → https://vercel.com 로그인 후 해당 프로젝트 선택
2. **Settings** → **General**
3. **Root Directory** 항목에서 **Edit** 클릭
4. **`web-development/frontend`** 입력 후 **Save**
5. **Deployments** → 최신 배포 **⋮** → **Redeploy** (선택 시 **Use existing Build Cache** 해제 후 재배포)

---

## 저장소 구조에 따른 Root Directory

| 연결한 GitHub 저장소 | Root Directory 값 |
|----------------------|--------------------|
| **ajjk1** (전체: model-server, web-development 포함) | **`web-development/frontend`** |
| **ajjk1/web-development** (backend, frontend만 있음) | **`frontend`** |

Root Directory를 비워 두면 Vercel은 저장소 루트에서 `package.json`을 찾고, 이 저장소 루트에는 Next.js 앱이 없어 **빌드 실패**가 발생합니다.

---

## Git 연결이 꼬였을 때 (예: 예전 커밋만 배포되는 경우)

1. **Settings** → **Git** → **Disconnect**
2. **Connect Git Repository** → **ajjk1/ajjk1** (또는 사용 중인 저장소) 선택
3. **Configure** 단계에서 **Root Directory**: `web-development/frontend` 지정
4. **Deploy** 실행

---

## 환경 변수 (프로덕션 API 연동)

**Settings** → **Environment Variables**에 다음을 설정한 뒤 재배포하세요.

| 이름 | 값 |
|------|-----|
| `BACKEND_URL` | `https://apple-retail-study-apple-retail-sales-strategy.hf.space` |
| `NEXT_PUBLIC_API_URL` | `https://apple-retail-study-apple-retail-sales-strategy.hf.space` |

자세한 내용은 `web-development/VERCEL_DEPLOY.md`를 참고하세요.
