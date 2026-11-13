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
if [ -n "${GZCTF_FLAG:-}" ]; then
  INSERT_FLAG="$GZCTF_FLAG"
elif [ -n "${DASFLAG:-}" ]; then
  INSERT_FLAG="$DASFLAG"
elif [ -n "${FLAG:-}" ]; then
  INSERT_FLAG="$FLAG"
else
  INSERT_FLAG="${STATIC_FLAG:-flag{change_me_before_deploy}}"
fi

printf '%s' "$INSERT_FLAG" > /flag
chmod 644 /flag || true
# 从环境里抹掉，避免被 SSTI 直接读环境变量拿到（必须真的去打内存马）
unset GZCTF_FLAG DASFLAG FLAG STATIC_FLAG || true

echo "[*] /flag written ($(wc -c < /flag) bytes)"

# ---------------------------------------------------------------------------
# 2. 出网封锁（核心教学点）
#
#    -A OUTPUT -o eth0 -p tcp --syn -j DROP
#       只丢“新建连接”的 SYN 包；回给入向请求的响应包不是 SYN，照常发出，
#       所以 docker -p 发布的端口仍然可用，反弹 shell / 外连打点全部失效。
#    -A OUTPUT -p udp --dport 53 -j DROP
#       断掉 DNS（在 Docker 里这很重要：内嵌 DNS 是 127.0.0.11，
#       流量走 lo 而不走 eth0，所以必须【不加 -o 限制】才能真的拦住 DNSLog）。
#    -A OUTPUT -o eth0 -p udp --dport 53 -j DROP
#       再补一条显式规则，便于 iptables -S 一眼看出出网策略（与上一条冗余但无害）。
#
#    这几条规则在 Docker Desktop (WSL2, x86_64) 上实测有效，见 README 的验收记录。
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
  if $IPT -A OUTPUT -o eth0 -p tcp --syn -j DROP 2>/dev/null \
     && $IPT -A OUTPUT -p udp --dport 53 -j DROP 2>/dev/null \
     && $IPT -A OUTPUT -o eth0 -p udp --dport 53 -j DROP 2>/dev/null; then
    echo "[*] no-egress: outbound TCP SYN + DNS(UDP/53) DROPPED"
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
