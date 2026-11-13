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
一份写入 `src/main/resources/memshell/MemshellFilter.class.b64`（方便核对），
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
