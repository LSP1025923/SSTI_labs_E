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
    // 漏洞点 2：Thymeleaf 模板注入
    //
    // 主题页 theme/aurora.html 里用 th:replace="~{fragments/${userTheme} :: body}" 动态选择
    // 「主题自带的小片段」。userTheme 直接来自请求参数、没有任何白名单。
    //
    // Thymeleaf 3 会对 th:* 属性值里的片段/模板表达式做 __${...}__ 预处理，
    // 预处理结果会交给 SpringEL 求值 —— 于是 userTheme 可控 = SpEL 注入 = RCE。
    // 这与「视图名注入」不是一回事：实测（3.0.15 与 3.0.11 都试过）视图名里的
    // __${...}__ 不会被求值，模板名是原样拼进错误信息的；可控的必须是
    // 模板内部参与表达式求值的那部分输入。
    // ------------------------------------------------------------------
    @GetMapping("/theme/thymeleaf")
    public String thymeleafPreview(@RequestParam(name = "theme", required = false, defaultValue = "aurora") String theme,
                                   @RequestParam(name = "fragment", required = false, defaultValue = "body") String fragment,
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
