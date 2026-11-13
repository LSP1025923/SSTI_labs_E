# `/api/lab-info` 响应示例（本靶场实测输出）

场景型靶场按 [`../../../docs/API.md`](../../../docs/API.md) 第 5 节最小契约实现。
下面是 `GET http://127.0.0.1:8098/api/lab-info` 的**实测**响应（节选，格式化后）。

```jsonc
{
  "id": "freemarker-memshell",
  "title": "FreeMarker / Thymeleaf SSTI → Tomcat 内存马",
  "subtitle": "出网被切断，反弹 shell / DNSLog 全部失效：只能把 shell 注进 JVM 内存",
  "engine": "freemarker",
  "engine_title": "FreeMarker",
  "description": "「ThemeHub」主题预览服务把运营提交的 FreeMarker 模板片段直接渲染，并且为了让模板能调用任意工具类，把类解析器配成了 UNRESTRICTED，于是 ${...?new(...)} 一路走到任意 Java 代码执行；同一站点还留了一个 Thymeleaf 视图名注入作为第二条（对照）入口。容器已切断出向 TCP，所以出网反弹不可用，需要把 Filter 动态注册进运行中的 Tomcat StandardContext，得到一个只在内存里存在、可复用的 webshell。",
  "no_egress": true,
  "no_egress_note": "容器已禁止出网：反弹 shell / DNSLog / 任何主动外连均不可用（iptables 丢弃 eth0 上的出向 TCP SYN 与 UDP/53，入向响应不受影响）。必须用内存马（或回显/写文件）通过已有的入向 HTTP 通道拿数据。",
  "flag_path": "/flag",
  "flag_format": "flag{...}",
  "doc_url": "/docs/lab.md",
  "hint": "预览接口 /theme/preview 的模板串是可控的：先确定引擎。FreeMarker 试 ${7*7}，Thymeleaf 试 __${7*7}__。注意容器不允许外连，任何要连出去的 payload 都不会有回显。",
  "theme": {
    "name": "ember",
    "accent": "#ff6b2b",
    "accent2": "#ffd166",
    "glow": "rgba(255,107,43,0.55)"
  },
  "engines": [
    { "id": "freemarker", "title": "FreeMarker 2.3.28" },
    { "id": "thymeleaf",  "title": "Thymeleaf 3.0 (SpringEL)" }
  ],
  "levels": [
    {
      "id": "1",
      "title": "L1 · 确认模板注入",
      "summary": "确认模板注入",
      "description": "GET /theme/preview?template=${7*7} 回显 49，说明用户输入真的进了 FreeMarker 解析器。",
      "blind": false,
      "no_egress": true,
      "waf": null,
      "hint": "先验证 ${...} 插值：${7*7} -> 49；再来 ${7*7?c}、<#list 1..3 as i>${i}</#list> 看是否真的是 FreeMarker。"
    },
    {
      "id": "2",
      "title": "L2 · 拿到任意代码执行",
      "summary": "拿到任意代码执行",
      "description": "类解析器为 UNRESTRICTED，?new() 可以解析任意类；FreeMarker 2.3.28 仍内置 freemarker.template.utility.Execute，直接命令执行。",
      "blind": false,
      "no_egress": true,
      "waf": null,
      "hint": "payload: ${ \"freemarker.template.utility.Execute\"?new()(\"id\") } —— 回显就是命令输出。注意：能执行命令 ≠ 能外连，容器出网已断。"
    },
    {
      "id": "3",
      "title": "L3 · 注入 Tomcat 内存马",
      "summary": "注入 Tomcat 内存马",
      "description": "用 L2 的代码执行能力，把一段实现了 javax.servlet.Filter 的字节码（FlushableClassLoader#defineClass）加载进来，反射拿到 Spring 应用里的 StandardContext（ApplicationContextFacade.context），addFilterDef + addFilterMap + filterStart 注册 /memshell。",
      "blind": false,
      "no_egress": true,
      "waf": null,
      "hint": "需要 ServletContext 参与注册：FreeMarker 数据模型里有 servletContext。payload 见 PAYLOADS.md 的「一步到位版」。"
    },
    {
      "id": "4",
      "title": "L4 · 通过内存马读 flag",
      "summary": "通过内存马读 flag",
      "description": "新注册的 Filter 走的是已有的入向 HTTP 通道，零出网流量：GET /memshell?cmd=cat%20/flag 直接回显。",
      "blind": false,
      "no_egress": true,
      "waf": null,
      "hint": "内存马只活在 JVM 里，进程重启就消失 —— 这正是「内存马」的意义。"
    }
  ],
  "endpoints": [
    { "method": "GET", "path": "/", "description": "主题预览控制台（HTML）" },
    { "method": "GET", "path": "/healthz", "description": "健康检查，返回 ok" },
    { "method": "GET", "path": "/api/lab-info", "description": "本靶场元信息（本接口）" },
    { "method": "GET", "path": "/theme/preview?template=<ftl>&theme=<name>", "description": "漏洞点 1：FreeMarker 模板串渲染（类解析器 UNRESTRICTED）" },
    { "method": "GET", "path": "/theme/thymeleaf?theme=<v>", "description": "漏洞点 2：Thymeleaf 视图名注入（__${...}__ → SpEL）" },
    { "method": "GET", "path": "/api/theme-vars", "description": "预览接口的数据模型说明" },
    { "method": "GET", "path": "/api/memshell-class", "description": "把内嵌的 memshell Filter 字节码（base64）吐出来，便于核对 payload" }
  ]
}
```

## 实测边界说明（与上面字段有关的诚实补充）

- `no_egress: true` 指的是 **`entrypoint.sh` 已安装 `iptables` 出网封锁规则**。
  实测结果：出向 TCP 被阻断（反弹 shell / 下载 payload 不可用）、直连外部 DNS 被阻断；
  但在本机 Docker Desktop（WSL2）上，**走 Docker 内嵌 resolver（127.0.0.11）的域名解析
  仍然成功**，因此「DNSLog 式外带」在该平台不能被宣称已完全排除。
  详见 [`../README.md`](../README.md#出网是怎么被切断的以及实测边界别过度宣称) 与
  [`MEMSHELL.md §2.1.1`](MEMSHELL.md#211-出网封锁的实测边界)。
- `no_egress_note` 里「DNSLog 不可用」这句是**面向学员的目标表述**：本靶场要求学员按
  「不能外连」来做；出向 TCP 的阻断是实测成立的，DNS 的差异见上一段。
- `levels[2].hint` 提到的「一步到位版」payload 就是在 `PAYLOADS.md` 的
  `${"com.lab.themepreview.memshell.InjectHelper"?new(servletContext)()}`。

## 其它接口

```bash
curl -s http://127.0.0.1:8098/api/theme-vars | jq
# {"engine":"freemarker","endpoint":"/theme/preview?template=<ftl>&theme=<name>",
#  "model_keys":["theme_name","now","site","servletContext"], ...}

curl -s http://127.0.0.1:8098/api/diag/context | jq '.chain[] | {class, field_context_type, value_class}'
# 把 ServletContext → ApplicationContextFacade → ApplicationContext → TomcatEmbeddedContext 摊开

curl -s http://127.0.0.1:8098/api/memshell-class | head -c 60
# yv66vgAAADQBMgoATwB/BwCACACBCwCCAIMKAAYAhAcAhQoAhgCHCgAGAIgKAIkAiggAiwoAjACNCgAG
```

本靶场**没有** `/api/render`、`/api/levels`、`/api/god/source`、`/api/admin/reset` 等
控制台契约接口——场景型靶场只受 `../../../docs/API.md` 第 5 节约束。
