# 竹林司马后端Dockerfile

# 第一阶段：构建依赖
FROM python:3.11-slim as builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖（用户目录）
RUN pip install --user --no-cache-dir -r requirements.txt

# 第二阶段：运行应用
FROM python:3.11-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN groupadd -r zhulin && useradd -r -g zhulin zhulin

# 从构建阶段复制已安装的包
COPY --from=builder /root/.local /root/.local

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/logs /app/uploads && \
    chown -R zhulin:zhulin /app

# 设置权限
RUN chmod +x /app/scripts/*.sh

# 设置PATH
ENV PATH=/root/.local/bin:$PATH

# 切换到非root用户
USER zhulin

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 运行应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]