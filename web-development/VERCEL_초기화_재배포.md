# Vercel 초기화 후 새로 배포하기

배포가 계속 실패할 때 아래 순서대로 진행하세요.

---

## 방법 1: 빌드 캐시 삭제 후 재배포 (가장 먼저 시도)

1. **Vercel** → [ajjk1/web-development](https://vercel.com/ajjk1/web-development) → **Deployments**
2. **맨 위 배포** 클릭(실패한 것도 가능)
3. 오른쪽 위 **⋮** (점 3개) → **Redeploy**
4. **"Use existing Build Cache"** 체크 **해제**
5. **Redeploy** 클릭

→ 이렇게 하면 최신 GitHub `main`(812c70f) 기준으로 캐시 없이 다시 빌드됩니다.

---

## 방법 2: Root Directory 다시 확인 후 재배포

1. **Vercel** → **web-development** → **Settings** → **General**
2. **Root Directory** 확인:
   - 저장소 루트에 `web-development` 폴더가 있으면: **`web-development/frontend`**
   - 저장소 루트가 이미 `frontend`만 있으면: 비워 두기
3. **Save** 후 **Deployments** → 맨 위 배포 **Redeploy** (캐시 해제 옵션 켜기)

---

## 방법 3: Git 연결 초기화 후 다시 연결

1. **Vercel** → **web-development** → **Settings** → **Git**
2. **Disconnect** (Git 연결 해제)
3. 같은 프로젝트에서 **Connect Git Repository** → **GitHub** → **ajjk1/web-development** 선택
4. **Configure** 단계에서:
   - **Root Directory**: `web-development/frontend` 입력
   - **Framework Preset**: Next.js
5. **Deploy** 로 첫 배포 실행

---

## 방법 4: CLI로 직접 배포 (로그인 필요)

터미널에서:

```powershell
cd d:\82.CLASS\88.PROJECT\01.assignment\ajjk1\web-development\frontend
npx vercel login
npx vercel --prod
```

로그인 후 현재 폴더 코드가 그대로 프로덕션에 배포됩니다.

---

## ⚠️ 빌드 로그에서 "commit: a113750"으로 나오는 경우

Vercel이 **예전 커밋(a113750)**만 가져와서 빌드하고 있는 상태입니다. 우리가 수정한 커밋(812c70f, 359bb94)이 반영되지 않아 계속 같은 에러가 납니다.

- **해결**: **방법 3 (Git 연결 해제 후 재연결)**을 하거나, Vercel **Settings** → **Git**에서 연결된 저장소/브랜치가 **ajjk1/web-development**, **main**인지 확인하세요.
- GitHub에서 **main** 브랜치 최신 커밋이 "chore: explicit Vercel build config..." 또는 "fix: add target ES2017..." 인지 확인한 뒤, Vercel에서 **Redeploy** 시 반드시 **최신 main**에서 배포되도록 하세요.

---

## 현재 저장소 상태

- `main` 최신 커밋: **359bb94** (Vercel 설정·가이드), **812c70f** (tsconfig 수정)
- 빌드 오류 수정 반영됨 (Set 이터레이션, Pie label, downlevelIteration)
- Next.js 14.2.24로 업그레이드 (deprecated/보안 경고 완화)
- 위 방법 1부터 순서대로 시도하면 됩니다.
