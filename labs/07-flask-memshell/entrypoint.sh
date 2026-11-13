#!/bin/sh
# 07-flask-memshell —— 统一入口：写 flag 到 /flag（不进镜像层），再以 __main__ 启动应用。
#
# 为什么用 Flask 自带服务器而不是 gunicorn：
#   多个靶场（尤其内存马）依赖应用模块名为 __main__，gunicorn 下会变成
#   gunicorn.app.wsgiapp，部分利用链会失效。本靶场是隔离的单实例教学环境。
set -e

# 出网切断：先落 iptables 规则，再启动应用（本仓库不做权限降级，容器内以 root 运行）。
# 规则只丢弃**新建**的对外连接（--syn），因此宿主机映射进来的入站端口不受影响。
# iptables 不可用时只告警不退出 —— 靶场不能因为加固失败而起不来。
block_egress() {
    if ! command -v iptables >/dev/null 2>&1; then
        echo "[!] 未安装 iptables，跳过出网切断（该靶场的不出网约束未被强制执行）" >&2
        return 0
    fi
    if iptables -A OUTPUT -o eth0 -p tcp --syn -j DROP 2>/dev/null \
       && iptables -A OUTPUT -o eth0 -p udp --dport 53 -j DROP 2>/dev/null; then
        echo "[*] 已切断出网：新建外部 TCP 连接与 DNS 查询被丢弃（入站端口不受影响）" >&2
    else
        echo "[!] 应用 iptables 规则失败（缺少 NET_ADMIN？），出网未被切断" >&2
    fi
}
block_egress

# flag 优先级 GZCTF_FLAG > DASFLAG > FLAG > STATIC_FLAG
#
# ⚠️ 不要写成 FLAG_VALUE="${GZCTF_FLAG:-${DASFLAG:-...}}"：
#   默认值里带的 `{` `}`（flag 本身就有花括号）会把嵌套的 `${VAR:-}`
#   提前闭合，结果是往 /flag 里多写一个 `}`。所以这里先落到变量再用 `||` 逐级兜底。
DEFAULT_FLAG='flag{flask_memshell}'
FLAG_VALUE="${GZCTF_FLAG:-}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${DASFLAG:-}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${FLAG:-}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${STATIC_FLAG:-$DEFAULT_FLAG}"

printf '%s' "$FLAG_VALUE" > /flag
chmod 644 /flag 2>/dev/null || true

echo "[*] $(id -un)@$(hostname) | lab=flask-memshell | 不出网 | flag -> /flag" >&2

exec python /app/app.py
