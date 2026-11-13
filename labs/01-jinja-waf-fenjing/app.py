#!/usr/bin/env python3
"""01-jinja-waf-fenjing —— 本仓库最早那版关键词 WAF 挑战（保留原题面与难点）。

这是 SSTI_labs_E 的**起点**：一个赛博朋克风格的模板渲染台，用户输入经
「关键词黑名单 + 危险正则」两层检查后交给 Jinja2 渲染，目标是拿到 `/flag`。

与后续 13 关链靶场的区别：
* 这里**只有一关**，但过滤是一张真正的关键词表（不是单一字符），
  属于「不可枚举过滤」——需要自动化手段（如 Fenjing 的 `crack-keywords`）
  或者很强的字符串构造功底。
* 渲染使用 ``jinja_plain``：裸 ``jinja2.Environment`` + 一组业务变量，
  与本仓库最初的 ``server.py`` 行为完全一致，因此**老 writeup 依然成立**。

关于过滤规则的忠实度说明：原实现的「危险正则」列表里有大量 ``__xxx__`` 形式的
条目，而 ``__`` 已经在关键词表里被整体拦截，那些正则是不可达的冗余。
这里保留了其中**真正起作用**的部分（函数调用类正则），并在上帝模式里
原样展示，方便对照。
"""

from __future__ import annotations

import ssti_core.labapp as labapp
from ssti_core import LabMeta, WafSpec, create_lab_app
from ssti_core.labmeta import THEMES
from ssti_core.level import Level, make

# ---------------------------------------------------------------------------
# 过滤规则（与原 server.py 的 UNSAFE_KEYWORDS 一致）
# ---------------------------------------------------------------------------
UNSAFE_KEYWORDS = [
    "__",
    "import",
    "os",
    "sys",
    "eval",
    "subprocess",
    "popen",
    "system",
    "%2f",
    "%2F",
    "flag",
    "cat",
    "?",
]

#: 原实现里「函数调用类」的危险正则（大小写不敏感）
DANGEROUS_REGEXES = [
    r"class\s*\(",
    r"globals\s*\(",
    r"locals\s*\(",
    r"getattr\s*\(",
    r"setattr\s*\(",
    r"delattr\s*\(",
    r"hasattr\s*\(",
    r"open\s*\(",
    r"file\s*\(",
    r"exec\s*\(",
    r"compile\s*\(",
    r"eval\s*\(",
    r"input\s*\(",
    r"raw_input\s*\(",
    r"help\s*\(",
    r"vars\s*\(",
    r"dir\s*\(",
    r"type\s*\(",
    r"isinstance\s*\(",
    r"issubclass\s*\(",
    r"super\s*\(",
    r"property\s*\(",
    r"staticmethod\s*\(",
    r"classmethod\s*\(",
]

WAF = WafSpec(
    substrings=tuple(UNSAFE_KEYWORDS),
    regexes=tuple(DANGEROUS_REGEXES),
    ignore_case=True,
    note=(
        "两层过滤：① 大小写不敏感的关键词子串黑名单（含 `__`、`os`、`flag`、`?` 等）；"
        "② 危险函数调用正则（`open(`、`getattr(`、`class(` …）。"
        "命中任一层即返回 403。"
    ),
)

#: 本靶场只放一关：过滤规则是「表」而不是「字符」，枚举成本高，应当用工具
@make
def KW_BYPASS() -> Level:
    return Level(
        level_id="0",
        engine="jinja",
        # 使用最初的裸 Environment + 业务变量，保证老 writeup 可复现
        renderer="jinja_plain",
        title="关键词 WAF 绕过",
        summary="不可枚举关键词表 · Fenjing crack-keywords 考点",
        description=(
            "模板先过关键词黑名单，再过危险正则，然后交给 Jinja2 渲染。"
            "注意 `__` 被整体拦截：任何 `__class__` / `__globals__` 都写不出来。"
            "但**字符串是可以拼出来的**——`'_'~'_'~'class'~'_'~'_'` 里并不包含 "
            "子串 `__`。这是本关的核心思路。"
            "另外 `flag`、`cat`、`?`、`os` 也在黑名单里，读文件时要逐项想办法。"
        ),
        waf=WAF,
        hint=(
            "① 先探边界：`{{7*7}}` 能过，`{{\"\".__class__}}` 会被拦。"
            "② 过滤是一张词表，人工猜很慢——这正是 Fenjing "
            "`crack-keywords --keywords-file app.py` 的用武之地。"
            "③ 手工路线：用 `~` 拼接字符串，再用 `|attr` 取属性，全程不要出现 `__`。"
        ),
    )


LEVELS = [KW_BYPASS]

META = LabMeta(
    id="jinja-waf-fenjing",
    title="Jinja2 关键词 WAF",
    subtitle="原版挑战 · 不可枚举过滤",
    engine="jinja",
    engine_title="Jinja2",
    theme=THEMES["violet"],
    description=(
        "SSTI_labs_E 的原版挑战：模板先过两层过滤再渲染，目标读取 `/flag`。"
        "过滤表包含 `__`、`os`、`flag`、`?` 等关键词，因此不能靠枚举字符解决——"
        "需要自动化工具（Fenjing）或系统性的字符串构造。"
        "渲染环境是最初的裸 `jinja2.Environment` + 业务变量，"
        "与仓库最初的 `server.py` 行为一致。"
    ),
    hint="先确认哪些能过：`{{7*7}}` 通过，`{{ ''.__class__ }}` 被 403。",
    doc_url="/docs/README.md",
)

app = create_lab_app(META, LEVELS, docs_folder="docs")

if __name__ == "__main__":
    labapp.run(app)
