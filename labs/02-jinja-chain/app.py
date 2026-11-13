#!/usr/bin/env python3
"""02-jinja-chain —— Jinja2 13 关 WAF 链靶场。

本文件刻意保持在 20 行以内：关卡定义在 ``ssti_core/levels/jinja.py``，
HTTP 编排在 ``ssti_core/labapp.py``。想改题目请改关卡文件，
想改交互请改公共库——不要把业务逻辑写回这里。
"""

from __future__ import annotations

import ssti_core.labapp as labapp
from ssti_core import LabMeta, create_lab_app
from ssti_core.labmeta import THEMES
from ssti_core.levels import engine_titles, levels_for

LEVELS = levels_for("jinja")

META = LabMeta(
    id="jinja-chain",
    title="Jinja2 WAF 链",
    subtitle="13 关递增过滤 · 同一目标逐层加压",
    engine="jinja",
    engine_title="Jinja2",
    theme=THEMES["cyber"],
    description=(
        "从「无过滤」到「符号 + 关键字双重封堵」，13 关共用同一个 Jinja2 注入点。"
        "每关只增加一条过滤规则，目的是让你清楚看到**是哪一条规则**让 payload 失效，"
        "从而把已知的 gadget 链逐字符地变形到仍然可用。"
        "第 3 关是盲渲染（只回显 correct / wrong），练习的是无回显条件下的探测思路。"
    ),
    hint=(
        "先确认引擎：提交 `{{7*7}}`。 "
        "练习模式看回显，上帝模式看 `template_after_waf`（过滤后的真实模板）与异常类型。"
    ),
    doc_url="/docs/SOLUTIONS.md",
)

app = create_lab_app(
    META,
    LEVELS,
    engine_titles=engine_titles(),
    docs_folder="docs",
)

if __name__ == "__main__":
    labapp.run(app)
