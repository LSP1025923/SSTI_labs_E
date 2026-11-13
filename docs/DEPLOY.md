# 部署指南（Deployment）

> 面向「把这一套靶场跑起来」的人：本地、单靶场、以及 CTF 平台批量部署。
> 契约细节见 [`API.md`](API.md)，架构见仓库根 [`README.md`](../README.md#架构)。

---

## 1. 前置：必须先有统一前端镜像

**所有 Python 系靶场（01–07）在构建时都依赖一个已存在的本地镜像 `ssti-frontend:local`。**

### 1.1 为什么

每个靶场的 Dockerfile 都是这样取前端产物的：

```dockerfile
ARG FRONTEND_IMAGE=ssti-frontend:local

FROM ${FRONTEND_IMAGE} AS frontend        # ← 把前端镜像变成一个「具名阶段」
FROM python:3.11-slim                     # ← 真正的应用镜像
...
COPY --from=frontend /app/build ./public  # ← 靠阶段名引用，不是靠变量
```

**为什么不能直接写 `COPY --from=${FRONTEND_IMAGE}`？**
Docker 内置的 dockerfile 前端**不支持在 `COPY --from=` 里做变量展开**，
会直接把 `${FRONTEND_IMAGE}` 当成镜像名去解析。
`# syntax=docker/dockerfile:1` 确实支持变量，但那要求从 Docker Hub 拉一个
buildkit 前端镜像 —— 在离线/受限网络环境下会直接失败。

官方给出的替代写法就是本仓库用的这种：**先用全局 `ARG` 把镜像名变成一个
有名字的阶段，再 `COPY --from=<阶段名>`**。

> 注意 `ARG FRONTEND_IMAGE` 出现在**第一个 `FROM` 之前**，是「全局 ARG」；
> `FROM ${FRONTEND_IMAGE} AS frontend` 能取到它的默认值或 `--build-arg` 覆盖值。

### 1.2 构建它

```bash
scripts/build-frontend.sh                    # Linux / macOS
scripts\build-frontend.ps1                   # Windows PowerShell
# 等价的裸命令（从仓库根目录）：
docker build -t ssti-frontend:local frontend
```

脚本还会 `docker run --rm --entrypoint ls ssti-frontend:local -la /app/build`
校验产物 —— 镜像里**必须直接包含 `/app/build/index.html`**。
（最终阶段基于 `alpine`，只放静态产物，不带 nginx / 不带运行时。）

`frontend/Dockerfile` 是多阶段的：`node:20-alpine` 里 `npm ci && npm run build`，
再把 `/app/build` 拷进 `alpine:3.20`。不指定命令时它的 `CMD` 是
`ls -la /app/build`，**它不是一个可以访问的服务**，只是产物载体。

### 1.3 不想用本地镜像？

用 `--build-arg` / compose 的 `args` 指向你的 registry：

```bash
docker build -f labs/02-jinja-chain/Dockerfile \
  --build-arg FRONTEND_IMAGE=registry.example.com/you/ssti-frontend:1.0 \
  -t ssti-jinja-chain:local .
```

或设 `FRONTEND_IMAGE` 环境变量（根 compose 与各单靶场 compose 都已参数化）。

---

## 2. 三种启动方式

### 2.1 一键脚本（推荐）

```bash
scripts/up-all.sh                 # 先确认前端镜像，再 docker compose up -d（01–07）
scripts/up-all.sh --with-java     # 额外起 08（--profile java）
scripts/up-all.sh --build         # 顺带重新构建镜像

# Windows
scripts\up-all.ps1
scripts\up-all.ps1 -WithJava
scripts\up-all.ps1 -Rebuild
```

脚本逻辑：检查 `ssti-frontend:local` 是否存在 → 不存在就先跑 `build-frontend` →
`docker compose [-p java] up -d [--build]` → 打印 `docker compose ps` 与端口速查。

### 2.2 根 compose（一次起全部）

```bash
docker compose up -d                       # 01–07
docker compose up -d jinja-chain           # 只起某个 service
docker compose --profile java up -d        # 额外起 08（首次构建要拉 Maven 依赖，慢）
docker compose logs -f mako-chain
docker compose down
```

根 `docker-compose.yml` 里的服务名（**不带编号前缀**）：
`jinja-waf-fenjing` / `jinja-chain` / `mako-chain` / `tornado-chain` /
`jinja-sandbox` / `blind-ssti` / `flask-memshell` / `freemarker-memshell`。
另有一个 `frontend-build` 服务（`profiles: ["build"]`），
只构建不常驻：`docker compose build frontend-build` 等价于 `build-frontend` 脚本。

### 2.3 单靶场自带 compose

每个 `labs/<NN>-<名字>/` 下都有一份 `docker-compose.yml`：

```bash
cd labs/02-jinja-chain
docker compose up --build            # → http://127.0.0.1:8092
```

注意：**build context 是仓库根目录**（`context: ../..`），因为镜像需要
`shared/` 公共库与统一前端产物。所以**不能**把 `labs/<NN>/` 单独拷出来构建。

### 2.4 生产 / 比赛编排

`docker-compose.prod.yml`：**只有 `image:`，没有 `build:`**。部署机上不需要
node / maven 工具链，也不需要源码。

```bash
# 构建机上产出并推送
scripts/build-all.sh --with-java
# 然后 docker push 到你的 registry

# 部署机上
export GZCTF_FLAG='flag{...}'        # 或由平台注入
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml --profile java up -d     # 含 08
```

镜像名可用 `IMAGE_PREFIX` / `IMAGE_TAG` 覆盖：

```bash
IMAGE_PREFIX=registry.cn-hangzhou.aliyuncs.com/yourname/ IMAGE_TAG=1.0 \
  docker compose -f docker-compose.prod.yml up -d
```

---

## 3. 端口与资源

端口以 `python scripts/scaffold_lab.py --list` 与根 compose 为准。
`8081` 在本机已被无关服务占用，所以靶场端口从 **8091** 起。

| 靶场 | 宿主端口 | 环境变量覆盖 | 容器内端口 | 服务名（根 compose） | 镜像 |
|------|----------|--------------|-----------|---------------------|------|
| 01-jinja-waf-fenjing | 8091 | `JINJA_WAF_PORT` | 5000 | `jinja-waf-fenjing` | `ssti-jinja-waf-fenjing:local` |
| 02-jinja-chain | 8092 | `JINJA_CHAIN_PORT` | 5000 | `jinja-chain` | `ssti-jinja-chain:local` |
| 03-mako-chain | 8093 | `MAKO_CHAIN_PORT` | 5000 | `mako-chain` | `ssti-mako-chain:local` |
| 04-tornado-chain | 8094 | `TORNADO_CHAIN_PORT` | 5000 | `tornado-chain` | `ssti-tornado-chain:local` |
| 05-jinja-sandbox | 8095 | `JINJA_SANDBOX_PORT` | 5000 | `jinja-sandbox` | `ssti-jinja-sandbox:local` |
| 06-blind-ssti | 8096 | `BLIND_SSTI_PORT` | 5000 | `blind-ssti` | `ssti-blind:local` |
| 07-flask-memshell | 8097 | `FLASK_MEMSHELL_PORT` | 5000 | `flask-memshell` | `ssti-flask-memshell:local` |
| 08-freemarker-memshell | 8098 | `FREEMARKER_MEMSHELL_PORT` | 8080 | `freemarker-memshell` | `ssti-freemarker-memshell:local` |

> ⚠️ 端口冲突请全部用环境变量改，**不要**直接改 `scaffold_lab.py` 里的表
> （那张表是唯一权威，改了要同时更新生成出来的 compose/Dockerfile 与本文）。

容量参考（本机实测的镜像体积）：

| 镜像 | 体积 |
|------|------|
| `ssti-frontend:local` | ~12.5 MB |
| `ssti-jinja-chain:local` | ~196 MB |
| `ssti-flask-memshell:local` | ~206 MB |
| Java 靶场（08） | 由 `eclipse-temurin:8-jre-alpine` + Spring Boot fat jar 决定，明显更大 |

Python 靶场运行期内存需求很小（Flask 自带服务器，单实例教学环境）；
08 的 `JAVA_OPTS` 默认 `-Xms64m -Xmx256m`，可按需覆盖。

---

## 4. Flag 注入（动态 flag）

### 4.1 优先级

所有靶场的 `entrypoint.sh` 都按同一顺序解析，**先命中先用**：

```text
GZCTF_FLAG  >  DASFLAG  >  FLAG  >  STATIC_FLAG
```

实现见 `shared/ssti_core/flagutil.py` 的 `_ENV_ORDER`；shell 侧见各
`entrypoint.sh`。解析结果写入容器内 `/flag`（`chmod 644`），**不进镜像层**：

```sh
DEFAULT_FLAG='flag{jinja_chain}'
FLAG_VALUE="${GZCTF_FLAG:-}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${DASFLAG:-}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${FLAG:-}"
[ -n "$FLAG_VALUE" ] || FLAG_VALUE="${STATIC_FLAG:-$DEFAULT_FLAG}"
printf '%s' "$FLAG_VALUE" > /flag
```

**为什么不是一行 `${A:-${B:-...}}`**：flag 自带花括号，嵌套默认值里的 `}` 会
提前闭合外层参数展开，结果往 `/flag` 里多写一个 `}`。所以必须逐级落变量兜底。
（entrypoint 注释里也写了这一条。）

### 4.2 各平台

| 平台 | 注入的环境变量 | 备注 |
|------|----------------|------|
| GZCTF | `GZCTF_FLAG` | 每队/每实例动态生成 |
| DASCTF | `DASFLAG` | 同上 |
| 其它 / 自建 | `FLAG` | 通用兜底 |
| 本地演示 | `STATIC_FLAG` | 或镜像内置的 `flag{...}` 默认值 |

```bash
# 本地模拟平台注入
docker run -d --name t -p 18091:5000 -e GZCTF_FLAG='flag{team_1}' ssti-jinja-waf-fenjing:local
docker exec t python -c "print(open('/flag').read())"      # flag{team_1}
```

**不要**在 `.env` 里设 `STATIC_FLAG` 来「测试注入」——它的优先级最低，
设了不会覆盖动态 flag，但会让你误判注入是否生效。用 `GZCTF_FLAG` 测。

### 4.3 重置 flag

`POST /api/admin/reset`，请求头 `X-Reset-Token: <RESET_TOKEN>`：

```bash
curl -s -X POST localhost:8092/api/admin/reset -H 'X-Reset-Token: my-secret'
# {"ok":true,"message":"已重写 /flag（来自当前环境变量优先级）"}
```

行为（本机实测）：

| 条件 | 响应 |
|------|------|
| 未配置 `RESET_TOKEN` | `403` `{"ok": false, "error": "RESET_TOKEN 未配置，拒绝重置"}` |
| 令牌错误 | `403` `{"ok": false, "error": "令牌错误"}` |
| 令牌正确 | `200` `{"ok": true, "message": "已重写 /flag（来自当前环境变量优先级）"}` |

实测：容器同时带 `STATIC_FLAG=flag{before}` 与 `GZCTF_FLAG=flag{after}` 启动，
`/flag` 初值即为 `flag{after}`（`GZCTF_FLAG` 优先级更高）；带正确令牌调用 reset 后
`/flag` 内容仍为 `flag{after}`。
即 **reset 重新执行的是「按优先级解析当前环境变量」**，不是「重新生成随机 flag」。
写文件用「临时文件 + rename」，避免重启瞬间读到半截。

> `RESET_TOKEN` 为空时接口默认拒绝（fail-closed），这是刻意的。

### 4.4 运行时可调项

| 环境变量 | 默认 | 作用 |
|----------|------|------|
| `LAB_ID` | `ssti-lab` | 靶场 id（日志用） |
| `FLAG_PATH` | `/flag` | flag 文件路径 |
| `SSTI_MAX_OUTPUT_CHARS` | `262144` | 渲染输出上限，超出从**尾部**截断并附 `\n... [输出已截断]` |
| `RESET_TOKEN` | 空 | `/api/admin/reset` 令牌，空则拒绝 |
| `SSTI_NO_EGRESS` | `0` | 仅用于前端提示；真正的断网在 entrypoint 的 iptables |
| `SSTI_ECHO_DIR` | `/app/public/echo`（lab 07 用 `/app/echo`） | 无回显靶场的回显目录 |
| `HOST` / `PORT` | `0.0.0.0` / `5000` | 应用监听地址与端口 |
| `SECRET_KEY` | 内置默认 | **仅 lab 07** 用于签 JWT session |
| `JAVA_OPTS` | `-Xms64m -Xmx256m -Dfile.encoding=UTF-8` | **仅 lab 08** |

---

## 5. 健康检查

Python 靶场（镜像内**没有 curl**，所以用 Python 自带的 urllib）：

```yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/healthz',timeout=3).status==200 else 1)\""]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 10s
```

Java 靶场（alpine 里有 busybox `wget`）：

```yaml
healthcheck:
  test: ["CMD-SHELL", "wget -q -O - http://127.0.0.1:8080/healthz || exit 1"]
  interval: 10s
  timeout: 3s
  retries: 30
  start_period: 40s
```

`/healthz` 是契约的一部分（纯文本 `ok`，见 [`API.md`](API.md) §1）。

```bash
docker compose ps                       # STATUS 列会显示 (healthy)
docker inspect --format '{{json .State.Health}}' ssti-02-jinja-chain | jq
```

---

## 6. 不出网靶场（07 / 08）的额外要求

| 要求 | 说明 |
|------|------|
| `cap_add: [NET_ADMIN]` | 没有它 entrypoint 里的 `iptables` 加不上规则 |
| 镜像内要有 `iptables` | 07 的 `apt_packages=["iptables"]`、08 的 `apk add iptables` 都已配好 |
| 不能禁用出网规则 | 删掉 `cap_add` 那几行，「不出网」这个前提就没了 |

容器启动时若加不上规则，entrypoint **只告警不退出**（靶场不能因为加固失败而起不来）：

```text
[!] 应用 iptables 规则失败（缺少 NET_ADMIN？），出网未被切断        # Python 系
[!] WARNING: iptables rules could NOT be installed. ...           # Java
```

但 `lab-info.no_egress` 仍会显示 `true`（它来自环境变量 `SSTI_NO_EGRESS`）
—— **判断是否真的断网请以容器日志为准**，或跑自证命令：

```bash
docker exec ssti-07-flask-memshell python -c "import socket; socket.create_connection(('93.184.216.34',80),timeout=5)"
docker exec ssti-07-flask-memshell python -c "import socket; socket.gethostbyname('example.com')"
```

原理见 [`MEMSHELL.md` §2](MEMSHELL.md)。

---

## 7. 故障排查

### 7.1 `pull access denied for ssti-frontend` / `ssti-frontend:local: not found`

**前端镜像没构建。** 这是最常见的一个：

```text
ERROR: failed to solve: ssti-frontend:local: pull access denied, repository does not exist
```

解决：从**仓库根目录**跑 `scripts/build-frontend.sh`（或 `docker build -t ssti-frontend:local frontend`），
再重新构建靶场。注意 Dockerfile 的构建上下文必须是仓库根：

```bash
docker build -f labs/02-jinja-chain/Dockerfile -t ssti-jinja-chain:local .
```

### 7.2 `ModuleNotFoundError: No module named 'ssti_core'`

`PYTHONPATH` 没指到公共库。镜像里 `shared/` 被 COPY 到 `/app/shared`，
Dockerfile 里设的是：

```dockerfile
ENV PYTHONPATH=/app/shared
```

本地直接 `python labs/02-jinja-chain/app.py` 跑会失败，因为本地没有这个路径。
本地调试请显式给：

```bash
# Windows
set PYTHONPATH=shared && python labs\02-jinja-chain\app.py
# Linux/macOS
PYTHONPATH=shared python labs/02-jinja-chain/app.py
```

`tests/test_core.py` 用的是 `sys.path.insert(0, ROOT / "shared")`，
所以它不需要 `PYTHONPATH` 也能跑（但 `tests/test_waf.py` 之类可能需要，
见各测试文件顶部的用法说明）。

### 7.3 端口已被占用

```text
Error response from daemon: Ports are not available: ... bind: address already in use
```

**不要**改 `scaffold_lab.py` 的表（那是唯一权威），用环境变量覆盖单次启动：

```bash
JINJA_CHAIN_PORT=18092 docker compose -f docker-compose.prod.yml up -d jinja-chain
# PowerShell: $env:JINJA_CHAIN_PORT='18092'; docker compose ... up -d jinja-chain
```

### 7.4 靶场起不来 / 立刻退出

```bash
docker compose logs --tail 80 <service>          # 先看日志
docker inspect --format '{{.State.ExitCode}}' ssti-02-jinja-chain
```

常见原因：

- **lab 05 / 06 没有 `app.py`**：这两项目前只有脚手架，`entrypoint.sh` 会
  `exec python /app/app.py` 然后立刻报 `can't open file`。**属于已知情况**，见根 README 的「已知问题」。
- 镜像构建到一半失败（前端镜像缺失 → 见 7.1）。
- Java 靶场首次构建需要拉 Maven 依赖，请留足时间并保证能访问 Maven 仓库。

### 7.5 页面是「降级控制台」而不是赛博朋克前端

说明前端产物没拷进镜像。检查：

```bash
docker exec ssti-02-jinja-chain ls -la /app/public
docker run --rm --entrypoint ls ssti-frontend:local -la /app/build
```

`/app/public/index.html` 应该存在。缺失时应用会回落到
`shared/ssti_core/labapp.py` 里的 `FALLBACK_CONSOLE_HTML`（单文件、零依赖、功能完整，
只是不好看）—— 这本身是有意的降级设计，不是崩溃。

### 7.6 `GET /console/` 404（场景型靶场）

lab 01 / 07 把业务页面放在 `/`、控制台挂在 `/console/`。
如果你在别的靶场上访问 `/console/`，它会被 SPA 路由吃成 404 或返回首页 —— 正常。
反之，在 lab 01/07 上访问 `/` 看到的是业务页面而不是控制台，也是正常。

### 7.7 渲染报 `[渲染异常] ...` 而不是 `WAF`

这不是故障，是信息：**`WAF` = 命中过滤；异常 = 过滤过了但载荷本身写错**。
用 `"mode":"god"` 可以看到 `error` / `exception_type` / `template_after_waf`。
盲关（`echo_mode != "full"`）在练习模式下只给 `ok` / `correct` / `wrong`，
判断逻辑见 [`API.md`](API.md) §6。

### 7.8 输出被截断

`output` 尾部出现 `\n... [输出已截断]` 且 `truncated: true` —— 命中了
`SSTI_MAX_OUTPUT_CHARS`（默认 262144）。`__subclasses__()` 这类载荷很容易撑爆。
调大环境变量或缩小 payload。

---

## 8. 验证部署

```bash
# 起临时容器，逐个靶场走 HTTP 断言（不会占用默认端口）
python scripts/verify_labs.py
python scripts/verify_labs.py 01 02 07
python scripts/verify_labs.py --keep            # 保留容器手工排查
python scripts/verify_labs.py --port-base 19500 # 探测端口起点（默认 19100）

# 公共库自检
python tests/test_core.py

# lab 07 内存马链条（容器内）
docker cp tests/verify_memshell.py ssti-07-flask-memshell:/tmp/v.py
docker exec ssti-07-flask-memshell python /tmp/v.py
```

`scripts/verify_labs.py` 只用标准库（urllib），宿主机任何 Python 3.8+ 都能跑，
退出码 0 表示全部通过。
