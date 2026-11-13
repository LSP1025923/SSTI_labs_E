"""可复用的 WAF 规则描述与执行。

设计目标：
* **声明式**——关卡只声明规则，不在渲染逻辑里散落 ``if`` 判断；
* **可序列化**——前端能拿到规则摘要（``to_json``），玩家不用 fuzz 猜过滤了什么；
* **可组合**——子串黑名单 / 字符黑名单 / 正则 / 固定前后缀编织四种原语自由叠加。

返回 ``replacement``（默认字面量 ``WAF``）而不是抛异常，是与参考项目
``ProbiusOfficial/ssti-lab`` 对齐的行为：玩家看到 ``WAF`` 就知道被拦了，
看到异常就知道绕过了过滤但载荷本身写错了。这两种反馈在教学上必须可区分。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class WafSpec:
    """一组过滤原语的组合。``apply`` 是唯一入口。"""

    #: 命中任一子串即拦截
    substrings: tuple[str, ...] = ()
    #: 命中任一字符即拦截
    chars: tuple[str, ...] = ()
    #: 命中任一正则即拦截
    regexes: tuple[str, ...] = ()
    #: 无论是否命中，都在载荷前拼接（参考项目的「前缀置空 config/self」型关卡）
    prefix: str = ""
    #: 同理，拼在载荷后
    suffix: str = ""
    #: 命中后的替换文本
    replacement: str = "WAF"
    #: 子串/正则是否忽略大小写
    ignore_case: bool = True
    #: 人类可读的规则说明（前端直接展示，务必写清楚「到底禁了什么」）
    note: str = ""

    _compiled: list[re.Pattern[str]] | None = field(default=None, repr=False, compare=False)

    # -- 构造便捷方法 ------------------------------------------------------
    @classmethod
    def blocked_substrings(
        cls, items: Iterable[str], note: str = "", ignore_case: bool = True
    ) -> "WafSpec":
        return cls(substrings=tuple(items), note=note, ignore_case=ignore_case)

    @classmethod
    def blocked_chars(cls, items: Iterable[str], note: str = "") -> "WafSpec":
        return cls(chars=tuple(items), note=note)

    @classmethod
    def prefix_with(cls, prefix: str, note: str = "") -> "WafSpec":
        return cls(prefix=prefix, note=note)

    # -- 属性 -------------------------------------------------------------
    @property
    def is_active(self) -> bool:
        return bool(self.substrings or self.chars or self.regexes or self.prefix or self.suffix)

    @property
    def kind(self) -> str:
        """机器可读的类型标签，供前端分组展示。"""
        blocking = int(bool(self.substrings)) + int(bool(self.chars)) + int(bool(self.regexes))
        if blocking == 0:
            return "prefix" if (self.prefix or self.suffix) else "none"
        if blocking == 1:
            if self.substrings:
                return "substring"
            if self.chars:
                return "chars"
            return "regex"
        return "combo"

    # -- 执行 -------------------------------------------------------------
    def _patterns(self) -> list[re.Pattern[str]]:
        if self._compiled is None:
            flags = re.IGNORECASE if self.ignore_case else 0
            self._compiled = [re.compile(p, flags) for p in self.regexes]
        return self._compiled

    def blocks(self, template: str) -> bool:
        """是否命中拦截规则（不含前后缀拼接）。"""
        haystack = template
        if self.substrings:
            probe = haystack.lower() if self.ignore_case else haystack
            for item in self.substrings:
                needle = item.lower() if self.ignore_case else item
                if needle in probe:
                    return True
        for ch in self.chars:
            if ch in haystack:
                return True
        return any(p.search(template) for p in self._patterns())

    def apply(self, template: str) -> str:
        """执行过滤：命中则整段替换，否则拼接前后缀。"""
        if self.blocks(template):
            return self.replacement
        return f"{self.prefix}{template}{self.suffix}"

    # -- 序列化 -----------------------------------------------------------
    def to_json(self) -> dict[str, Any] | None:
        """给前端的规则摘要；无过滤时返回 ``None``。"""
        if not self.is_active:
            return None
        payload: dict[str, Any] = {"kind": self.kind}
        if self.substrings:
            payload["substrings"] = list(self.substrings)
        if self.chars:
            payload["chars"] = list(self.chars)
        if self.regexes:
            payload["regexes"] = list(self.regexes)
        if self.prefix:
            payload["prefix"] = self.prefix
        if self.suffix:
            payload["suffix"] = self.suffix
        #: 兼容契约里的 items 字段：前端可能只渲染 items
        payload["items"] = list(self.substrings) + list(self.chars) + list(self.regexes)
        payload["note"] = self.note or self._auto_note()
        return payload

    def _auto_note(self) -> str:
        bits: list[str] = []
        if self.substrings:
            bits.append("命中任一子串即拦截：" + ", ".join(self.substrings))
        if self.chars:
            bits.append("包含任一字符即拦截：" + " ".join(self.chars))
        if self.regexes:
            bits.append("命中任一正则即拦截：" + ", ".join(self.regexes))
        if self.prefix or self.suffix:
            bits.append("载荷会被拼接固定前后缀")
        return "；".join(bits)


#: 无过滤
NO_WAF = WafSpec(note="无过滤")
