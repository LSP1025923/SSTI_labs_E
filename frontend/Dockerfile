#
# 统一 SSTI 靶场前端 —— 多阶段构建
#
# 产物位置约定（非常重要，各靶场镜像靠它 COPY）：
#   最终镜像内 /app/build/index.html  ← 直接在 /app/build 下
#   各靶场这样取用：
#     ARG FRONTEND_IMAGE=ssti-frontend:local
#     COPY --from=${FRONTEND_IMAGE} /app/build ./public
#
# 因此最终阶段只做一件事：把一个静态目录放进 /app/build。
# 不装 nginx、不装任何运行时，镜像体积最小（busybox/alpine 即可）。
#
# 构建：
#   docker build -t ssti-frontend:local .
# 校验：
#   docker run --rm ssti-frontend:local ls -la /app/build

ARG NODE_IMAGE=node:20-alpine

# ------------------------------------------------------------------ build
FROM ${NODE_IMAGE} AS build

WORKDIR /app

# 先只拷贝依赖清单，让 npm ci 这一层可以被 Docker 缓存复用。
COPY package.json package-lock.json ./

# 有 lockfile 时使用 npm ci：可复现、更快、更严格。
RUN npm ci --no-audit --no-fund

# 再拷贝源码（node_modules / build 由 .dockerignore 排除）。
COPY . .

# 产出 /app/build/index.html + /app/build/assets/*
RUN npm run build

# ------------------------------------------------------------------- dist
FROM alpine:3.20 AS dist

WORKDIR /app

# 只搬运静态产物，一个字节的构建工具都不留。
COPY --from=build /app/build /app/build

# 不带参数运行该镜像时，直接列出产物便于排查。
CMD ["ls", "-la", "/app/build"]
