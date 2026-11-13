#!/usr/bin/env python3
"""03-mako-chain —— Mako 13 关 WAF 链靶场。"""

from __future__ import annotations

import ssti_core.labapp as labapp
from ssti_core import LabMeta, create_lab_app
from ssti_core.labmeta import THEMES
from ssti_core.levels import engine_titles, levels_for

LEVELS = levels_for("mako")

META = LabMeta(
    id="mako-chain",
    title="Mako WAF 链",
    subtitle="13 关递增过滤 · 编译型模板引擎",
    engine="mako",
    engine_title="Mako",
    theme=THEMES["matrix"],
    description=(
        "与 Jinja 链同构的 13 关，但目标是 Mako。Mako 会把模板**编译成 Python 模块**"
        "再执行：`<%! %>` 是模块级代码、`<% %>` 是函数体、`context.write` 直接写输出。"
        "所以 `${` 被拦之后，整片代码块仍然可用 —— 这是 Mako 与 Jinja 最大的差别。"
        "渲染器已注入与 Flask 同构的 `request` / `session` / `config` / `lipsum` 等，"
        "方便你把两个靶场的 gadget 链对照着看。"
    ),
    hint="先确认引擎：提交 `${7*7}`。Mako 的 `${ }` 内是原生 Python 表达式。",
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
