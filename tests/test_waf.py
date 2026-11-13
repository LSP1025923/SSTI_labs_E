#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""``WafSpec`` 与 flag 工具的纯单元测试（不需要 Flask、不需要 Docker）。

用法::

    PYTHONPATH=shared python tests/test_waf.py

为什么单独一个文件：``ssti_core.waf`` 是整个题库的**公共语义层**——
13 关 × 3 引擎的题目难度完全由它决定。它一旦有 bug（比如大小写敏感搞反、
前缀被当成拦截、命中后没替换），会同时污染几十道题，而且症状很隐蔽
（玩家以为是自己 payload 写错了）。所以这里对每个原语都单独钉死行为。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "shared"))

from ssti_core import flagutil  # noqa: E402
from ssti_core.waf import NO_WAF, WafSpec  # noqa: E402

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


def main() -> int:
    print("[1] 无过滤")
    check("NO_WAF.is_active 为假", NO_WAF.is_active is False)
    check("NO_WAF.kind == 'none'", NO_WAF.kind == "none")
    check("NO_WAF 原样返回", NO_WAF.apply("{{7*7}}") == "{{7*7}}")
    check("NO_WAF.to_json() 为 None", NO_WAF.to_json() is None)

    print("[2] 子串拦截（默认忽略大小写）")
    w = WafSpec.blocked_substrings(("__", "os"), note="测试")
    check("kind == 'substring'", w.kind == "substring")
    check("命中 `__` 被替换", w.apply("{{ ''.__class__ }}") == "WAF")
    check("命中 `os` 被替换", w.apply("{{ os }}") == "WAF")
    check("大小写不敏感（OS 也拦）", w.apply("{{ OS }}") == "WAF")
    check("未命中则原样通过", w.apply("{{7*7}}") == "{{7*7}}")
    check("blocks() 与 apply() 一致", w.blocks("{{os}}") is True and w.blocks("{{7*7}}") is False)

    print("[3] 子串拦截（大小写敏感）")
    ws = WafSpec(substrings=("class", "init"), ignore_case=False)
    check("小写 class 被拦", ws.apply("class") == "WAF")
    check("大写 CLASS 放行（大小写敏感）", ws.apply("CLASS") == "CLASS")
    check("`__init__` 命中子串 init", ws.apply("__init__") == "WAF")
    # 注意：`print` **不**包含子串 `init`（p-r-i-n-t），别拿它当例子
    check("`print` 不命中 init", ws.apply("print") == "print")

    print("[4] 字符拦截")
    c = WafSpec.blocked_chars(("[", "]", "'", '"'))
    check("kind == 'chars'", c.kind == "chars")
    check("命中 [ 被替换", c.apply("{{ [1] }}") == "WAF")
    check("命中 ' 被替换", c.apply("{{ 'a' }}") == "WAF")
    check("不含被禁字符则通过", c.apply("{{7*7}}") == "{{7*7}}")

    print("[5] 正则拦截")
    r = WafSpec(regexes=(r"open\s*\(", r"\{\{"))
    check("kind == 'regex'", r.kind == "regex")
    check("命中 `open(`（含空白）", r.apply("open (1)") == "WAF")
    check("命中 `{{`", r.apply("{{7}}") == "WAF")
    check("未命中则通过", r.apply("{% print(1) %}") == "{% print(1) %}")

    print("[6] 前缀/后缀：是**拼接**，不是拦截")
    p = WafSpec(prefix="{% set config=None%}", suffix="<!--x-->")
    check("kind == 'prefix'", p.kind == "prefix")
    check("前缀被拼上", p.apply("{{7*7}}") == "{% set config=None%}{{7*7}}<!--x-->")
    check("前缀规则不产生 WAF", p.apply("{{7*7}}") != "WAF")
    check("blocks() 对纯前缀规则为假", p.blocks("{{7*7}}") is False)
    check("to_json 含 prefix", p.to_json()["prefix"] == "{% set config=None%}")

    print("[7] 组合规则")
    combo = WafSpec(
        chars=("'", '"', "+"),
        substrings=("request",),
        regexes=(r"\{\{",),
        note="组合",
    )
    check("kind == 'combo'", combo.kind == "combo")
    check("命中字符", combo.apply("a+b") == "WAF")
    check("命中子串", combo.apply("request") == "WAF")
    check("命中正则", combo.apply("{{1}}") == "WAF")
    check("全部未命中则通过", combo.apply("{% print(7) %}") == "{% print(7) %}")

    print("[8] 前缀 + 拦截同时存在时，命中优先（不拼接）")
    both = WafSpec(substrings=("bad",), prefix="PRE:")
    check("命中时返回 replacement，不加前缀", both.apply("bad") == "WAF")
    check("未命中时加前缀", both.apply("good") == "PRE:good")

    print("[9] to_json 契约（前端依赖）")
    j = WafSpec(chars=("[", "]"), substrings=("os",), regexes=(r"x",), note="n").to_json()
    check("含 kind", "kind" in j)
    check("items 是三者合并", set(j["items"]) == {"[", "]", "os", "x"}, str(j["items"]))
    check("含 note", j["note"] == "n")
    check("kind 为 combo", j["kind"] == "combo")
    check("细分字段齐全", all(k in j for k in ("substrings", "chars", "regexes")))

    print("[10] 缓存不串味（regexes 编译结果按实例缓存）")
    a = WafSpec(regexes=(r"aaa",))
    b = WafSpec(regexes=(r"bbb",))
    check("a 命中 aaa", a.apply("aaa") == "WAF")
    check("b 不命中 aaa", b.apply("aaa") == "aaa")
    check("b 命中 bbb", b.apply("bbb") == "WAF")

    print("[11] flag 工具（含优先级）")
    tmp = Path(tempfile.mkdtemp(prefix="ssti-waf-test-"))
    saved = {k: os.environ.get(k) for k in ("GZCTF_FLAG", "DASFLAG", "FLAG", "STATIC_FLAG")}
    try:
        for k in saved:
            os.environ.pop(k, None)
        check("全部未设置时用内置默认", flagutil.resolve_flag() == flagutil.DEFAULT_STATIC_FLAG)

        os.environ["STATIC_FLAG"] = "flag{static}"
        check("STATIC_FLAG 生效", flagutil.resolve_flag() == "flag{static}")
        os.environ["FLAG"] = "flag{plain}"
        check("FLAG 覆盖 STATIC_FLAG", flagutil.resolve_flag() == "flag{plain}")
        os.environ["DASFLAG"] = "flag{das}"
        check("DASFLAG 覆盖 FLAG", flagutil.resolve_flag() == "flag{das}")
        os.environ["GZCTF_FLAG"] = "flag{gzctf}"
        check("GZCTF_FLAG 优先级最高", flagutil.resolve_flag() == "flag{gzctf}")

        target = tmp / "flag"
        written = flagutil.write_flag_file(str(target))
        check("写文件返回写入内容", written == "flag{gzctf}")
        check("读回一致且已 strip", flagutil.read_flag_file(str(target)) == "flag{gzctf}")
        check("flag_found_in 命中", flagutil.flag_found_in(f"xx flag{{gzctf}} yy", str(target)))
        check("flag_found_in 不误报", not flagutil.flag_found_in("nothing", str(target)))

        # 空字符串的环境变量必须被当作「未设置」，否则平台注入空值时 flag 会变空
        os.environ["GZCTF_FLAG"] = "   "
        check("空白 GZCTF_FLAG 被跳过", flagutil.resolve_flag() == "flag{das}")
        check("mask 不泄露随机部分", flagutil.mask("flag{secret}") == "flag{***}")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print()
    print(f"共 {CHECKS} 项，失败 {len(FAILS)} 项")
    if FAILS:
        print("失败项：" + ", ".join(FAILS))
        return 1
    print("全部通过 ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
