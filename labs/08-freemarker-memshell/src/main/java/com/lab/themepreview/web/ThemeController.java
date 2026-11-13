package com.lab.themepreview.web;

import com.lab.themepreview.config.WebConfig;
import com.lab.themepreview.service.ThemePreviewService;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;

import javax.servlet.http.HttpServletRequest;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 运营后台的「主题预览」控制器。
 *
 *  GET /theme/preview        —— 漏洞点 1：FreeMarker SSTI
 *  GET /theme/thymeleaf      —— 漏洞点 2：Thymeleaf 视图名注入（SpringEL）
 *
 * 两个入口都是真实业务里出现过的写法，不是硬塞的 ?tpl= 后门。
 */
@Controller
public class ThemeController {

    private final ThemePreviewService previewService;

    public ThemeController(ThemePreviewService previewService) {
        this.previewService = previewService;
    }

    // ------------------------------------------------------------------
    // 漏洞点 1：FreeMarker 模板串渲染（unrestricted class resolver）
    // ------------------------------------------------------------------
    @GetMapping(value = "/theme/preview", produces = MediaType.TEXT_HTML_VALUE + ";charset=UTF-8")
    @ResponseBody
    public String freeMarkerPreview(@RequestParam(name = "template", required = false) String template,
                                    @RequestParam(name = "theme", required = false, defaultValue = "aurora") String theme,
                                    HttpServletRequest request) {
        if (template == null || template.isEmpty()) {
            template = "<div class=\"tpl-card\">\n"
                    + "  <h2>${theme_name?cap_first} 主题预览</h2>\n"
                    + "  <p>把左侧编辑区的 FreeMarker 片段粘贴到 preview.html 中即可看到效果。</p>\n"
                    + "  <p>站点主题：<b>${theme_name}</b> ｜ 预览时间：${now?string(\"yyyy-MM-dd HH:mm:ss\")}</p>\n"
                    + "</div>\n";
        }
        Map<String, Object> model = new HashMap<>();
        model.put("theme_name", theme);
        model.put("now", new java.util.Date());
        model.put("site", "ThemeHub SaaS");
        // 模板里可以拿到 ServletContext（业务上用来取站点配置，教学上让 payload 自包含）
        model.put("servletContext", request.getServletContext());
        try {
            return previewService.renderTemplateString(template, model);
        } catch (Throwable t) {
            return "<pre class=\"tpl-error\">[FreeMarker 渲染异常] "
                    + escape(t.getClass().getName() + ": " + t.getMessage()) + "</pre>";
        }
    }

    // ------------------------------------------------------------------
    // 漏洞点 2：Thymeleaf 视图名注入（经典 CVE-2021-25741 形态）
    //
    // 业务上等价于「主题模板名由前端传入，后台直接当视图名返回」：
    //     GET /theme/thymeleaf?theme=aurora      -> 渲染 templates/theme/aurora.html
    //     GET /theme/thymeleaf?theme=<任意内容>   -> 视图名被原样拼接，无白名单
    //
    // fragment 参数是历史遗留（早期版本的主题页用它动态选片段）；
    // 现在的主题页用固定片段 th:replace="~{fragments/header :: body}"，
    // 但请求参数仍然照收不误，方便对照实验。
    //
    // ⚠ 实测结论（见 docs/PAYLOADS.md 与 README「Thymeleaf 这条路的实测边界」）：
    //   在 Thymeleaf 3.0.15（Boot 2.7.18 默认）以及 3.0.11 上，
    //   视图名【不会】做 __${...}__ 预处理、片段名【不会】被当作 SpEL 求值
    //   （报错信息里模板名始终原样，例如 theme/__${7*7}__），
    //   甚至 Thymeleaf 的片段选择器 ~{...} 内部也不会对 ${...} 做插值。
    //   也就是说：可控的「模板名/片段名」本身不构成 SpEL 注入点（和不少网文说法相反）。
    //   这条入口因此是「存在注入面但默认不可达 RCE」的对照题；
    //   本靶场真正能打通到 RCE 的是 FreeMarker 那条链。
    // ------------------------------------------------------------------
    @GetMapping("/theme/thymeleaf")
    public String thymeleafPreview(@RequestParam(name = "theme", required = false, defaultValue = "aurora") String theme,
                                   @RequestParam(name = "fragment", required = false, defaultValue = "header") String fragment,
                                   org.springframework.ui.Model model) {
        model.addAttribute("userTheme", fragment);
        model.addAttribute("themeName", theme);
        return "theme/" + theme;
    }

    // ------------------------------------------------------------------
    // 只读辅助端点：暴露 memshell 字节码，便于核对 payload
    // ------------------------------------------------------------------
    @GetMapping(value = "/api/memshell-class", produces = MediaType.TEXT_PLAIN_VALUE + ";charset=UTF-8")
    @ResponseBody
    public String memshellClass() {
        try {
            return WebConfig.memshellClassBase64();
        } catch (Exception e) {
            return "ERR " + e;
        }
    }

    @GetMapping(value = "/api/theme-vars", produces = MediaType.APPLICATION_JSON_VALUE + ";charset=UTF-8")
    @ResponseBody
    public Map<String, Object> themeVars() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("engine", "freemarker");
        m.put("endpoint", "/theme/preview?template=<ftl>&theme=<name>");
        m.put("model_keys", new String[]{"theme_name", "now", "site", "servletContext"});
        m.put("note", "预览接口直接渲染用户提交的模板串；类解析器已配置为 UNRESTRICTED。");
        return m;
    }

    private static String escape(String s) {
        if (s == null) {
            return "null";
        }
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
