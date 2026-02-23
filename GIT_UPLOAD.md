# GitHub 업로드 가이드 (폴더 트리 구조 + 브랜치)

현재 프로젝트 폴더 구조가 그대로 브랜치에 반영됩니다. 아래 순서대로 진행하세요.

---

## 1. 브랜치 정리

- 기본 브랜치 이름: **main** (이미 생성된 상태)
- 다른 브랜치로 올리고 싶다면 2단계 후에 브랜치 생성/전환

---

## 2. 첫 커밋 & 푸시 (폴더 구조 유지)

아래 명령을 **프로젝트 루트(ajjk1)** 에서 실행하세요.

```powershell
cd d:\82.CLASS\88.PROJECT\01.assignment\ajjk1

# 1) 전체 폴더/파일 추가 (.gitignore 제외된 항목은 자동 제외)
git add .

# 2) 추가될 내용 확인 (폴더 트리 유지)
git status

# 3) 첫 커밋
git commit -m "Initial commit: 프로젝트 폴더 구조 업로드"

# 4) GitHub 원격 저장소 연결
git remote add origin https://github.com/ajjk1/web-development.git

# 5) main 브랜치로 푸시 (폴더 트리 그대로 업로드)
git branch -M main
git push -u origin main
```

- `git add .` 시 **현재 디렉터리 트리 전체**가 스테이징되며, `.gitignore`에 있는 항목만 제외됩니다.
- 따라서 `model-server/`, `web-development/` 등 폴더 구조가 그대로 커밋·푸시됩니다.

---

## 3. 다른 브랜치에 올리고 싶을 때

예: `backup` 브랜치에 같은 내용 올리기

```powershell
# 현재 main 기준으로 backup 브랜치 생성 후 전환
git checkout -b backup

# 원격에 backup 브랜치 푸시
git push -u origin backup
```

예: 처음부터 `develop` 브랜치만 사용

```powershell
git checkout -b develop
git add .
git commit -m "Initial commit: 프로젝트 폴더 구조"
git remote add origin https://github.com/ajjk1/web-development.git
git push -u origin develop
```

---

## 4. 업로드 후 GitHub에서 확인

- GitHub 저장소 페이지 → **Code** 탭에서 폴더 트리가 그대로 보이면 성공입니다.
- **main** (또는 푸시한 브랜치) 선택 시 해당 브랜치 기준 폴더 구조가 표시됩니다.

---

## 5. 주의사항

| 항목 | 설명 |
|------|------|
| **.env.local** | .gitignore에 포함되어 있어 업로드되지 않습니다. (의도된 동작) |
| **node_modules, .next** | 제외됨. 클론 후 `npm install`, `npm run dev`로 재생성합니다. |
| **01.data/*.sql** | 약 94MB 포함됩니다. 제외하려면 .gitignore에 `model-server/01.data/*.sql` 추가 |

원격 저장소: https://github.com/ajjk1/web-development.git
