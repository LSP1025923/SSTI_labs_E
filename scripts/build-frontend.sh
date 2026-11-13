#!/usr/bin/env bash
# 构建统一前端镜像 ssti-frontend:local。
#
# 所有 Python 靶场的 Dockerfile 都用
#     FROM ${FRONTEND_IMAGE} AS frontend
#     COPY --from=frontend /app/build ./public
# 取用它的产物，所以**必须先构建它**，否则单靶场 build 会失败并提示
# pull access denied for ssti-frontend。
#
# 为什么是「先 FROM 成阶段」而不是直接 COPY --from=${VAR}：
# Docker 内置的 dockerfile 前端不支持在 --from 里做变量展开
# （# syntax=docker/dockerfile:1 支持，但那要从 Docker Hub 拉 buildkit 前端镜像，
#  离线/受限网络下会超时），官方建议的替代写法就是先 FROM 一个带名字的阶段。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${FRONTEND_IMAGE:-ssti-frontend:local}"

echo "[*] 构建前端镜像 ${IMAGE}（context: frontend/）"
docker build -t "$IMAGE" "$ROOT/frontend"

echo "[*] 校验产物：镜像内 /app/build 必须直接包含 index.html"
docker run --rm --entrypoint ls "$IMAGE" -la /app/build

echo "[+] 完成：${IMAGE}"
