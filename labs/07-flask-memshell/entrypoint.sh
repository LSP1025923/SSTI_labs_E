#!/bin/sh
# 07-flask-memshell —— 统一入口：写 flag 到 /flag（不进镜像层），再以 __main__ 启动应用。
#
# 为什么用 Flask 自带服务器而不是 gunicorn：
#   多个靶场（尤其内存马）依赖应用模块名为 __main__，gunicorn 下会变成
#   gunicorn.app.wsgiapp，部分利用链会失效。本靶场是隔离的单实例教学环境。
set -e

# ---------------------------------------------------------------------------
# 出网切断（本靶场的核心教学前提）
#
# 目标：让「反弹 shell / 外连下载 / 直连外部 DNS」全部失效，
#       同时**保留**入站端口与容器内环回（环回要留给自己人做验证脚本）。
#
# 规则说明：
#   ! -o lo -p tcp --syn        —— 丢弃所有「非环回」的新建 TCP 连接。
#                                  用 ! -o lo 而不是 -o eth0：接口名不保证叫 eth0。
#                                  入站连接的**回包**不是 SYN，所以已发布的端口照常可用。
#   -p udp --dport 53 / tcp 53  —— 丢弃**所有**接口上的 DNS。
#                                  不加 -o 限定，因为 Docker 的内嵌解析器在 127.0.0.11，
#                                  走环回；只限 eth0 会漏掉它。
#
# ⚠️ 已知平台差异（务必看 docs/MEMSHELL.md「出网到底断没断」）：
#   在 **Docker Desktop for Windows/macOS（WSL2/VM）** 上，容器发往 127.0.0.11 的
#   DNS 请求**不经过容器自己的 netfilter**，所以上面的 DNS 规则**匹配不到包**
#   （实测：规则计数 0，而解析依然成功）。也就是说在这类环境下
#   「外连 TCP 已断，但 DNS 仍可解析」，DNSLog 外带理论上仍可行。
#   在**原生 Linux Docker** 上内嵌解析器是容器 netns 里的进程，规则生效 —— 但这一点
#   需要在目标平台自行验证，不要照抄本文档当结论。
#   无论哪种环境，反弹 shell 与外连下载都是断的。
#
# iptables 不可用时只告警不退出 —— 靶场不能因为加固失败而起不来。
# ---------------------------------------------------------------------------
block_egress() {
    if ! command -v iptables >/dev/null 2>&1; then
        echo "[!] 未安装 iptables，跳过出网切断（该靶场的不出网约束未被强制执行）" >&2
        return 0
    fi
    if iptables -A OUTPUT ! -o lo -p tcp --syn -j DROP 2>/dev/null \
       && iptables -A OUTPUT -p udp --dport 53 -j DROP 2>/dev/null \
       && iptables -A OUTPUT -p tcp --dport 53 -j DROP 2>/dev/null; then
        echo "[*] 已切断出网：非环回新建 TCP + 全部 DNS 被丢弃（入站端口与环回不受影响）" >&2
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
