#!/usr/bin/env python3
"""04-tornado-chain —— Tornado 13 关 WAF 链靶场。"""

from __future__ import annotations

import ssti_core.labapp as labapp
from ssti_core import LabMeta, create_lab_app
from ssti_core.labmeta import THEMES
from ssti_core.levels import engine_titles, levels_for

LEVELS = levels_for("tornado")

META = LabMeta(
    id="tornado-chain",
    title="Tornado WAF 链",
    subtitle="13 关递增过滤 · 带 Handler 上下文",
    engine="tornado",
    engine_title="Tornado",
    theme=THEMES["amber"],
    description=(
        "13 关同构链的 Tornado 版本。Tornado 模板同样被编译成 Python，"
        "并且默认命名空间里有几个别处没有的起点：`escape`（实为 `xhtml_escape`）、"
        "`datetime`，以及渲染器注入的 `handler` 桩（带 `get_argument` / "
        "`get_secure_cookie` / `reverse_url`）——真实站点里 `handler.settings` "
        "往往直接泄露 `cookie_secret`，这是 Tornado 最常见的敏感信息入口。"
        "另外 `{% import %}` 可以直接导入模块，是比 Jinja 短得多的 RCE 路径。"
    ),
    hint="先确认引擎：提交 `{{ 7*7 }}`。注意 `{% import %}` 的存在。",
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
