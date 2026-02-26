"""
엄격 테스트용 공통 픽스처.
- TestClient는 main.app 로드 시 프로젝트 루트·모델서버 경로가 설정된 상태를 사용.
- model-server 모듈 단위 테스트를 위해 sys.path에 model-server 루트 추가.
"""
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

# 프로젝트 루트: conftest 기준 backend/tests -> backend -> web-development -> 루트
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent.parent
_MODEL_SERVER = _PROJECT_ROOT / "model-server"

# backend가 path에 있어야 main 임포트 가능 (pytest 실행 시 보통 cwd=backend)
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
# model-server 단위 테스트용 (load_sales_data 등)
if str(_MODEL_SERVER) not in sys.path:
    sys.path.insert(0, str(_MODEL_SERVER))


@pytest.fixture(scope="session")
def client():
    """FastAPI TestClient (세션 스코프로 앱 1회만 로드)."""
    from main import app
    return TestClient(app)
