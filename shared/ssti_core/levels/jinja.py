"""Jinja2 13 关 WAF 链。

难度曲线与 ``ProbiusOfficial/ssti-lab`` 的 Jinja 链对齐：从「无过滤」开始，
每关只加一条规则，逼玩家把已知的 gadget 链逐字符地变形。这样做的教学价值在于
**同一目标、逐步加压**：玩家能清楚看到「是哪一条规则让我的 payload 死掉的」。

God 模式会把下面每个 `Lxx` 工厂函数的源码原样展示，过滤规则一目了然。
"""

from __future__ import annotations

from ssti_core.level import Level, make
from ssti_core.waf import WafSpec

ENGINE = "jinja"
ENGINE_TITLE = "Jinja2"


@make
def L01() -> Level:
    return Level(
        level_id="0",
        engine=ENGINE,
        title="L1 - 无过滤",
        summary="裸 render_template_string",
        description=(
            "用户输入原样进入 Flask 的 `render_template_string`。"
            "先用 `{{7*7}}` 确认注入点，再熟悉 Flask 注入的上下文："
            "`config` / `request` / `session` / `url_for` / `get_flashed_messages` "
            "以及 Jinja 默认全局 `lipsum` / `cycler` / `joiner` / `namespace`。"
        ),
        hint="Flask 的注入点首选 `config`，其次 `lipsum.__globals__`。",
    )


@make
def L02() -> Level:
    return Level(
        level_id="1",
        engine=ENGINE,
        title="L2 - 拦截 {{",
        summary="双花括号被整段替换为 WAF",
        description=(
            "只要载荷里出现 `{{`，整段就被替换成字面量 `WAF`。"
            "但 `{%` 语句块没有被拦——`{%` 里也能求值。"
        ),
        waf=WafSpec(
            substrings=("{{",),
            ignore_case=False,
            note="出现 `{{` 即整段替换为 `WAF`；`{% %}` 未拦。",
        ),
        hint="Jinja 的语句块 `{% print(...) %}` 同样会求值表达式。",
    )


@make
def L03() -> Level:
    return Level(
        level_id="2",
        engine=ENGINE,
        title="L3 - 盲渲染",
        summary="只回显 correct / wrong",
        description=(
            "服务端只告诉你模板「渲染成功」还是「抛异常」：成功返回 `correct`，"
            "失败返回 `wrong`，不再回显求值结果。这就是**无回显 SSTI** 的基本形态，"
            "你需要把「拿到数据」变成「控制成功与否」。"
        ),
        echo_mode="bool",
        hint="把条件判断塞进模板：用 `{% if %}` 制造异常/不异常，或让渲染成功本身携带信息。",
    )


@make
def L04() -> Level:
    return Level(
        level_id="3",
        engine=ENGINE,
        title="L4 - 禁止方括号",
        summary="过滤 [ 与 ]",
        description="出现 `[` 或 `]` 即返回 `WAF`。下标取值全部失效，改用过滤器取元素。",
        waf=WafSpec(chars=("[", "]"), note="包含 `[` 或 `]` 即返回 `WAF`。"),
        hint="Jinja 有 `|first` / `|last` / `|list` 等过滤器，可以完全替代下标。",
    )


@make
def L05() -> Level:
    return Level(
        level_id="4",
        engine=ENGINE,
        title="L5 - 禁止引号",
        summary="过滤 ' 与 \"",
        description=(
            "出现单引号或双引号即返回 `WAF`。字符串字面量没法写了，"
            "但 `request.args` / `request.values` 里的内容本来就是字符串。"
        ),
        waf=WafSpec(chars=("'", '"'), note="包含 `'` 或 `\"` 即返回 `WAF`。"),
        hint="用 `request.args.x` 从 URL 取字符串；也可用 `|string` 把数字变成字符串。",
    )


@make
def L06() -> Level:
    return Level(
        level_id="5",
        engine=ENGINE,
        title="L6 - 禁止下划线",
        summary="过滤 _",
        description=(
            "出现 `_` 即返回 `WAF`。所有 `__class__` / `__globals__` 这类魔术属性"
            "都不能直接写。"
        ),
        waf=WafSpec(chars=("_",), note="包含 `_` 即返回 `WAF`。"),
        hint="`|attr` 过滤器接受**字符串**形式的属性名，而字符串可以从请求参数里取。",
    )


@make
def L07() -> Level:
    return Level(
        level_id="6",
        engine=ENGINE,
        title="L7 - 禁止点号",
        summary="过滤 .",
        description="出现 `.` 即返回 `WAF`。属性访问的语法糖被封，改用 `|attr` 或下标。",
        waf=WafSpec(chars=(".",), note="包含 `.` 即返回 `WAF`。"),
        hint="`|attr` 不经过点号；`[]` 在本关没有被拦。",
    )


@make
def L08() -> Level:
    return Level(
        level_id="7",
        engine=ENGINE,
        title="L8 - 关键字子串黑名单",
        summary="12 个高危子串（大小写敏感）",
        description=(
            "载荷中不能出现以下任一**子串**（大小写敏感）：`class`, `arg`, `form`, "
            "`value`, `data`, `request`, `init`, `global`, `open`, `mro`, `base`, `attr`。"
            "注意 `getattr` 含 `attr`、`request` 自身就是入口，都被封了。"
        ),
        waf=WafSpec(
            substrings=(
                "class", "arg", "form", "value", "data", "request",
                "init", "global", "open", "mro", "base", "attr",
            ),
            ignore_case=False,
            note="命中任一子串即返回 `WAF`（大小写敏感）。",
        ),
        hint="把关键字拼出来：Jinja 里字符串拼接、`|join`、`~` 都能拼；"
        "也可以从 `request.args` 直接读——但 `request` 也被拦，想想其它取值通道。",
    )


@make
def L09() -> Level:
    return Level(
        level_id="8",
        engine=ENGINE,
        title="L9 - 禁止数字",
        summary="过滤 0-9",
        description=(
            "出现任何数字即返回 `WAF`。`chr(95)` 这种写法直接作废，需要用"
            "布尔/长度运算拼出所需整数，或用上下文里已有的整数。"
        ),
        waf=WafSpec(chars=tuple("0123456789"), note="包含 `0-9` 任一数字即返回 `WAF`。"),
        hint="`true|int`、`(a|length)`、`self|length` 都能产生整数；"
        "Jinja 的数字也可以用 `~` 拼接后再交给过滤器。",
    )


@make
def L10() -> Level:
    return Level(
        level_id="9",
        engine=ENGINE,
        title="L10 - 前缀置空 config / self",
        summary="载荷前被拼接固定前缀",
        description=(
            "服务端会在你的载荷**前面**拼上一段固定代码："
            "`{% set config=None%}{% set self=None%}`。"
            "于是 `config` 与 `self` 这两个常用入口被置空了——但它们的**类**还在。"
        ),
        waf=WafSpec(
            prefix="{% set config=None%}{% set self=None%}",
            note="载荷前自动拼接 `{% set config=None%}{% set self=None%}`。",
        ),
        hint="变量被置空不代表类型消失：`config` 拿不到了，但其它未置空的全局还在。",
    )


@make
def L11() -> Level:
    return Level(
        level_id="10",
        engine=ENGINE,
        title="L11 - 组合过滤",
        summary="引号 / 加号 / 点号 / 方括号 / request",
        description=(
            "同时禁止 `'`、`\"`、`+`、`.`、`[`、`]` 以及子串 `request`。"
            "字符串拼接、下标取值、属性访问、请求取参全部被封。"
        ),
        waf=WafSpec(
            chars=("'", '"', "+", ".", "[", "]"),
            substrings=("request",),
            ignore_case=False,
            note="禁止 `' \" + . [ ]` 与子串 `request`。",
        ),
        hint="`|join` 可以替代 `+` 拼字符串；`|attr` 替代点号；"
        "取值通道仍然存在，只是不能用 `request` 这个名字。",
    )


@make
def L12() -> Level:
    return Level(
        level_id="11",
        engine=ENGINE,
        title="L12 - 强字符集",
        summary="下划线 / 点号 / 数字 / 反斜杠 / 引号 / 方括号",
        description=(
            "在上一关基础上再禁 `_`、数字 `0-9` 与反斜杠。"
            "魔术属性、数字常量、字符串字面量三条路同时被堵死，属于 CTF 硬关。"
        ),
        waf=WafSpec(
            chars=("_", ".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "\\", "'", '"', "[", "]"),
            note="禁止 `_ . 0-9 \\ ' \" [ ]`。",
        ),
        hint="剩下的字符里仍然有 `~`、`|`、`%`、`(`、`)`、字母；"
        "重点想「怎么在没有下划线的情况下拼出 `__class__`」。",
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
            "`arg`、`config`、`app`、`self`。注意 `init` 会命中 `print` 里的子串——"
            "连调试输出都要换写法。"
        ),
        waf=WafSpec(
            chars=("_", ".", "\\", "'", '"', "+", "[", "]"),
            substrings=("request", "class", "init", "arg", "config", "app", "self"),
            ignore_case=False,
            note="禁止 `_ . \\ ' \" + [ ]` 与子串 `request/class/init/arg/config/app/self`。",
        ),
        hint="这是刻意设计的硬关：先看上帝模式里的 `template_after_waf` 确认过滤行为，"
        "再逐字符压缩载荷。可行方向之一是把关键字符串拆到多个上下文通道里。",
    )


ALL: list[Level] = [L01, L02, L03, L04, L05, L06, L07, L08, L09, L10, L11, L12, L13]
