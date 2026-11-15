#!/usr/bin/env python3
"""为 Python 系靶场生成 Docker 环境骨架（Dockerfile / docker-compose.yml / entrypoint.sh）。

为什么要有这个脚本：8 个靶场的容器编排几乎一致，只有端口、镜像名、依赖、
以及「是否切断出网」不同。与其复制粘贴 8 份容易改漏的 Dockerfile，
不如把差异收敛到下面的 ``LABS`` 表里 —— 这张表同时也是**端口分配的唯一定义处**。

用法::

    python scripts/scaffold_lab.py --list                 # 看端口分配表
    python scripts/scaffold_lab.py 03-mako-chain          # 生成单个
    python scripts/scaffold_lab.py --all                  # 生成全部（已存在则跳过）
    python scripts/scaffold_lab.py --all --force          # 覆盖重建

只生成脚手架；``app.py`` / ``requirements.txt`` / ``README.md`` / ``docs/``
由各靶场自己维护（它们才是题目的本体）。
"""

from __future__ import annotations

import argparse
import sys

# --- Windows 控制台默认编码是 GBK，而本脚本会打印 ✅ / ⚠️ 这类字符 -----------
# 不处理的话，即使所有断言都通过，最后一行 print 也会抛 UnicodeEncodeError，
# 脚本以非 0 退出（在 CI 上看起来就是「失败」）。这里强制走 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # 老解释器 / 已被重定向的流
        pass

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABS_DIR = ROOT / "labs"


@dataclass
class LabSpec:
    dirname: str
    lab_id: str
    image: str
    port: int
    port_env: str
    static_flag: str
    title: str
    requirements: list[str] = field(default_factory=lambda: ["Flask>=3.0,<4.0", "Jinja2>=3.1.4"])
    #: 是否在容器内用 iptables 切断出网（需要 NET_ADMIN）
    no_egress: bool = False
    #: 场景型靶场（自己渲染业务页面，而不是套用统一前端控制台）
    scenario: bool = False
    #: 额外的系统包
    apt_packages: list[str] = field(default_factory=list)
    #: 应用监听端口（容器内）
    app_port: int = 5000
    #: 手写编排：登记在表里（端口分配的唯一来源），但生成器**不会**碰它的文件。
    #: Java 靶场就是这种情况 —— 它的 Dockerfile/compose 与 Python 系完全不同。
    handwritten: bool = False


LABS: dict[str, LabSpec] = {
    "01-jinja-waf-fenjing": LabSpec(
        dirname="01-jinja-waf-fenjing",
        lab_id="jinja-waf-fenjing",
        image="ssti-jinja-waf-fenjing",
        port=8091,
        port_env="JINJA_WAF_PORT",
        static_flag="flag{jinja_waf_fenjing}",
        title="Jinja2 关键词 WAF 绕过",
        scenario=True,
    ),
    "02-jinja-chain": LabSpec(
        dirname="02-jinja-chain",
        lab_id="jinja-chain",
        image="ssti-jinja-chain",
        port=8092,
        port_env="JINJA_CHAIN_PORT",
        static_flag="flag{jinja_chain}",
        title="Jinja2 13 关 WAF 链",
    ),
    "03-mako-chain": LabSpec(
        dirname="03-mako-chain",
        lab_id="mako-chain",
        image="ssti-mako-chain",
        port=8093,
        port_env="MAKO_CHAIN_PORT",
        static_flag="flag{mako_chain}",
        title="Mako 13 关 WAF 链",
        requirements=["Flask>=3.0,<4.0", "Jinja2>=3.1.4", "Mako>=1.3.5"],
    ),
    "04-tornado-chain": LabSpec(
        dirname="04-tornado-chain",
        lab_id="tornado-chain",
        image="ssti-tornado-chain",
        port=8094,
        port_env="TORNADO_CHAIN_PORT",
        static_flag="flag{tornado_chain}",
        title="Tornado 13 关 WAF 链",
        requirements=["Flask>=3.0,<4.0", "Jinja2>=3.1.4", "tornado>=6.4"],
    ),
    "09-bottle-chain": LabSpec(
        dirname="09-bottle-chain",
        lab_id="bottle-chain",
        image="ssti-bottle-chain",
        port=8099,
        port_env="BOTTLE_CHAIN_PORT",
        static_flag="flag{bottle_chain}",
        title="Bottle SimpleTemplate 13 关 WAF 链",
        requirements=["Flask>=3.0,<4.0", "Jinja2>=3.1.4", "bottle>=0.13,<0.14"],
    ),
    "05-jinja-sandbox": LabSpec(
        dirname="05-jinja-sandbox",
        lab_id="jinja-sandbox",
        image="ssti-jinja-sandbox",
        port=8095,
        port_env="JINJA_SANDBOX_PORT",
        static_flag="flag{jinja_sandbox_escape}",
        title="Jinja2 沙箱逃逸",
    ),
    "06-blind-ssti": LabSpec(
        dirname="06-blind-ssti",
        lab_id="blind-ssti",
        image="ssti-blind",
        port=8096,
        port_env="BLIND_SSTI_PORT",
        static_flag="flag{blind_ssti}",
        title="无回显 SSTI（盲注与侧信道）",
    ),
    "07-flask-memshell": LabSpec(
        dirname="07-flask-memshell",
        lab_id="flask-memshell",
        image="ssti-flask-memshell",
        port=8097,
        port_env="FLASK_MEMSHELL_PORT",
        static_flag="flag{flask_memshell}",
        title="不出网 SSTI：Flask 内存马",
        requirements=["Flask>=3.0,<4.0", "Jinja2>=3.1.4", "PyJWT>=2.8.0", "requests>=2.32.0"],
        no_egress=True,
        scenario=True,
        apt_packages=["iptables"],
    ),
    # Java 系靶场：只登记端口（让 --list 成为端口分配的唯一来源），
    # 其 Dockerfile / docker-compose.yml / entrypoint.sh 均由该靶场手写维护。
    # 为什么不让生成器管：它用 Maven 多阶段构建、运行阶段是 alpine + JRE，
    # 且 build context 是靶场目录本身（不需要 shared/ 与统一前端），
    # 与 Python 系的模板没有共同点 —— 套模板只会产生误导性文件。
    "08-freemarker-memshell": LabSpec(
        dirname="08-freemarker-memshell",
        lab_id="freemarker-memshell",
        image="ssti-freemarker-memshell",
        port=8098,
        port_env="FREEMARKER_MEMSHELL_PORT",
        static_flag="flag{freemarker_memshell}",
        title="不出网 SSTI：Java FreeMarker/Thymeleaf → Tomcat 内存马",
        no_egress=True,
        scenario=True,
        app_port=8080,
        handwritten=True,
    ),
}

#: 生成器统一使用的 Dockerfile 头注释
_HEADER = """#
# {dirname} —— {title}
#
# 本文件由 scripts/scaffold_lab.py 生成。改编排请改生成器，改题目请改 app.py。
#
# 构建上下文必须是**仓库根目录**（需要 COPY shared/ 与统一前端产物）：
#     docker build -f labs/{dirname}/Dockerfile -t {image}:local .
#
# 前置：前端镜像 ssti-frontend:local 必须已存在（scripts/build-frontend.sh）。
#
# 注意：内置的 dockerfile 前端**不支持**在 `COPY --from=` 里做变量展开
# （`# syntax=docker/dockerfile:1` 能支持，但那需要从 Docker Hub 拉 buildkit
#  前端镜像，离线/受限网络下会直接失败）。所以这里用官方推荐的替代写法：
# 先用全局 ARG 把前端镜像变成一个有名字的阶段，再 `COPY --from=<阶段名>`。
ARG FRONTEND_IMAGE=ssti-frontend:local

FROM ${{FRONTEND_IMAGE}} AS frontend
"""

_EGRESS_SETUP = r"""
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
"""

_ENTRY_TMPL = """#!/bin/sh
# {dirname} —— 统一入口：写 flag 到 /flag（不进镜像层），再以 __main__ 启动应用。
#
# 为什么用 Flask 自带服务器而不是 gunicorn：
#   多个靶场（尤其内存马）依赖应用模块名为 __main__，gunicorn 下会变成
#   gunicorn.app.wsgiapp，部分利用链会失效。本靶场是隔离的单实例教学环境。
set -e
{egress}
# flag 优先级 GZCTF_FLAG > DASFLAG > FLAG > STATIC_FLAG
#
# ⚠️ 不要写成 FLAG_VALUE="${{GZCTF_FLAG:-${{DASFLAG:-...}}}}"：
#   默认值里带的 `{{` `}}`（flag 本身就有花括号）会把嵌套的 `${{VAR:-}}`
#   提前闭合，结果是往 /flag 里多写一个 `}}`。所以这里先落到变量再用 `||` 逐级兜底。
DEFAULT_FLAG='{static_flag}'
FLAG_VALUE="${{GZCTF_FLAG:-}}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${{DASFLAG:-}}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${{FLAG:-}}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${{STATIC_FLAG:-$DEFAULT_FLAG}}"

printf '%s' "$FLAG_VALUE" > /flag
chmod 644 /flag 2>/dev/null || true

echo "[*] $(id -un)@$(hostname) | lab={lab_id}{egress_note} | flag -> /flag" >&2

exec python /app/app.py
"""

_COMPOSE_TMPL = """# 单靶场独立环境：在本目录直接 `docker compose up --build` 即可（端口 {port}）。
#
# 注意：build context 是仓库根目录，因为镜像需要 shared/ 公共库与统一前端产物。
# 首次启动前请先构建前端镜像：
#     ../../scripts/build-frontend.sh          # Linux/macOS
#     ..\\..\\scripts\\build-frontend.ps1         # Windows
services:
  {service}:
    build:
      context: ../..
      dockerfile: labs/{dirname}/Dockerfile
      args:
        FRONTEND_IMAGE: ${{FRONTEND_IMAGE:-ssti-frontend:local}}
    image: {image}:local
    container_name: ssti-{service}
    ports:
      - "${{{port_env}:-{port}}}:{app_port}"{cap_add}
    environment:
      LAB_ID: {lab_id}
      PORT: "{app_port}"
      SSTI_NO_EGRESS: "{no_egress_int}"
      # flag 优先级 GZCTF_FLAG > DASFLAG > FLAG > STATIC_FLAG
      GZCTF_FLAG: ${{GZCTF_FLAG:-}}
      DASFLAG: ${{DASFLAG:-}}
      FLAG: ${{FLAG:-}}
      STATIC_FLAG: ${{STATIC_FLAG:-{static_flag}}}
      RESET_TOKEN: ${{RESET_TOKEN:-}}
      SSTI_MAX_OUTPUT_CHARS: ${{SSTI_MAX_OUTPUT_CHARS:-262144}}
    restart: unless-stopped
"""


def _service_name(spec: LabSpec) -> str:
    return spec.dirname.split("-", 1)[1]


def render_dockerfile(spec: LabSpec) -> str:
    apt = ""
    pkgs = list(spec.apt_packages)
    if pkgs:
        apt = (
            "RUN apt-get update \\\n"
            "    && apt-get install -y --no-install-recommends "
            + " ".join(pkgs)
            + " \\\n"
            "    && rm -rf /var/lib/apt/lists/*\n\n"
        )
    return f"""{_HEADER.format(dirname=spec.dirname, title=spec.title, image=spec.image)}
FROM python:3.11-slim

LABEL org.opencontainers.image.title="{spec.image}" \\
      org.opencontainers.image.description="{spec.title} SSTI lab (CTF, isolated use only)"

ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    PIP_DISABLE_PIP_VERSION_CHECK=1 \\
    PYTHONPATH=/app/shared \\
    LAB_ID={spec.lab_id} \\
    PORT={spec.app_port} \\
    SSTI_NO_EGRESS={1 if spec.no_egress else 0}

WORKDIR /app

{apt}# 依赖单独一层，改代码不会触发重装
COPY labs/{spec.dirname}/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 公共库（关卡定义 / 渲染编排 / 应用工厂 / flag 处理）
COPY shared/ ./shared/

# 靶场自身的代码与文档（README 同时充当容器内的 /docs 题解）
COPY labs/{spec.dirname}/app.py ./app.py
COPY labs/{spec.dirname}/README.md ./docs/README.md
COPY labs/{spec.dirname}/entrypoint.sh /entrypoint.sh

# 统一前端构建产物（来自文件顶部命名的 frontend 阶段）；
# 场景型靶场自带页面，用不到它也不会报错。
COPY --from=frontend /app/build ./public

RUN chmod +x /entrypoint.sh

EXPOSE {spec.app_port}

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \\
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:{spec.app_port}/healthz',timeout=3).status==200 else 1)"

ENTRYPOINT ["/entrypoint.sh"]
"""


def render_entrypoint(spec: LabSpec) -> str:
    return _ENTRY_TMPL.format(
        dirname=spec.dirname,
        static_flag=spec.static_flag,
        lab_id=spec.lab_id,
        egress=_EGRESS_SETUP if spec.no_egress else "",
        egress_note=" | 不出网" if spec.no_egress else "",
    )


def render_compose(spec: LabSpec) -> str:
    cap_add = "\n    cap_add:\n      - NET_ADMIN" if spec.no_egress else ""
    return _COMPOSE_TMPL.format(
        service=_service_name(spec),
        dirname=spec.dirname,
        image=spec.image,
        port=spec.port,
        port_env=spec.port_env,
        lab_id=spec.lab_id,
        static_flag=spec.static_flag,
        app_port=spec.app_port,
        cap_add=cap_add,
        no_egress_int=1 if spec.no_egress else 0,
    )


def write_file(path: Path, content: str, *, force: bool) -> bool:
    if path.exists() and not force:
        print(f"  skip  {path.relative_to(ROOT)}（已存在）")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    print(f"  write {path.relative_to(ROOT)}")
    return True


def scaffold(spec: LabSpec, *, force: bool) -> None:
    target = LABS_DIR / spec.dirname
    if spec.handwritten:
        print(f"[{spec.dirname}] 手写编排（端口 {spec.port} / {spec.port_env}），生成器跳过")
        return
    print(f"[{spec.dirname}] -> {target.relative_to(ROOT)}")
    write_file(target / "Dockerfile", render_dockerfile(spec), force=force)
    write_file(target / "docker-compose.yml", render_compose(spec), force=force)
    write_file(target / "entrypoint.sh", render_entrypoint(spec), force=force)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 Python 系靶场的 Docker 环境骨架")
    parser.add_argument("labs", nargs="*", help="靶场目录名，如 03-mako-chain")
    parser.add_argument("--all", action="store_true", help="生成 LABS 表中的全部靶场")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的文件")
    parser.add_argument("--list", action="store_true", help="打印端口分配表")
    args = parser.parse_args(argv)

    if args.list:
        print(f"{'目录':<26}{'端口':<8}{'环境变量':<24}{'不出网':<8}说明")
        for spec in LABS.values():
            print(
                f"{spec.dirname:<26}{spec.port:<8}{spec.port_env:<24}"
                f"{'是' if spec.no_egress else '否':<8}{spec.title}"
            )
        return 0

    targets = list(LABS.values()) if args.all else [LABS[n] for n in args.labs if n in LABS]
    unknown = [n for n in args.labs if n not in LABS]
    for name in unknown:
        print(f"未知靶场：{name}（用 --list 查看可选值）", file=sys.stderr)
    if not targets:
        parser.print_help()
        return 1 if unknown else 0

    for spec in targets:
        scaffold(spec, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
