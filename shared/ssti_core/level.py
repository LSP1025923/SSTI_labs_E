"""关卡定义与渲染编排。

**渲染编排是这一层的唯一职责**：先过 WAF，再交给引擎，最后按关卡语义
（普通 / 盲关）包装输出。引擎差异被 ``ssti_core.engines`` 隐藏。
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from ssti_core.config import Config
from ssti_core.engines import render_with_engine
from ssti_core.render import RenderResult, plain_text_output, truncate
from ssti_core.waf import NO_WAF, WafSpec


@dataclass
class Level:
    """一个关卡 = 一套（模板引擎 + WAF 规则 + 回显方式）。"""

    level_id: str = "0"
    title: str = ""
    description: str = ""
    #: 引擎展示分组（前端引擎切换器用），如 ``jinja`` / ``mako`` / ``tornado``
    engine: str = "jinja"
    #: 实际渲染器键；留空则用 ``engine``。用于同一引擎的不同运行模式
    #: （例如 ``jinja`` vs ``jinja_sandbox``）
    renderer: str = ""
    waf: WafSpec = field(default_factory=lambda: NO_WAF)
    #: 回显方式，决定「你能看到什么」，是盲注类题目的核心设计维度：
    #:   full —— 正常回显渲染结果
    #:   bool —— 只回显 correct / wrong（布尔信道）
    #:   none —— 恒定回显固定字符串，连成功失败都不告诉你（只能靠时间/副作用）
    #:   file —— 不回显，要求你把结果写到可 HTTP 访问的目录再取回
    echo_mode: str = "full"
    #: 恒定回显内容（``echo_mode == "none"`` 时使用）
    echo_text: str = "ok"
    #: 本关是否额外要求「不出网」利用
    no_egress: bool = False
    #: 一句话概述（关卡列表里展示）
    summary: str = ""
    #: 思路提示（前端折叠展示，不要写完整题解）
    hint: str = ""
    #: 传给渲染器的引擎专属参数（沙箱模式、注入的上下文变量等）
    options: dict[str, Any] = field(default_factory=dict)
    #: 上帝模式展示的出题源码（由 :func:`make` 自动抓取）
    source: str = field(default="", repr=False)
    #: 构造本关的工厂函数名
    factory_name: str = field(default="", repr=False)

    # -- 元信息 -----------------------------------------------------------
    @property
    def renderer_key(self) -> str:
        return self.renderer or self.engine

    @property
    def blind(self) -> bool:
        """是否属于「不回显真实输出」的关卡（前端据此打盲注标记）。"""
        return self.echo_mode != "full"

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.level_id,
            "title": self.title,
            "summary": self.summary or self.title,
            "description": self.description,
            "blind": self.blind,
            "echo_mode": self.echo_mode,
            "no_egress": self.no_egress,
            "waf": self.waf.to_json(),
            "hint": self.hint,
        }

    # -- 渲染 -------------------------------------------------------------
    def build_template(self, raw: str) -> str:
        return self.waf.apply(raw)

    def render(self, raw: str, max_chars: int | None = None) -> RenderResult:
        limit = Config.MAX_OUTPUT_CHARS if max_chars is None else max_chars
        template_after_waf = self.waf.apply(raw)

        if self.waf.is_active and self.waf.blocks(raw):
            return RenderResult(
                practice_output=self.waf.replacement,
                raw_output="",
                error=None,
                exception_type=None,
                waf_blocked=True,
                template_after_waf=template_after_waf,
            )

        try:
            raw_out = plain_text_output(render_with_engine(self.renderer_key, template_after_waf, self))
            error: str | None = None
            exception_type: str | None = None
        except Exception as exc:  # noqa: BLE001 —— 题目要回显异常类型，不能吞细节
            raw_out = ""
            error = f"{type(exc).__name__}: {exc}"
            exception_type = type(exc).__name__

        shown, truncated = truncate(raw_out, limit)

        mode = self.echo_mode
        if mode == "bool":
            # 布尔信道：成功/失败是唯一信息；真实输出只在上帝模式暴露
            practice = "wrong" if error is not None else "correct"
        elif mode in ("none", "file"):
            # 信道完全关闭：只有时间差与副作用（写文件）可观测
            practice = self.echo_text
        else:
            practice = shown if error is None else f"[渲染异常] {exception_type}"

        return RenderResult(
            practice_output=practice,
            raw_output=shown,
            error=error,
            exception_type=exception_type,
            truncated=truncated,
            waf_blocked=False,
            template_after_waf=template_after_waf,
        )


def make(factory: Callable[[], Level]) -> Level:
    """关卡装饰器：构造 ``Level`` 并抓取工厂函数源码用于上帝模式。

    用法::

        @make
        def L01() -> Level:
            return Level(level_id="0", title="L1 - 无过滤", ...)

    装饰后 ``L01`` 就是 ``Level`` 实例。上帝模式把 ``inspect.getsource`` 抓到的
    这段源码原样展示，玩家能看到**过滤规则究竟是哪几行**——这比给一份
    文字说明有用得多，也是参考项目 ``/api/god/source`` 的核心价值。
    """
    level = factory()
    level.factory_name = factory.__name__
    try:
        level.source = inspect.getsource(factory)
    except (OSError, TypeError):  # 冻结/打包环境中源码不可得
        level.source = ""
    return level


def find_level(levels: list[Level], level_id: str | None) -> Level:
    """按 id 取关卡；找不到时回落到第一关（与参考项目行为一致）。"""
    if not levels:
        raise ValueError("靶场未定义任何关卡")
    if level_id is None or level_id == "":
        return levels[0]
    for lv in levels:
        if lv.level_id == str(level_id):
            return lv
    return levels[0]


def group_engines(levels: list[Level], titles: dict[str, str] | None = None) -> list[dict[str, str]]:
    """按出现顺序汇总引擎列表，供前端切换器使用。"""
    seen: list[str] = []
    for lv in levels:
        if lv.engine not in seen:
            seen.append(lv.engine)
    titles = titles or {}
    return [{"id": e, "title": titles.get(e, e.title())} for e in seen]
