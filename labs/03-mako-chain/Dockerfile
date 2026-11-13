#
# 03-mako-chain —— Mako 13 关 WAF 链
#
# 本文件由 scripts/scaffold_lab.py 生成。改编排请改生成器，改题目请改 app.py。
#
# 构建上下文必须是**仓库根目录**（需要 COPY shared/ 与统一前端产物）：
#     docker build -f labs/03-mako-chain/Dockerfile -t ssti-mako-chain:local .
#
# 前置：前端镜像 ssti-frontend:local 必须已存在（scripts/build-frontend.sh）。
#
# 注意：内置的 dockerfile 前端**不支持**在 `COPY --from=` 里做变量展开
# （`# syntax=docker/dockerfile:1` 能支持，但那需要从 Docker Hub 拉 buildkit
#  前端镜像，离线/受限网络下会直接失败）。所以这里用官方推荐的替代写法：
# 先用全局 ARG 把前端镜像变成一个有名字的阶段，再 `COPY --from=<阶段名>`。
ARG FRONTEND_IMAGE=ssti-frontend:local

FROM ${FRONTEND_IMAGE} AS frontend

FROM python:3.11-slim

LABEL org.opencontainers.image.title="ssti-mako-chain" \
      org.opencontainers.image.description="Mako 13 关 WAF 链 SSTI lab (CTF, isolated use only)"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/shared \
    LAB_ID=mako-chain \
    PORT=5000 \
    SSTI_NO_EGRESS=0

WORKDIR /app

# 依赖单独一层，改代码不会触发重装
COPY labs/03-mako-chain/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 公共库（关卡定义 / 渲染编排 / 应用工厂 / flag 处理）
COPY shared/ ./shared/

# 靶场自身的代码与文档（README 同时充当容器内的 /docs 题解）
COPY labs/03-mako-chain/app.py ./app.py
COPY labs/03-mako-chain/README.md ./docs/README.md
COPY labs/03-mako-chain/entrypoint.sh /entrypoint.sh

# 统一前端构建产物（来自文件顶部命名的 frontend 阶段）；
# 场景型靶场自带页面，用不到它也不会报错。
COPY --from=frontend /app/build ./public

RUN chmod +x /entrypoint.sh

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/healthz',timeout=3).status==200 else 1)"

ENTRYPOINT ["/entrypoint.sh"]
