# =====================================================================
# 多阶段 Dockerfile：前端构建 -> 后端运行
# 最终镜像内同时包含：
#   - LibreOffice + poppler-utils（PPT->PDF->PNG 必备）
#   - Python 3.12 + FastAPI 应用
#   - 前端 dist/ 由 FastAPI 直接 serve（生产环境同源，无 CORS 问题）
# =====================================================================

# ---------- Stage 1: 构建前端 ----------
FROM node:20-bookworm-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: 后端运行时 ----------
FROM python:3.12-slim-bookworm AS runtime

# 安装 LibreOffice 与 PDF 渲染工具
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-impress \
        libreoffice-core \
        libreoffice-common \
        poppler-utils \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        fonts-dejavu \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 依赖
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r backend/requirements.txt

# 后端代码
COPY backend/ ./backend/

# 前端构建产物（由 FastAPI 静态托管 / 入口在 backend/app/main.py 中挂载）
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 创建非 root 用户
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    SERVE_STATIC_DIR=/app/frontend/dist \
    PORT=8000

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT}/healthz || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
