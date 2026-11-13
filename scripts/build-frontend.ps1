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
#  受限网络下会超时），官方建议的替代写法就是先 FROM 一个带名字的阶段。
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$image = if ($env:FRONTEND_IMAGE) { $env:FRONTEND_IMAGE } else { 'ssti-frontend:local' }

Write-Host "[*] 构建前端镜像 $image（context: frontend/）"
docker build -t $image (Join-Path $root 'frontend')
if ($LASTEXITCODE -ne 0) { throw "前端镜像构建失败" }

Write-Host "[*] 校验产物：镜像内 /app/build 必须直接包含 index.html"
docker run --rm --entrypoint ls $image -la /app/build
if ($LASTEXITCODE -ne 0) { throw "前端产物校验失败" }

Write-Host "[+] 完成：$image"
