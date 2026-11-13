"""Bottle ``SimpleTemplate`` 渲染器（可选引擎）。

Bottle 的 ``SimpleTemplate`` 用 ``{{ }}`` / ``%`` 行语法，Python 表达式直接求值。
它的 ``include`` / ``rebase`` 支持把模板名当路径用，天然带一层本地文件包含，
是「SSTI 与 LFI 交界」的好教具。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ssti_core.render import plain_text_output

if TYPE_CHECKING:  # pragma: no cover
    from ssti_core.level import Level


def _flask_context() -> dict[str, Any]:
    try:
        from flask import current_app, has_request_context, request, session
    except ImportError:  # pragma: no cover
        return {}
    if not has_request_context():
        return {}
    return {"request": request, "session": session, "config": current_app.config}


def render(template: str, level: "Level") -> str:
    from bottle import SimpleTemplate

    context = {**_flask_context(), **(level.options.get("context") or {})}
    return plain_text_output(SimpleTemplate(template).render(**context))
