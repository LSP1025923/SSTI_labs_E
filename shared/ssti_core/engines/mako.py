"""Mako 渲染器：``mako.template.Template(...).render()``。

与参考项目一致，主动把 Flask 侧上下文（``request`` / ``session`` / ``g`` /
``url_for`` / ``get_flashed_messages`` / ``config``）以及 Jinja 的几个默认全局
（``lipsum`` / ``cycler`` / ``joiner`` / ``namespace``）注入进去 ——
这样 Mako 关也能走出与 Jinja 关同构的 gadget 链，便于对照教学。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ssti_core.render import plain_text_output

if TYPE_CHECKING:  # pragma: no cover
    from ssti_core.level import Level


def _flask_context() -> dict[str, Any]:
    try:
        from flask import (
            current_app,
            g,
            get_flashed_messages,
            has_request_context,
            request,
            session,
            url_for,
        )
    except ImportError:  # pragma: no cover - flask 是硬依赖
        return {}

    if not has_request_context():
        return {}

    rv: dict[str, Any] = {
        "request": request,
        "session": session,
        "g": g,
        "url_for": url_for,
        "get_flashed_messages": get_flashed_messages,
        "config": current_app.config,
    }
    env = current_app.jinja_env
    for name in ("lipsum", "cycler", "joiner", "namespace"):
        fn = env.globals.get(name)
        if fn is not None:
            rv[name] = fn
    return rv


def render(template: str, level: "Level") -> str:
    from mako.template import Template

    context = {**_flask_context(), **(level.options.get("context") or {})}
    return plain_text_output(Template(template).render(**context))
