package com.lab.themepreview.config;

import freemarker.core.TemplateClassResolver;
import freemarker.template.Configuration;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * ★ 漏洞点 1 的成因就在这个类里。
 *
 * 业务需求：「运营的模板预览要能调用任意工具类、能 new 任意对象，
 * 否则和线上渲染结果不一致」—— 于是有人把 FreeMarker 的类解析器配成了 UNRESTRICTED。
 *
 * FreeMarker 默认的 TemplateClassResolver 只放行
 *   freemarker.template.utility.ObjectConstructor / JythonRuntime / Execute
 * 三个白名单类（新版还进一步收紧）；UNRESTRICTED_RESOLVER 则允许 ?new() 解析
 * <b>任意</b>类 —— 等于把「写模板的人」当成「能在 JVM 里执行代码的人」。
 *
 * 配合 freemarker 2.3.28（还带着 freemarker.template.utility.Execute），
 * 就得到最经典的 FreeMarker SSTI RCE：
 *   ${"freemarker.template.utility.Execute"?new()("id")}
 */
@Configuration
public class FreemarkerConfig {

    /**
     * 直接改 Spring Boot 自动配置出来的那个 Configuration。
     *
     * 不要用 @Primary 另建 FreeMarkerConfigurer：那会和
     * FreeMarkerAutoConfiguration 的 @ConditionalOnMissingBean 打架，
     * 有可能拿到一个并不是真正被 ViewResolver 使用的实例。
     */
    @Bean
    public Object freeMarkerHardening(
            @Qualifier("freeMarkerConfiguration") Configuration configuration) {
        // ★★★ 漏洞就在这里：模板作者 = 代码执行者 ★★★
        configuration.setNewBuiltinClassResolver(TemplateClassResolver.UNRESTRICTED_RESOLVER);
        System.out.println("[*] FreeMarker " + Configuration.getVersion()
                + " newBuiltinClassResolver = UNRESTRICTED (vulnerable by design)");
        return new Object();
    }
}
