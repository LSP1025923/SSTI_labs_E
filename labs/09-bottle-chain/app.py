#!/usr/bin/env python3
"""09-bottle-chain —— Bottle SimpleTemplate 13 关 WAF 链靶场。"""

from __future__ import annotations

import ssti_core.labapp as labapp
from ssti_core import LabMeta, create_lab_app
from ssti_core.labmeta import THEMES
from ssti_core.levels import engine_titles, levels_for

LEVELS = levels_for("bottle")

META = LabMeta(
    id="bottle-chain",
    title="Bottle WAF 链",
    subtitle="13 关递增过滤 · 编译型模板引擎",
    engine="bottle",
    engine_title="Bottle",
    theme=THEMES["ice"],
    description=(
        "与 02/03/04 同构的第 4 条 13 关链，目标是 Bottle 的 SimpleTemplate。"
        "它同样是**编译成 Python** 的引擎：`{{ }}` 是输出表达式，"
        "`% 行代码` 与 `<% %>` 是真正的 Python，代码块里拿得到模板的输出原语 "
        "`_stdout` / `_printlist` —— 所以 `{{` 被拦之后回显通道并没有死。"
        "与 Jinja/Mako 关最大的差别：模板跑在 `exec(code, env)` 里，"
        "**Python 内置函数全部直接可用**；但 `lipsum` / `cycler` 这些 Jinja 全局"
        "在这里不存在，gadget 链要从内置函数与 `request` 出发。"
    ),
    hint="先确认引擎：提交 `{{7*7}}`。Bottle 的 `{{ }}` 内是原生 Python 表达式。",
    doc_url="/docs/README.md",
)

app = create_lab_app(
    META,
    LEVELS,
    engine_titles=engine_titles(),
    docs_folder="docs",
)

if __name__ == "__main__":
    labapp.run(app)
