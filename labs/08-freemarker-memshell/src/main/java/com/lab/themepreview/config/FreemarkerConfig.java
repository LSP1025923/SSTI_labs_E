package com.lab.themepreview.config;

import freemarker.core.TemplateClassResolver;
import freemarker.template.Configuration;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.web.servlet.view.freemarker.FreeMarkerConfigurer;

/**
 * ★ 漏洞点 1 的成因就在这个类里。
 *
 * 业务需求：「运营的模板预览要能调用任意工具类、能 new 任意对象，
 * 否则和线上渲染结果不一致」—— 于是有人把 FreeMarker 的类解析器改成了 UNRESTRICTED。
 *
 * FreeMarker 默认的 TemplateClassResolver 只允许
 *   freemarker.template.utility.ObjectConstructor / JythonRuntime / Execute（2.3.29 及更早）
 * 三个白名单类；UNRESTRICTED_RESOLVER 则允许 ?new() 解析<b>任意</b>类，
 * 即把模板作者等同于 JVM 里的代码执行者。
 *
 * 配合 freemarker 2.3.29（还带着 freemarker.template.utility.Execute），
 * 就得到最经典的 FreeMarker SSTI RCE：
 *   ${"freemarker.template.utility.Execute"?new()("id")}
 */
@org.springframework.context.annotation.Configuration
public class FreemarkerConfig {

    @Bean
    @Primary
    public FreeMarkerConfigurer freeMarkerConfigurer() {
        FreeMarkerConfigurer configurer = new FreeMarkerConfigurer();
        configurer.setTemplateLoaderPath("classpath:/templates/freemarker/");
        configurer.setDefaultEncoding("UTF-8");
        configurer.setFreemarkerSettings(new java.util.Properties());
        return configurer;
    }

    /**
     * 拿到 Spring Boot 自动配置好的 Configuration，把类解析器改成不受限。
     * （真实事故现场通常就是这么一行 setNewBuiltinClassResolver 埋进去的。）
     */
    @Bean
    public Object unrestrictedClassResolver(
            @Qualifier("freeMarkerConfiguration") Configuration configuration) {
        configuration.setNewBuiltinClassResolver(TemplateClassResolver.UNRESTRICTED_RESOLVER);
        // 让模板渲染时的异常信息带上更多上下文，方便教学观察
        configuration.setLogTemplateExceptions(false);
        System.out.println("[*] FreeMarker class resolver = UNRESTRICTED (vulnerable by design)");
        return new Object();
    }
}
