"""Mako 13 关 WAF 链。

与 Jinja 关的差别不只是语法：Mako 把模板**编译成 Python 模块**再执行，
所以 `<%! %>` 是模块级代码、`<% %>` 是函数体代码，`context.write` 直接写输出。
这让 Mako 的「语法面」比 Jinja 宽得多——`${` 被拦之后还有整片代码块可用。

渲染器已向模板注入 ``request`` / ``session`` / ``g`` / ``url_for`` /
``get_flashed_messages`` / ``config`` 以及 Jinja 的 ``lipsum`` / ``cycler`` /
``joiner`` / ``namespace``，因此 Mako 关也能走与 Jinja 关同构的 gadget 链，
方便两个靶场对照着看。
"""

from __future__ import annotations

from ssti_core.level import Level, make
from ssti_core.waf import WafSpec

ENGINE = "mako"
ENGINE_TITLE = "Mako"


@make
def L01() -> Level:
    return Level(
        level_id="0",
        engine=ENGINE,
        title="L1 - 无过滤",
        summary="裸 Template(...).render()",
        description=(
            "用户输入进入 `mako.template.Template(...).render()`。先确认语法："
            "`${7*7}`、`%for` / `%if` 行控制、`<% %>` 代码块、`<%! %>` 模块级代码。"
            "最直接的读文件是 `${open('/flag').read()}`。"
        ),
        hint="Mako 里 `${ }` 内是**原生 Python 表达式**，不需要绕属性就能直接调内置函数。",
    )


@make
def L02() -> Level:
    return Level(
        level_id="1",
        engine=ENGINE,
        title="L2 - 拦截 ${",
        summary="${ 被整段替换为 WAF",
        description=(
            "只要出现 `${` 整段就被替换成 `WAF`。但 `${}` 只是输出表达式的一种写法，"
            "代码块 `<% %>` 与 `<%! %>` 都还在。"
        ),
        waf=WafSpec(substrings=("${",), ignore_case=False, note="出现 `${` 即整段替换为 `WAF`。"),
        hint="在 `<% %>` 里用 `context.write(...)` 写输出，完全不需要 `${}`。",
    )


@make
def L03() -> Level:
    return Level(
        level_id="2",
        engine=ENGINE,
        title="L3 - 盲编译/渲染",
        summary="只回显 correct / wrong",
        description=(
            "服务端只反馈「编译并渲染成功」（`correct`）或「失败」（`wrong`），"
            "不回显输出。Mako 的模板是编译成 Python 的，所以**语法错误也会**导致 `wrong`，"
            "这让它天然成了一个布尔盲注信道。"
        ),
        echo_mode="bool",
        hint="任何能成功渲染的模板都返回 correct；要读数据就把它变成「成功/失败」的判断。",
    )


@make
def L04() -> Level:
    return Level(
        level_id="3",
        engine=ENGINE,
        title="L4 - 禁止方括号",
        summary="过滤 [ 与 ]",
        description="出现 `[` 或 `]` 即返回 `WAF`。不要用 `[:n]` 截断，直接读全文。",
        waf=WafSpec(chars=("[", "]"), note="包含 `[` 或 `]` 即返回 `WAF`。"),
        hint="`__subclasses__()` 之后通常要靠下标取类——本关要用 `.__getitem__` 之外的办法，"
        "或者干脆不走上游链，直接找不需要下标的入口。",
    )


@make
def L05() -> Level:
    return Level(
        level_id="4",
        engine=ENGINE,
        title="L5 - 禁止引号",
        summary="过滤 ' 与 \"",
        description=(
            "出现单引号或双引号即返回 `WAF`。字符串字面量写不出来，"
            "但 `chr()` 可以拼出任意字节。"
        ),
        waf=WafSpec(chars=("'", '"'), note="包含 `'` 或 `\"` 即返回 `WAF`。"),
        hint="`chr(47)` 就是 `/`。把路径一个字节一个字节拼出来。",
    )


@make
def L06() -> Level:
    return Level(
        level_id="5",
        engine=ENGINE,
        title="L6 - 禁止下划线",
        summary="过滤 _",
        description="出现 `_` 即返回 `WAF`。魔术属性全部写不了；`chr` 拼串方案依然可用。",
        waf=WafSpec(chars=("_",), note="包含 `_` 即返回 `WAF`。"),
        hint="上一关那套 `chr()` 拼接在**不使用任何下划线标识符**时仍然成立。",
    )


@make
def L07() -> Level:
    return Level(
        level_id="6",
        engine=ENGINE,
        title="L7 - 禁止点号",
        summary="过滤 .",
        description="出现 `.` 即返回 `WAF`。属性访问的点号语法被封，改用 `getattr`。",
        waf=WafSpec(chars=(".",), note="包含 `.` 即返回 `WAF`。"),
        hint="`getattr(obj, name)()` 可以完全替代 `obj.name()`。",
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
            "`getattr` 含 `attr` 被禁，`open` 也写不出来——"
            "但 `__import__` 不在黑名单里，可以借它导入模块。"
        ),
        waf=WafSpec(
            substrings=(
                "class", "arg", "form", "value", "data", "request",
                "init", "global", "open", "mro", "base", "attr",
            ),
            ignore_case=False,
            note="命中任一子串即返回 `WAF`（大小写敏感）。",
        ),
        hint="`__import__` 里没有被禁子串，可以直接导入 `subprocess`，"
        "再调 `getoutput` 执行命令。",
    )


@make
def L09() -> Level:
    return Level(
        level_id="8",
        engine=ENGINE,
        title="L9 - 禁止数字",
        summary="过滤 0-9",
        description=(
            "出现任何数字即返回 `WAF`。`chr(47)` 这类方案需要数字，必须改用"
            "`True` / `False` / `len(())` 之类的运算拼出整数。"
        ),
        waf=WafSpec(chars=tuple("0123456789"), note="包含 `0-9` 任一数字即返回 `WAF`。"),
        hint="布尔值在 Python 里就是整数：`True` 是 1、`False` 是 0；"
        "再用加减移位凑出 47 这种数，或用 `request` 之外的通道把数字带进来。",
    )


@make
def L10() -> Level:
    return Level(
        level_id="9",
        engine=ENGINE,
        title="L10 - 前缀空分支",
        summary="载荷前被拼接固定的 % if False 块",
        description=(
            "服务端在载荷前拼接 `% if False:\\n% endif\\n`，用来打乱部分「直接开写」的"
            "结构。它不会真的拦你，只是改变了模板的起始上下文。"
        ),
        waf=WafSpec(
            prefix="% if False:\n% endif\n",
            note="载荷前自动拼接 `% if False:\\n% endif\\n`。",
        ),
        hint="前缀本身是合法的 Mako 行语法；照常写你的载荷即可。",
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
        hint="Mako 的 `${}` 里 Python 内置函数直接可用：`__import__` 没有被禁，"
        "`getattr` 替代点号，`str(bytes((…)), 编码)` 可以无引号/无加号地造出任意字符串。",
    )


@make
def L12() -> Level:
    return Level(
        level_id="11",
        engine=ENGINE,
        title="L12 - 强字符集",
        summary="下划线 / 点号 / 数字 / 反斜杠 / 引号 / 方括号",
        description=(
            "在上一关基础上再禁 `_`、数字与反斜杠。字符串、数字、魔术属性三条路同时被堵，"
            "属于 CTF 硬关。"
        ),
        waf=WafSpec(
            chars=("_", ".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "\\", "'", '"', "[", "]"),
            note="禁止 `_ . 0-9 \\ ' \" [ ]`。",
        ),
        hint="Mako 是编译成 Python 的，`%` 行控制与代码块仍然可用；"
        "本关 `+` 并没有被禁，`True` 参与算术能凑出整数，`chr()` 就回来了。"
        "另一条路：`open` 是内置函数，`from os import sep` 能无下划线地拿到 `/`。",
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
        hint="本关封了 `getattr`（含 `attr`）与 `+`，但 `<% %>` 代码块里的 "
        "`from x import y` 语句没有被禁，数字也仍然可用；"
        "`str(bytes((…)), 编码)` 造串不需要任何运算符。"
        "先用上帝模式确认过滤行为再压载荷。",
    )


ALL: list[Level] = [L01, L02, L03, L04, L05, L06, L07, L08, L09, L10, L11, L12, L13]
