package com.lab.themepreview.web;

import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 实现 docs/API.md 第 5 节「场景型靶场」的最小契约：
 *   GET /healthz  -> 200 "ok"
 *   GET /api/lab-info -> id/title/description/no_egress/levels[] 等
 */
@RestController
public class MetaController {

    @GetMapping(value = "/healthz", produces = MediaType.TEXT_PLAIN_VALUE + ";charset=UTF-8")
    public String healthz() {
        return "ok";
    }

    @GetMapping(value = "/api/lab-info", produces = MediaType.APPLICATION_JSON_VALUE + ";charset=UTF-8")
    public Map<String, Object> labInfo() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", "freemarker-memshell");
        m.put("title", "FreeMarker / Thymeleaf SSTI → Tomcat 内存马");
        m.put("subtitle", "出网被切断，反弹 shell / DNSLog 全部失效：只能把 shell 注进 JVM 内存");
        m.put("engine", "freemarker");
        m.put("engine_title", "FreeMarker");
        m.put("description",
                "「ThemeHub」主题预览服务把运营提交的 FreeMarker 模板片段直接渲染，"
              + "并且为了让模板能调用任意工具类，把类解析器配成了 UNRESTRICTED，"
              + "于是 ${...?new(...)} 一路走到任意 Java 代码执行；同一站点还留了一个 "
              + "Thymeleaf 视图名注入（__${...}__ 预处理 → SpEL）作为第二条 RCE 路径。"
              + "容器已用 iptables 切断出网（仅放行入向响应），所以出网反弹不可用，"
              + "需要把 Filter 动态注册进运行中的 Tomcat StandardContext，"
              + "得到一个只在内存里存在、可复用的 webshell。");
        m.put("no_egress", true);
        m.put("no_egress_note",
                "容器已禁止出网：反弹 shell / DNSLog / 任何主动外连均不可用"
              + "（iptables 丢弃 eth0 上的出向 TCP SYN 与 UDP/53，入向响应不受影响）。"
              + "必须用内存马（或回显/写文件）通过已有的入向 HTTP 通道拿数据。");
        m.put("flag_path", "/flag");
        m.put("flag_format", "flag{...}");
        m.put("doc_url", "/docs/lab.md");
        m.put("hint",
                "预览接口 /theme/preview 的模板串是可控的：先确定引擎。"
              + "FreeMarker 试 ${7*7}，Thymeleaf 试 __${7*7}__。"
              + "注意容器不允许外连，任何要连出去的 payload 都不会有回显。");
        m.put("theme", theme());
        m.put("engines", engines());
        m.put("levels", levels());
        m.put("endpoints", endpoints());
        return m;
    }

    private Map<String, Object> theme() {
        Map<String, Object> t = new LinkedHashMap<>();
        t.put("name", "ember");
        t.put("accent", "#ff6b2b");
        t.put("accent2", "#ffd166");
        t.put("glow", "rgba(255,107,43,0.55)");
        return t;
    }

    private List<Map<String, Object>> engines() {
        List<Map<String, Object>> list = new ArrayList<>();
        list.add(engine("freemarker", "FreeMarker 2.3.29"));
        list.add(engine("thymeleaf", "Thymeleaf 3.0 (SpringEL)"));
        return list;
    }

    private Map<String, Object> engine(String id, String title) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("id", id);
        e.put("title", title);
        return e;
    }

    private List<Map<String, Object>> levels() {
        List<Map<String, Object>> list = new ArrayList<>();
        list.add(level("1", "L1 · 确认模板注入",
                "GET /theme/preview?template=${7*7} 回显 49，说明用户输入真的进了 FreeMarker 解析器。",
                "先验证 ${...} 插值：${7*7} -> 49；再来 ${7*7?c}、<#list 1..3 as i>${i}</#list> 看是否真的是 FreeMarker。"));
        list.add(level("2", "L2 · 拿到任意代码执行",
                "类解析器为 UNRESTRICTED，?new() 可以解析任意类；"
              + "FreeMarker 2.3.29 仍内置 freemarker.template.utility.Execute，直接命令执行。",
                "payload: ${ \"freemarker.template.utility.Execute\"?new()(\"id\") }"
              + " —— 回显就是命令输出。注意：能执行命令 ≠ 能外连，容器出网已断。"));
        list.add(level("3", "L3 · 注入 Tomcat 内存马",
                "用 L2 的代码执行能力，把一段实现了 javax.servlet.Filter 的字节码"
              + "（FlushableClassLoader#defineClass）加载进来，反射拿到 Spring 应用里的"
              + " StandardContext（ApplicationContextFacade.context），"
              + "addFilterDef + addFilterMap + filterStart 注册 /memshell。",
                "需要 ServletContext 参与注册：FreeMarker 数据模型里有 servletContext。"
              + "payload 见 docs/PAYLOADS.md 的 「一步到位版」。"));
        list.add(level("4", "L4 · 通过内存马读 flag",
                "新注册的 Filter 走的是已有的入向 HTTP 通道，零出网流量："
              + "GET /memshell?cmd=cat%20/flag 直接回显。",
                "内存马只活在 JVM 里，进程重启就消失 —— 这正是「内存马」的意义。"));
        return list;
    }

    private Map<String, Object> level(String id, String title, String description, String hint) {
        Map<String, Object> l = new LinkedHashMap<>();
        l.put("id", id);
        l.put("title", title);
        l.put("summary", title.substring(title.indexOf('·') + 1).trim());
        l.put("description", description);
        l.put("blind", false);
        l.put("no_egress", true);
        l.put("waf", null);
        l.put("hint", hint);
        return l;
    }

    private List<Map<String, Object>> endpoints() {
        List<Map<String, Object>> list = new ArrayList<>();
        list.add(ep("GET", "/", "主题预览控制台（HTML）"));
        list.add(ep("GET", "/healthz", "健康检查，返回 ok"));
        list.add(ep("GET", "/api/lab-info", "本靶场元信息（本接口）"));
        list.add(ep("GET", "/theme/preview?template=<ftl>&theme=<name>", "漏洞点 1：FreeMarker 模板串渲染（类解析器 UNRESTRICTED）"));
        list.add(ep("GET", "/theme/thymeleaf?theme=<v>", "漏洞点 2：Thymeleaf 视图名注入（__${...}__ → SpEL）"));
        list.add(ep("GET", "/api/theme-vars", "预览接口的数据模型说明"));
        list.add(ep("GET", "/api/memshell-class", "把内嵌的 memshell Filter 字节码（base64）吐出来，便于核对 payload"));
        return list;
    }

    private Map<String, Object> ep(String method, String path, String desc) {
        Map<String, Object> e = new LinkedHashMap<>();
        e.put("method", method);
        e.put("path", path);
        e.put("description", desc);
        return e;
    }
}
