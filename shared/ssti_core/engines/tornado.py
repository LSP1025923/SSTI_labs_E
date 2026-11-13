"""Tornado 渲染器：``tornado.template.Template(...).generate()``。

``generate()`` 返回 ``bytes``，需要解码后回显。默认命名空间里有 ``escape``
（实为 ``xhtml_escape``）与 ``datetime`` 等，都是有价值的 gadget 起点。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from ssti_core.render import plain_text_output

if TYPE_CHECKING:  # pragma: no cover
    from ssti_core.level import Level


def _generate_kwargs() -> dict[str, Any]:
    """构造 ``generate()`` 的 kwargs，模拟 Tornado Handler 的 ``self`` 环境。"""
    try:
        from flask import has_request_context, request
    except ImportError:  # pragma: no cover
        return {}

    if not has_request_context():
        return {}

    def get_argument(name: str, default: Any = None) -> Any:
        return request.values.get(name, default)

    def get_secure_cookie(name: str, default: Any = None) -> Any:
        return request.cookies.get(name, default)

    handler = SimpleNamespace(
        get_argument=get_argument,
        get_secure_cookie=get_secure_cookie,
        request=request,
        reverse_url=lambda *a, **kw: "/",
    )
    return {"request": request, "handler": handler}


def render(template: str, level: "Level") -> str:
    from tornado.template import Template

    context = {**_generate_kwargs(), **(level.options.get("context") or {})}
    raw = Template(template).generate(**context)
    return plain_text_output(raw)
