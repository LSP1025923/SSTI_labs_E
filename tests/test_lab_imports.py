"""临时冒烟：确认各靶场 app.py 能导入且路由表正常（本文件是 CI 的一部分，不要改成 _ 前缀，否则会被 .gitignore 排除）。"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

REPO = Path("/repo")
LABS = [
    "01-jinja-waf-fenjing",
    "02-jinja-chain",
    "03-mako-chain",
    "04-tornado-chain",
    "05-jinja-sandbox",
    "06-blind-ssti",
    "07-flask-memshell",
]

fails = []
for lab in LABS:
    path = REPO / "labs" / lab
    if not (path / "app.py").is_file():
        print(f"  skip  {lab}（还没有 app.py）")
        continue
    sys.path[:] = [str(REPO / "shared"), str(path)] + [
        p for p in sys.path if p not in (str(REPO / "shared"), str(path))
    ]
    for mod in ("app", "ssti_core"):
        sys.modules.pop(mod, None)
    os.environ.setdefault("FLAG_PATH", "/tmp/flag")
    try:
        mod = importlib.import_module("app")
        app = getattr(mod, "app")
        rules = sorted(str(r.rule) for r in app.url_map.iter_rules())
        levels = len(getattr(mod, "LEVELS", []))
        has_render = "/api/render" in rules
        print(f"  ok    {lab}: levels={levels} /api/render={has_render} rules={rules[:5]}")
    except Exception as exc:  # noqa: BLE001
        fails.append(lab)
        print(f"  FAIL  {lab}: {type(exc).__name__}: {exc}")

print()
if fails:
    print("导入失败：" + ", ".join(fails))
    sys.exit(1)
print("全部 app.py 导入正常 ✅")
