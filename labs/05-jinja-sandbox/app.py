#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""05-jinja-sandbox —— Jinja2 沙箱逃逸靶场（``jinja_sandbox`` 渲染器，4 关）。

关卡定义在 ``ssti_core/levels/sandbox.py``，HTTP 编排在 ``ssti_core/labapp.py``。
本文件只多做一件沙箱题必须做的事：**给沙箱模板注册一个业务对象**。

为什么要在这里碰引擎内部：
``jinja_sandbox`` 渲染器只认 ``options["sandbox"]``（``default`` / ``immutable``），
没有「往沙箱 globals 里注册业务对象」的开关；而沙箱题必须有一个起点对象，
否则玩家连 `helper` 都拿不到。引擎源码注释里写明「沙箱题通常还会注册几个模板里
能直接用的业务对象，否则 payload 连起点都没有」——这里就是那次注册：
取引擎缓存的沙箱环境，update 一次 globals（两个沙箱各注册一次）。

flag 的处理（**教学装置，README 里有完整说明**）：
本靶场固定的 Jinja2 < 3.1.6，能用的逃逸原语是「只读属性遍历」（CVE-2025-27516），
做不到 RCE 去读 ``/flag``，所以 flag 同时以模块全局 ``SITEDATA['flag']`` 的形式
存在于服务端内存里；``SITEDATA`` 是应用模块的全局变量，因此它就在
``helper.__globals__`` 里 —— 玩家必须真正突破沙箱才能把它 dump 出来。
"""

from __future__ import annotations

import sys

from flask import jsonify

import ssti_core.labapp as labapp
from ssti_core import LabMeta, create_lab_app, flagutil
from ssti_core.engines import jinja as jinja_engine
from ssti_core.labmeta import THEMES
from ssti_core.levels import levels_for
from ssti_core.levels import sandbox as sandbox_levels

# ---------------------------------------------------------------------------
# 版本自检：本靶场依赖 CVE-2025-27516（Jinja2 3.1.6 修复）。
# 一旦有人 `pip install -U`，四关会**静默变成无解**——所以这里必须吵起来。
# ---------------------------------------------------------------------------
JINJA2_MIN = "3.1.4"
JINJA2_MAX_EXCLUSIVE = "3.1.6"
#: 修复 CVE-2025-27516 的版本：`format` / `format_map` 访问会被包成 SandboxedFormatter
JINJA2_FIXED_IN = "3.1.6"
CVE = "CVE-2025-27516"


def _jinja2_version() -> str:
    try:  # 首选 importlib.metadata，避免依赖已被弃用的 jinja2.__version__
        from importlib.metadata import version

        return version("Jinja2")
    except Exception:  # noqa: BLE001
        try:
            import jinja2

            return str(jinja2.__version__)
        except Exception:  # noqa: BLE001
            return "unknown"


def _version_tuple(raw: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in raw.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _escape_available(version: str) -> bool:
    """当前 Jinja2 是否仍然存在 CVE-2025-27516 的逃逸原语。"""
    parsed = _version_tuple(version)
    return _version_tuple(JINJA2_MIN) <= parsed < _version_tuple(JINJA2_MAX_EXCLUSIVE)


JINJA2_VERSION = _jinja2_version()
ESCAPE_AVAILABLE = _escape_available(JINJA2_VERSION)

if not ESCAPE_AVAILABLE:
    print(
        "\n"
        "=" * 78 + "\n"
        f"⚠️ 版本自检失败：本靶场要求 Jinja2 >={JINJA2_MIN},<{JINJA2_MAX_EXCLUSIVE}，"
        f"当前装的是 {JINJA2_VERSION}。\n"
        f"   逃逸原语（{CVE}）在 {JINJA2_FIXED_IN} 已被修复，"
        "四个关卡会全部无解。\n"
        "   请勿升级 Jinja2；需要最新版就把 requirements.txt 的固定范围一起改，\n"
        "   并先读 README「为什么锁定 Jinja2 3.1.5」。\n" + "=" * 78 + "\n",
        file=sys.stderr,
    )

#: 业务数据。flag 放在这里（模块全局）是刻意的：只有逃出沙箱、
#: 拿到 `helper.__globals__` 的人才能读到它。
SITEDATA: dict[str, str] = {
    "flag": flagutil.read_flag_file() or flagutil.resolve_flag(),
    "welcome": "abking's notes",
    "version": "1.0.0",
}


def site_helper(action: str = "version") -> str:
    """模板全局里注册的业务回调 —— 沙箱题的起点对象。

    它本身只返回站点版本号（无害），价值在于 ``__globals__`` 指向本模块的全局字典。
    """
    return f"notes-service v{SITEDATA['version']} ({action})"


def _register_sandbox_globals() -> None:
    """把业务回调登记进引擎缓存的两种沙箱环境。"""
    for kind in (sandbox_levels.SANDBOX_DEFAULT, sandbox_levels.SANDBOX_IMMUTABLE):
        try:
            env = jinja_engine._sandbox_environment(kind)  # noqa: SLF001 —— 引擎没有公开扩展点
        except Exception:  # noqa: BLE001 —— 引擎被改坏时也不该让靶场起不来
            continue
        env.globals["helper"] = site_helper


_register_sandbox_globals()

LEVELS = levels_for(sandbox_levels.REGISTRY_KEY)

META = LabMeta(
    id="jinja-sandbox",
    title="Jinja2 沙箱逃逸",
    subtitle="4 关：默认沙箱 / 不可变沙箱 / 关键字 WAF / 字符 WAF",
    engine=sandbox_levels.ENGINE,
    engine_title=sandbox_levels.ENGINE_TITLE,
    theme=THEMES["violet"],
    description=(
        "四个关卡都在 Jinja2 的沙箱渲染器里跑：`SandboxedEnvironment` 与 "
        "`ImmutableSandboxedEnvironment`。沙箱封的是**属性名**——所有 `_` 开头的名字"
        "（`__class__` / `__globals__` / `__subclasses__` …）都拿不到，"
        "教科书里的 `|attr` 链早已失效；本靶场教你当前仍然有效的原语，"
        "以及当 WAF 继续加压时怎么把关键字与字符在运行期拼回来。"
        "靶场固定 `Jinja2>=3.1.4,<3.1.6`（CVE-2025-27516 的修复版本是 3.1.6，"
        "升级后四关会全部无解）；原因与代价见 README 的「为什么锁定 Jinja2 3.1.5」。"
        f"\n\n运行时自检：Jinja2 {JINJA2_VERSION} · "
        f"逃逸原语{'可用 ✅' if ESCAPE_AVAILABLE else '不可用 ❌（版本漂移！）'} · "
        f"CVE {CVE}（{JINJA2_FIXED_IN} 修复）"
    ),
    hint=(
        "先看清沙箱拦了什么：`{{ ''|attr('__class__') }}` 是空的。 "
        "练习模式看回显，上帝模式看 `template_after_waf` 与异常类型区分「被 WAF 拦」和「载荷写错」。"
    ),
    doc_url="/docs/README.md",
)


def _extra_routes(flask_app) -> None:
    """机器可读的运行时自检：CI / 运维可以直接查逃逸原语是否还在。"""

    @flask_app.get("/api/sandbox/runtime")
    def api_sandbox_runtime():
        return jsonify(
            {
                "ok": ESCAPE_AVAILABLE,
                "cve": CVE,
                "fixed_in": JINJA2_FIXED_IN,
                "jinja2": JINJA2_VERSION,
                "supported": f">={JINJA2_MIN},<{JINJA2_MAX_EXCLUSIVE}",
                "escape_available": ESCAPE_AVAILABLE,
                "note": (
                    "逃逸原语可用" if ESCAPE_AVAILABLE else "版本漂移：CVE 已修复，四关无解，请回滚 Jinja2"
                ),
            }
        )


app = create_lab_app(
    META,
    LEVELS,
    engine_titles={sandbox_levels.ENGINE: sandbox_levels.ENGINE_TITLE},
    docs_folder="docs",
    extra_routes=_extra_routes,
)

if __name__ == "__main__":
    labapp.run(app)
