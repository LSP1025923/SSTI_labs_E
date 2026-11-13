package com.lab.themepreview.service;

import freemarker.template.Configuration;
import freemarker.template.Template;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.ui.freemarker.FreeMarkerTemplateUtils;

import java.io.StringReader;
import java.util.HashMap;
import java.util.Map;

/**
 * 「模板预览」核心逻辑：把运营在后台填的一段 FreeMarker 片段渲染成 HTML。
 *
 * 关键：用 {@link Configuration#getTemplate} + StringReader 渲染<b>用户提供的模板源</b>，
 * 而不是渲染磁盘上已经审核过的模板文件，所以模板里写什么就执行什么。
 */
@Service
public class ThemePreviewService {

    private final Configuration configuration;

    public ThemePreviewService(@Qualifier("freeMarkerConfiguration") Configuration configuration) {
        this.configuration = configuration;
    }

    public String renderTemplateString(String templateSource, Map<String, Object> model) throws Exception {
        Template template = new Template("preview/" + System.nanoTime() + ".ftl",
                new StringReader(templateSource), configuration);
        Map<String, Object> data = new HashMap<>();
        if (model != null) {
            data.putAll(model);
        }
        return FreeMarkerTemplateUtils.processTemplateIntoString(template, data);
    }
}
