"""模板引擎渲染器注册表。

新增引擎只需：
1. 在本包内加一个模块，暴露 ``render(template: str, level) -> str``；
2. 在 ``_RENDERERS`` 里登记；
3. 在 ``REQUIRED_PACKAGES`` 里登记它需要的 pip 包（用于构建期自检）。

约定：渲染器**直接抛异常**，不要自己 try/except —— 异常类型是题目反馈的一部分，
由 ``ssti_core.level.Level.render`` 统一收集。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:  # pragma: no cover
    from ssti_core.level import Level

Renderer = Callable[[str, "Level"], str]

#: 渲染器 -> 需要的 pip 包名（镜像构建期做一次 import 自检）
REQUIRED_PACKAGES: dict[str, str] = {
    "jinja": "jinja2",
    "jinja_sandbox": "jinja2",
    "jinja_plain": "jinja2",
    "mako": "mako",
    "tornado": "tornado",
    "bottle": "bottle",
}


def _load(key: str) -> Renderer:
    if key in ("jinja", "jinja_sandbox", "jinja_plain"):
        from ssti_core.engines import jinja

        return jinja.render
    if key == "mako":
        from ssti_core.engines import mako

        return mako.render
    if key == "tornado":
        from ssti_core.engines import tornado

        return tornado.render
    if key == "bottle":
        from ssti_core.engines import bottle

        return bottle.render
    raise KeyError(f"未知渲染器: {key!r}（可用: {', '.join(REQUIRED_PACKAGES)}）")


def render_with_engine(key: str, template: str, level: "Level") -> str:
    return _load(key)(template, level)


def available_renderers() -> list[str]:
    return sorted(REQUIRED_PACKAGES)
