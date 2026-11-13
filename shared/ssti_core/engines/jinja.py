"""Jinja2 渲染器：三种运行模式。

* ``jinja``         —— Flask ``render_template_string``，带完整 Flask 上下文
                       （``config`` / ``request`` / ``session`` / ``g`` / ``url_for`` /
                       ``get_flashed_messages`` 以及 Jinja 默认全局 ``lipsum`` / ``cycler`` /
                       ``joiner`` / ``namespace``）。这是真实 Flask 应用最常见的暴露面，
                       也是 ``config.__class__`` 与 ``lipsum.__globals__`` 两条经典链的来源。
* ``jinja_plain``   —— 裸 ``jinja2.Environment`` + 一组业务变量，对应本仓库最早期那版
                       「只有 name/numbers/string/dict/list」的挑战。
* ``jinja_sandbox`` —— ``SandboxedEnvironment`` / ``ImmutableSandboxedEnvironment``，
                       用于沙箱逃逸专项靶场。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from jinja2 import BaseLoader, Environment

from ssti_core.render import plain_text_output

if TYPE_CHECKING:  # pragma: no cover
    from ssti_core.level import Level


#: 早期那版挑战注入的业务变量，保持原样以便老题解仍然可用
LEGACY_CONTEXT: dict[str, Any] = {
    "name": "Eecho",
    "version": "1.0.0",
    "challenge": "SSTI CTF",
    "numbers": [1, 2, 3, 4, 5],
    "string": "Hello World",
    "dict": {"key": "value", "test": "data"},
    "list": ["a", "b", "c", "d", "e"],
    "true": True,
    "false": False,
    "none": None,
    "int": 42,
    "float": 3.14,
}


def _render_flask(template: str, level: "Level") -> str:
    from flask import render_template_string

    context = dict(level.options.get("context") or {})
    return plain_text_output(render_template_string(template, **context))


def _render_plain(template: str, level: "Level") -> str:
    # 刻意保持 Jinja 的默认 Undefined 行为（未定义变量渲染为空串），
    # 与本仓库最早那版 server.py 完全一致，保证老题解仍然成立。
    env = Environment(loader=BaseLoader())
    context = {**LEGACY_CONTEXT, **(level.options.get("context") or {})}
    return plain_text_output(env.from_string(template).render(**context))


_SANDBOXES: dict[str, Any] = {}


def _sandbox_environment(kind: str) -> Environment:
    """构造并缓存沙箱环境。

    ``default`` 只挡属性访问，``immutable`` 连修改也挡 —— 后者是 CTF 里
    更常见（也更难）的形态，两条逃逸链完全不同，所以分成两种。
    """
    if kind in _SANDBOXES:
        return _SANDBOXES[kind]
    from jinja2.sandbox import ImmutableSandboxedEnvironment, SandboxedEnvironment

    cls = ImmutableSandboxedEnvironment if kind == "immutable" else SandboxedEnvironment
    env = cls(loader=BaseLoader())
    # 沙箱题通常还会注册几个模板里能直接用的业务对象，
    # 否则 payload 连起点都没有；默认给一组与 Flask 站点同构的全局。
    env.globals.update(
        {
            "config": {"SECRET_KEY": "ssti-lab", "DEBUG": False},
            "session": {},
            "request": {"args": {}, "values": {}, "headers": {}},
            "url_for": lambda *a, **kw: "/",
            "get_flashed_messages": lambda *a, **kw: [],
        }
    )
    _SANDBOXES[kind] = env
    return env


def _render_sandbox(template: str, level: "Level") -> str:
    kind = str(level.options.get("sandbox", "default"))
    env = _sandbox_environment(kind)
    return plain_text_output(env.from_string(template).render())


def render(template: str, level: "Level") -> str:
    key = level.renderer_key
    if key == "jinja_plain":
        return _render_plain(template, level)
    if key == "jinja_sandbox":
        return _render_sandbox(template, level)
    return _render_flask(template, level)
