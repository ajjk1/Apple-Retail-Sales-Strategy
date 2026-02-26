# Hugging Face Space: FastAPI 백엔드 (포트 7860)
# 경로 규칙: main.py 기준 parent.parent.parent = /app → model-server = /app/model-server
FROM python:3.11-slim

WORKDIR /app

# 프로젝트 루트 구조 유지 (main.py _PROJECT_ROOT = /app, _MODEL_SERVER = /app/model-server)
COPY model-server/ /app/model-server/
COPY web-development/backend/ /app/web-development/backend/

# HF 구동 점검: load_sales_data.py 없으면 빌드 실패 (경로 오류 조기 발견)
RUN test -f /app/model-server/load_sales_data.py || (echo "Build error: model-server/load_sales_data.py not found" && exit 1)

WORKDIR /app/web-development/backend
RUN pip install --no-cache-dir -r requirements.txt

# 배포 시 02.Database for dashboard 경량 SQL 사용 (01.data 대용량 업로드 불필요)
ENV USE_DASHBOARD_SQL=1

# HF Spaces 기본 포트 7860
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
