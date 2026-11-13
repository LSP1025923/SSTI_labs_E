#!/bin/sh
# 03-mako-chain —— 统一入口：写 flag 到 /flag（不进镜像层），再以 __main__ 启动应用。
#
# 为什么用 Flask 自带服务器而不是 gunicorn：
#   多个靶场（尤其内存马）依赖应用模块名为 __main__，gunicorn 下会变成
#   gunicorn.app.wsgiapp，部分利用链会失效。本靶场是隔离的单实例教学环境。
set -e

# flag 优先级 GZCTF_FLAG > DASFLAG > FLAG > STATIC_FLAG
#
# ⚠️ 不要写成 FLAG_VALUE="${GZCTF_FLAG:-${DASFLAG:-...}}"：
#   默认值里带的 `{` `}`（flag 本身就有花括号）会把嵌套的 `${VAR:-}`
#   提前闭合，结果是往 /flag 里多写一个 `}`。所以这里先落到变量再用 `||` 逐级兜底。
DEFAULT_FLAG='flag{mako_chain}'
FLAG_VALUE="${GZCTF_FLAG:-}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${DASFLAG:-}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${FLAG:-}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${STATIC_FLAG:-$DEFAULT_FLAG}"

printf '%s' "$FLAG_VALUE" > /flag
chmod 644 /flag 2>/dev/null || true

echo "[*] $(id -un)@$(hostname) | lab=mako-chain | flag -> /flag" >&2

exec python /app/app.py
