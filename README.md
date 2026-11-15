# Eecho's SSTI Labs —— 多靶场 SSTI 训练平台

> 一个仓库，多个**互相独立**的 SSTI 靶场容器：每个靶场 = 一个容器 + 一个镜像 + 一个端口。
> 它们共享同一份公共库 `shared/ssti_core/`，但各自构建、各自运行、互不影响。

这个仓库**长出来的地方**是作者最早那版单题挑战
[`LSP1025923/SSTI_labs_E`](https://github.com/LSP1025923/SSTI_labs_E)
（Jinja2 + 关键词 WAF，赛博朋克渲染台）。那一题被原样保留为 **lab 01**，
其余靶场是在它之上按知识点铺开的：Jinja2 / Mako / Tornado 三条同构 WAF 链、
沙箱逃逸、盲注与侧信道、以及两个「不出网」内存马靶场。

知识点参照了 [`ProbiusOfficial/ssti-lab`](https://github.com/ProbiusOfficial/ssti-lab)，
并在其之上补了本仓库自己的重点：**不出网场景下的内存马**。

---

## 靶场索引

端口以 `python scripts/scaffold_lab.py --list` 为**唯一权威**（本表与它一致）。

| 靶场 | 端口 | 引擎 | 关卡数 | 不出网 | 一句话 |
|------|------|------|--------|--------|--------|
| [`01-jinja-waf-fenjing`](labs/01-jinja-waf-fenjing/README.md) | 8091 | Jinja2（裸 `Environment`） | 1 | 否 | 原版挑战：**不可枚举的关键词表**，考 `Fenjing crack-keywords` 与字符串构造 |
| [`02-jinja-chain`](labs/02-jinja-chain/README.md) | 8092 | Jinja2（Flask `render_template_string`） | 13 | 否 | Jinja2 WAF 链：13 关递增过滤，逐层绕过 |
| [`03-mako-chain`](labs/03-mako-chain/README.md) | 8093 | Mako | 13 | 否 | 与 Jinja 同构的 13 关，但 Mako 编译成 Python 模块 —— `${` 被拦还有 `<% %>` |
| [`04-tornado-chain`](labs/04-tornado-chain/README.md) | 8094 | Tornado | 13 | 否 | 同构链的 Tornado 版：`escape` / `datetime` / `handler` 桩 + `{% import %}` 直导模块 |
| [`05-jinja-sandbox`](labs/05-jinja-sandbox/README.md) | 8095 | Jinja2 `SandboxedEnvironment` | 4 | 否 | 沙箱逃逸：**精确锁 `Jinja2==3.1.5`**，用 CVE-2025-27516 的只读属性遍历突破沙箱，再扛关键字/字符黑名单 |
| [`06-blind-ssti`](labs/06-blind-ssti/README.md) | 8096 | Jinja2 | 4 | 否 | 无回显 SSTI：布尔盲注 → 时间盲注 → 写文件侧信道 → 不出网过渡（指向 07） |
| [`07-flask-memshell`](labs/07-flask-memshell/README.md) | 8097 | Jinja2 → Flask | 5（攻击链台阶） | **是** | 不出网：写文件侧信道 → 绕过 `setupmethod` 把 webshell 注进运行中的 Flask |
| [`08-freemarker-memshell`](labs/08-freemarker-memshell/README.md) | 8098 | FreeMarker / Thymeleaf → Tomcat | 4 | **是** | 不出网：Java 侧同构目标，`?new()` + `UNRESTRICTED` 类解析器 → Tomcat Filter 内存马 |
| [`09-bottle-chain`](labs/09-bottle-chain/README.md) | 8099 | Bottle `SimpleTemplate` | 13 | 否 | 第 4 条同构 13 关链：编译成 Python + Jinja 式花括号，`{{` 被拦后代码块里还有 `_stdout` 可用 |

说明：

- **lab 08 通过 compose profile 单独启用**（首次构建要拉 Maven 依赖，较慢）：
  `docker compose --profile java up -d`，或 `scripts/up-all.sh --with-java`。
- **lab 02 / 03 / 04 / 09 是同构的 13 关链**：同一套难度曲线在四个引擎上各走一遍，
  便于对照「同一条规则在不同语法面下怎么绕」。可解性矩阵（51/52）见
  [`docs/SOLVABILITY.md`](docs/SOLVABILITY.md)。
- lab 01 / 07 是**场景型靶场**：`/` 是业务页面，统一控制台挂在 `/console/`；
  其余靶场的 `/` 就是控制台。见 [`docs/API.md`](docs/API.md) §5。

---

## 知识点地图（这套靶场到底覆盖了什么）

| 知识点 | 在教什么 | 覆盖靶场 / 关卡 |
|--------|----------|-----------------|
| **注入识别** | `{{7*7}}` → `49` 确认模板被求值 | 02 id0、03 id0、04 id0、09 id0、01、07 step0 |
| **引擎指纹** | `${7*7}` → Mako；`<%= %>` → ERB；`${{ }}` → Handlebars 系；Jinja/Twig 用状态码 49 vs 7777777 区分 | 01–04 各自的 L1；见 [`docs/KNOWLEDGE.md`](docs/KNOWLEDGE.md) |
| **语法面绕过（定界符）** | `{{` 被拦 → `{% print(...) %}`（Jinja）、`_stdout`/`_printlist` 代码块（Bottle）、`<% %>` + `context.write`（Mako） | 02 id1、03 id1、09 id1、07 step1（04 id1 已改为拦 `open`，见 SOLVABILITY.md §2.1） |
| **黑名单绕过 · 字符串构造** | `~` / 相邻字面量隐式拼接 / `chr()` / `str(bytes((…)),编码)` / `dict(kw=…)` 键名白嫖，绕开 `__`、`flag`、`cat`、`popen` 等词 | 01 全关、02 id7–id11、03 id4–id12、04 id4–id12、09 id4–id12 |
| **黑名单绕过 · 字符集** | 禁引号 → `chr()`；禁下划线 → 不用魔术属性；禁点号 → `getattr` / `|attr` / `[]`；禁数字 → `True`/`len()` | 02 id3–id8、03 id3–id8、04 id3–id8、09 id3–id8 |
| **魔术属性访问** | `|attr('_'~'_'~'class'~'_'~'_')`、`foo['__globals__']`、`getattr(obj, name)` | 02 id5–id7、04 id6 |
| **对象图 → 危险模块** | `lipsum.__globals__`、`cycler.__init__.__globals__.__builtins__`、`sys.modules['os']`、`__import__` | 01、02 id0–id7、04 id7、09 id7 |
| **前缀污染 / 变量置空** | 载荷前被拼 `{% set config=None %}`、`% if False:` —— 换入口，而不是硬绕 | 02 id9、03 id9、04 id9 |
| **盲注（布尔信道）** | 只回 `correct` / `wrong`：把「读数据」变成「控制成功与否」 | 02 id2、03 id2、04 id2、09 id2、07 step2（连成败都不回） |
| **盲注（时间 / 副作用）** | `echo_mode="none"`：唯一信号是副作用 | 07 step2/3/4 |
| **无回显文件回显** | 命令输出写进 Web 可访问目录，再用 HTTP 取回 | 07 step3（`/echo/`，`cat</flag>/app/echo/x`） |
| **沙箱逃逸** | `SandboxedEnvironment` / `ImmutableSandboxedEnvironment` 的属性白名单怎么绕 | 05 |
| **不出网内存马** | 反弹 shell / DNSLog / 外连下载全部失效时，把能力挂到**已有的入站 HTTP 通道** | 07 step4（Flask 路由型 + Filter 型）、08（Tomcat Filter 型） |

更细的原理、payload 与「哪条规则为什么必被绕过」见
[`docs/KNOWLEDGE.md`](docs/KNOWLEDGE.md)；逐关速查见 [`docs/SOLUTIONS.md`](docs/SOLUTIONS.md)；
内存马专题见 [`docs/MEMSHELL.md`](docs/MEMSHELL.md)。

---

## 快速开始

### 0) 前置：先构建统一前端镜像

所有 Python 系靶场的 Dockerfile 都通过一个**具名构建阶段**取前端产物：

```dockerfile
ARG FRONTEND_IMAGE=ssti-frontend:local
FROM ${FRONTEND_IMAGE} AS frontend
...
COPY --from=frontend /app/build ./public
```

所以**必须先有 `ssti-frontend:local`**，否则单靶场 `docker build` 会去 Docker Hub
找同名镜像并报 `pull access denied`。原因与替代写法见 [`docs/DEPLOY.md`](docs/DEPLOY.md)。

```bash
scripts/build-frontend.sh           # Linux / macOS
scripts\build-frontend.ps1          # Windows PowerShell
# 等价的裸命令：
docker build -t ssti-frontend:local frontend
```

### 1) 一键起全部（推荐）

```bash
scripts/up-all.sh                   # 01–07、09（Windows: scripts\up-all.ps1）
scripts/up-all.sh --with-java       # 额外起 08（Java，首次构建慢）
```

脚本会先检查 `ssti-frontend:local` 是否存在，不存在就先构建，然后交给根
`docker compose`。

### 2) 或者直接用根 compose

```bash
docker compose up -d                # 01–07、09
docker compose up -d jinja-chain    # 只起某一个服务
docker compose --profile java up -d # 额外起 08
docker compose down
```

### 3) 或者只起单个靶场（自带 compose）

```bash
cd labs/02-jinja-chain
docker compose up --build           # → http://127.0.0.1:8092
```

### 访问地址

| 靶场 | 地址 |
|------|------|
| 01 | <http://127.0.0.1:8091> |
| 02 | <http://127.0.0.1:8092> |
| 03 | <http://127.0.0.1:8093> |
| 04 | <http://127.0.0.1:8094> |
| 05 | <http://127.0.0.1:8095> |
| 06 | <http://127.0.0.1:8096> |
| 07 | <http://127.0.0.1:8097> |
| 08 | <http://127.0.0.1:8098>（`--profile java`） |
| 09 | <http://127.0.0.1:8099> |

端口都可用环境变量覆盖：`JINJA_WAF_PORT` / `JINJA_CHAIN_PORT` / `MAKO_CHAIN_PORT` /
`TORNADO_CHAIN_PORT` / `JINJA_SANDBOX_PORT` / `BLIND_SSTI_PORT` /
`FLASK_MEMSHELL_PORT` / `FREEMARKER_MEMSHELL_PORT` / `BOTTLE_CHAIN_PORT`。

### 验证

```bash
python scripts/verify_labs.py        # 起临时容器把每个靶场 HTTP 打一遍
python scripts/verify_labs.py 02 07  # 只验指定编号
python tests/test_core.py            # 公共库自检（需要 PYTHONPATH=shared）
```

lab 07 的内存马链条另有一份**容器内**端到端验证（见 [`docs/MEMSHELL.md`](docs/MEMSHELL.md)）：

```bash
docker cp tests/verify_memshell.py ssti-07-flask-memshell:/tmp/v.py
docker exec ssti-07-flask-memshell python /tmp/v.py
```

---

## 架构

```text
user-repo/
├── shared/ssti_core/          # 公共库：所有靶场共用（COPY 进每个镜像的 /app/shared）
│   ├── level.py               #   Level：一套（引擎 + WAF + 回显方式），渲染编排的唯一入口
│   ├── waf.py                 #   WafSpec：声明式过滤规则（子串/字符/正则/前后缀）
│   ├── render.py              #   RenderResult + plain_text_output（统一转义出口）
│   ├── engines/               #   渲染器：jinja / jinja_plain / jinja_sandbox / mako / tornado / bottle
│   ├── levels/                #   关卡定义：jinja.py / mako.py / tornado.py / bottle.py（各 13 关）+ sandbox.py
│   ├── labapp.py              #   create_lab_app()：契约里的 /api/*、/docs/*、降级控制台
│   ├── labmeta.py             #   LabMeta + Theme：靶场元信息与配色
│   ├── flagutil.py            #   flag 解析/写入/命中判定
│   └── config.py              #   全部运行时配置（来自环境变量）
├── labs/<NN>-<name>/          # 一个靶场 = 一个目录
│   ├── app.py                 #   十几行的入口（控制台型）；场景型自己写业务路由
│   ├── README.md              #   题解，构建时 COPY 成容器内 /docs/README.md
│   ├── Dockerfile / docker-compose.yml / entrypoint.sh   # 由 scripts/scaffold_lab.py 生成
│   └── requirements.txt
├── frontend/                  # 统一前端（React + Vite）→ 构建成 ssti-frontend:local
├── scripts/                   # scaffold_lab.py / build-frontend.* / build-all.* / up-all.* / verify_labs.py
├── tests/                     # test_core.py / test_waf.py / verify_memshell.py
├── docs/                      # API.md / KNOWLEDGE.md / SOLUTIONS.md / MEMSHELL.md / DEPLOY.md
├── docker-compose.yml         # 根编排：一次起全部（08 走 java profile）
└── docker-compose.prod.yml    # 生产编排：只用预构建镜像，不含 build:
```

### 设计约定（本仓库的核心）

1. **一个靶场 = 一个容器 + 一个镜像 + 一个端口。** 不共享运行时状态，
   一个靶场崩了不影响其它靶场，也便于按知识点单独给选手发题。
2. **声明式 WAF。** 关卡只声明规则，不写 `if`：
   ```python
   waf=WafSpec(
       chars=("_", ".", "'", '"'),
       substrings=("request", "class"),
       regexes=(r"getattr\s*\(",),
       prefix="{% set config=None%}",
       note="命中任一即返回 WAF",
   )
   ```
   `WafSpec` 可 `to_json()`，所以前端能直接把「禁了什么」渲染给玩家 ——
   玩家不需要 fuzz 猜规则。
3. **`Level` 是一套（引擎 + WAF + 回显方式）。** 回显方式（`echo_mode`）是独立维度：
   `full` / `bool`（只回 correct/wrong）/ `none`（恒定回显）/ `file`（要求写文件）。
   盲注类题目就是靠它构造的。
4. **渲染器只抛异常，不 try/except。** 异常类型本身就是题目的反馈，
   由 `Level.render()` 统一收集成 `error` / `exception_type`。
5. **统一前端只构建一次**，各靶场镜像通过具名阶段 `FROM ... AS frontend` 复用它的
   `/app/build`。前端 `base: './'`，所以挂到 `/` 或 `/console/` 都能加载。
6. **`PYTHONPATH=/app/shared`。** 镜像里 `shared/` 被 COPY 到 `/app/shared`，
   应用用 `import ssti_core`。写错就会 `ModuleNotFoundError: ssti_core`
   （见 [`docs/DEPLOY.md`](docs/DEPLOY.md) 的排查章节）。
7. **flag 不进镜像层。** entrypoint 在容器启动时把 flag 写进 `/flag`，
   应用不读环境变量、也不在 API 里回显。优先级：

   ```text
   GZCTF_FLAG  >  DASFLAG  >  FLAG  >  STATIC_FLAG
   ```

   （`shared/ssti_core/flagutil.py` 的 `_ENV_ORDER`，与 GZCTF/DASCTF 的动态 flag 对齐。）

### 上帝模式（"上帝模式" 是出题人工具，不是玩家作弊）

`POST /api/render` 支持 `"mode":"god"`，额外返回：

| 字段 | 用途 |
|------|------|
| `template_after_waf` | 过滤/拼接之后的**真实模板** —— 确认规则到底怎么生效（前缀污染型关卡的关键） |
| `raw_output` | **未经盲关包装**的真实渲染结果（`echo_mode=none` 时这是唯一能看到结果的地方） |
| `error` / `exception_type` | 区分「被 WAF 拦」与「载荷语法错」 |
| `waf_blocked` | 本次是否命中拦截 |
| `source_class` | 触发渲染的关卡定义（便于定位代码） |

配套的 `GET /api/god/source?engine=&level=` 直接返回**那一关的工厂函数源码**
（`inspect.getsource`），前端「关卡源码」按钮就调它 —— 出题改规则、复盘确认规则，
比读文档快得多。

它服务的是**出题人与复盘**：写新关卡时确认 `WafSpec` 是否按预期命中、
选手卡住时判断到底是 WAF 还是 payload 语法问题。
练习模式（默认）看不到这些字段，所以它不构成对玩家的「白送」。
字段级语义（盲关到底看哪个字段等）以 [`docs/API.md`](docs/API.md) §6 为准。

---

## 怎么加一个新靶场

1. **（可选）加引擎。** 在 `shared/ssti_core/engines/` 加一个模块，暴露
   `render(template: str, level: Level) -> str`，然后在 `shared/ssti_core/engines/__init__.py` 的
   `_RENDERERS`（`REQUIRED_PACKAGES`）里登记。渲染器**直接抛异常**，
   不要自己 try/except。
2. **加关卡库。** 在 `shared/ssti_core/levels/` 加 `<engine>.py`，用 `@make` 装饰
   工厂函数定义关卡并导出 `ALL`，再在 `shared/ssti_core/levels/__init__.py` 的 `_BY_ENGINE` 里登记：

   ```python
   @make
   def L01() -> Level:
       return Level(level_id="0", engine="myengine", title="L1 - 无过滤", ...)
   ```
3. **建靶场目录。** 在 `scripts/scaffold_lab.py` 的 `LABS` 表里加一条
   （**端口分配的唯一定义处**），然后：

   ```bash
   python scripts/scaffold_lab.py --list          # 确认端口没冲突
   python scripts/scaffold_lab.py 09-my-lab       # 生成 Dockerfile / compose / entrypoint
   ```

4. **写 `app.py`。** 控制台型靶场只要十几行：

   ```python
   from ssti_core import LabMeta, create_lab_app
   from ssti_core.labmeta import THEMES
   from ssti_core.levels import levels_for
   import ssti_core.labapp as labapp

   app = create_lab_app(LabMeta(id="my-lab", title="...", engine="myengine"), levels_for("myengine"))
   if __name__ == "__main__":
       labapp.run(app)
   ```

   场景型（要模拟真实业务）改成自己持有 Flask 应用，然后
   `register_lab_api(app, META, LEVELS, docs_folder="docs")` +
   `mount_console(app, "public", "/console")`（照抄 `labs/07-flask-memshell/app.py`）。
5. **写 `README.md`。** 它就是容器内的 `/docs/README.md`（`doc_url` 指向它）。
6. **登记验证。** 在 `scripts/verify_labs.py` 的 `LABS` 里加探针，跑一遍。
7. 用 `docker compose up -d <service>` 起，或在根 compose 里加 service。

---

## 部署到 CTF 平台

平台会为每个实例注入动态 flag，本仓库按
`GZCTF_FLAG > DASFLAG > FLAG > STATIC_FLAG` 的顺序解析。

```bash
# 构建机上：产出镜像（01–07、09；--with-java 额外构建 08）
scripts/build-all.sh --with-java
# 然后 push 到你的 registry

# 部署机上：只用预构建镜像，不需要 node/maven 工具链
export GZCTF_FLAG='flag{...}'          # 或让平台注入
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml --profile java up -d   # 含 08
```

注意：

- **不要在 `.env` 里设 `STATIC_FLAG`。** 它只是最后兜底；设了不会覆盖动态 flag
  （优先级在它之上），但容易让人误以为「平台没注入成功」。
- `docker-compose.prod.yml` **没有 `build:`**，镜像名可用 `IMAGE_PREFIX` / `IMAGE_TAG`
  指向你的 registry。
- 不出网靶场（07/08）需要 `cap_add: [NET_ADMIN]`，两个 compose 文件都已带上。
  平台若禁用该 capability，容器仍能起来，但**出网切不断**，entrypoint 会打印
  `[!]` 告警 —— 请以容器日志为准。
- 重置 flag：`POST /api/admin/reset`，请求头 `X-Reset-Token: <RESET_TOKEN>`；
  未配置 `RESET_TOKEN` 时该接口返回 403（默认就是拒绝）。
- 更完整的部署说明（含故障排查）见 [`docs/DEPLOY.md`](docs/DEPLOY.md)。

---

## 已知问题与边界

### 已修复（曾记录在此，留痕以免重复排查）

| # | 位置 | 问题 | 现状 |
|---|------|------|------|
| 1 | `labs/08-freemarker-memshell/docker-compose.yml` | 单靶场 compose 默认端口曾是旧的 `8088`（`MEM_LAB_PORT`），与根 compose 的 **8098** 不一致 | ✅ 已统一为 `${FREEMARKER_MEMSHELL_PORT:-8098}`，镜像名也改为 `ssti-freemarker-memshell:local` |
| 2 | `labs/02-jinja-chain/README.md` | README 声称大量 ✅ payload 由 `verify_labs.py` 断言，但该脚本只覆盖 6 条 | ✅ `verify_labs.py` 对 02 已扩到 **23 条探针**，覆盖 id 0–8、10 的成功与拦截 |
| 3 | `labs/05-jinja-sandbox/`、`labs/06-blind-ssti/` | 只有脚手架没有 `app.py` | ✅ 两个靶场均已实现并验证（4 关 + 4 关） |
| 4 | `shared/ssti_core/engines/__init__.py` | `bottle` 渲染器已登记但没有任何关卡使用 | ✅ 新增 **lab 09-bottle-chain**：13 关同构 WAF 链，`bottle` 引擎正式启用（端口 8099） |
| 5 | 02/03/04 链式靶场有 9 关没有已证明的解 | 上一轮审计记为「未找到解」 | ✅ 本轮审计 **8 关找到真实解**（`min(dict(kw))` 取键名 + `str(bytes(…),'utf8')` 造串两条通用通道；02 id 11 用 `request.args` 传参），**04 id 1 属设计缺陷已直接修复**（拦 `{{` → 拦 `open`）。当前矩阵 **51/52**，仅 02 id 12 保留为作者挑战关，见 [`docs/SOLVABILITY.md`](docs/SOLVABILITY.md) |

### 仍然存在

| # | 位置 | 问题 |
|---|------|------|
| 6 | 出网切断的 DNS 部分**平台相关** | 在 Docker Desktop(WSL2) 上，Docker 内嵌解析器（`127.0.0.11`）的 DNS **不经过容器 netfilter**（实测 iptables 规则计数为 0，解析照常成功）。该平台上「不出网」只等于「TCP 出不去」；原生 Linux 上两条 DNS 规则才会命中，请在目标平台自行复验。见 [`docs/MEMSHELL.md`](docs/MEMSHELL.md) 2.1.1 |
| 7 | `labs/08-freemarker-memshell` 的 Thymeleaf 入口 | **不是 RCE**（Thymeleaf 3.0.15 与 3.0.11 均实测模板名不求值）。作为刻意保留的**对照案例**，题面与 README 都已如实标注；想让它真能打通，需要让某个模板把用户输入拼进 Thymeleaf **表达式源码**（而非模板名） |
| 8 | `02-jinja-chain` id 12（L13 扩展关键字） | 全仓库唯一保留的**无已知解**关卡：`attr` 在子串表内 ⇒ Jinja 全部属性访问原语写不出来，加上点号/方括号被禁，已知 gadget 链全部依赖至少一次属性访问。题面已如实标注；教学场次需要人人可过时按 [`docs/SOLVABILITY.md`](docs/SOLVABILITY.md) §2.5 放宽一条约束即可 |

> 可解性的**实测矩阵**是这套仓库里最该看的一张表：
> [`docs/SOLVABILITY.md`](docs/SOLVABILITY.md)。它由 `tests/audit_solvability.py`
> 逐关实打生成 —— 出题前请看它，别把「可能有解」当成「有解」。

---

## 学习资源

- [OWASP: Server-Side Template Injection](https://owasp.org/www-community/attacks/Server-Side_Template_Injection)
- [PortSwigger: SSTI](https://portswigger.net/web-security/server-side-template-injection)
- [HackTricks: SSTI (Jinja2)](https://book.hacktricks.xyz/pentesting-web/ssti-server-side-template-injection)
- [Jinja2 官方文档](https://jinja.palletsprojects.com/)
- [Mako 官方文档](https://docs.makotemplates.org/)
- [Tornado 官方文档 · template](https://www.tornadoweb.org/en/stable/template.html)
- [Fenjing](https://github.com/Marven11/Fenjing)（本仓库 lab 01 的推荐工具）
- [ProbiusOfficial/ssti-lab](https://github.com/ProbiusOfficial/ssti-lab)（知识点参照）
- [CTF Wiki](https://ctf-wiki.org/) · [PayloadsAllTheThings · SSTI](https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/Server%20Side%20Template%20Injection)

---

## 📝 许可证

This project is licensed under the MIT [LICENSE](LICENSE)

## 👨‍💻 作者

**Eecho**

- 博客: [www.eecho.top](https://www.eecho.top)
- GitHub: [@LSP1025923](https://github.com/LSP1025923)
- 原版单题挑战: [SSTI_labs_E](https://github.com/LSP1025923/SSTI_labs_E)

## ⚠️ 免责声明

**重要提醒**:

- 这是一个教育目的的 CTF 靶场集合
- 仅用于学习和研究 SSTI 漏洞
- 请勿用于恶意攻击或非法用途
- 在授权环境中进行测试
- 「不出网 / 内存马」靶场的高危 payload 仅用于隔离的实验容器

---

**Happy Hacking! 🎉**
