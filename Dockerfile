# Hugging Face Space: FastAPI 백엔드 (포트 7860)
FROM python:3.11-slim

WORKDIR /app

# 프로젝트 루트 구조 유지 (main.py에서 parent.parent.parent = /app 기준)
COPY model-server/ /app/model-server/
COPY web-development/backend/ /app/web-development/backend/

WORKDIR /app/web-development/backend
RUN pip install --no-cache-dir -r requirements.txt

# HF Spaces 기본 포트 7860
EXPOSE 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
