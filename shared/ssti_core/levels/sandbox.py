"""Jinja2 沙箱逃逸 4 关（``SandboxedEnvironment`` / ``ImmutableSandboxedEnvironment``）。

先说结论（``python:3.11-slim`` + pip 装 3.1.4 / 3.1.5 / 3.1.6，逐条 payload 实测）：

* 网上流传的「经典 ``|attr`` 链」::

      {{ ()|attr('__class__')|attr('__base__')|attr('__subclasses__')() }}

  在 Jinja2 **2.11.3 之后就已经失效**：``SandboxedEnvironment.getattr`` 会调用
  ``is_safe_attribute``，任何以 ``_`` 开头的属性名都返回 ``UnsafeUndefined``。
  点号、``|attr``、``|map(attribute=)``、``'{0.__class__}'.format(x)`` 四条路全部被检查。
  本仓库实测：3.1.4 / 3.1.5 / 3.1.6 **三个版本都拦得住**这条链。
* 仍然有效的原语是 **CVE-2025-27516**：``|attr('format')`` 取到的 ``str.format``
  没有经过沙箱包装，而格式字段名 ``{0.__globals__[SITEDATA]}`` 是 CPython 在 C 层
  解析的，**不经过 Jinja 的检查**，于是可以做只读的属性遍历/取值。
* **版本边界（本仓库实测，很反直觉，务必按这个来）**：

  ============  ==========================================================
  Jinja2 3.1.4   原语**不可用**：``SecurityError: access to attribute
                 '__globals__' of 'function' object is unsafe.``
  Jinja2 3.1.5   原语**可用** —— **唯一可用版本**
  Jinja2 3.1.6   已修复：访问 ``format`` / ``format_map`` 返回 SandboxedFormatter
  ============  ==========================================================

  所以 ``labs/05-jinja-sandbox/requirements.txt`` 写的是**精确锁** ``Jinja2==3.1.5``。
  写成 ``>=3.1.4,<3.1.6`` 是错的：它在语义上把 3.1.4 也算作可用，而 3.1.4 上这四关
  同样无解（只是失败原因不同）。宿主 ``app.py`` 会在启动时做版本自检并大声告警，
  ``GET /api/sandbox/runtime`` 可机器可读地查询。

要说清楚的代价：这条原语是**只读**的（只能把属性路径打印成字符串，不能调用），
拿不到 RCE，因此本靶场把 flag 同时放进服务端内存，关卡目标是把它 dump 出来。
宿主 ``app.py`` 必须提供两样东西（见 ``labs/05-jinja-sandbox/app.py``）：

1. 模板全局 ``helper`` —— 一个注册进沙箱环境的业务回调（沙箱题的起点对象）；
2. 应用模块全局 ``SITEDATA``（``SITEDATA['flag']`` 里是 flag）——
   ``helper.__globals__`` 就是应用模块的全局字典。
"""

from __future__ import annotations

from ssti_core.level import Level, make
from ssti_core.waf import WafSpec

#: 展示分组仍是 Jinja2：沙箱只是同一引擎的另一种运行模式
ENGINE = "jinja"
ENGINE_TITLE = "Jinja2 沙箱"

#: 注册键。**不能**复用 ``"jinja"``（那是 13 关 WAF 链的键），否则会覆盖 ``jinja.ALL``；
#: 关卡本身仍然声明 ``engine="jinja"``，所以前端只会看到一个「Jinja2 沙箱」引擎。
REGISTRY_KEY = "jinja-sandbox"

SANDBOX_DEFAULT = "default"
SANDBOX_IMMUTABLE = "immutable"


@make
def L01() -> Level:
    return Level(
        level_id="0",
        engine=ENGINE,
        renderer="jinja_sandbox",
        options={"sandbox": SANDBOX_DEFAULT},
        title="L1 - 默认沙箱",
        summary="SandboxedEnvironment：以 _ 开头的属性名一律拿不到",
        description=(
            "模板在 `SandboxedEnvironment` 里渲染。沙箱只做一件事，却足以封死教科书上的整条链："
            "**属性名以 `_` 开头就拒绝**（`is_safe_attribute`）。"
            "点号 `x.__class__`、`x|attr('__class__')`、`x|map(attribute='__class__')`、"
            "`'{0.__class__}'.format(x)` 四条路都被检查，拿到的是 `UnsafeUndefined`"
            "（单独渲染成空串，继续取属性才抛 `SecurityError` / `UndefinedError`）。\n"
            "因此 writeup 里的「经典 `|attr` 链」在本关**可以亲手复现它失败**——"
            "那条链在 Jinja2 2.11.3 之后就不再成立。\n"
            "本关的 flag 同时放在服务端内存里：模板全局注册了业务回调 `helper`，"
            "它的 `__globals__` 就是应用模块的全局字典（里面有 `SITEDATA['flag']`）。\n"
            "⚠️ 本关（以及 L2/L3/L4）的逃逸原语是 **CVE-2025-27516**：本靶场因此把 Jinja2 "
            "固定为 `>=3.1.4,<3.1.6`（实际装到 3.1.5）；**3.1.6 是修复版本**，"
            "升级之后这四关会全部无解（README 有完整说明）。"
        ),
        hint=(
            "别在 `__class__` 上耗时间。换个入口：`|attr` 能取到 `str.format`，"
            "而格式字段名（`{0.xxx}` / `{0[ok]}`）是 CPython 在 C 层解析的，"
            "不经过 Jinja 的沙箱（CVE-2025-27516）。"
        ),
    )


@make
def L02() -> Level:
    return Level(
        level_id="1",
        engine=ENGINE,
        renderer="jinja_sandbox",
        options={"sandbox": SANDBOX_IMMUTABLE},
        title="L2 - 不可变沙箱",
        summary="ImmutableSandboxedEnvironment：只多挡了「修改」",
        description=(
            "这一关换成 `ImmutableSandboxedEnvironment`。它继承 `SandboxedEnvironment`，"
            "**属性访问策略、可调用策略与 L1 完全一致**，只多了一条 "
            "`modifies_known_mutable`：禁止修改内置可变对象——list / set / dict / deque 的 "
            "`append` `clear` `pop` `remove` `update` `sort` `setdefault` … 全部 `SecurityError`。\n"
            "可验证的差别：`{{ [1,2,3].append(4) }}` 在 L1 正常执行（渲染成空串），"
            "在本关抛 `SecurityError: access to attribute 'append' of 'list' object is unsafe.`。\n"
            "结论：**沙箱类名不同 ≠ 安全性不同**。L1 的逃逸原语在本关一字不改照样成立"
            "（同为 CVE-2025-27516；靶场固定 Jinja2 3.1.5，3.1.6 起该原语被修复）。"
        ),
        hint="把 L1 的逃逸原语原样搬过来即可；差别只体现在「修改」上，属性遍历没有任何变化。",
    )


@make
def L03() -> Level:
    return Level(
        level_id="2",
        engine=ENGINE,
        renderer="jinja_sandbox",
        options={"sandbox": SANDBOX_DEFAULT},
        title="L3 - 关键字子串黑名单",
        summary="沙箱 + 过滤 format/globals/class/subclasses/mro/builtins/flag",
        description=(
            "沙箱仍是 `SandboxedEnvironment`（同 L1），额外加了一层 WAF："
            "载荷里出现 `format`、`globals`、`class`、`subclasses`、`mro`、`builtins`、`flag` "
            "任一**子串**（大小写敏感）即整段替换为 `WAF`。\n"
            "被拦的是**你写在模板里的字面量**，不是运行时的过滤器名/字段名："
            "关键字拆成几段再用 `~` 拼起来就能写出来。"
            "（注意 Jinja 里过滤器 `|` 的优先级**高于** `~`，拼出来的整串要加括号再 `|attr(...)`。）\n"
            "为什么不干脆拦 `attr`：在当前固定的 Jinja2 版本上，`|attr` 是拿 `str.format` 的"
            "**唯一入口**，拦掉它这一关就无解——这是实测结论，不是偷懒。\n"
            "本关与 L1 共用 CVE-2025-27516 原语（靶场固定 Jinja2 3.1.5；3.1.6 修复，之后四关无解）。"
        ),
        waf=WafSpec(
            substrings=("format", "globals", "class", "subclasses", "mro", "builtins", "flag"),
            ignore_case=False,
            note=(
                "命中任一子串（大小写敏感）即返回 `WAF`："
                "`format` `globals` `class` `subclasses` `mro` `builtins` `flag`。"
            ),
        ),
        hint=(
            "`|attr` 的参数本来就是字符串：`'for'~'mat'` 能拼出被拦的过滤器名；"
            "格式串里的 `globals` / `flag` 同理拆开。"
        ),
    )


@make
def L04() -> Level:
    return Level(
        level_id="3",
        engine=ENGINE,
        renderer="jinja_sandbox",
        options={"sandbox": SANDBOX_DEFAULT},
        title="L4 - 字符黑名单：下划线",
        summary="沙箱 + 过滤 _ ：下划线必须在运行时造出来",
        description=(
            "沙箱仍是 `SandboxedEnvironment`（同 L1），WAF 换成**字符**黑名单："
            "载荷里出现 `_` 即整段替换为 `WAF`。于是 `__globals__` / `__class__` 这类名字"
            "连「拆成字符串片段写」都不行——每个下划线都得在运行时构造。\n"
            "可用原语：`|format` 是 printf 风格，`'%c'|format(95)` 得到 `_`"
            "（95 是下划线的码点），再用 `~` 把它拼进格式字符串。\n"
            "本关同样依赖 CVE-2025-27516 原语（靶场固定 Jinja2 3.1.5；3.1.6 起修复，之后四关无解）。"
        ),
        waf=WafSpec(chars=("_",), note="包含 `_` 即返回 `WAF`。"),
        hint=(
            "`'%c'|format(95)` → `_`；把它当作积木拼出 `{0.__globals__[SITEDATA][flag]}`。"
            "整串格式字符串要用括号包住再 `|attr('format')`，否则过滤器只作用在最后一个 `~` 操作数上。"
        ),
    )


ALL: list[Level] = [L01, L02, L03, L04]
