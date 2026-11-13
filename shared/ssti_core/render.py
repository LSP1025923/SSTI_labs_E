"""渲染结果的统一表示。"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RenderResult:
    """一次模板渲染的完整结果。

    ``practice_output`` 是给玩家看的，``raw_output`` 是真实求值结果
    （盲关下两者不同，只有上帝模式能看到后者）。
    """

    practice_output: str = ""
    raw_output: str = ""
    error: str | None = None
    exception_type: str | None = None
    truncated: bool = False
    waf_blocked: bool = False
    template_after_waf: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """练习模式的「成功」语义：WAF 没拦、且没有异常。"""
        return not self.waf_blocked and self.error is None

    def to_json(self, *, god: bool = False, flag_found: bool = False, **meta: Any) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": self.ok,
            "output": self.practice_output,
            "truncated": self.truncated,
            "flag_found": flag_found,
        }
        payload.update(meta)
        if god:
            payload.update(
                {
                    "template_after_waf": self.template_after_waf,
                    "raw_output": self.raw_output,
                    "error": self.error,
                    "exception_type": self.exception_type,
                    "waf_blocked": self.waf_blocked,
                }
            )
            payload.update(self.extra)
        return payload


def plain_text_output(value: object) -> str:
    """把任意渲染结果转成纯文本，并抵消 Jinja autoescape 带来的 HTML 实体。

    统一出口的好处：不同引擎（Jinja 会转义、Mako/Tornado 不会）在多引擎
    对照教学时表现一致，玩家不会因为实体编码而误判 payload 失败。
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        return html.unescape(value.decode("utf-8", errors="replace"))
    return html.unescape(str(value))


def truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[:max_chars] + "\n... [输出已截断]", True
