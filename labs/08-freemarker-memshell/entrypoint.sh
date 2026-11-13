#!/bin/sh
# =============================================================================
# 08-freemarker-memshell entrypoint
#   1. 按仓库约定从环境变量写入 /flag（不落镜像层）
#   2. 用 iptables 切断出网（保留已发布端口的入向流量）
#   3. 启动 Spring Boot 应用
#
# 全部 POSIX sh，运行阶段是 alpine（eclipse-temurin:8-jre-alpine）。
# =============================================================================
set -eu

# ---------------------------------------------------------------------------
# 1. Flag 注入：GZCTF_FLAG > DASFLAG > FLAG > STATIC_FLAG
# ---------------------------------------------------------------------------
# flag 优先级：GZCTF_FLAG > DASFLAG > FLAG > STATIC_FLAG
#
# ⚠️ 最后一级**不能**写成 `INSERT_FLAG="${STATIC_FLAG:-flag{change_me}}"`
#    —— 默认值里本身带花括号，POSIX sh 会把默认值的 `}` 当成参数展开的结束符，
#    结果是往 /flag 里多写一个 `}`（实测会得到 `flag{xxx}}`）。
#    所以先落到变量、再用 `||` 逐级兜底。
DEFAULT_FLAG='flag{change_me_before_deploy}'
INSERT_FLAG="${GZCTF_FLAG:-}"
[ -n "$INSERT_FLAG" ] || INSERT_FLAG="${DASFLAG:-}"
[ -n "$INSERT_FLAG" ] || INSERT_FLAG="${FLAG:-}"
[ -n "$INSERT_FLAG" ] || INSERT_FLAG="${STATIC_FLAG:-$DEFAULT_FLAG}"

printf '%s' "$INSERT_FLAG" > /flag
chmod 644 /flag || true
# 从环境里抹掉，避免被 SSTI 直接读环境变量拿到（必须真的去打内存马）
unset GZCTF_FLAG DASFLAG FLAG STATIC_FLAG || true

echo "[*] /flag written ($(wc -c < /flag) bytes)"

# ---------------------------------------------------------------------------
# 2. 出网封锁（核心教学点）
#
#    -A OUTPUT ! -o lo -p tcp --syn -j DROP
#       丢所有“非环回”的新建 TCP 连接。用 ! -o lo 而不是写死 -o eth0：
#       容器里的网卡名不保证叫 eth0（compose 自定义网络、CNI、IPv6-only 都可能变），
#       写死接口名会出现“规则装上了但根本不匹配”的静默失效。
#       保留 lo 是刻意的：容器内自检（curl 127.0.0.1:8080）与 healthcheck 必须还能用。
#    -A OUTPUT -p udp --dport 53 -j DROP
#    -A OUTPUT -p tcp --dport 53 -j DROP
#       断 DNS（UDP + TCP）。这里【不能】加 -o 限制：
#       Docker 内嵌 DNS(dockerd 的 resolver / 127.0.0.11) 在部分平台上
#       是通过环回送达的，一旦限制接口就永远不匹配。
#
#    实测边界（本机 Docker Desktop for Windows / WSL2，见 README 与
#    docs/MEMSHELL.md §2.1.1）：
#      * 出向 TCP（反弹 shell、wget 下载）——已阻断 ✅
#      * 直连外部解析器（dig @8.8.8.8）——已阻断 ✅
#      * 走 Docker 内嵌 resolver(127.0.0.11) 的域名解析——仍然可用 ⚠
#        （这些包不经过容器的 netfilter，所以 DNSLog 式外带在本平台
#          不能算被完全排除；原生 Linux Docker 上 DNS 规则才会真正生效）
#
#    best-effort：没有 iptables / 没有 NET_ADMIN 时大声告警但继续启动，
#    不能让靶场因为封锁失败就起不来。
# ---------------------------------------------------------------------------
IPT=""
for cand in iptables /sbin/iptables /usr/sbin/iptables; do
  if command -v "$cand" >/dev/null 2>&1; then
    IPT="$cand"
    break
  fi
done

if [ -n "$IPT" ]; then
  if $IPT -A OUTPUT ! -o lo -p tcp --syn -j DROP 2>/dev/null \
     && $IPT -A OUTPUT -p udp --dport 53 -j DROP 2>/dev/null \
     && $IPT -A OUTPUT -p tcp --dport 53 -j DROP 2>/dev/null; then
    echo "[*] no-egress: outbound TCP SYN (non-lo) + DNS(UDP/TCP 53) DROPPED"
    $IPT -S OUTPUT 2>/dev/null || true
  else
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "[!] WARNING: iptables rules could NOT be installed."
    echo "[!] The container may still have outbound network access."
    echo "[!] Start with cap_add: [NET_ADMIN] (see docker-compose.yml)."
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  fi
else
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
  echo "[!] WARNING: iptables binary not found; egress is NOT blocked."
  echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
fi

# ---------------------------------------------------------------------------
# 3. 启动应用
# ---------------------------------------------------------------------------
echo "[*] starting Spring Boot (Tomcat) on 0.0.0.0:8080 ..."
exec java ${JAVA_OPTS:-} -jar /app/app.jar
