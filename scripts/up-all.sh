#!/usr/bin/env bash
# 一键起全部靶场：先确保前端镜像存在，再交给根 compose。
#
# 用法：
#   scripts/up-all.sh              # 起 01–07
#   scripts/up-all.sh --with-java  # 额外起 08
#   scripts/up-all.sh --build      # 重新构建镜像
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-ssti-frontend:local}"
PROFILE_ARGS=()
COMPOSE_ARGS=()

for arg in "$@"; do
  case "$arg" in
    --with-java) PROFILE_ARGS+=(--profile java) ;;
    --build)     COMPOSE_ARGS+=(--build) ;;
    *) echo "未知参数: $arg" >&2; exit 2 ;;
  esac
done

# 前端镜像是所有 Python 靶场构建时的前置依赖
if ! docker image inspect "$FRONTEND_IMAGE" >/dev/null 2>&1; then
  echo "[*] 未找到 $FRONTEND_IMAGE，先构建它"
  "$ROOT/scripts/build-frontend.sh"
fi

echo "[*] docker compose ${PROFILE_ARGS[*]:-} up -d ${COMPOSE_ARGS[*]:-}"
cd "$ROOT"
docker compose "${PROFILE_ARGS[@]}" up -d "${COMPOSE_ARGS[@]}"

echo ""
echo "[+] 状态："
docker compose "${PROFILE_ARGS[@]}" ps

cat <<'EOF'

端口速查
  8091 01-jinja-waf-fenjing   8092 02-jinja-chain     8093 03-mako-chain
  8094 04-tornado-chain       8095 05-jinja-sandbox   8096 06-blind-ssti
  8097 07-flask-memshell      8098 08-freemarker-memshell（--with-java）
  8099 09-bottle-chain

健康检查：scripts/verify_labs.py
EOF
