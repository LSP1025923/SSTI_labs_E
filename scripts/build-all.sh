#!/usr/bin/env bash
# 构建全部靶场镜像（先前端，再各靶场）。
#
# 用法：
#   scripts/build-all.sh              # 构建 01–07（Python 系）
#   scripts/build-all.sh --with-java  # 额外构建 08（Java，首次很慢）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WITH_JAVA=0
[[ "${1:-}" == "--with-java" ]] && WITH_JAVA=1

"$ROOT/scripts/build-frontend.sh"

build() { # build <lab-dir> <tag>
  echo ""
  echo "[*] 构建 $2（labs/$1/Dockerfile）"
  docker build -f "$ROOT/labs/$1/Dockerfile" -t "$2:local" "$ROOT"
}

build 01-jinja-waf-fenjing  ssti-jinja-waf-fenjing
build 02-jinja-chain        ssti-jinja-chain
build 03-mako-chain         ssti-mako-chain
build 04-tornado-chain      ssti-tornado-chain
build 05-jinja-sandbox      ssti-jinja-sandbox
build 06-blind-ssti         ssti-blind
build 07-flask-memshell     ssti-flask-memshell

if [[ "$WITH_JAVA" == "1" ]]; then
  echo ""
  echo "[*] 构建 08-freemarker-memshell（Maven 首次下载依赖，可能 5–15 分钟）"
  docker build -t ssti-freemarker-memshell:local "$ROOT/labs/08-freemarker-memshell"
fi

echo ""
echo "[+] 完成。镜像列表："
docker images --format '{{.Repository}}:{{.Tag}}' | grep -E '^ssti-' || true
echo ""
echo "    启动：scripts/up-all.sh     健康检查：scripts/verify_labs.py"
