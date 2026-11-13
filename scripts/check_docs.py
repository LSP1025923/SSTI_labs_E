#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Markdown 文档链接/路径检查器。

文档密集的仓库最容易腐烂的地方不是正文，而是**链接**：改了目录、挪了靶场、
把 README 改名之后，正文看着没问题，点进去 404。这个脚本把这类问题变成
CI 里的一条硬断言。

它区分两类目标，因为两者的正确语义**不同**：

1. **Markdown 链接** ``[文字](目标)`` —— 按 Markdown/GitHub 语义必须**相对当前文件**。
   所以 ``docs/SOLUTIONS.md`` 里写 ``labs/02-jinja-chain/README.md`` 是坏链
   （会被解析成 ``docs/labs/...``），必须写 ``../labs/02-jinja-chain/README.md``。
   这类问题单独报为「坏链（需 ../）」。
2. **行内代码里的路径** `` `scripts/verify_labs.py` `` —— 本仓库约定写成
   **仓库根相对**（读起来更像"项目里的哪个文件"）。这类同时接受根相对与文件相对。

为避免把 payload 误判成链接，扫描前先剥掉围栏代码块与行内代码。

用法::

    python scripts/check_docs.py           # 检查全部 .md
    python scripts/check_docs.py -v        # 打印每个被检查的目标

退出码 1 表示存在断链。
"""

from __future__ import annotations

import argparse
import re
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

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {".git", "node_modules", "build", "target", "__pycache__", ".venv", "venv"}
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "ftp://", "//", "data:")

#: 已知文件扩展名（用于判断「这看起来像个路径」）
KNOWN_EXT = (
    "py", "md", "sh", "ps1", "yml", "yaml", "json", "js", "jsx", "java", "xml",
    "txt", "b64", "toml", "cfg", "ini", "conf", "html", "css", "jar", "example",
)

FENCED = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
MD_LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
#: 行内代码里的路径（带已知扩展名）
CODE_PATH = re.compile(
    r"`([A-Za-z0-9_.\-/]*/[A-Za-z0-9_.\-/]+\.(?:" + "|".join(KNOWN_EXT) + r"))`"
)
#: 行内代码里的裸目录（以仓库顶层目录开头）
CODE_DIR = re.compile(r"`((?:labs|shared|frontend|scripts|tests|docs)/[A-Za-z0-9_.\-/]*/?)`")


def iter_markdown() -> list[Path]:
    out: list[Path] = []
    for p in ROOT.rglob("*.md"):
        if any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        out.append(p)
    return sorted(out)


def _in_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT)
        return True
    except ValueError:
        return False


def looks_like_path(target: str, *, root_relative_ok: bool) -> bool:
    """过滤掉 `'os'`、`...` 这类明显不是路径的目标。

    ``root_relative_ok=True`` 表示来自行内代码：以 ``/`` 开头的是**容器内路径**
    （如 ``/app/build/index.html``、``/flag``），不是仓库路径，直接跳过。
    而 Markdown 链接里以 ``/`` 开头是**站点绝对路径**，在仓库里一定点不开，
    所以要报错——两者的语义不同，不能一概而论。
    """
    if not target or target.startswith(EXTERNAL_PREFIXES) or target.startswith("#"):
        return False
    if any(ch in target for ch in "'\"<>|{}() "):
        return False
    if "..." in target:  # 省略号简写，不是真实路径
        return False
    if target.startswith("/"):
        return not root_relative_ok
    if target.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".mp4")):
        return True
    return "/" in target or target.endswith(KNOWN_EXT)


def resolve(src: Path, target: str, *, root_relative_ok: bool) -> tuple[Path | None, str | None]:
    """返回 (命中的路径, 错误说明)。"""
    path_part = target.split("#", 1)[0].split("?", 1)[0]
    if not path_part:
        return None, None

    # Markdown 链接里以 / 开头 = 站点绝对路径，在仓库里点不开
    if path_part.startswith("/") and not root_relative_ok:
        return None, (
            f"{src.relative_to(ROOT)} -> 坏链：`{target}` 以 `/` 开头，会被当成站点绝对路径；"
            f"仓库内请写成相对当前文件的形式（如 `../{path_part.lstrip('/')}`）"
        )

    rel_to_file = (src.parent / path_part).resolve()
    if _in_repo(rel_to_file) and rel_to_file.exists():
        return rel_to_file, None

    if root_relative_ok:
        rel_to_root = (ROOT / path_part).resolve()
        if _in_repo(rel_to_root) and rel_to_root.exists():
            return rel_to_root, None

    # 文件相对不存在，但根相对存在 —— 说明写法用错了基准
    rel_to_root = (ROOT / path_part).resolve()
    if _in_repo(rel_to_root) and rel_to_root.exists():
        return None, (
            f"{src.relative_to(ROOT)} -> 坏链：`{target}` 按 Markdown 语义会解析到 "
            f"{src.parent.relative_to(ROOT)}/ 下；应写成相对当前文件的形式"
            f"（例如 `../{path_part}`）"
        )
    return None, f"{src.relative_to(ROOT)} -> 断链: {target}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 Markdown 里的本地链接与路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="打印每个被检查的目标")
    args = parser.parse_args(argv)

    errors: list[str] = []
    files = iter_markdown()
    checked = 0

    for md in files:
        rel = md.relative_to(ROOT)
        if args.verbose:
            print(f"[{rel}]")
        text = md.read_text(encoding="utf-8", errors="replace")
        # 剥掉代码块与行内代码，避免把 payload 当成链接
        prose = INLINE_CODE.sub("``", FENCED.sub("", text))

        targets: list[tuple[str, bool]] = []  # (target, root_relative_ok)
        targets += [(m.group("target"), False) for m in MD_LINK.finditer(prose)]
        targets += [(m.group(1), True) for m in CODE_PATH.finditer(text)]
        targets += [(m.group(1), True) for m in CODE_DIR.finditer(text)]

        for target, root_ok in targets:
            if not looks_like_path(target, root_relative_ok=root_ok):
                continue
            checked += 1
            hit, err = resolve(md, target, root_relative_ok=root_ok)
            if err:
                errors.append(err)
            elif args.verbose:
                print(f"    ok  {rel} -> {target}")

    print()
    print(f"扫描 {len(files)} 个 Markdown 文件，检查 {checked} 个本地目标")
    if errors:
        print(f"发现 {len(errors)} 处问题：")
        for e in sorted(set(errors)):
            print(f"  - {e}")
        return 1
    print("没有断链 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
