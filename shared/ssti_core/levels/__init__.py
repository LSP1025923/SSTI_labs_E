"""关卡注册表：按引擎汇总，并提供靶场按需取用的入口。

新增引擎/关卡的步骤：
1. 在本包下加 ``<engine>.py``，用 ``@make`` 定义关卡，导出 ``ALL``；
2. 在 ``_BY_ENGINE`` 里登记；
3. 建 ``labs/<编号>-<名字>/``（app.py + Dockerfile + compose + README）。
"""

from __future__ import annotations

from typing import Any

from ssti_core.level import Level
from ssti_core.levels import jinja, mako, sandbox, tornado

#: 注册键 -> 关卡列表。
#:
#: 多数情况下注册键就是 ``ENGINE``；但沙箱关卡（``sandbox.ENGINE == "jinja"``）
#: 与 13 关 WAF 链共用同一个引擎展示分组，**不能**用 ``"jinja"`` 当键，
#: 否则会覆盖 ``jinja.ALL``——所以它用自己的 ``sandbox.REGISTRY_KEY``。
_BY_ENGINE: dict[str, list[Level]] = {
    jinja.ENGINE: jinja.ALL,
    mako.ENGINE: mako.ALL,
    tornado.ENGINE: tornado.ALL,
    sandbox.REGISTRY_KEY: sandbox.ALL,
}

#: 注册键 -> 展示名
ENGINE_TITLES: dict[str, str] = {
    jinja.ENGINE: jinja.ENGINE_TITLE,
    mako.ENGINE: mako.ENGINE_TITLE,
    tornado.ENGINE: tornado.ENGINE_TITLE,
    sandbox.REGISTRY_KEY: sandbox.ENGINE_TITLE,
}


def levels_for(*engines: str) -> list[Level]:
    """按给定顺序拼接多个引擎的关卡；不传则返回全部。"""
    keys = engines or tuple(_BY_ENGINE)
    out: list[Level] = []
    for key in keys:
        out.extend(_BY_ENGINE.get(key, []))
    return out


def engine_of(levels: list[Level]) -> str:
    return levels[0].engine if levels else "jinja"


def engine_titles() -> dict[str, str]:
    return dict(ENGINE_TITLES)


def registry() -> dict[str, Any]:
    return {k: len(v) for k, v in _BY_ENGINE.items()}


__all__ = ["levels_for", "engine_of", "engine_titles", "registry", "ENGINE_TITLES"]
