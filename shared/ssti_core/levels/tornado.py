"""Tornado 13 关 WAF 链。

Tornado 模板同样被编译成 Python。它的默认命名空间里有几个别处没有的起点：
``escape``（实为 ``xhtml_escape``）、``datetime``、``handler``（本项目注入的
Handler 桩，带 ``get_argument`` / ``get_secure_cookie`` / ``reverse_url``）、
``request``。真实 Tornado 应用里 ``handler.settings`` 会直接泄露
``cookie_secret`` —— 这是 Tornado 站点最常见的敏感信息入口。

语法面上 ``{% import %}`` 可以直接导入模块，是比 Jinja 短得多的 RCE 路径。
"""

from __future__ import annotations

from ssti_core.level import Level, make
from ssti_core.waf import WafSpec

ENGINE = "tornado"
ENGINE_TITLE = "Tornado"


@make
def L01() -> Level:
    return Level(
        level_id="0",
        engine=ENGINE,
        title="L1 - 无过滤",
        summary="裸 Template(...).generate()",
        description=(
            "用户输入进入 `tornado.template.Template(...).generate()`，"
            "返回值是 `bytes`，解码后回显。熟悉 `{{ ... }}` 与 `{% ... %}`，"
            "并注意默认命名空间里已经有的 `escape` / `datetime` / `handler` / `request`。"
        ),
        hint="Tornado 的 `{% import %}` 是直接导入模块的；"
        "真实站点里 `handler.settings` 常常直接暴露 `cookie_secret`。",
    )


@make
def L02() -> Level:
    return Level(
        level_id="1",
        engine=ENGINE,
        title="L2 - 拦截 {{",
        summary="双花括号被整段替换为 WAF",
        description="只要出现 `{{` 整段就被替换成 `WAF`；`{% %}` 语句块没有拦。",
        waf=WafSpec(substrings=("{{",), ignore_case=False, note="出现 `{{` 即整段替换为 `WAF`。"),
        hint="`{% import %}`、`{% set %}`、`{% if %}` 都是语句块。",
    )


@make
def L03() -> Level:
    return Level(
        level_id="2",
        engine=ENGINE,
        title="L3 - 盲渲染",
        summary="只回显 correct / wrong",
        description=(
            "服务端只反馈模板能否成功生成（`correct` / `wrong`），不回显内容。"
            "Tornado 模板编译失败同样落入 `wrong`，因此这也是一个布尔信道。"
        ),
        echo_mode="bool",
        hint="把「读到的数据」转换成「模板是否渲染成功」。",
    )


@make
def L04() -> Level:
    return Level(
        level_id="3",
        engine=ENGINE,
        title="L4 - 禁止方括号",
        summary="过滤 [ 与 ]",
        description="出现 `[` 或 `]` 即返回 `WAF`。下标取值不可用。",
        waf=WafSpec(chars=("[", "]"), note="包含 `[` 或 `]` 即返回 `WAF`。"),
        hint="Tornado 模板里可以用 `{% for %}` 遍历，也可以调用 `.__getitem__` 之外的方法。",
    )


@make
def L05() -> Level:
    return Level(
        level_id="4",
        engine=ENGINE,
        title="L5 - 禁止引号",
        summary="过滤 ' 与 \"",
        description="出现单引号或双引号即返回 `WAF`。字符串字面量写不了。",
        waf=WafSpec(chars=("'", '"'), note="包含 `'` 或 `\"` 即返回 `WAF`。"),
        hint="`chr()` 依旧可用；Tornado 也允许在模板里直接调用内置函数。",
    )


@make
def L06() -> Level:
    return Level(
        level_id="5",
        engine=ENGINE,
        title="L6 - 禁止下划线",
        summary="过滤 _",
        description="出现 `_` 即返回 `WAF`。`__class__` / `__globals__` 这类属性全部写不了。",
        waf=WafSpec(chars=("_",), note="包含 `_` 即返回 `WAF`。"),
        hint="Tornado 模板是编译过的 Python，`getattr(obj, 字符串)` 依然可用——"
        "而属性名字符串可以用 `chr` 拼。",
    )


@make
def L07() -> Level:
    return Level(
        level_id="6",
        engine=ENGINE,
        title="L7 - 禁止点号",
        summary="过滤 .",
        description="出现 `.` 即返回 `WAF`。属性访问语法被封，改用 `getattr` / `__getitem__`。",
        waf=WafSpec(chars=(".",), note="包含 `.` 即返回 `WAF`。"),
        hint="本关方括号没有被拦，`obj[名字]` 可以完全替代 `obj.名字`。",
    )


@make
def L08() -> Level:
    return Level(
        level_id="7",
        engine=ENGINE,
        title="L8 - 关键字子串黑名单",
        summary="12 个高危子串（大小写敏感）",
        description=(
            "不能出现子串：`class`、`arg`、`form`、`value`、`data`、`request`、`init`、"
            "`global`、`open`、`mro`、`base`、`attr`。"
        ),
        waf=WafSpec(
            substrings=(
                "class", "arg", "form", "value", "data", "request",
                "init", "global", "open", "mro", "base", "attr",
            ),
            ignore_case=False,
            note="命中任一子串即返回 `WAF`（大小写敏感）。",
        ),
        hint="`escape` / `datetime` / `handler` 这些上下文对象名都没有被禁，"
        "顺着它们往上走；也可以 `{% import %}` 直接导入模块（注意 `os` 没被禁）。",
    )


@make
def L09() -> Level:
    return Level(
        level_id="8",
        engine=ENGINE,
        title="L9 - 禁止数字",
        summary="过滤 0-9",
        description="出现任何数字即返回 `WAF`。需要用布尔/长度运算拼出整数。",
        waf=WafSpec(chars=tuple("0123456789"), note="包含 `0-9` 任一数字即返回 `WAF`。"),
        hint="`True` 与 `False` 在 Python 里就是 1 和 0；"
        "`escape` / `handler` 这类对象的名字长度也是整数来源。",
    )


@make
def L10() -> Level:
    return Level(
        level_id="9",
        engine=ENGINE,
        title="L10 - 前缀置空 config / self",
        summary="载荷前被拼接固定前缀",
        description=(
            "服务端在载荷前拼接 `{% set config=None %}{% set self=None %}`，"
            "把两个常用入口置空。"
        ),
        waf=WafSpec(
            prefix="{% set config=None %}{% set self=None %}",
            note="载荷前自动拼接 `{% set config=None %}{% set self=None %}`。",
        ),
        hint="被置空的是变量，不是类型；其它全局对象不受影响。",
    )


@make
def L11() -> Level:
    return Level(
        level_id="10",
        engine=ENGINE,
        title="L11 - 组合过滤",
        summary="引号 / 加号 / 点号 / 方括号 / request",
        description="同时禁止 `'`、`\"`、`+`、`.`、`[`、`]` 与子串 `request`。",
        waf=WafSpec(
            chars=("'", '"', "+", ".", "[", "]"),
            substrings=("request",),
            ignore_case=False,
            note="禁止 `' \" + . [ ]` 与子串 `request`。",
        ),
        hint="`str.join` 替代加号、`getattr` 替代点号；取值通道要绕开 `request` 这个名字。",
    )


@make
def L12() -> Level:
    return Level(
        level_id="11",
        engine=ENGINE,
        title="L12 - 强字符集",
        summary="下划线 / 点号 / 数字 / 反斜杠 / 引号 / 方括号",
        description="在上一关基础上再禁 `_`、数字与反斜杠。属于 CTF 硬关。",
        waf=WafSpec(
            chars=("_", ".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "\\", "'", '"', "[", "]"),
            note="禁止 `_ . 0-9 \\ ' \" [ ]`。",
        ),
        hint="Tornado 的 `{% import %}` 语句本身不含被禁字符，是很好的起点。",
    )


@make
def L13() -> Level:
    return Level(
        level_id="12",
        engine=ENGINE,
        title="L13 - 扩展关键字与符号",
        summary="最严一关：符号 + 关键字双重封堵",
        description=(
            "综合黑名单：符号 `_ . \\ ' \" + [ ]` 与子串 `request`、`class`、`init`、"
            "`arg`、`config`、`app`、`self`。"
        ),
        waf=WafSpec(
            chars=("_", ".", "\\", "'", '"', "+", "[", "]"),
            substrings=("request", "class", "init", "arg", "config", "app", "self"),
            ignore_case=False,
            note="禁止 `_ . \\ ' \" + [ ]` 与子串 `request/class/init/arg/config/app/self`。",
        ),
        hint="刻意设计的硬关：先用上帝模式观察 `template_after_waf`，再逐项压缩。",
    )


ALL: list[Level] = [L01, L02, L03, L04, L05, L06, L07, L08, L09, L10, L11, L12, L13]
