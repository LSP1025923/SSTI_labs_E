"""临时冒烟：确认各靶场 app.py 能导入且路由表正常（本文件是 CI 的一部分，不要改成 _ 前缀，否则会被 .gitignore 排除）。"""

from __future__ import annotations

import importlib
import os
import sys

# --- Windows 控制台默认编码是 GBK，而本脚本会打印 ✅ / ⚠️ 这类字符 -----------
# 不处理的话，即使所有断言都通过，最后一行 print 也会抛 UnicodeEncodeError，
# 脚本以非 0 退出（在 CI 上看起来就是「失败」）。这里强制走 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):  # 老解释器 / 已被重定向的流
        pass

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
    "09-bottle-chain",
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
