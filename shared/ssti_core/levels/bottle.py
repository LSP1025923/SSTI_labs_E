"""Bottle SimpleTemplate 13 关 WAF 链。

Bottle 的 ``SimpleTemplate`` 与 Mako 同属「编译成 Python」的引擎：
``{{ }}`` 是输出表达式（自动 HTML 转义，``!{{ }}`` 原始输出），
``% 行`` 与 ``<% %>%>`` 是真正的 Python 代码。模板在 ``exec(code, env)``
里执行，env 同时是模板的 globals —— 所以：

* **Python 内置函数全部直接可用**（``open`` / ``getattr`` / ``min`` / ``chr``…），
  这是与 Jinja 关最大的差别；
* 代码块里拿得到模板机制的输出原语 ``_stdout``（list）与
  ``_printlist``（= ``_stdout.extend``），``{{ }}`` 被拦之后它们就是回显通道；
* ``include`` / ``rebase`` 把模板名当路径用，天然带一层 LFI 交界（见
  ``docs/KNOWLEDGE.md``）。

渲染器（``ssti_core.engines.bottle``）已注入 Flask 侧上下文
``request`` / ``session`` / ``config`` —— 注意与 Jinja/Mako 关不同，
``lipsum`` / ``cycler`` 这些 Jinja 默认全局在 Bottle 里**不存在**，
gadget 链要从内置函数与 ``request`` 出发。

难度曲线与 02/03/04 同构：从「无过滤」开始，每关只加一条规则。
"""

from __future__ import annotations

from ssti_core.level import Level, make
from ssti_core.waf import WafSpec

ENGINE = "bottle"
ENGINE_TITLE = "Bottle"


@make
def L01() -> Level:
    return Level(
        level_id="0",
        engine=ENGINE,
        title="L1 - 无过滤",
        summary="裸 SimpleTemplate(...).render()",
        description=(
            "用户输入进入 `bottle.SimpleTemplate(...).render()`。先确认语法："
            "`{{7*7}}` 输出表达式（自动 HTML 转义）、`!{{7*7}}` 原始输出、"
            "`% 行代码`、`<% 代码块 %>`（`%>` 后要换行）。"
            "上下文里有 Flask 侧的 `request` / `session` / `config`，"
            "模板机制名 `_stdout` / `_printlist` / `_escape` 也直接可用。"
            "最直接的读文件是 `{{open('/flag').read()}}`。"
        ),
        hint="Bottle 是编译成 Python 的引擎：`{{ }}` 里可以调用任何内置函数，"
        "不需要绕属性就能 `open('/flag')`。",
    )


@make
def L02() -> Level:
    return Level(
        level_id="1",
        engine=ENGINE,
        title="L2 - 拦截 {{",
        summary="{{ 被整段替换为 WAF",
        description=(
            "只要出现 `{{` 整段就被替换成 `WAF`。但 `% 行代码` 与 `<% %>` 代码块"
            "都没有被拦，而代码块里拿得到模板的输出原语："
            "`_stdout` 是输出列表、`_printlist` 就是 `_stdout.extend`。"
            "用它们写输出，完全不需要 `{{ }}`。"
        ),
        waf=WafSpec(substrings=("{{",), ignore_case=False, note="出现 `{{` 即整段替换为 `WAF`。"),
        hint="`<% _printlist((str(7*7),),) %>` 或 `% _stdout.append(str(7*7))` "
        "都能把内容写进响应——注意 `_printlist` 不会替你转 str。",
    )


@make
def L03() -> Level:
    return Level(
        level_id="2",
        engine=ENGINE,
        title="L3 - 盲编译/渲染",
        summary="只回显 correct / wrong",
        description=(
            "服务端只反馈「编译并渲染成功」（`correct`）或「失败」（`wrong`）。"
            "Bottle 模板编译成 Python，语法错误同样落入 `wrong`，"
            "天然是一个布尔盲注信道。"
        ),
        echo_mode="bool",
        hint="把「读到的数据」转换成「模板是否抛异常」，再从 correct/wrong 里还原内容。",
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
        hint="读全文不需要下标；`_stdout` / `_printlist` 传的是元组不是列表字面量。",
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
        hint="`chr()` 一个字节一个字节地把 `/flag` 拼出来。",
    )


@make
def L06() -> Level:
    return Level(
        level_id="5",
        engine=ENGINE,
        title="L6 - 禁止下划线",
        summary="过滤 _",
        description=(
            "出现 `_` 即返回 `WAF`。`__import__` / `_stdout` 这类带下划线的名字"
            "全部写不了；`open` / `getattr` / `min` 这些不带下划线的内置函数还在。"
        ),
        waf=WafSpec(chars=("_",), note="包含 `_` 即返回 `WAF`。"),
        hint="上一关的 `chr()` 拼路径在不用下划线标识符时依然成立。",
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
        hint="`getattr(obj, 名字)` 可以完全替代 `obj.名字`；方法名本身用 `chr` 拼。",
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
            "`open` 与 `getattr` 都写不出来——但 `__import__` 不在黑名单里，"
            "可以借它导入模块。"
        ),
        waf=WafSpec(
            substrings=(
                "class", "arg", "form", "value", "data", "request",
                "init", "global", "open", "mro", "base", "attr",
            ),
            ignore_case=False,
            note="命中任一子串即返回 `WAF`（大小写敏感）。",
        ),
        hint="`__import__('subprocess')` 里没有被禁子串，`getoutput` 同样干净；"
        "引号与数字在本关都还可用。",
    )


@make
def L09() -> Level:
    return Level(
        level_id="8",
        engine=ENGINE,
        title="L9 - 禁止数字",
        summary="过滤 0-9",
        description=(
            "出现任何数字即返回 `WAF`。`chr(47)` 这类写法直接作废——"
            "但 `request` 没被禁，命令可以从请求里带入；"
            "`True` / `False` 在 Python 里就是 1 和 0。"
        ),
        waf=WafSpec(chars=tuple("0123456789"), note="包含 `0-9` 任一数字即返回 `WAF`。"),
        hint="`request.args.get('c')` 把字符串带进来，模板里一个数字都不出现；"
        "或者用 `True` 参与算术凑出整数。",
    )


@make
def L10() -> Level:
    return Level(
        level_id="9",
        engine=ENGINE,
        title="L10 - 前缀置空 config",
        summary="载荷前被拼接 <% config = None %>",
        description=(
            "服务端在载荷前拼接 `<% config = None %>`，把 Flask 侧最常用的"
            "`config` 入口置空。被置空的是变量，不是内置函数——"
            "`open` / `__import__` 这些不受影响。"
        ),
        waf=WafSpec(
            prefix="<% config = None %>\n",
            note="载荷前自动拼接 `<% config = None %>`。",
        ),
        hint="`config` 没了就换入口：`open` 直读，或 `__import__` 导入模块。",
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
        hint="`dict(关键字=值)` 的键名就是现成的字符串；"
        "`str(bytes((…)), 编码)` 能在无引号、无加号的条件下造出任意字符串。",
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
            "魔术属性、数字常量、字符串字面量三条路同时被堵，属于 CTF 硬关——"
            "但注意 `+` 与 `True` 都还在。"
        ),
        waf=WafSpec(
            chars=("_", ".", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "\\", "'", '"', "[", "]"),
            note="禁止 `_ . 0-9 \\ ' \" [ ]`。",
        ),
        hint="`True` 参与乘法能凑出任意整数，`chr()` 随之复活；"
        "文件名 `flag` 可以用 `dict(flag=…)` 的键名白嫖。",
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
            "注意子串判定是大小写敏感的整体匹配；写 payload 前先逐个子串过一遍。"
        ),
        waf=WafSpec(
            chars=("_", ".", "\\", "'", '"', "+", "[", "]"),
            substrings=("request", "class", "init", "arg", "config", "app", "self"),
            ignore_case=False,
            note="禁止 `_ . \\ ' \" + [ ]` 与子串 `request/class/init/arg/config/app/self`。",
        ),
        hint="`<% %>` 代码块里的 `from x import y` 语句不在黑名单里；"
        "数字仍然可用；`str(bytes((…)), 编码)` 造串不需要任何被禁字符。",
    )


ALL: list[Level] = [L01, L02, L03, L04, L05, L06, L07, L08, L09, L10, L11, L12, L13]
